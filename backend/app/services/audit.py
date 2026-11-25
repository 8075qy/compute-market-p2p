import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


def _normalize_iso(value: datetime) -> str:
    """SQLite 会丢失时区信息，统一按 UTC 计算哈希。"""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _compute_hash(prev_hash: str | None, payload_json: str, created_at: str) -> str:
    return hashlib.sha256(
        f"{prev_hash or ''}{payload_json}{created_at}".encode()
    ).hexdigest()


class AuditService:
    """追加式、哈希链式审计日志。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def log(
        self,
        event_type: str,
        entity_type: str,
        entity_id: uuid.UUID | None,
        payload: dict,
        user_id: uuid.UUID | None = None,
    ) -> AuditLog:
        stmt = (
            select(AuditLog.hash, AuditLog.created_at)
            .order_by(AuditLog.created_at.desc())
            .limit(1)
        )
        last = (await self.session.execute(stmt)).first()
        prev_hash = last.hash if last else None

        payload_json = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
        )
        created_at = datetime.now(UTC)
        if last and last.created_at is not None:
            last_created = last.created_at
            if last_created.tzinfo is None:
                last_created = last_created.replace(tzinfo=UTC)
            if created_at <= last_created:
                created_at = last_created + timedelta(microseconds=1)
        current_hash = _compute_hash(
            prev_hash, payload_json, _normalize_iso(created_at)
        )

        audit_log = AuditLog(
            prev_hash=prev_hash,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            user_id=user_id,
            payload_json=payload_json,
            hash=current_hash,
            created_at=created_at,
        )
        self.session.add(audit_log)
        await self.session.flush()
        return audit_log

    async def verify_chain(
        self, start_from: datetime | None = None
    ) -> tuple[bool, list[str]]:
        """验证审计日志哈希链完整性。"""
        errors: list[str] = []
        prev_hash: str | None = None

        if start_from:
            # 找到起点之前最后一条日志，用于校验链连续性
            previous = (
                await self.session.execute(
                    select(AuditLog.hash)
                    .where(AuditLog.created_at < start_from)
                    .order_by(AuditLog.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            prev_hash = previous

        stmt = select(AuditLog).order_by(AuditLog.created_at.asc())
        if start_from:
            stmt = stmt.where(AuditLog.created_at >= start_from)

        logs = (await self.session.execute(stmt)).scalars().all()

        for log in logs:
            computed_hash = _compute_hash(
                log.prev_hash, log.payload_json, _normalize_iso(log.created_at)
            )
            if computed_hash != log.hash:
                errors.append(
                    f"Hash mismatch at {log.id}: expected {computed_hash}, got {log.hash}"
                )

            if prev_hash is not None and log.prev_hash != prev_hash:
                errors.append(
                    f"Chain broken at {log.id}: prev_hash {log.prev_hash} != {prev_hash}"
                )

            prev_hash = log.hash

        return len(errors) == 0, errors
