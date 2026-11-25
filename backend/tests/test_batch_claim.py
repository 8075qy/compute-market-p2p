"""4.3 动态批量领取测试：Redis 原子游标切分工作项区间、即时生成 execution。"""
import pytest

from app.core.redis_client import get_redis
from app.core.redis_keys import RedisKeys
from app.models import Node, NodeStatus, Task, TaskStatus, TaskType
from app.services.execution import ExecutionService


async def _create_batch_task(
    db_session,
    demander,
    total: int = 100,
    batch_size: int = 0,
    status: TaskStatus = TaskStatus.ASSIGNED,
) -> Task:
    task = Task(
        task_no=f"TB-{demander.id.hex[:8]}-{total}-{batch_size}-{status.value}",
        demander_id=demander.id,
        type=TaskType.BATCH,
        title="批量推理任务",
        model_source="platform",
        params_json="{}",
        required_vram_gb=8,
        budget_points=50000,
        min_settlement_unit=1000,
        status=status,
        total_work_units=total,
        batch_size=batch_size,
        input_file_key=f"inputs/{demander.id.hex}/abc/data.zip",
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    return task


async def _claim_all(service: ExecutionService, node: Node) -> list[tuple[int, int]]:
    """循环领取直到耗尽，返回全部工作项区间（按领取顺序）。"""
    intervals: list[tuple[int, int]] = []
    while True:
        execution = await service._claim_batch_work(node)
        if execution is None:
            break
        intervals.append((execution.work_unit_start, execution.work_unit_end))
    return intervals


@pytest.mark.asyncio
async def test_claim_batch_allocates_sequential_intervals(
    db_session, test_user, test_supplier, online_node
):
    """K=8 时区间连续覆盖 [0, total)，末批自动截断。"""
    await _create_batch_task(db_session, test_user, total=25, batch_size=8)

    service = ExecutionService(db_session)
    intervals = await _claim_all(service, online_node)

    assert intervals == [(0, 8), (8, 16), (16, 24), (24, 25)]


@pytest.mark.asyncio
async def test_claim_batch_prefers_task_batch_size(
    db_session, test_user, test_supplier, online_node
):
    """batch_size > 0 时优先于节点算力档位。"""
    await _create_batch_task(db_session, test_user, total=100, batch_size=20)

    service = ExecutionService(db_session)
    execution = await service._claim_batch_work(online_node)

    assert execution is not None
    assert execution.work_unit_start == 0
    assert execution.work_unit_end == 20


@pytest.mark.asyncio
async def test_claim_batch_default_single_gpu(
    db_session, test_user, test_supplier, online_node
):
    """batch_size=0 且单卡节点，默认每批 8 个工作项。"""
    await _create_batch_task(db_session, test_user, total=100, batch_size=0)

    service = ExecutionService(db_session)
    execution = await service._claim_batch_work(online_node)

    assert execution is not None
    assert (execution.work_unit_end - execution.work_unit_start) == 8


@pytest.mark.asyncio
async def test_claim_batch_default_multi_gpu(
    db_session, test_user, test_supplier, online_node
):
    """batch_size=0 且整机(多卡)节点，默认每批 64 个工作项。"""
    await _create_batch_task(db_session, test_user, total=200, batch_size=0)
    multi_gpu_node = Node(
        owner_id=test_supplier.id,
        name="A100 8卡整机",
        gpu_model="A100",
        vram_gb=80,
        peak_tflops=312.0,
        gpu_count=8,
        status=NodeStatus.ONLINE,
        is_online=True,
        reputation_score=100,
    )
    db_session.add(multi_gpu_node)
    await db_session.commit()
    await db_session.refresh(multi_gpu_node)

    service = ExecutionService(db_session)
    execution = await service._claim_batch_work(multi_gpu_node)

    assert execution is not None
    assert (execution.work_unit_end - execution.work_unit_start) == 64


@pytest.mark.asyncio
async def test_claim_batch_stops_when_exhausted(
    db_session, test_user, test_supplier, online_node
):
    """全部工作项领取完毕后不再生成 execution，游标也不再增长。"""
    task = await _create_batch_task(db_session, test_user, total=20, batch_size=8)

    service = ExecutionService(db_session)
    intervals = await _claim_all(service, online_node)
    assert intervals == [(0, 8), (8, 16), (16, 20)]

    # 耗尽后再次领取应返回 None，且游标保持不变
    cursor_key = RedisKeys.BATCH_CURSOR.format(task_id=str(task.id))
    before = int(await get_redis().get(cursor_key) or 0)
    assert await service._claim_batch_work(online_node) is None
    after = int(await get_redis().get(cursor_key) or 0)
    assert after == before


@pytest.mark.asyncio
async def test_claim_batch_two_nodes_no_overlap(
    db_session, test_user, test_supplier, online_node
):
    """两个节点交替领取，区间不重叠且连续覆盖 [0, total)。"""
    await _create_batch_task(db_session, test_user, total=100, batch_size=8)
    node_b = Node(
        owner_id=test_supplier.id,
        name="RTX 4080 Node",
        gpu_model="RTX 4080",
        vram_gb=16,
        peak_tflops=48.7,
        status=NodeStatus.ONLINE,
        is_online=True,
        reputation_score=100,
    )
    db_session.add(node_b)
    await db_session.commit()
    await db_session.refresh(node_b)

    service = ExecutionService(db_session)
    nodes = [online_node, node_b]
    intervals: list[tuple[int, int]] = []
    i = 0
    while True:
        execution = await service._claim_batch_work(nodes[i % 2])
        if execution is None:
            break
        intervals.append((execution.work_unit_start, execution.work_unit_end))
        i += 1

    intervals.sort()
    assert intervals[0][0] == 0
    assert intervals[-1][1] == 100
    # 相邻区间首尾相接，无重叠、无遗漏
    for idx in range(1, len(intervals)):
        assert intervals[idx - 1][1] == intervals[idx][0]


@pytest.mark.asyncio
async def test_claim_batch_10000_units_1250_executions(
    db_session, test_user, test_supplier, online_node
):
    """验收标准：10000 工作项 + K=8 → 累计生成 1250 条 execution。"""
    await _create_batch_task(db_session, test_user, total=10000, batch_size=8)

    service = ExecutionService(db_session)
    intervals = await _claim_all(service, online_node)

    assert len(intervals) == 1250
    assert intervals[0] == (0, 8)
    assert intervals[-1] == (9992, 10000)


@pytest.mark.asyncio
async def test_pending_executions_returns_work_unit_fields(
    db_session, test_user, test_supplier, online_node
):
    """Agent 轮询接口返回 work_unit_start/end 供按区间执行。"""
    await _create_batch_task(db_session, test_user, total=100, batch_size=8)

    service = ExecutionService(db_session)
    items = await service.get_pending_executions(online_node.id, test_supplier.id)

    assert len(items) == 1
    assert items[0]["work_unit_start"] == 0
    assert items[0]["work_unit_end"] == 8
    assert items[0]["task_no"] is not None


@pytest.mark.asyncio
async def test_claim_batch_skips_non_batch_and_inactive(
    db_session, test_user, test_supplier, online_node
):
    """非批处理任务、未进入执行阶段的批处理任务均不被动态领取。"""
    inference = Task(
        task_no="TB-infer-0001",
        demander_id=test_user.id,
        type=TaskType.INFERENCE,
        title="普通推理任务",
        model_source="platform",
        params_json="{}",
        required_vram_gb=8,
        budget_points=10000,
        min_settlement_unit=1000,
        status=TaskStatus.ASSIGNED,
    )
    db_session.add(inference)
    await db_session.commit()

    # 尚未被调度器标记为 ASSIGNED 的批处理任务也不可领取
    await _create_batch_task(
        db_session, test_user, total=50, batch_size=8, status=TaskStatus.SCHEDULING
    )

    service = ExecutionService(db_session)
    assert await service._claim_batch_work(online_node) is None


@pytest.mark.asyncio
async def test_claim_batch_skips_zero_work_units(
    db_session, test_user, test_supplier, online_node
):
    """total_work_units 为 0 的批处理任务不参与领取。"""
    await _create_batch_task(db_session, test_user, total=0, batch_size=8)

    service = ExecutionService(db_session)
    assert await service._claim_batch_work(online_node) is None
