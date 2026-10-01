# Repository assessment - September 30, 2026

## Verdict

The project has a sensible architecture and a useful development foundation.
Its maturity is **alpha**. The June scaffold on `main` overstates readiness;
substantial August stabilization work is still in draft PR #2. Finishing that
work and recording live Revit evidence should precede expansion into more
tools, a setup GUI, or firm-wide deployment.

## What actually exists

At the start of this audit, the checkout was clean on `main`, synchronized with
`origin/main` at `207655f`. The last merge was June 19, 2026. GitHub had no
branch protection or rulesets, despite onboarding documentation saying the
production branch was protected. There were no published releases or open
issues, and the repository was not marked as a GitHub template.

The additional remote branch `robmintzes/runtime-stabilization` was at
`573c382`, six commits ahead, with 81 changed files and approximately 8,400
insertions. [Draft PR #2](https://github.com/robmintzes/pyrevit-toolbar-template/pull/2)
is mergeable. Its latest [GitHub CI run](https://github.com/robmintzes/pyrevit-toolbar-template/actions/runs/30972128549)
passed Python 3.10, Python 3.11, and Windows smoke jobs on August 4, 2026
(America/New_York). Its PR description's test counts and Windows limitations
predate later commits; the actual workflow and verification documents are more
current.

## Strengths

- Repository governance, specs, docs, and validators are separate from the
  deployable extension. That boundary is worth preserving.
- Vendor-neutral instructions and thin agent adapters avoid tying the project
  to one coding assistant.
- The toolbar registry, design guidance, and narrow localhost MCP adapter give
  future development a coherent structure.
- PR #2 substantially strengthens validators, runtime helpers, MCP contracts,
  generated-checkout testing, and Windows script coverage. It also implements
  portable diagnostics and an evidence-producing live verification harness.
- Its configuration-first generator roadmap is the right order: stabilize the
  schema and repeatable CLI before building an optional GUI.

## Problems and priority

| Priority | Finding | Practical consequence / next action |
| --- | --- | --- |
| High | `main`'s Hello Button appends `[Audited]` to a selected view name, while the spec describes a greeting and view list. | A sample button unexpectedly writes to a model. PR #2 replaces it with a read-only reference tool. |
| High | The sample on `main` uses Python 3 annotations and `from __future__ import annotations`; the repository does not establish which embedded engine can execute it. | Static CPython checks do not establish pyRevit runtime compatibility. PR #2 adds compatibility helpers and tests; live engine verification remains required. |
| High | No recorded live Revit/pyRevit combination has passed verification, including on PR #2. | Ribbon loading, document contexts, Routes lifecycle, and end-to-end MCP behavior remain unproven in the host. Complete the verification matrix before claiming a supported deployment. |
| Medium | `main` has three lightweight validators and no regression test suite. Its transaction check searches for strings anywhere in a file. | Passing validation cannot prove safe transaction control flow, correct APIs, or truthful tool behavior. PR #2 improves structural coverage; runtime review remains necessary. |
| Medium | Original Python and PowerShell bootstrappers update different surfaces and mutate a checkout once through replacements. | Rebranding can drift or leave partial changes. PR #2 brings the implementations into parity but still treats them as transitional; prioritize an idempotent generator next. |
| Medium | `main` documentation includes machine-specific `file:///Users/bert/...` links, unsupported deployment claims, and uncited future-version API assumptions. | Onboarding and agent memory can mislead. PR #2 repairs much of this; reconcile the documentation when the branches merge. |
| Medium | PR #2 combines runtime repair, validators, CLI, diagnostics, and verification infrastructure in a large change. | Review it by subsystem and refresh its description; do not infer readiness from its green badge alone. |

## Verification performed during this audit

- Original `main`: all three static validators passed, despite the sample/spec
  mismatch above. This illustrates their limited scope.
- Exact PR #2 snapshot, tested on Windows with CPython 3.11: **74 repository
  tests**, **11 extension helper tests**, and all three validators passed.
- PR #2's external MCP tests: **18 passed** in an isolated environment using MCP
  SDK **2.2.0**; `pip check` found no broken requirements. The snapshot initially
  lacked Git metadata, causing the build-identity assertion to fail; restoring
  the exact commit metadata made the complete suite pass. These tests use
  synthetic Routes responses and do not constitute live Revit evidence.
- Branch policy changes: **9 tests** passed, including actual commit/push
  rejection in disposable Git repositories with paths containing spaces.
- No Revit model was opened or modified as part of this audit.

## Governance changes

The [branch policy](../onboarding/BRANCH_POLICY.md) now specifies human-owned
task branches, preflight checks, clone-local commit/push hooks, PRs for every
change, and stable required CI check names. Conflicting owner examples and the
direct-to-main documentation exception were removed.

GitHub [ruleset 24278014](https://github.com/robmintzes/pyrevit-toolbar-template/rules/24278014)
is active for `main` and a future `stable` branch. Readback confirmed required
PRs, current-base checks, resolved review conversations, blocked force pushes
and deletion, and no bypass actors. Required independent approvals remain zero
for the current single-maintainer repository. Hooks are installed in the local
clone; other clones must install them separately. This matches GitHub's
[documented ruleset model](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets).

The policy code and documentation are on `robmintzes/branch-policy-audit`.
They need to merge first so existing PRs can inherit the required workflow;
this audit does not merge either branch.

## Recommended sequence

1. Review and merge the branch-policy PR, then update PR #2 with `main`.
   Preserve the new policy while reconciling its README/onboarding edits.
2. Review PR #2 by subsystem and refresh its stale PR description. Decide
   deliberately whether its documented alpha boundary is acceptable for merge.
3. Record live Windows/Revit/pyRevit evidence, using its verification runner and
   required Routes-reset procedure, for each declared supported combination.
4. Build the configuration schema and repeatable generator. Keep the GUI and
   broad distribution behind a proven onboarding path.
