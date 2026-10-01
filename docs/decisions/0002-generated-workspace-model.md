# ADR 0002 - Generated workspace, not in-place fork

Status: **accepted** (Rob, 2026-09-30).

## Context

Rob described firms that "fork and convert" the repository. Codex proposed a
generator that writes a separate firm workspace. These differ: an in-place fork
mixes foundation source, generated files, and firm code in one tree, and every
upstream merge collides with generated output. GitHub template repositories do
not keep fork history, so "fork" mostly means "start from a copy" anyway.

## Decision

A firm's repository is a generated workspace: `firm/` inputs, managed generated
files, seeded files, firm-owned code, and `.toolkit/manifest.json` pinned to a
foundation version. The foundation is a tool the firm runs; generation never
mutates the foundation checkout. Upgrades bump the foundation version and
re-render with conflict reporting.

## Consequences

- The experience can still be "click Use this template": a template repository
  holding an initialized workspace is a later distribution channel.
- The existing `scripts/bootstrap.*` in-place replacement scripts are
  transitional and will be retired once `init`/`render` cover the sample.
- Distribution of the engine to adopters (pip package, pinned checkout, or
  vendored copy) is an open packaging question tracked in the backlog.
