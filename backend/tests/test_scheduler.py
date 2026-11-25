import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import (
    Account,
    Node,
    NodeStatus,
    Task,
    TaskExecution,
    TaskStatus,
    TaskType,
    User,
)
from app.services.scheduler import NodeHeartbeatService, TaskRetryHandler, TaskScheduler
from app.services.settlement import SettlementEngine


def make_task(user: User, **kwargs) -> Task:
    data = {
        "task_no": kwargs.pop("task_no", "T202601010001"),
        "demander_id": user.id,
        "type": TaskType.INFERENCE,
        "title": kwargs.pop("title", "调度测试任务"),
        "model_source": "platform",
        "params_json": "{}",
        "required_vram_gb": 8,
        "budget_points": 5000,
        "preauthorized_points": 5000,
        "min_settlement_unit": 1000,
        "status": TaskStatus.SCHEDULING,
        "retry_count": 0,
        "max_retries": 3,
    }
    data.update(kwargs)
    return Task(**data)


@pytest.mark.asyncio
async def test_scheduler_picks_closest_vram(db_session, test_user, test_supplier, online_node):
    small = Node(
        owner_id=test_supplier.id,
        name="Small",
        gpu_model="RTX 3060",
        vram_gb=10,
        peak_tflops=13,
        region_province="贵州省",
        region_city="贵阳市",
        status=NodeStatus.ONLINE,
        is_online=True,
        reputation_score=90,
    )
    db_session.add(small)
    task = make_task(test_user)
    db_session.add(task)
    await db_session.commit()

    scheduler = TaskScheduler(db_session)
    chosen = await scheduler.assign_task(task)

    assert chosen is not None
    assert chosen.id == small.id  # 10GB 比 24GB 更接近 8GB 需求


@pytest.mark.asyncio
async def test_scheduler_skips_offline_and_low_reputation(db_session, test_user, test_supplier):
    offline = Node(
        owner_id=test_supplier.id,
        name="Offline",
        gpu_model="RTX 4090",
        vram_gb=24,
        peak_tflops=82.6,
        region_province="贵州省",
        region_city="贵阳市",
        status=NodeStatus.OFFLINE,
        is_online=False,
        reputation_score=100,
    )
    bad = Node(
        owner_id=test_supplier.id,
        name="Bad Rep",
        gpu_model="RTX 4090",
        vram_gb=24,
        peak_tflops=82.6,
        region_province="贵州省",
        region_city="贵阳市",
        status=NodeStatus.ONLINE,
        is_online=True,
        reputation_score=30,
    )
    db_session.add_all([offline, bad])
    task = make_task(test_user, task_no="T202601010002")
    db_session.add(task)
    await db_session.commit()

    scheduler = TaskScheduler(db_session)
    assert await scheduler.assign_task(task) is None


def test_estimate_points_rounds_up():
    """预授权预估：按算力满载 N 分钟向上取整，缺失算力回退最低 1 分。"""
    assert SettlementEngine.estimate_points(13.5, 60) == 14
    assert SettlementEngine.estimate_points(82.6, 60) == 83  # noqa: PLR2004
    assert SettlementEngine.estimate_points(None, 60) == 1
    assert SettlementEngine.estimate_points(0, 60) == 1


@pytest.mark.asyncio
async def test_ensure_preauthorized_tops_up_from_balance(db_session, test_user):
    """预授权续冻：额度不足时从需求方余额补足，余额与冻结同步增减。"""
    task = make_task(test_user, preauthorized_points=0)
    db_session.add(task)
    await db_session.commit()

    engine = SettlementEngine(db_session)
    ok = await engine.ensure_preauthorized(task, 14)
    assert ok is True
    assert task.preauthorized_points == 14

    account = (
        await db_session.execute(select(Account).where(Account.user_id == test_user.id))
    ).scalar_one()
    assert account.balance_points == 19986
    assert account.frozen_points == 14


@pytest.mark.asyncio
async def test_ensure_preauthorized_fails_when_balance_insufficient(db_session, test_user):
    """预授权续冻失败：余额不足时不扣款、不增额，返回 False。"""
    task = make_task(test_user, preauthorized_points=0)
    db_session.add(task)
    await db_session.commit()

    account = (
        await db_session.execute(select(Account).where(Account.user_id == test_user.id))
    ).scalar_one()
    account.balance_points = 5
    await db_session.commit()

    engine = SettlementEngine(db_session)
    ok = await engine.ensure_preauthorized(task, 14)
    assert ok is False
    assert task.preauthorized_points == 0
    assert account.frozen_points == 0


@pytest.mark.asyncio
async def test_dispatch_task_pauses_when_balance_insufficient(
    db_session, test_user, online_node
):
    """余额不足以预授权首个分片时，任务置 PAUSED 并持久化。"""
    task = make_task(test_user, preauthorized_points=0)
    db_session.add(task)
    await db_session.commit()

    account = (
        await db_session.execute(select(Account).where(Account.user_id == test_user.id))
    ).scalar_one()
    account.balance_points = 10
    await db_session.commit()

    scheduler = TaskScheduler(db_session)
    await scheduler.schedule_pending_tasks()

    await db_session.refresh(task)
    assert task.status == TaskStatus.PAUSED


@pytest.mark.asyncio
async def test_resume_paused_tasks_resumes_after_balance_restored(
    db_session, test_user, online_node
):
    """余额恢复后，定时任务续冻并将 PAUSED 任务重新入队 SCHEDULING。"""
    task = make_task(
        test_user,
        preauthorized_points=0,
        required_tflops=13.5,
        status=TaskStatus.PAUSED,
    )
    db_session.add(task)
    await db_session.commit()

    scheduler = TaskScheduler(db_session)
    resumed = await scheduler.resume_paused_tasks()

    assert resumed == 1
    await db_session.refresh(task)
    assert task.status == TaskStatus.SCHEDULING
    assert task.preauthorized_points == 14

    account = (
        await db_session.execute(select(Account).where(Account.user_id == test_user.id))
    ).scalar_one()
    assert account.balance_points == 19986
    assert account.frozen_points == 14


@pytest.mark.asyncio
async def test_resume_paused_tasks_keeps_paused_when_still_insufficient(
    db_session, test_user
):
    """余额仍不足时，任务保持 PAUSED，不产生副作用。"""
    task = make_task(
        test_user,
        preauthorized_points=0,
        required_tflops=13.5,
        status=TaskStatus.PAUSED,
    )
    db_session.add(task)
    await db_session.commit()

    account = (
        await db_session.execute(select(Account).where(Account.user_id == test_user.id))
    ).scalar_one()
    account.balance_points = 5
    await db_session.commit()

    scheduler = TaskScheduler(db_session)
    resumed = await scheduler.resume_paused_tasks()

    assert resumed == 0
    await db_session.refresh(task)
    assert task.status == TaskStatus.PAUSED
    assert task.preauthorized_points == 0


@pytest.mark.asyncio
async def test_schedule_cycle_creates_assigned_execution(
    db_session, test_user, online_node
):
    task = make_task(test_user, task_no="T202601010003")
    db_session.add(task)
    await db_session.commit()

    scheduler = TaskScheduler(db_session)
    count = await scheduler.schedule_pending_tasks()

    assert count == 1
    await db_session.refresh(task)
    assert task.status == TaskStatus.ASSIGNED
    assert task.assigned_node_id == online_node.id

    execution = (
        await db_session.execute(
            select(TaskExecution).where(TaskExecution.task_id == task.id)
        )
    ).scalar_one()
    assert execution.attempt_no == 1
    assert execution.status == TaskStatus.ASSIGNED
    assert execution.started_at is None
    assert execution.platform_fee_rate == 0


@pytest.mark.asyncio
async def test_heartbeat_updates_metrics(db_session, online_node):
    online_node.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=6)
    await db_session.commit()

    from app.schemas.node import NodeHeartbeatRequest

    service = NodeHeartbeatService(db_session)
    await service.heartbeat(
        online_node.id, NodeHeartbeatRequest(gpu_util=55, vram_used_gb=9, temp_c=65)
    )

    await db_session.refresh(online_node)
    assert online_node.is_online is True
    assert online_node.status == NodeStatus.ONLINE
    assert float(online_node.gpu_utilization) == 55
    assert online_node.vram_used_gb == 9
    assert online_node.temp_c == 65


@pytest.mark.asyncio
async def test_heartbeat_timeout_marks_node_offline(db_session, online_node):
    online_node.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=6)
    await db_session.commit()

    service = NodeHeartbeatService(db_session)
    count = await service.check_offline_nodes()

    assert count == 1
    await db_session.refresh(online_node)
    assert online_node.is_online is False
    assert online_node.status == NodeStatus.OFFLINE


@pytest.mark.asyncio
async def test_recent_heartbeat_keeps_node_online(db_session, online_node):
    online_node.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=2)
    await db_session.commit()

    service = NodeHeartbeatService(db_session)
    assert await service.check_offline_nodes() == 0

    await db_session.refresh(online_node)
    assert online_node.status == NodeStatus.ONLINE


@pytest.mark.asyncio
async def test_retry_handler_reschedules_and_increments(
    db_session, test_user, online_node
):
    task = make_task(test_user, task_no="T202601010004", status=TaskStatus.RUNNING)
    db_session.add(task)
    await db_session.flush()
    execution = TaskExecution(
        task_id=task.id,
        node_id=online_node.id,
        attempt_no=1,
        status=TaskStatus.FAILED,
        completed_at=datetime.now(UTC),
        error_message="OOM",
        platform_fee_rate=1000,
    )
    db_session.add(execution)
    await db_session.commit()

    handler = TaskRetryHandler(db_session)
    await handler.handle_failed_execution(execution)

    await db_session.refresh(task)
    assert task.retry_count == 1
    assert task.status == TaskStatus.SCHEDULING
    assert task.assigned_node_id is None


@pytest.mark.asyncio
async def test_retry_handler_refunds_after_max_retries(
    db_session, test_user, online_node
):
    account = (
        await db_session.execute(select(Account).where(Account.user_id == test_user.id))
    ).scalar_one()
    account.balance_points = 15000
    account.frozen_points = 5000
    task = make_task(
        test_user,
        task_no="T202601010005",
        status=TaskStatus.RUNNING,
        retry_count=3,
    )
    db_session.add(task)
    await db_session.flush()
    execution = TaskExecution(
        task_id=task.id,
        node_id=online_node.id,
        attempt_no=4,
        status=TaskStatus.FAILED,
        completed_at=datetime.now(UTC),
        error_message="final",
        platform_fee_rate=1000,
    )
    db_session.add(execution)
    await db_session.commit()

    handler = TaskRetryHandler(db_session)
    await handler.handle_failed_execution(execution)

    await db_session.refresh(task)
    await db_session.refresh(account)
    assert task.status == TaskStatus.FAILED
    assert task.retry_count == 3
    assert account.frozen_points == 0
    assert account.balance_points == 20000


@pytest.mark.asyncio
async def test_scale_out_adds_slice_below_max_concurrency(
    db_session, test_user, test_supplier, online_node
):
    node2 = Node(
        owner_id=test_supplier.id,
        name="Node 2",
        gpu_model="RTX 4090",
        vram_gb=24,
        peak_tflops=82.6,
        status=NodeStatus.ONLINE,
        is_online=True,
        reputation_score=100,
    )
    db_session.add(node2)
    task = make_task(
        test_user,
        task_no="T202601010010",
        status=TaskStatus.RUNNING,
        concurrency=1,
        max_concurrency=3,
        budget_points=10000,
    )
    db_session.add(task)
    await db_session.flush()
    db_session.add(
        TaskExecution(
            task_id=task.id,
            node_id=online_node.id,
            slice_index=0,
            attempt_no=1,
            status=TaskStatus.RUNNING,
        )
    )
    await db_session.commit()

    scheduler = TaskScheduler(db_session)
    added = await scheduler.scale_out_running_tasks()

    assert added == 1
    executions = (
        await db_session.execute(
            select(TaskExecution)
            .where(TaskExecution.task_id == task.id)
            .order_by(TaskExecution.slice_index)
        )
    ).scalars().all()
    assert len(executions) == 2
    assert executions[1].slice_index == 1
    assert executions[1].node_id == node2.id
    assert executions[1].attempt_no == 1


@pytest.mark.asyncio
async def test_scale_out_stops_at_max_concurrency(
    db_session, test_user, online_node
):
    # max_concurrency 为 NULL 时回退到 concurrency（=1）
    task = make_task(
        test_user, task_no="T202601010011", status=TaskStatus.RUNNING, concurrency=1
    )
    db_session.add(task)
    await db_session.flush()
    db_session.add(
        TaskExecution(
            task_id=task.id,
            node_id=online_node.id,
            slice_index=0,
            attempt_no=1,
            status=TaskStatus.RUNNING,
        )
    )
    await db_session.commit()

    scheduler = TaskScheduler(db_session)
    assert await scheduler.scale_out_running_tasks() == 0


@pytest.mark.asyncio
async def test_scale_out_skips_when_budget_insufficient(
    db_session, test_user, online_node
):
    task = make_task(
        test_user,
        task_no="T202601010012",
        status=TaskStatus.RUNNING,
        concurrency=1,
        max_concurrency=3,
        budget_points=500,  # 低于最小结算单位 1000
    )
    db_session.add(task)
    await db_session.flush()
    db_session.add(
        TaskExecution(
            task_id=task.id,
            node_id=online_node.id,
            slice_index=0,
            attempt_no=1,
            status=TaskStatus.RUNNING,
        )
    )
    await db_session.commit()

    scheduler = TaskScheduler(db_session)
    assert await scheduler.scale_out_running_tasks() == 0


@pytest.mark.asyncio
async def test_scheduler_excludes_demander_own_node(
    db_session, test_user, test_supplier, online_node
):
    """P0 反作弊：调度时排除需求方自己的节点，防止自买自卖刷储备贡献率与利息。"""
    own = Node(
        owner_id=test_user.id,
        name="Self Node",
        gpu_model="RTX 3090",
        vram_gb=24,
        peak_tflops=35.6,
        region_province="贵州省",
        region_city="贵阳市",
        status=NodeStatus.ONLINE,
        is_online=True,
        reputation_score=100,
    )
    db_session.add(own)
    task = make_task(test_user, task_no="T202601010099")
    db_session.add(task)
    await db_session.commit()

    scheduler = TaskScheduler(db_session)
    ranked = await scheduler._rank_nodes(task)

    ids = [n.id for n in ranked]
    assert own.id not in ids
    assert online_node.id in ids


@pytest.mark.asyncio
async def test_create_execution_generates_challenge_nonce(
    db_session, test_user, online_node
):
    """P0 反作弊：每次执行生成唯一挑战种子，供 Agent 绑定 proof_hash 防重放。"""
    task = make_task(test_user, task_no="T202601010100")
    db_session.add(task)
    await db_session.commit()

    scheduler = TaskScheduler(db_session)
    first = await scheduler.create_execution(task, online_node)
    second = await scheduler.create_execution(task, online_node, slice_index=1)

    assert first.challenge_nonce
    assert len(first.challenge_nonce) == 32
    assert first.challenge_nonce != second.challenge_nonce


@pytest.mark.asyncio
async def test_parallel_dispatch_creates_multiple_slices(
    db_session, test_user, test_supplier, online_node
):
    node2 = Node(
        owner_id=test_supplier.id,
        name="RTX 4080",
        gpu_model="RTX 4080",
        vram_gb=16,
        peak_tflops=48.7,
        region_province="贵州省",
        region_city="贵阳市",
        status=NodeStatus.ONLINE,
        is_online=True,
        reputation_score=95,
    )
    db_session.add(node2)
    task = make_task(test_user, task_no="T202601010006", concurrency=2)
    db_session.add(task)
    await db_session.commit()

    scheduler = TaskScheduler(db_session)
    count = await scheduler.schedule_pending_tasks()

    assert count == 1
    await db_session.refresh(task)
    assert task.status == TaskStatus.ASSIGNED

    executions = (
        await db_session.execute(
            select(TaskExecution)
            .where(TaskExecution.task_id == task.id)
            .order_by(TaskExecution.slice_index)
        )
    ).scalars().all()
    assert len(executions) == 2
    assert [e.slice_index for e in executions] == [0, 1]
    assert all(e.status == TaskStatus.ASSIGNED for e in executions)


@pytest.mark.asyncio
async def test_parallel_slice_retry_reschedules_only_failed_slice(
    db_session, test_user, online_node
):
    task = make_task(
        test_user,
        task_no="T202601010007",
        status=TaskStatus.RUNNING,
        concurrency=2,
    )
    db_session.add(task)
    await db_session.flush()
    failed = TaskExecution(
        task_id=task.id,
        node_id=online_node.id,
        slice_index=0,
        attempt_no=1,
        status=TaskStatus.FAILED,
        completed_at=datetime.now(UTC),
        error_message="OOM",
        platform_fee_rate=1000,
    )
    running = TaskExecution(
        task_id=task.id,
        node_id=online_node.id,
        slice_index=1,
        attempt_no=1,
        status=TaskStatus.RUNNING,
        platform_fee_rate=1000,
    )
    db_session.add_all([failed, running])
    await db_session.commit()

    handler = TaskRetryHandler(db_session)
    await handler.handle_failed_execution(failed)

    await db_session.refresh(task)
    assert task.status == TaskStatus.RUNNING
    assert task.retry_count == 1

    executions = (
        await db_session.execute(
            select(TaskExecution)
            .where(TaskExecution.task_id == task.id)
            .order_by(TaskExecution.slice_index, TaskExecution.attempt_no)
        )
    ).scalars().all()
    assert len(executions) == 3
    retried = [e for e in executions if e.slice_index == 0 and e.attempt_no == 2]
    assert len(retried) == 1
    assert retried[0].status == TaskStatus.ASSIGNED
    # 健康分片不受影响
    assert all(e.status == TaskStatus.RUNNING for e in executions if e.slice_index == 1)


@pytest.mark.asyncio
async def test_scheduler_prefers_cached_model_node(db_session, test_user, test_supplier):
    """B2：显存相同的情况下，已缓存任务模型的节点应被优先调度。"""
    cached = Node(
        owner_id=test_supplier.id,
        name="Cached Node",
        gpu_model="RTX 3080",
        vram_gb=10,
        peak_tflops=30,
        region_province="贵州省",
        region_city="贵阳市",
        status=NodeStatus.ONLINE,
        is_online=True,
        reputation_score=100,
        cached_models_json=json.dumps(["models/cached-model.bin"]),
    )
    plain = Node(
        owner_id=test_supplier.id,
        name="Plain Node",
        gpu_model="RTX 3080",
        vram_gb=10,
        peak_tflops=30,
        region_province="贵州省",
        region_city="贵阳市",
        status=NodeStatus.ONLINE,
        is_online=True,
        reputation_score=100,
    )
    db_session.add_all([cached, plain])
    task = make_task(
        test_user,
        task_no="T202601010008",
        model_source="upload",
        model_file_key="models/cached-model.bin",
    )
    db_session.add(task)
    await db_session.commit()

    scheduler = TaskScheduler(db_session)
    chosen = await scheduler.assign_task(task)

    assert chosen is not None
    assert chosen.id == cached.id


@pytest.mark.asyncio
async def test_heartbeat_records_cached_models(db_session, online_node):
    """B2：节点心跳上报缓存模型列表后正确落库。"""
    from app.schemas.node import NodeHeartbeatRequest

    service = NodeHeartbeatService(db_session)
    await service.heartbeat(
        online_node.id,
        NodeHeartbeatRequest(gpu_util=50, cached_models=["models/a.bin", "models/b.bin"]),
    )

    await db_session.refresh(online_node)
    assert online_node.cached_models == ["models/a.bin", "models/b.bin"]


@pytest.mark.asyncio
async def test_scheduler_prefers_higher_reserve_contribution(
    db_session, test_user, test_supplier, online_node
):
    """储备贡献率高的供给方节点优先调度（贡献越多、取用越优先）。"""
    from app.core.security import get_password_hash
    from app.models import UserRole

    supplier_acct = (
        await db_session.execute(
            select(Account).where(Account.user_id == test_supplier.id)
        )
    ).scalar_one()
    supplier_acct.reserve_points = 100
    supplier_acct.total_earned = 1000  # 贡献率 0.1

    high = User(
        phone="13600136000",
        password_hash=get_password_hash("password123"),
        nickname="high-contributor",
        roles=[UserRole.USER.value],
        is_active=True,
    )
    db_session.add(high)
    await db_session.flush()
    db_session.add(Account(user_id=high.id, reserve_points=300, total_earned=1000))  # 贡献率 0.3

    high_node = Node(
        owner_id=high.id,
        name="High Reserve Node",
        gpu_model="RTX 4090",
        vram_gb=24,
        peak_tflops=82.6,
        region_province="贵州省",
        region_city="贵阳市",
        status=NodeStatus.ONLINE,
        is_online=True,
        reputation_score=100,
    )
    db_session.add(high_node)
    task = make_task(test_user)
    db_session.add(task)
    await db_session.commit()

    scheduler = TaskScheduler(db_session)
    chosen = await scheduler.assign_task(task)

    assert chosen is not None
    assert chosen.id == high_node.id  # 贡献率 0.3 > 0.1，应优先


@pytest.mark.asyncio
async def test_scale_in_terminates_lagging_slice(
    db_session, test_user, test_supplier, online_node
):
    node2 = Node(
        owner_id=test_supplier.id,
        name="Node 2",
        gpu_model="RTX 4090",
        vram_gb=24,
        peak_tflops=82.6,
        status=NodeStatus.ONLINE,
        is_online=True,
        reputation_score=100,
    )
    db_session.add(node2)
    task = make_task(
        test_user,
        task_no="T202601010020",
        status=TaskStatus.RUNNING,
        concurrency=2,
        budget_points=10000,
    )
    db_session.add(task)
    await db_session.flush()
    now = datetime.now(UTC)
    db_session.add_all(
        [
            TaskExecution(
                task_id=task.id,
                node_id=online_node.id,
                slice_index=0,
                attempt_no=1,
                status=TaskStatus.COMPLETED,
                compute_points=1000,
                compute_duration_seconds=3600,
                started_at=now - timedelta(hours=1),
                completed_at=now - timedelta(minutes=30),
            ),
            TaskExecution(
                task_id=task.id,
                node_id=node2.id,
                slice_index=1,
                attempt_no=1,
                status=TaskStatus.RUNNING,
                started_at=now - timedelta(minutes=20),
            ),
        ]
    )
    await db_session.commit()

    scheduler = TaskScheduler(db_session)
    scaled_in = await scheduler.scale_in_lagging_tasks()

    assert scaled_in == 1
    lagging = (
        await db_session.execute(
            select(TaskExecution).where(
                TaskExecution.task_id == task.id,
                TaskExecution.slice_index == 1,
            )
        )
    ).scalar_one()
    assert lagging.status == TaskStatus.COMPLETED
    assert lagging.compute_points is not None and lagging.compute_points > 0
    assert "弹性缩容" in (lagging.error_message or "")

    await db_session.refresh(task)
    assert task.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_scale_in_skips_without_completed_slice(
    db_session, test_user, online_node
):
    task = make_task(
        test_user, task_no="T202601010021", status=TaskStatus.RUNNING, concurrency=1
    )
    db_session.add(task)
    await db_session.flush()
    now = datetime.now(UTC)
    db_session.add(
        TaskExecution(
            task_id=task.id,
            node_id=online_node.id,
            slice_index=0,
            attempt_no=1,
            status=TaskStatus.RUNNING,
            started_at=now - timedelta(minutes=30),
        )
    )
    await db_session.commit()

    scheduler = TaskScheduler(db_session)
    assert await scheduler.scale_in_lagging_tasks() == 0


@pytest.mark.asyncio
async def test_scale_in_skips_fresh_running_slice(
    db_session, test_user, online_node
):
    task = make_task(
        test_user, task_no="T202601010022", status=TaskStatus.RUNNING, concurrency=2
    )
    db_session.add(task)
    await db_session.flush()
    now = datetime.now(UTC)
    db_session.add_all(
        [
            TaskExecution(
                task_id=task.id,
                node_id=online_node.id,
                slice_index=0,
                attempt_no=1,
                status=TaskStatus.COMPLETED,
                compute_points=1000,
                compute_duration_seconds=3600,
                started_at=now - timedelta(hours=1),
                completed_at=now - timedelta(minutes=5),
            ),
            TaskExecution(
                task_id=task.id,
                node_id=online_node.id,
                slice_index=1,
                attempt_no=1,
                status=TaskStatus.RUNNING,
                started_at=now - timedelta(minutes=2),
            ),
        ]
    )
    await db_session.commit()

    scheduler = TaskScheduler(db_session)
    assert await scheduler.scale_in_lagging_tasks() == 0


@pytest.mark.asyncio
async def test_large_vram_task_only_assigned_to_multi_gpu_node(
    db_session, test_user, test_supplier, online_node
):
    """多卡整机：required_vram_gb 大于单卡显存时，只派给总显存足够的整机节点。"""
    # online_node 为单卡 RTX 4090（24GB），总显存 24GB < 100GB 需求，应被过滤
    h100 = Node(
        owner_id=test_supplier.id,
        name="8x H100 Node",
        gpu_model="NVIDIA H100",
        vram_gb=80,
        gpu_count=8,
        peak_tflops=989,
        region_province="贵州省",
        region_city="贵阳市",
        status=NodeStatus.ONLINE,
        is_online=True,
        reputation_score=100,
    )
    db_session.add(h100)
    task = make_task(test_user, task_no="T202601010200", required_vram_gb=100)
    db_session.add(task)
    await db_session.commit()

    scheduler = TaskScheduler(db_session)
    chosen = await scheduler.assign_task(task)

    assert chosen is not None
    assert chosen.id == h100.id  # 总显存 640GB 满足需求；单卡节点被过滤


@pytest.mark.asyncio
async def test_large_vram_task_no_eligible_node_returns_none(
    db_session, test_user, online_node
):
    """多卡整机：总显存不足的单卡节点无法承接大显存任务。"""
    # online_node 为单卡 RTX 4090（24GB）
    task = make_task(test_user, task_no="T202601010201", required_vram_gb=48)
    db_session.add(task)
    await db_session.commit()

    scheduler = TaskScheduler(db_session)
    assert await scheduler.assign_task(task) is None
