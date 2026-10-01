# settings.py
# All configuration for the Revit MCP server.
# Values are read from environment variables with safe defaults.

import ipaddress
import math
import os
from urllib.parse import urlsplit


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        raise RuntimeError(f"{name} must be an integer.") from None


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        raise RuntimeError(f"{name} must be a number.") from None


def _loopback_url(name: str, value: str) -> str:
    """Validate an HTTP URL that must stay on this workstation."""
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except (TypeError, ValueError):
        raise RuntimeError(
            f"{name} must be a valid loopback HTTP URL."
        ) from None

    hostname = parsed.hostname
    is_loopback = False
    if hostname and hostname.lower() == "localhost":
        is_loopback = True
    elif hostname:
        try:
            is_loopback = ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            is_loopback = False

    if (
        parsed.scheme not in {"http", "https"}
        or not is_loopback
        or port is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeError(
            f"Refusing non-local or malformed {name}. "
            "This unauthenticated foundation supports explicit loopback URLs only."
        )
    return value.rstrip("/")


# ---------------------------------------------------------------------------
# pyRevit Routes connection
# ---------------------------------------------------------------------------

# Base URL of the pyRevit Routes server running inside Revit.
# Must end with the route namespace prefix (/placeholder), no trailing slash.
REVIT_ROUTES_BASE_URL: str = _loopback_url(
    "REVIT_ROUTES_BASE_URL",
    os.environ.get(
        "REVIT_ROUTES_BASE_URL",
        "http://127.0.0.1:48884/placeholder",
    ),
)

# Timeout in seconds for requests to pyRevit Routes.
REVIT_ROUTES_TIMEOUT: float = _env_float("REVIT_ROUTES_TIMEOUT", 10.0)
if (
    not math.isfinite(REVIT_ROUTES_TIMEOUT)
    or REVIT_ROUTES_TIMEOUT <= 0
    or REVIT_ROUTES_TIMEOUT > 120
):
    raise RuntimeError(
        "REVIT_ROUTES_TIMEOUT must be greater than zero and at most 120 seconds."
    )

# ---------------------------------------------------------------------------
# MCP server binding
# ---------------------------------------------------------------------------

MCP_HOST: str = os.environ.get("MCP_HOST", "127.0.0.1")
MCP_PORT: int = _env_int("MCP_PORT", 3001)
MCP_STREAMABLE_HTTP_PATH: str = os.environ.get("MCP_STREAMABLE_HTTP_PATH", "/mcp")
MCP_JSON_RESPONSE: bool = _env_bool("MCP_JSON_RESPONSE")
MCP_STATELESS_HTTP: bool = _env_bool("MCP_STATELESS_HTTP")

_LOCAL_BIND_HOSTS = {"127.0.0.1", "localhost", "::1"}
if MCP_HOST not in _LOCAL_BIND_HOSTS:
    raise RuntimeError(
        "Refusing to bind MCP server to non-local host "
        f"{MCP_HOST!r}. This unauthenticated foundation supports loopback only."
    )

# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------

ENABLE_WRITE_TOOLS: bool = _env_bool("ENABLE_WRITE_TOOLS")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO").upper()
