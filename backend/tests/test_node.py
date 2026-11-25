"""节点防多开（gpu_uuid）与硬件谎报检测（算力对标）单元测试。"""
import pytest
from httpx import AsyncClient

from app.models import GpuSpec, Node


def _node_payload(**overrides) -> dict:
    payload = {
        "name": "RTX 4090 Node",
        "gpu_model": "RTX 4090",
        "vram_gb": 24,
        "peak_tflops": 82.6,
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_create_node_with_gpu_uuid(client: AsyncClient, supplier_headers: dict):
    resp = await client.post(
        "/api/v1/supplier/nodes",
        json=_node_payload(gpu_uuid="GPU-abcdef-0001"),
        headers=supplier_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["gpu_uuid"] == "GPU-abcdef-0001"


@pytest.mark.asyncio
async def test_duplicate_gpu_uuid_rejected(client: AsyncClient, supplier_headers: dict):
    first = await client.post(
        "/api/v1/supplier/nodes",
        json=_node_payload(gpu_uuid="GPU-abcdef-0002"),
        headers=supplier_headers,
    )
    assert first.status_code == 200, first.text

    second = await client.post(
        "/api/v1/supplier/nodes",
        json=_node_payload(name="Second Node", gpu_uuid="GPU-abcdef-0002"),
        headers=supplier_headers,
    )
    assert second.status_code == 400, second.text
    assert "多开" in second.json()["message"]


@pytest.mark.asyncio
async def test_distinct_gpu_uuid_allowed(client: AsyncClient, supplier_headers: dict):
    first = await client.post(
        "/api/v1/supplier/nodes",
        json=_node_payload(gpu_uuid="GPU-aaaa-0001"),
        headers=supplier_headers,
    )
    assert first.status_code == 200, first.text
    second = await client.post(
        "/api/v1/supplier/nodes",
        json=_node_payload(name="Second Node", gpu_uuid="GPU-bbbb-0002"),
        headers=supplier_headers,
    )
    assert second.status_code == 200, second.text


@pytest.mark.asyncio
async def test_nodes_without_gpu_uuid_unrestricted(
    client: AsyncClient, supplier_headers: dict
):
    for i in range(2):
        resp = await client.post(
            "/api/v1/supplier/nodes",
            json=_node_payload(name=f"Node {i}"),
            headers=supplier_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["gpu_uuid"] is None


async def _seed_gpu_spec(db_session) -> GpuSpec:
    spec = GpuSpec(
        gpu_model="NVIDIA GeForce RTX 4090",
        vendor="nvidia",
        vram_gb=24,
        peak_tflops=83,
        aliases_json='["RTX 4090", "4090"]',
    )
    db_session.add(spec)
    await db_session.commit()
    return spec


async def _create_node(client: AsyncClient, headers: dict, **overrides) -> str:
    resp = await client.post(
        "/api/v1/supplier/nodes", json=_node_payload(**overrides), headers=headers
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


@pytest.mark.asyncio
async def test_benchmark_verified_on_match(client: AsyncClient, supplier_headers: dict):
    node_id = await _create_node(client, supplier_headers)
    resp = await client.post(
        f"/api/v1/supplier/nodes/{node_id}/benchmark",
        json={"benchmark_tflops": 82.6},
        headers=supplier_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["benchmark_status"] == "verified"
    assert data["benchmark_tflops"] == 82.6


@pytest.mark.asyncio
async def test_benchmark_failed_on_exceeded_claim(
    client: AsyncClient, supplier_headers: dict
):
    node_id = await _create_node(client, supplier_headers)
    resp = await client.post(
        f"/api/v1/supplier/nodes/{node_id}/benchmark",
        json={"benchmark_tflops": 60.0},
        headers=supplier_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["benchmark_status"] == "failed"
    assert data["reputation_score"] == 90


@pytest.mark.asyncio
async def test_benchmark_within_tolerance_verified(
    client: AsyncClient, supplier_headers: dict
):
    node_id = await _create_node(client, supplier_headers)
    resp = await client.post(
        f"/api/v1/supplier/nodes/{node_id}/benchmark",
        json={"benchmark_tflops": 64.0},
        headers=supplier_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["benchmark_status"] == "verified"


@pytest.mark.asyncio
async def test_create_node_claim_exceeds_spec_rejected(
    db_session, client: AsyncClient, supplier_headers: dict
):
    await _seed_gpu_spec(db_session)
    resp = await client.post(
        "/api/v1/supplier/nodes",
        json=_node_payload(peak_tflops=200.0),
        headers=supplier_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "谎报" in resp.json()["message"]


@pytest.mark.asyncio
async def test_sybil_node_limit_per_user(
    db_session, test_supplier, client: AsyncClient, supplier_headers: dict
):
    # MAX_NODES_PER_USER 默认 10，先塞满该账号节点配额
    for i in range(10):
        db_session.add(
            Node(
                owner_id=test_supplier.id,
                name=f"Node {i}",
                gpu_model="RTX 4090",
                vram_gb=24,
                peak_tflops=82.6,
            )
        )
    await db_session.commit()

    resp = await client.post(
        "/api/v1/supplier/nodes",
        json=_node_payload(name="Node overflow"),
        headers=supplier_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "女巫" in resp.json()["message"]


@pytest.mark.asyncio
async def test_update_node_resets_benchmark(
    client: AsyncClient, supplier_headers: dict
):
    node_id = await _create_node(client, supplier_headers)

    bench = await client.post(
        f"/api/v1/supplier/nodes/{node_id}/benchmark",
        json={"benchmark_tflops": 82.6},
        headers=supplier_headers,
    )
    assert bench.json()["data"]["benchmark_status"] == "verified"

    # 修改峰值算力后，原对标结果失效，重置为待对标
    resp = await client.put(
        f"/api/v1/supplier/nodes/{node_id}",
        json={"peak_tflops": 90.0},
        headers=supplier_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["benchmark_status"] == "pending"
    assert data["benchmark_tflops"] is None
    assert data["benchmarked_at"] is None


@pytest.mark.asyncio
async def test_update_node_name_keeps_benchmark(
    client: AsyncClient, supplier_headers: dict
):
    node_id = await _create_node(client, supplier_headers)

    await client.post(
        f"/api/v1/supplier/nodes/{node_id}/benchmark",
        json={"benchmark_tflops": 82.6},
        headers=supplier_headers,
    )

    # 仅修改名称（非硬件规格）不应重置对标结果
    resp = await client.put(
        f"/api/v1/supplier/nodes/{node_id}",
        json={"name": "Renamed Node"},
        headers=supplier_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["benchmark_status"] == "verified"
    assert data["benchmark_tflops"] == 82.6
