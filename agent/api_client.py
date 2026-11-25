"""后端控制面 API 客户端：封装供给方节点所需的全部接口。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx


class ApiClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=60.0)
        self.access_token: str | None = None

    async def close(self) -> None:
        await self._client.aclose()

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    async def _request(
        self, method: str, path: str, **kwargs: Any
    ) -> Any:
        resp = await self._client.request(
            method, f"{self.base_url}{path}", headers=self._headers(), **kwargs
        )
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("code") not in (0, None):
            raise RuntimeError(payload.get("message", "接口调用失败"))
        return payload.get("data") or {}

    # ---- 认证 ----
    async def login(self, contact: str, password: str) -> str:
        data = await self._request(
            "POST", "/auth/login", json={"contact": contact, "password": password}
        )
        token = str(data["access_token"])
        self.access_token = token
        return token

    # ---- 节点 ----
    async def register_node(self, node: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/supplier/nodes", json=node)

    async def update_node(self, node_id: str, node: dict[str, Any]) -> dict[str, Any]:
        return await self._request("PUT", f"/supplier/nodes/{node_id}", json=node)

    async def report_benchmark(self, node_id: str, benchmark_tflops: float) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/supplier/nodes/{node_id}/benchmark",
            json={"benchmark_tflops": benchmark_tflops},
        )

    async def heartbeat(self, node_id: str, metrics: dict[str, Any]) -> dict[str, Any]:
        return await self._request(
            "POST", f"/supplier/nodes/{node_id}/heartbeat", json=metrics
        )

    # ---- GPU 规格库 ----
    async def match_gpu_spec(self, model: str) -> dict[str, Any]:
        return await self._request("GET", "/gpu-specs/match", params={"model": model})

    # ---- 分片执行 ----
    async def pending_executions(self, node_id: str) -> list[dict[str, Any]]:
        return await self._request(
            "GET", f"/supplier/nodes/{node_id}/pending-executions"
        )

    async def start_execution(self, execution_id: str) -> dict[str, Any]:
        return await self._request(
            "POST", f"/supplier/executions/{execution_id}/start", json={}
        )

    async def complete_execution(
        self, execution_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._request(
            "POST", f"/supplier/executions/{execution_id}/complete", json=payload
        )

    async def fail_execution(
        self, execution_id: str, error_message: str
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/supplier/executions/{execution_id}/fail",
            json={"error_message": error_message},
        )

    # ---- 模型与结果文件 ----
    async def model_download_url(self, execution_id: str) -> dict[str, Any]:
        return await self._request(
            "GET", f"/supplier/executions/{execution_id}/model/download"
        )

    async def input_download_url(self, execution_id: str) -> dict[str, Any]:
        return await self._request(
            "GET", f"/supplier/executions/{execution_id}/input/download"
        )

    async def presign_result_upload(
        self, execution_id: str, filename: str, size: int
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/supplier/uploads/result/presign?execution_id={execution_id}",
            json={"filename": filename, "size": size},
        )

    async def upload_file(self, upload_url: str, file_path: str | Path) -> None:
        with open(file_path, "rb") as fh:
            resp = await self._client.put(
                upload_url, content=fh.read(), headers={"Content-Type": "application/octet-stream"}
            )
        resp.raise_for_status()

    async def download_file(self, download_url: str, dest_path: str | Path) -> None:
        async with self._client.stream("GET", download_url) as resp:
            resp.raise_for_status()
            with open(dest_path, "wb") as fh:
                async for chunk in resp.aiter_bytes():
                    fh.write(chunk)