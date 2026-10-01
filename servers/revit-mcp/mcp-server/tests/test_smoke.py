from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


SERVER_DIR = Path(__file__).resolve().parents[1]


def test_server_modules_import_under_mcp_v2() -> None:
    env = os.environ.copy()
    env["MCP_HOST"] = "127.0.0.1"
    code = (
        "from mcp.server import MCPServer; "
        "import app, main; "
        "assert isinstance(app.mcp, MCPServer)"
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=SERVER_DIR,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
