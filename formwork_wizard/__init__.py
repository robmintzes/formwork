"""Local onboarding wizard: a loopback HTTP service over formwork_engine (ADR 0006).

The wizard edits an in-memory *draft* of a firm configuration, validates and
previews it with the same engine the CLI uses, and saves it only into a
workspace's ``firm/`` inputs followed by a normal render. Standard library only.
"""

from __future__ import annotations
