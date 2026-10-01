# revit_client.py
# HTTP client that talks to pyRevit Routes running inside Revit.

from __future__ import annotations

import logging
import json
from typing import Any

import httpx

import settings
from schemas import RevitResponse

logger = logging.getLogger(__name__)
MAX_RESPONSE_BYTES = 1024 * 1024

_UNREACHABLE_CHECKS = [
    "Confirm Revit is open.",
    "Confirm pyRevit is loaded (look for the pyRevit ribbon tab).",
    "Confirm the toolbar extension is installed and listed in pyRevit extensions.",
    f"Confirm pyRevit Routes is listening on {settings.REVIT_ROUTES_BASE_URL}.",
]


class RevitClientError(Exception):
    """Raised when the client cannot reach pyRevit Routes or parses a bad response."""

    def __init__(self, code: str, message: str, checks: list[str] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.checks = checks or _UNREACHABLE_CHECKS


class RevitClient:
    """Thin HTTP client for pyRevit Routes."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self._base_url = (base_url or settings.REVIT_ROUTES_BASE_URL).rstrip("/")
        self._timeout = timeout or settings.REVIT_ROUTES_TIMEOUT

    async def get(self, path: str) -> RevitResponse:
        """Make a GET request to pyRevit Routes and return a parsed RevitResponse."""
        url = self._base_url + "/" + path.lstrip("/")
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                trust_env=False,
                follow_redirects=False,
            ) as client:
                async with client.stream("GET", url) as resp:
                    resp.raise_for_status()
                    body = bytearray()
                    async for chunk in resp.aiter_bytes():
                        if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                            raise RevitClientError(
                                "revit_response_too_large",
                                "pyRevit Routes returned more than the allowed response size.",
                                ["Reduce the endpoint response before retrying."],
                            )
                        body.extend(chunk)
                payload = json.loads(body.decode("utf-8"))
                del body
                return RevitResponse.model_validate(payload)
        except RevitClientError:
            raise
        except httpx.ConnectError:
            raise RevitClientError(
                "revit_unreachable",
                (
                    f"Cannot connect to pyRevit Routes at {url}. "
                    "Is Revit open with the extension loaded?"
                ),
                _UNREACHABLE_CHECKS,
            )
        except httpx.TimeoutException:
            raise RevitClientError(
                "revit_timeout",
                f"Request to pyRevit Routes timed out after {self._timeout}s ({url}).",
                _UNREACHABLE_CHECKS,
            )
        except httpx.HTTPStatusError as exc:
            raise RevitClientError(
                "revit_http_error",
                f"pyRevit Routes returned HTTP {exc.response.status_code} for {url}.",
                ["Check the pyRevit Routes log for the endpoint failure."],
            )
        except Exception as exc:
            raise RevitClientError(
                "revit_client_error",
                f"Unexpected error calling pyRevit Routes ({url}): {exc}",
                _UNREACHABLE_CHECKS,
            )


def build_error_result(tool: str, exc: RevitClientError) -> dict[str, Any]:
    """Build a normalised MCP tool result dict from a RevitClientError."""
    return {
        "status": "error",
        "tool": tool,
        "risk_class": "read_only",
        "document": {"title": None, "path": None, "is_workshared": False},
        "data": {},
        "messages": [],
        "next_actions": [],
        "error": {
            "code": exc.code,
            "message": exc.message,
            "checks": exc.checks,
        },
    }
