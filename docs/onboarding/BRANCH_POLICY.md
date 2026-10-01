# Development branch policy

## Branches and ownership

`main` is the integration branch, not a promise of production readiness. No
`stable` branch currently exists; the same rules apply if it is created later.
Every contribution, including documentation, uses a task branch and pull
request. There is no direct-push typo exception.

Use `<human-owner>/<lowercase-task-slug>`, for example
`robmintzes/branch-policy-audit` or `jdoe/fix-selection`. Each component contains
lowercase letters, digits, and single internal hyphens. The prefix identifies
the accountable human, including when an agent authors the changes. AI vendor
prefixes are rejected. Naming is self-declared; it does not authenticate a
contributor or grant repository access.

## Start work

Install the tracked hooks once per clone with CPython 3.10+ available:

```powershell
.\scripts\install-git-hooks.ps1 -Owner robmintzes
```

The installer sets clone-local `branchPolicy.owner` and
`core.hooksPath=.githooks`. It refuses to overwrite another hooks configuration.
For another human, supply their prefix. On macOS/Linux, configure the same
settings using `git config --local branchPolicy.owner <human-prefix>` and
`git config --local core.hooksPath .githooks`.

Before changing files, inspect the working tree and existing branch. Preserve
uncommitted work; never reset or move someone else's changes to satisfy policy.
For a new task from a clean checkout:

```powershell
git status --short --branch
git fetch origin
git switch -c robmintzes/task-name origin/main
py -3.11 validators/check_branch_policy.py
```

Continue an existing task on its branch when appropriate. Use a different base
only for an explicit dependency and identify it in the PR. Never start code
development on `main`, `stable`, detached HEAD, or another owner's branch.

## Local and GitHub enforcement

- Pre-commit rejects protected branches, detached HEAD, missing owner
  configuration, invalid names, and a prefix that differs from the local owner.
- Pre-push validates both source and destination branch names. Pushing an owned
  branch to `main` or `stable`, including deletion, is blocked. Deleting an owned
  task branch is allowed. No release-tag naming rules are imposed; a tag push
  still requires a valid owned checkout.
- Local hooks are an accident guard and can be bypassed or absent in another
  client. GitHub rules provide the merge boundary.
- The checked-in [ruleset](../../.github/main-branch-ruleset.json) requires PRs
  into `main`/`stable`, resolved review conversations, and successful
  `branch-policy` and `repository-validation` checks against the current base.
  It allows no bypass actors, including admins, and blocks branch deletion and
  force pushes. Checks are bound to the GitHub Actions app.
- [Development Policy](../../.github/workflows/development-policy.yml) validates
  branch names, tests the actual hooks, runs static validators and repository
  tests, and runs extension/MCP regression suites when those suites exist.
  Its stable check names survive the original CI job's transition to a matrix
  in the stabilization PR. Existing CI remains additional coverage.

For the current single-owner workflow, required approving reviews are **zero**;
the PR and CI requirements still apply. A second maintainer should trigger a
deliberate move to at least one independent approval. Agents must not merge,
change approval requirements, or release merely because checks are green.

## Activation and maintenance

Committing a JSON file does not activate server rules. The maintainer applies
the ruleset through GitHub settings or the authenticated CLI:

```powershell
gh api --method POST repos/robmintzes/formwork/rulesets --input .github/main-branch-ruleset.json
gh api repos/robmintzes/formwork/rulesets
```

After initial creation, update the existing ruleset by its returned ID with
`PUT .../rulesets/<id>`; do not create duplicates. Verify the stored conditions,
checks, and bypass actors after changes. Adopting repositories must apply this
configuration to their own GitHub repository separately.

The policy PR must merge before other existing PRs: its workflow runs on that
PR, but older PRs cannot satisfy the new required checks until updated with the
policy files. Then update those branches from `main` and rerun their full CI.
Keep required check names and the workflow synchronized to avoid an impossible
merge gate. No automated merge is part of this setup.
