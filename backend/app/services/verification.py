"""采样复核服务（D1 第二阶段）：结算后抽样重算结果哈希，不一致时回滚结算。"""
import hashlib
import json
import random
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.core.minio_client import get_object_bytes
from app.models import (
    Account,
    NotificationType,
    PlatformConfig,
    Settlement,
    SettlementRole,
    SettlementStatus,
    TaskExecution,
    User,
    UserRole,
    VerificationRecord,
    VerificationStatus,
)
from app.services.audit import AuditService
from app.services.notification import NotificationService


def _compose_proof_hash(nonce: str, content_hash: str) -> str:
    """防重放协议：proof_hash = sha256(challenge_nonce + ':' + content_hash)。

    每次执行的 nonce 不同，即使结果文件内容相同，proof_hash 也不同，无法跨次缓存复用。
    """
    digest = hashlib.sha256()
    digest.update(nonce.encode("utf-8"))
    digest.update(b":")
    digest.update(content_hash.encode("utf-8"))
    return digest.hexdigest()


class VerificationService:
    """结果抽样重算验证：随机抽取已完成执行记录，重算内容哈希并与算力证明比对。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    async def _get_config(self) -> PlatformConfig:
        config = await self.session.get(PlatformConfig, 1)
        if not config:
            config = PlatformConfig()
            self.session.add(config)
            await self.session.flush()
        return config

    async def maybe_sample(
        self, execution: TaskExecution, result_files: list[dict]
    ) -> VerificationRecord | None:
        """结算完成后按比例随机抽样，命中则创建待复核记录。"""
        if not execution.proof_hash or not result_files:
            return None

        config = await self._get_config()
        rate = config.verification_sample_rate or 0
        if rate <= 0:
            return None
        if rate < 10000 and random.randrange(10000) >= rate:  # noqa: PLR2004
            return None

        record = VerificationRecord(
            execution_id=execution.id,
            task_id=execution.task_id,
            status=VerificationStatus.PENDING,
            expected_hash=execution.proof_hash,
            result_files_json=json.dumps(result_files, ensure_ascii=False),
        )
        self.session.add(record)
        await self.session.flush()

        await self.audit.log(
            "verification.sampled",
            "execution",
            execution.id,
            {"task_id": str(execution.task_id), "expected_hash": execution.proof_hash},
        )
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def _recompute_hash(self, result_files_json: str | None) -> str | None:
        """按与供给方一致的规则重算内容哈希（文件名 + 内容，按文件名排序）。"""
        if not result_files_json:
            return None
        try:
            files = json.loads(result_files_json)
        except (TypeError, ValueError):
            return None
        if not isinstance(files, list):
            return None

        files = [f for f in files if isinstance(f, dict) and f.get("key")]
        if not files:
            return None
        files.sort(key=lambda f: f.get("name") or "")

        digest = hashlib.sha256()
        for f in files:
            name = f.get("name") or ""
            digest.update(name.encode("utf-8"))
            content = await get_object_bytes(f["key"])
            if content is None:
                raise FileNotFoundError(f"结果文件不存在或无法读取: {f['key']}")
            digest.update(content)
        return digest.hexdigest()

    async def run_verification(
        self, record_id: uuid.UUID, operator_id: uuid.UUID | None = None
    ) -> VerificationRecord:
        """执行复核：重算哈希比对，不一致则回滚该笔结算。幂等。"""
        record = await self.session.get(VerificationRecord, record_id)
        if not record:
            raise NotFoundError("复核记录不存在")
        if record.status != VerificationStatus.PENDING:
            return record

        expected = record.expected_hash
        actual: str | None = None
        error: str | None = None
        try:
            content_hash = await self._recompute_hash(record.result_files_json)
            actual = None
            if content_hash is not None:
                execution = await self.session.get(TaskExecution, record.execution_id)
                nonce = execution.challenge_nonce if execution else ""
                actual = _compose_proof_hash(nonce, content_hash)
        except Exception as exc:  # noqa: BLE001 - 复核过程异常统一记录
            error = str(exc)

        now = datetime.now(UTC)
        if actual is not None and expected and actual == expected:
            record.status = VerificationStatus.VERIFIED
            record.actual_hash = actual
        else:
            record.status = VerificationStatus.FAILED
            record.actual_hash = actual
            record.error_message = error or "结果内容哈希与算力证明不一致"
        record.checked_at = now

        if record.status == VerificationStatus.FAILED:
            await self._reverse_settlement(record)

        await self.audit.log(
            "verification.checked",
            "execution",
            record.execution_id,
            {
                "verification_record_id": str(record.id),
                "status": record.status.value,
                "expected_hash": expected,
                "actual_hash": actual,
                "error": record.error_message,
            },
            user_id=operator_id,
        )
        await self.session.commit()

        # 重新加载并预取关联，供响应序列化使用
        return (
            await self.session.execute(
                select(VerificationRecord)
                .options(
                    selectinload(VerificationRecord.task),
                    selectinload(VerificationRecord.execution),
                )
                .where(VerificationRecord.id == record_id)
            )
        ).scalar_one()

    async def _reverse_settlement(self, record: VerificationRecord) -> None:
        """复核失败：追回供给方收益、回滚结算单、扣减信誉分并通知管理员。"""
        execution = await self.session.get(TaskExecution, record.execution_id)
        if not execution:
            return
        await self.session.refresh(execution, ["node"])
        node = execution.node
        if not node:
            return

        supplier_settlement = (
            await self.session.execute(
                select(Settlement).where(
                    Settlement.execution_id == execution.id,
                    Settlement.role == SettlementRole.SUPPLIER,
                    Settlement.status == SettlementStatus.SETTLED,
                )
            )
        ).scalar_one_or_none()

        earnings = execution.supplier_earnings_points or 0
        if supplier_settlement is not None:
            earnings = supplier_settlement.net_points
            supplier_settlement.status = SettlementStatus.REVERSED
            supplier_settlement.updated_at = datetime.now(UTC)
            self.session.add(
                Settlement(
                    settlement_no=await self._generate_reversal_no("V"),
                    user_id=supplier_settlement.user_id,
                    task_id=execution.task_id,
                    execution_id=execution.id,
                    role=SettlementRole.SUPPLIER,
                    compute_points=0,
                    platform_fee_rate=supplier_settlement.platform_fee_rate,
                    platform_fee_points=0,
                    net_points=-earnings,
                    destination_account="作弊复核回滚",
                    status=SettlementStatus.REVERSED,
                    settled_at=datetime.now(UTC),
                )
            )

        account = (
            await self.session.execute(
                select(Account).where(Account.user_id == node.owner_id)
            )
        ).scalar_one_or_none()
        if account:
            reserve = execution.reserve_points or 0
            free = max(0, earnings - reserve)
            account.balance_points = max(0, account.balance_points - free)
            account.reserve_points = max(0, account.reserve_points - reserve)
            account.total_earned = max(0, account.total_earned - earnings)

        node.total_points_earned = max(0, node.total_points_earned - earnings)
        node.total_tasks_completed = max(0, node.total_tasks_completed - 1)
        node.reputation_score = max(0, node.reputation_score - 20)

        await self._notify_admins(
            "复核失败",
            f"执行记录 {record.execution_id} 结果哈希与算力证明不一致，已回滚 {earnings} 分",
            ref_id=execution.task_id,
        )

    async def _generate_reversal_no(self, prefix: str) -> str:
        now = datetime.now(UTC)
        date_prefix = f"{prefix}{now.strftime('%Y%m%d')}"
        count = (
            await self.session.execute(
                select(func.count(Settlement.id)).where(
                    Settlement.settlement_no.like(f"{date_prefix}%")
                )
            )
        ).scalar_one()
        return f"{date_prefix}{count + 1:04d}"

    async def _notify_admins(
        self, title: str, content: str, ref_id: uuid.UUID | None = None
    ) -> None:
        users = (await self.session.execute(select(User))).scalars().all()
        admins = [u for u in users if u.has_role(UserRole.ADMIN)]
        notification = NotificationService(self.session)
        for admin in admins:
            await notification.create(
                admin.id,
                NotificationType.SYSTEM,
                title,
                content,
                ref_id=ref_id,
            )

    async def list_records(
        self,
        page: int = 1,
        page_size: int = 20,
        status: VerificationStatus | None = None,
    ) -> tuple[list[VerificationRecord], int]:
        stmt = select(VerificationRecord).options(
            selectinload(VerificationRecord.task),
            selectinload(VerificationRecord.execution),
        )
        if status:
            stmt = stmt.where(VerificationRecord.status == status)

        total = (
            await self.session.execute(select(func.count()).select_from(stmt.subquery()))
        ).scalar_one()

        stmt = (
            stmt.order_by(VerificationRecord.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        records = (await self.session.execute(stmt)).scalars().all()
        return list(records), total
