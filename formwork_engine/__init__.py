"""Firm-neutral workspace generation engine.

The engine turns a validated firm configuration (``firm/``) into a generated
workspace. It has no command-line presentation; ``formwork_cli`` and future
clients (wizard, agents) call these functions. Standard library only.
"""

from __future__ import annotations

__version__ = "0.3.0-alpha.1"

CONFIG_SCHEMA_VERSION = 1
MANIFEST_SCHEMA_VERSION = 1
WORKSPACE_SCHEMA_VERSION = 1
