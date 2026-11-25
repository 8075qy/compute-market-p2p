import pytest
from sqlalchemy import select

from app.models import AuditLog
from app.services.audit import AuditService


@pytest.mark.asyncio
async def test_audit_chain_is_valid(db_session, test_user):
    service = AuditService(db_session)
    for index in range(3):
        await service.log(
            "ACCOUNT_CREDIT",
            "Account",
            test_user.id,
            {"amount": (index + 1) * 100},
            test_user.id,
        )
    await db_session.commit()

    valid, errors = await service.verify_chain()
    assert valid is True
    assert errors == []


@pytest.mark.asyncio
async def test_audit_chain_detects_tampering(db_session, test_user):
    service = AuditService(db_session)
    first = await service.log("ACCOUNT_CREDIT", "Account", test_user.id, {"amount": 100})
    second = await service.log("ACCOUNT_DEBIT", "Account", test_user.id, {"amount": 50})
    await db_session.commit()

    assert second.prev_hash == first.hash

    second.payload_json = '{"amount": 999999}'
    await db_session.commit()

    valid, errors = await service.verify_chain()
    assert valid is False
    assert any("Hash mismatch" in error for error in errors)


@pytest.mark.asyncio
async def test_audit_chain_detects_missing_link(db_session, test_user):
    service = AuditService(db_session)
    first = await service.log("A", "Account", test_user.id, {"n": 1})
    second = await service.log("B", "Account", test_user.id, {"n": 2})
    third = await service.log("C", "Account", test_user.id, {"n": 3})
    await db_session.commit()

    await db_session.delete(second)
    await db_session.commit()

    valid, errors = await service.verify_chain()
    assert valid is False
    assert any("Chain broken" in error for error in errors)
    assert first.hash and third.hash


@pytest.mark.asyncio
async def test_audit_logs_are_append_only_ordered(db_session, test_user):
    service = AuditService(db_session)
    logs = []
    for event in ["created", "assigned", "settled"]:
        logs.append(
            await service.log(event, "Task", test_user.id, {"event": event})
        )
    await db_session.commit()

    stored = (
        await db_session.execute(select(AuditLog).order_by(AuditLog.created_at))
    ).scalars().all()
    assert [item.event_type for item in stored] == ["created", "assigned", "settled"]
    assert stored[0].prev_hash is None
    assert stored[1].prev_hash == stored[0].hash
    assert stored[2].prev_hash == stored[1].hash
