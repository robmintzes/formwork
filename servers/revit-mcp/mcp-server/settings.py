# settings.py
# All configuration for the Revit MCP server.
# Values are read from environment variables with safe defaults.

import os


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
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer, got {raw!r}.") from exc


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a number, got {raw!r}.") from exc


# ---------------------------------------------------------------------------
# pyRevit Routes connection
# ---------------------------------------------------------------------------

# Base URL of the pyRevit Routes server running inside Revit.
# Must end with the route namespace prefix (/placeholder), no trailing slash.
REVIT_ROUTES_BASE_URL: str = os.environ.get(
    "REVIT_ROUTES_BASE_URL",
    "http://127.0.0.1:48884/placeholder",
)

# Timeout in seconds for requests to pyRevit Routes.
REVIT_ROUTES_TIMEOUT: float = _env_float("REVIT_ROUTES_TIMEOUT", 10.0)

# ---------------------------------------------------------------------------
# MCP server binding
# ---------------------------------------------------------------------------

MCP_HOST: str = os.environ.get("MCP_HOST", "127.0.0.1")
MCP_PORT: int = _env_int("MCP_PORT", 3001)
MCP_STREAMABLE_HTTP_PATH: str = os.environ.get("MCP_STREAMABLE_HTTP_PATH", "/mcp")
MCP_JSON_RESPONSE: bool = _env_bool("MCP_JSON_RESPONSE")
MCP_STATELESS_HTTP: bool = _env_bool("MCP_STATELESS_HTTP")
ALLOW_NONLOCAL_BIND: bool = _env_bool("ALLOW_NONLOCAL_BIND")

_LOCAL_BIND_HOSTS = {"127.0.0.1", "localhost", "::1"}
if MCP_HOST not in _LOCAL_BIND_HOSTS and not ALLOW_NONLOCAL_BIND:
    raise RuntimeError(
        "Refusing to bind MCP server to non-local host "
        f"{MCP_HOST!r}. Use 127.0.0.1 for local read-only phases, or set "
        "ALLOW_NONLOCAL_BIND=true only after adding auth and origin policy."
    )

# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------

ENABLE_WRITE_TOOLS: bool = _env_bool("ENABLE_WRITE_TOOLS")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO").upper()
