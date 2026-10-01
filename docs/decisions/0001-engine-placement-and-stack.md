# ADR 0001 - Engine placement and stack

Status: branch base **accepted** (Rob, 2026-09-30); stack **proposed**.

## Context

PR #2 (`robmintzes/runtime-stabilization`) already contains `toolkit_cli`
(stdlib argparse, `CheckResult`, 0/1/2 exit codes, injectable dependencies), a
read-only sample, and the roadmap naming `init`/`render`/`validate`. The
planning branch did not contain any of it.

## Decision

- Implementation branch `robmintzes/foundation-generator` = planning branch +
  a merge of `origin/robmintzes/runtime-stabilization`. Its PR is stacked on
  PR #3 and PR #2 until Rob merges those.
- Generation logic lives in a separate package, `toolkit_engine/`, with no
  CLI or I/O presentation. `toolkit_cli` adds thin commands over it. The future
  wizard service imports the engine directly; it does not shell out.
- CPython 3.10+, standard library only, matching `toolkit_cli`. JSON Schema
  validation of fixtures uses no third-party validator at runtime.

## Consequences

- The generator PR diff includes PR #2 and #3 until they merge; reviewers should
  read it as stacked.
- No dependency installation is needed to generate a workspace.
- Hand-written validation is more code than a schema library but gives coded,
  actionable diagnostics and no runtime dependency.

Rejected: building beside PR #2 (duplicates the CLI and sample); waiting for
merges before writing code (stalls on review).
