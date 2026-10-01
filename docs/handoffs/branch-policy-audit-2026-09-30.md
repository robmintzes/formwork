# Handoff - branch policy and repository assessment

## State

- Audit baseline: `main` / `207655f`; clean checkout; remote stabilization
  draft PR #2 at `573c382` remains unmerged.
- Work branch: `robmintzes/branch-policy-audit`.
- Added canonical branch policy, executable local guards, hook installer,
  regression tests, and independent required CI workflow.
- Local hooks installed for `robmintzes` in this clone.
- GitHub ruleset 24278014 is active for `main` and future `stable`; no bypass
  actors; PRs, two CI checks, current base, resolved conversations required;
  deletion and force pushes blocked; independent approval count zero.
- [Repository assessment](../reviews/repository-state-2026-09-30.md) records
  findings and fresh verification: 9 policy tests, 74 stabilization root tests,
  11 extension tests, 18 MCP tests, and static validators passed.

## Open

- Human review and merge of the policy PR first; no merge is authorized by this
  audit. Older PRs must inherit the new required workflow before merging.
- Reconcile shared README, onboarding, and AGENTS edits when updating PR #2.
- Refresh PR #2's stale description, review subsystems, and complete its live
  Revit verification matrix.
- Each new clone must install hooks; an adopting repository must apply its own
  GitHub ruleset. Update the existing ruleset by ID instead of duplicating it.

## Incremental Edit Log

- **2026-09-30**: Identified unenforced branch instructions and unmerged August
  stabilization work. Added and tested local/CI guards, enabled and verified
  server enforcement, removed direct-main exceptions, and recorded the audit.
