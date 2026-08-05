from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


SERVER_DIR = Path(__file__).resolve().parents[1]
MCP_ENV_NAMES = {
    "ENABLE_WRITE_TOOLS",
    "LOG_LEVEL",
    "MCP_HOST",
    "MCP_JSON_RESPONSE",
    "MCP_PORT",
    "MCP_STATELESS_HTTP",
    "MCP_STREAMABLE_HTTP_PATH",
    "REVIT_ROUTES_BASE_URL",
    "REVIT_ROUTES_TIMEOUT",
}


def _clean_env() -> dict[str, str]:
    env = os.environ.copy()
    for name in MCP_ENV_NAMES:
        env.pop(name, None)
    return env


def _run_settings(code: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=SERVER_DIR,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_settings_default_to_localhost() -> None:
    result = _run_settings(
        "import json, settings; print(json.dumps([settings.MCP_HOST, settings.MCP_PORT]))",
        _clean_env(),
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == ["127.0.0.1", 3001]


def test_settings_refuse_nonlocal_revit_routes_url() -> None:
    env = _clean_env()
    env["REVIT_ROUTES_BASE_URL"] = "http://192.168.1.20:48884/placeholder"

    result = _run_settings("import settings", env)

    assert result.returncode != 0
    assert "explicit loopback URLs only" in result.stderr


def test_settings_accept_ipv6_loopback_revit_routes_url() -> None:
    env = _clean_env()
    env["REVIT_ROUTES_BASE_URL"] = "http://[::1]:48884/placeholder/"

    result = _run_settings(
        "import settings; print(settings.REVIT_ROUTES_BASE_URL)", env
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "http://[::1]:48884/placeholder"


def test_settings_reject_routes_url_with_credentials_or_query() -> None:
    for url in (
        "http://user:secret@127.0.0.1:48884/placeholder",
        "http://127.0.0.1:48884/placeholder?token=secret",
        "http://127.0.0.1/placeholder",
        "http://127.0.0.1:secret-port/placeholder",
    ):
        env = _clean_env()
        env["REVIT_ROUTES_BASE_URL"] = url

        result = _run_settings("import settings", env)

        assert result.returncode != 0, url
        assert "user:secret" not in result.stderr
        assert "token=secret" not in result.stderr
        assert "secret-port" not in result.stderr


def test_settings_require_a_finite_bounded_routes_timeout() -> None:
    for timeout in ("0", "-1", "nan", "inf", "120.1"):
        env = _clean_env()
        env["REVIT_ROUTES_TIMEOUT"] = timeout

        result = _run_settings("import settings", env)

        assert result.returncode != 0, timeout
        assert "at most 120 seconds" in result.stderr

    for timeout in ("0.01", "120"):
        env = _clean_env()
        env["REVIT_ROUTES_TIMEOUT"] = timeout

        result = _run_settings(
            "import settings; print(settings.REVIT_ROUTES_TIMEOUT)", env
        )

        assert result.returncode == 0, result.stderr

    env = _clean_env()
    env["REVIT_ROUTES_TIMEOUT"] = "secret-timeout-value"
    result = _run_settings("import settings", env)
    assert result.returncode != 0
    assert "secret-timeout-value" not in result.stderr


def test_settings_refuse_nonlocal_binding_without_explicit_override() -> None:
    env = _clean_env()
    env["MCP_HOST"] = "0.0.0.0"

    result = _run_settings("import settings", env)

    assert result.returncode != 0
    assert "Refusing to bind MCP server to non-local host" in result.stderr


def test_settings_ignore_legacy_nonlocal_override() -> None:
    env = _clean_env()
    env.update(MCP_HOST="0.0.0.0", ALLOW_NONLOCAL_BIND="true")

    result = _run_settings("import settings", env)

    assert result.returncode != 0
    assert "supports loopback only" in result.stderr
