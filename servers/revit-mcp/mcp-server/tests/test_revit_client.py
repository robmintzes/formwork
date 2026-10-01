from __future__ import annotations

from typing import Any

import pytest

import revit_client


@pytest.mark.asyncio
async def test_http_client_ignores_proxy_environment_and_refuses_redirects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    class Response:
        def raise_for_status(self) -> None:
            return None

        async def aiter_bytes(self):
            payload = {
                "status": "ok",
                "tool": "revit_health_ping",
                "risk_class": "read_only",
                "document": {
                    "title": None,
                    "path": None,
                    "is_workshared": False,
                },
                "data": {},
                "messages": [],
                "next_actions": [],
                "error": None,
            }
            yield revit_client.json.dumps(payload).encode("utf-8")

    class Client:
        def __init__(self, **kwargs: Any) -> None:
            observed.update(kwargs)

        async def __aenter__(self) -> "Client":
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

        def stream(self, method: str, url: str) -> Response:
            observed["method"] = method
            observed["url"] = url
            return Response()

    async def response_enter(self: Response) -> Response:
        return self

    async def response_exit(self: Response, *args: Any) -> None:
        return None

    monkeypatch.setattr(Response, "__aenter__", response_enter, raising=False)
    monkeypatch.setattr(Response, "__aexit__", response_exit, raising=False)

    monkeypatch.setattr(revit_client.httpx, "AsyncClient", Client)

    result = await revit_client.RevitClient(
        "http://127.0.0.1:48884/example", timeout=3.0
    ).get("/health/")

    assert result.tool == "revit_health_ping"
    assert observed == {
        "timeout": 3.0,
        "trust_env": False,
        "follow_redirects": False,
        "method": "GET",
        "url": "http://127.0.0.1:48884/example/health/",
    }


@pytest.mark.asyncio
async def test_http_client_rejects_response_over_byte_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Response:
        async def __aenter__(self) -> "Response":
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

        def raise_for_status(self) -> None:
            return None

        async def aiter_bytes(self):
            yield b"x" * (revit_client.MAX_RESPONSE_BYTES + 1)

    class Client:
        def __init__(self, **kwargs: Any) -> None:
            return None

        async def __aenter__(self) -> "Client":
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

        def stream(self, method: str, url: str) -> Response:
            return Response()

    monkeypatch.setattr(revit_client.httpx, "AsyncClient", Client)

    with pytest.raises(revit_client.RevitClientError) as error:
        await revit_client.RevitClient(
            "http://127.0.0.1:48884/example", timeout=3.0
        ).get("/health/")

    assert error.value.code == "revit_response_too_large"
