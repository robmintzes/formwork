# ADR 0009 - Engine distribution to adopters

Status: **accepted** (Rob, 2026-10-01). Closes backlog B16.

## Context

A firm adopting Formwork needs the engine to run `init`, `render`, and
`validate` against its generated workspace. The workspace never contains the
engine (ADR 0002). There are three ways to get it to the firm:

| Option | Upgrade path | Cost |
| --- | --- | --- |
| **Pinned checkout** of `robmintzes/formwork` at a known commit (a release tag once tags exist) | `git fetch`, check out the newer commit, render with `--dry-run` | Nothing to build. The adopter needs Git and must record which commit they run. |
| **pip install** of a published `formwork-dt` package | `pip install -U formwork-dt` | Packaging, release tagging, and a PyPI project to maintain. Publishing is irreversible: a released name and version cannot be taken back. |
| **Vendored** copy of the engine inside the firm's workspace | Copy the new engine over and resolve the differences by hand | Every upgrade becomes a manual merge. It also contradicts the generated-workspace model, where the foundation owns the engine and the firm owns `firm/`. |

## Decision

- **Now:** a pinned checkout is the only supported route.
  [ADOPTING.md](../onboarding/ADOPTING.md) documents it. No release tags exist
  yet, so adopters pin a commit; tagging starts with the first release.
- **After the live Revit gate (B11) passes:** publish to PyPI as `formwork-dt`.
  The import names stay `formwork_engine`, `formwork_cli`, and
  `formwork_wizard`. The package exposes a `formwork` console script.
- **Vendoring is rejected.**

## Why this order

- The engine has never been run against a real Revit session. Publishing first
  would stamp a version number on unverified host code, and PyPI versions
  cannot be withdrawn cleanly.
- The B21 rename lands before any release (ADR 0010). The first published
  package then has its final names, and no adopter ever imports `toolkit_*`.
- Until there are outside adopters, a checkout costs nothing extra.

## Consequences

- There is no `pyproject.toml` for the engine yet. Adding one is part of the
  publishing work, tracked as backlog B22.
- Adopters run `python -m formwork_cli` from the checkout. The bare `formwork`
  command arrives with the package.
- Publishing to PyPI is outward-facing. It needs Rob's explicit go-ahead at the
  time, even though this record approves the plan.
