"""算力时间银行：储备利息分配、公共池可视化、借用/取用、利息明细与借用流水。"""
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessError, NotFoundError, ParamError
from app.models import (
    Account,
    PlatformConfig,
    ReserveBorrowRecord,
    ReserveInterestAllocation,
    ReserveInterestRecord,
    TaskExecution,
)
from app.services.audit import AuditService


class ReserveInterestService:
    """周期将公共池产出按储备占比分配给储备贡献者。

    产出来源：本周期结算新锁定进储备池的储备分（task_executions.reserve_points）。
    分配规则：产出的 reserve_interest_ratio%（默认 50%）按各账户储备占比返还，
    利息继续计入储备分形成复利；剩余部分沉淀为公共池自身增长。
    同时为每个受益账户写入单账户分配明细，支撑「利息明细」查询。
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    async def _get_platform_config(self) -> PlatformConfig:
        config = await self.session.get(PlatformConfig, 1)
        if not config:
            config = PlatformConfig()
            self.session.add(config)
            await self.session.flush()
        return config

    async def distribute(self) -> int:
        """执行一次储备利息分配，返回受益账户数（幂等：以最近分配记录为界）。"""
        config = await self._get_platform_config()

        last = (
            await self.session.execute(
                select(func.max(ReserveInterestRecord.distributed_at))
            )
        ).scalar_one_or_none()
        last_time = last or datetime.min.replace(tzinfo=UTC)

        # 本周期公共池产出：上次分配以来结算新锁定的储备分
        output = int(
            (
                await self.session.execute(
                    select(
                        func.coalesce(func.sum(TaskExecution.reserve_points), 0)
                    ).where(
                        TaskExecution.reserve_points.isnot(None),
                        TaskExecution.completed_at > last_time,
                    )
                )
            ).scalar_one()
            or 0
        )

        if output <= 0:
            return 0

        total_reserve = int(
            (
                await self.session.execute(
                    select(func.coalesce(func.sum(Account.reserve_points), 0))
                )
            ).scalar_one()
            or 0
        )

        if total_reserve <= 0:
            return 0

        interest = output * config.reserve_interest_ratio // 100
        if interest <= 0:
            return 0

        accounts = (
            await self.session.execute(
                select(Account).where(Account.reserve_points > 0)
            )
        ).scalars().all()

        now = datetime.now(UTC)
        record = ReserveInterestRecord(
            cycle_output_points=output,
            interest_points=interest,
            total_reserve_points=total_reserve,
            distributed_at=now,
        )
        self.session.add(record)
        await self.session.flush()

        distributed = 0
        for account in accounts:
            share = interest * account.reserve_points // total_reserve
            if share > 0:
                self.session.add(
                    ReserveInterestAllocation(
                        record_id=record.id,
                        user_id=account.user_id,
                        reserve_points_before=account.reserve_points,
                        interest_points=share,
                        distributed_at=now,
                    )
                )
                account.reserve_points += share
                distributed += 1

        await self.audit.log(
            "reserve.interest_distributed",
            "reserve_interest_record",
            record.id,
            {
                "cycle_output_points": output,
                "interest_points": interest,
                "total_reserve_points": total_reserve,
                "beneficiaries": distributed,
                "reserve_interest_ratio": config.reserve_interest_ratio,
            },
        )

        await self.session.commit()
        return distributed


class ReserveService:
    """算力时间银行：公共池可视化、储备贡献率、借用/取用、利息明细、借用流水。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    async def _get_platform_config(self) -> PlatformConfig:
        config = await self.session.get(PlatformConfig, 1)
        if not config:
            config = PlatformConfig()
            self.session.add(config)
            await self.session.flush()
        return config

    async def _get_account(self, user_id: uuid.UUID) -> Account:
        account = (
            await self.session.execute(
                select(Account).where(Account.user_id == user_id)
            )
        ).scalar_one_or_none()
        if not account:
            raise NotFoundError("账户不存在")
        return account

    async def _pool_total(self) -> int:
        return int(
            (
                await self.session.execute(
                    select(func.coalesce(func.sum(Account.reserve_points), 0))
                )
            ).scalar_one()
            or 0
        )

    async def _pool_contributors(self) -> int:
        return int(
            (
                await self.session.execute(
                    select(func.count(Account.id)).where(Account.reserve_points > 0)
                )
            ).scalar_one()
            or 0
        )

    async def get_pool_overview(self) -> dict:
        """公共池可视化：池总量、贡献人数、累计产出、累计利息、最近分配时间。"""
        total_output = int(
            (
                await self.session.execute(
                    select(func.coalesce(func.sum(ReserveInterestRecord.cycle_output_points), 0))
                )
            ).scalar_one()
            or 0
        )
        total_interest = int(
            (
                await self.session.execute(
                    select(func.coalesce(func.sum(ReserveInterestRecord.interest_points), 0))
                )
            ).scalar_one()
            or 0
        )
        last = (
            await self.session.execute(
                select(func.max(ReserveInterestRecord.distributed_at))
            )
        ).scalar_one_or_none()

        return {
            "pool_total_points": await self._pool_total(),
            "pool_contributors": await self._pool_contributors(),
            "total_output_points": total_output,
            "total_interest_points": total_interest,
            "last_distributed_at": last,
        }

    async def list_interest_records(
        self, page: int = 1, page_size: int = 20
    ) -> tuple[list[ReserveInterestRecord], int]:
        """公共池分配历史（全局可见）。"""
        count_stmt = select(func.count()).select_from(ReserveInterestRecord)
        total = int((await self.session.execute(count_stmt)).scalar_one() or 0)

        stmt = (
            select(ReserveInterestRecord)
            .order_by(ReserveInterestRecord.distributed_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = (await self.session.execute(stmt)).scalars().all()
        return list(items), total

    async def borrow(self, user_id: uuid.UUID, amount: int) -> dict:
        """借用（取用）储备分转为自由分，受自身储备与公共池单人借用上限约束。"""
        if amount <= 0:
            raise ParamError("借用金额必须大于 0")

        account = await self._get_account(user_id)
        config = await self._get_platform_config()

        if amount > account.reserve_points:
            raise BusinessError("借用金额不能超过你的储备分")

        pool_total = await self._pool_total()
        borrow_cap = pool_total * config.max_borrow_ratio // 100
        if amount > borrow_cap:
            raise BusinessError(f"单次借用不能超过公共池上限 {borrow_cap} 分")

        balance_before = account.balance_points
        reserve_before = account.reserve_points
        account.reserve_points -= amount
        account.balance_points += amount

        record = ReserveBorrowRecord(
            user_id=user_id,
            amount_points=amount,
            balance_before=balance_before,
            reserve_before=reserve_before,
        )
        self.session.add(record)
        await self.session.flush()

        await self.audit.log(
            "reserve.borrowed",
            "reserve_borrow_record",
            record.id,
            {
                "amount_points": amount,
                "balance_before": balance_before,
                "reserve_before": reserve_before,
                "max_borrow_ratio": config.max_borrow_ratio,
                "pool_total_points": pool_total,
            },
            user_id=user_id,
        )

        await self.session.commit()
        return {
            "amount_points": amount,
            "balance_points": account.balance_points,
            "reserve_points": account.reserve_points,
        }

    async def list_interest_allocations(
        self, user_id: uuid.UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[ReserveInterestAllocation], int]:
        """我的利息分配明细（单账户）。"""
        count_stmt = (
            select(func.count())
            .select_from(ReserveInterestAllocation)
            .where(ReserveInterestAllocation.user_id == user_id)
        )
        total = int((await self.session.execute(count_stmt)).scalar_one() or 0)

        stmt = (
            select(ReserveInterestAllocation)
            .where(ReserveInterestAllocation.user_id == user_id)
            .order_by(ReserveInterestAllocation.distributed_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = (await self.session.execute(stmt)).scalars().all()
        return list(items), total

    async def list_borrow_records(
        self, user_id: uuid.UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[ReserveBorrowRecord], int]:
        """我的借用流水。"""
        count_stmt = (
            select(func.count())
            .select_from(ReserveBorrowRecord)
            .where(ReserveBorrowRecord.user_id == user_id)
        )
        total = int((await self.session.execute(count_stmt)).scalar_one() or 0)

        stmt = (
            select(ReserveBorrowRecord)
            .where(ReserveBorrowRecord.user_id == user_id)
            .order_by(ReserveBorrowRecord.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = (await self.session.execute(stmt)).scalars().all()
        return list(items), total
