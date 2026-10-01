# Adopting the foundation

For a design technology lead who wants a branded pyRevit toolbar, WPF UI kit,
guides, governance, and a read-only MCP bridge for their own firm. Any firm
size; one person is enough.

This foundation is **alpha**. Everything it generates passes automated and
static checks. **Nothing has been verified live in Revit or pyRevit yet.** You
will be the first to run it there, and the [live check](#9-install-into-pyrevit-and-run-the-live-check)
exists to turn that into recorded evidence.

Contributing to the foundation itself? Start at the [developer
onboarding guide](README.md) instead.

---

## 1. What you get

You never edit this repository to rebrand it. You generate a separate
**workspace** from a firm configuration (`firm/`), and regenerate it whenever
that configuration changes. Surfaces are chosen per firm in `surfaces` in
`firm.json`.

| Surface | What it produces in your workspace | Status |
| --- | --- | --- |
| `pyrevit-sample` | pyRevit extension, one read-only Hello Button, light/dark icons, a toolbar-spec fragment, a tool guide | Generated and tested (static validators, IronPython 2.7 syntax guard). Not live-verified. |
| `wpf-specimen` | `Theme.xaml`, `Controls.xaml`, `Specimen.xaml`, a PowerShell runner, bundled fonts | Generated and tested. Native WPF render captured in a harness, not inside Revit. |
| `html-guide` | Self-contained offline Hello Button guide with your brand header | Generated and tested. Browser render inspected; offline check automated. |
| `governance` | `AGENTS.md`, thin agent pointers, branch policy, git hooks, CI workflow, GitHub ruleset JSON, pyRevit playbook | Generated and tested. Hooks exercised in a temporary repository. The ruleset protects nothing until you apply it. |
| `mcp-bridge` | Read-only pyRevit Routes bridge, external FastMCP server, setup scripts, guide | Generated and tested (contract and runtime tests, no Revit). Not live-verified. |
| `ui-kit` | Themed WPF dialogs (chooser, selector, result), controls, icons, a `UI Kit Demo` button | Generated and tested. Native renders recorded in a harness. Not live-verified. |
| `web-host` | `lib/<namespace>_web`: an HTML tool host for pyRevit (WebView2 in a WPF window, locked to two local virtual hosts), bridge, session helpers, themed assets and fonts, a read-only `Web Tool Demo` report console | Generated and tested (pure modules run under CPython, page checked in a browser with a stub bridge). The WebView2 assemblies come from your Revit installation, none are shipped. Not live-verified: no WebView2 window has been opened in Revit. |
| `revit-addin` | C# add-in project (Revit 2025-2027): ribbon button, read-only command with a themed window, manifest with a stable `AddInId`, README | Builds offline with the .NET SDK against the installed Revit API (tested). Never loaded in Revit. Revit 2024 is not covered. |
| `python-app` | `apps/<namespace>-report`: a stdlib-only Python CLI that turns a CSV or JSON table into a branded offline HTML report, with tests and a sample | Generated and tested: its unittest suite and CLI run in the foundation's tests. Needs no Revit. |
| `web-app` | `apps/<namespace>-web`: a dependency-free TypeScript web starter (loopback-only static server, branded app shell, `node --test` suite, brand fonts) | Generated and tested with `node --test` (when Node is installed). Types are not checked. Needs no Revit. |

`mcp-bridge`, `ui-kit` and `web-host` require `pyrevit-sample`; `python-app` and `web-app` stand alone. Supported host combination
for the first live run: Revit 2026, pyRevit 6.5.5 (IronPython 2.7.12), Windows
11. No combination is recorded as passing in the [verification
matrix](../verification/MATRIX.md).

Default and example profiles live in `profiles/`:

- `bimxbert`, the default. The BIMxBert name and marks are **not** MIT-licensed;
  replace them before you publish anything under your own name.
- `quillmoor`, a fictional firm. Safe to copy and rename.

---

## 2. Prerequisites

- Windows 10 or 11 for the toolbar and live checks. Generation itself runs on
  any OS.
- CPython 3.10 or newer. The CLI, generator, and wizard use the standard
  library only; no `pip install` is needed to generate a workspace.
- Git.
- pyRevit, only to load the generated toolbar in Revit.
- Python packages from `servers/revit-mcp/mcp-server/requirements.txt`, only if
  you run the MCP server (the generated workspace has its own setup script).
- .NET 10 SDK (or 8 for un-updated Revit 2025/2026 hosts): only for the
  `revit-addin` starter. Revit 2025.5 and 2026.5 and later run on .NET 10, like
  2027. The build reads the installed host and needs no NuGet packages.
- Node.js 22.18 or newer (24 is fine): only for the `web-app` starter. Node runs
  its TypeScript directly by stripping types, so there is no `npm install` and
  no build. Type-checking is optional and needs you to install `typescript`
  yourself. The `python-app` starter needs nothing beyond CPython 3.10+.
- No AI subscription. The wizard and CLI work without any agent; agents are
  optional clients of the same commands.

If `python` opens the Microsoft Store, use the launcher: `py -3.11 -m
toolkit_cli ...` (any installed 3.10+ works).

Get the foundation:

```powershell
git clone https://github.com/robmintzes/formwork.git "D:\Tools\foundation"
cd "D:\Tools\foundation"
```

All commands below run from that checkout. Your workspace lives in a **different**
folder: it must be new or empty, outside the checkout, and not a drive root or
your home folder. Paths with spaces work; quote them.

---

## 3. Path A: the wizard

```powershell
python -m toolkit_cli serve
```

This starts a local service on `127.0.0.1` (random free port, or `--port N`),
prints a link, and opens your browser. Use `--no-open` to print the link
without opening it.

- The link carries a per-launch token in its fragment. Without it the API
  refuses every request. It is held in memory and dies when you stop the
  wizard (Ctrl+C or **Shut down wizard**). Do not share the link.
- Nothing is written to disk until the last step.

Steps, in order:

1. **Start**: copy a starter profile (`bimxbert` or fictional `quillmoor`) into
   a draft, or open an existing workspace to edit its `firm/` inputs.
2. **Identity**: display name, short name, author, logo alt text, support link.
   Safe to change any time.
3. **Technical identity**: namespace, workspace id, pyRevit extension, tab, and
   sample panel; maintainers and branch prefixes. Choose carefully; see
   [section 6](#6-rebranding-later-versus-changing-technical-identity).
4. **Logos**: wordmark and symbol, light and inverse, each as SVG and PNG.
5. **Colour and type**: design tokens, with live contrast ratios.
6. **Components**: button and badge treatments, and which surfaces to generate.
7. **Preview**: the HTML guide with your draft applied. The WPF preview is a
   browser approximation; the native render only happens on Windows.
8. **Generate**: enter an absolute folder, **Plan** (read-only), review, then
   **Generate**. It refuses to apply a plan that has errors or conflicts.

The final screen lists the next commands: validate, register with pyRevit, run
the live check.

---

## 4. Path B: CLI only

Copy the fictional example somewhere that is yours. Keeping your profile outside
the foundation checkout avoids losing it when you update the foundation.

```powershell
Copy-Item -Recurse "D:\Tools\foundation\profiles\quillmoor" "D:\Firm Inputs\acme"
```

Edit in `D:\Firm Inputs\acme`:

- `firm.json`: `profile.id`, `identity.*`, `technical.*`, `maintainers`,
  `surfaces`. Remove `"fictional": true`. Unknown keys are errors, with a
  "did you mean" hint; keys starting `x-` are yours and are ignored.
  [`schemas/firm-config.v1.schema.json`](../../schemas/firm-config.v1.schema.json)
  gives editors completion.
- `tokens.tokens.json`: your colours, fonts, sizes. Every required role must
  exist; see [spec section 3](../product/FOUNDATION_SPEC.md#3-design-token-contract-firmtokenstokensjson).
- `assets/`: your four logo files as SVG and PNG, referenced from `firm.json`.
- Fonts: optional. Packaged fonts need a licence file; unpackaged families fall
  back to the token's fallback stack.

Then:

```powershell
cd "D:\Tools\foundation"
python -m toolkit_cli config validate --firm "D:\Firm Inputs\acme"
python -m toolkit_cli init --profile "D:\Firm Inputs\acme" --workspace "D:\Firm\acme-dt"
python -m toolkit_cli render --workspace "D:\Firm\acme-dt" --dry-run
python -m toolkit_cli render --workspace "D:\Firm\acme-dt"
python -m toolkit_cli validate --workspace "D:\Firm\acme-dt"
```

- `config validate` checks `firm.json`, tokens, assets, and fonts. Fix errors
  first; warnings do not block.
- `init` copies your inputs into the workspace's `firm/` folder and marks the
  folder as a workspace. It does not render.
- `render --dry-run` is strictly read-only and lists every create, update,
  delete, and conflict. `render` applies it.
- `validate` runs the bundle, spec, and safety validators and the firm's own
  `tests/` if it has any (`--skip-tests` to skip). A new workspace has none, so
  that line reads SKIP.

Every command takes `--format json` and `--output <file>` for a machine-readable
report. Exit codes: `0` success (including "nothing changed"), `1` blocked by
invalid configuration or conflicts, `2` could not run (usage, unsafe path,
I/O).

Once `init` has run, the workspace's `firm/` copy is the source of truth, not
your original folder. Edit `D:\Firm\acme-dt\firm\` from then on.

---

## 5. Ownership rules

| Class | Where | What the generator does |
| --- | --- | --- |
| Input | `firm/**` | Reads. Never writes after `init`. Yours to edit. |
| Managed | Extension manifest, sample bundle, themes, guides, fonts, notices, governance and bridge files, validators | Rewrites on every render. Hash-tracked in `.toolkit/manifest.json`. |
| Seed | `docs/toolbar/toolbar_spec.md`, `README.md`, `.gitattributes`, `docs/agents/FIRM_RULES.md`, `docs/handoffs/INDEX.md` | Written once if absent. Yours afterwards; never rewritten. A deleted seed is not recreated. |
| Firm-owned | Anything not in the manifest, for example your own pushbuttons | Never read for writing, moved, or deleted. |

**Do not edit managed files.** Change `firm/` and re-render instead. A managed
file that has been edited, or a file of yours sitting at a managed path, is a
**conflict** (`managed-modified`, `unmanaged-at-managed-path`, or
`retired-modified`). Any conflict blocks the whole render: nothing is written,
exit code 1, and the report lists each path.

Resolve each conflict one of four ways:

1. Revert your edit, then re-render.
2. Delete the file to accept regeneration, then re-render.
3. Move your customization to a firm-owned path (a seed file, or a new panel),
   then do 1 or 2.
4. To keep your version of a generated file deliberately, copy it to
   `firm/overrides/<same path>` (for example
   `firm/overrides/specimens/wpf/Theme.xaml`), then delete the edited original
   and re-render. The override wins on every render. When the generator's
   own version changes later, render warns `override.upstream-changed` so you
   can review it. Delete the override to return to generated content.

Re-running `render` with no changes is a no-op. Edit hashes ignore line-ending
differences, so Git `autocrlf` does not create false conflicts.

---

## 6. Rebranding later versus changing technical identity

**Rebrand (safe, routine).** Change `identity.*`, tokens, logos, or
`appearance`, then `render --dry-run` and `render`. Visible text and styling
update. Paths, identifiers, and persistence keys do not move. Notices cannot be
removed this way.

**Technical identity (a migration, not a rebrand).** `technical.namespace`,
`technical.pyrevit.extension`, `.tab`, and `.sample_panel` name folders,
CSS and XAML key prefixes, the Python UI package, and the MCP Routes URL
prefix. pyRevit derives command identity from folder paths.

- Changing them makes the old managed files obsolete. They are deleted only if
  unmodified; modified ones are conflicts. Empty folders are reported, not
  removed.
- Your own tools under the old tab are firm-owned and are **not** moved. You
  move them, and fix any imports of the old `<namespace>_ui` package.
- The Routes URL changes with the namespace, so update MCP clients.
- `technical.workspace_id` cannot change in place: render refuses a workspace
  initialized for another id (`workspace.id-mismatch`).
- There is no `config migrate` yet (backlog B13). Always `render --dry-run` and
  read the plan before applying.

Decide technical identity at the start. It is cheap now and awkward later.

---

## 7. Adding your own tools

1. Register the tool in `docs/toolbar/toolbar_spec.md` **first**. That file is
   the single source of truth for the ribbon; the seeded copy has a commented
   example. Do not create the bundle folder before the entry exists.
2. Create your own panel inside the generated tab, for example
   `extensions\<Extension>.extension\<Tab>.tab\Studio.panel\`. Do not put tools
   in the generated sample panel or edit `docs/toolbar/spec.d/`; those are
   managed.
3. Add `docs/toolbar/tools/<tool-id>.md` for each tool. See the [documentation
   guide](DOCUMENTATION_GUIDE.md) for the pattern (the generated workspace
   carries the same rule in its `AGENTS.md`).
4. Run `python -m toolkit_cli validate --workspace "D:\Firm\acme-dt"`.

Follow the Revit safety rules in the workspace `AGENTS.md`: check context
before dialogs, never hold a transaction open while a dialog is showing, and
treat linked documents as read-only. Generated pyRevit Python must stay
IronPython 2.7 compatible.

Firm-specific conventions go in `docs/agents/FIRM_RULES.md` (a seed, so it is
yours).

---

## 8. Put the workspace in Git and GitHub

The workspace is an ordinary folder until you make it a repository.

```powershell
cd "D:\Firm\acme-dt"
git init -b main
.\scripts\install-git-hooks.ps1 -Owner <your-branch-prefix>
git add -A
git update-index --chmod=+x .githooks/check-branch .githooks/pre-commit .githooks/pre-push
git commit -m "Initial generated workspace"
```

`<your-branch-prefix>` is the `branch_prefix` of a maintainer in `firm.json`.
Branches are `<prefix>/<task-slug>`. AI or vendor prefixes are rejected
(`config.branch-prefix-agent`) because the prefix names an accountable human.
The `update-index` line marks the hooks executable so they also run on macOS
and Linux.

If script policy blocks `.ps1` files, set the same thing with Git directly:

```powershell
git config --local branchPolicy.owner <your-branch-prefix>
git config --local core.hooksPath .githooks
```

Then create the GitHub repository, push, and **apply the ruleset**.
Generating `.github/rulesets/main-branch-ruleset.json` does not protect
anything (`governance.ruleset-not-applied` reminds you on every render). A
repository administrator runs it once:

```powershell
gh api --method POST repos/<owner>/<repo>/rulesets --input .github/rulesets/main-branch-ruleset.json
gh api repos/<owner>/<repo>/rulesets
```

The second call reads it back; confirm the required checks (`branch-policy`,
`repository-validation`) and bypass actors. Update the same ruleset by ID later
rather than creating duplicates. The workspace's `docs/onboarding/BRANCH_POLICY.md`
has the full text. Required approvals default to 0 for one maintainer and 1
for more; set `governance.required_approvals` to choose. The foundation's own
[branch policy](BRANCH_POLICY.md) is the model.

---

## 9. Install into pyRevit and run the live check

Register the workspace's extensions folder (the one command here that changes
pyRevit configuration):

```powershell
pyrevit extensions paths add "D:\Firm\acme-dt\extensions"
```

Reload pyRevit in Revit. You should see your tab, your sample panel, and the
Hello Button (and `UI Kit Demo` if `ui-kit` is on, `Web Tool Demo` if `web-host` is on). Use a disposable project
and family for the first run.

Then follow the runbook: [live check, generated workspace in
Revit](../verification/GENERATED_WORKSPACE.md). It walks a checklist, then:

```powershell
python -m toolkit_cli verify workspace --workspace "D:\Firm\acme-dt" --manual-checks .logs\workspace-verification\manual-checks.json --revit-version 2026
```

Exit `0` pass, `1` fail, `2` incomplete. Evidence is written under the
foundation checkout's `.logs/`, redacted to outcomes and versions.

The MCP bridge has its own live step with a **mandatory reset rule**: after
clicking pyRevit Reload, do not call a route until you restart Revit or toggle
Routes off and on. Reloading does not safely refresh the Routes listener and can
destabilize Revit. See the workspace's `docs/onboarding/MCP_GUIDE.md` and the
[Windows and live verification guide](../verification/README.md).

For native WPF rendering outside Revit, run `specimens\wpf\show-specimen.ps1`
in the workspace.

---

## 10. Working with agents

- `AGENTS.md` in the workspace is the **canonical, vendor-neutral** rule set.
  `CLAUDE.md`, `GEMINI.md`, and `.github/copilot-instructions.md` are thin
  pointers with no rule text, so clients cannot drift. Edit firm rules in
  `docs/agents/FIRM_RULES.md`, not the pointers.
- Agents use the same CLI you do and can read `--format json` reports. Brand
  truth is the validated `firm/` input, not an agent's reading of a logo.
- Tell agents the same thing you'd tell a colleague: edit `firm/` and
  re-render, never hand-edit managed files, register tools in the toolbar spec
  first, work on a human-prefixed branch, and run `validate` before opening a
  pull request.
- Passing checks does not authorize an agent to merge or release.

---

## 11. Upgrading the foundation

The workspace records the foundation version that rendered it in
`.toolkit/manifest.json`.

```powershell
cd "D:\Tools\foundation"
git pull --ff-only
python -m toolkit_cli render --workspace "D:\Firm\acme-dt" --dry-run
python -m toolkit_cli render --workspace "D:\Firm\acme-dt"
python -m toolkit_cli validate --workspace "D:\Firm\acme-dt"
git -C "D:\Firm\acme-dt" diff
```

Read the dry run before applying. A newer foundation may update managed files
(that is the point), and retire files it no longer produces. If you edited a managed file, you will see a conflict now rather
than lose the edit later; see [section 5](#5-ownership-rules). Upgrading is
allowed; a workspace rendered by a **newer** foundation than the one you run is
refused (`foundation.downgrade`).

Seed files are never updated, so new seed templates reach you only if you copy
them over yourself. Template-level overrides and three-way upgrade merges are
not built yet (backlog B13). How the engine is distributed to adopters (pip,
pinned checkout) is still undecided (B16); a pinned checkout, as above, is the
only supported route.

---

## 12. Troubleshooting

Diagnostics print as `[SEVERITY] code location - message` with a `hint:` line
where one exists. Codes below are the ones you will meet first.

| Code | Meaning | What to do |
| --- | --- | --- |
| `config.unknown-field` | Typo or unsupported key in `firm.json` | Use the "did you mean" hint, or prefix your own data with `x-`. |
| `config.missing-field` | A required field is absent | Add it; see the schema or spec section 2. |
| `config.schema-too-new` | `firm.json` needs a newer foundation | Update the foundation checkout. |
| `config.surface-requires` | `mcp-bridge`, `ui-kit` or `web-host` without `pyrevit-sample` | Add `pyrevit-sample` to `surfaces`. |
| `config.branch-prefix-agent` | A maintainer prefix names an AI or vendor | Use the accountable human's prefix. |
| `config.name-reserved` | Extension or tab name is reserved | Pick another name. |
| `brand.asset-missing`, `brand.png-invalid`, `brand.svg-unsafe`, `brand.svg-external` | Logo file missing, malformed, or unsafe | Fix the file; every variant needs both SVG and PNG, and SVGs may not reference external resources. |
| `brand.inverse-fallback` (warning) | No inverse logo supplied | Add inverse variants, or accept the light one. |
| `token.role-missing` | A required design role is absent | Add it; see spec section 3.3. |
| `token.alias-missing`, `token.alias-cycle`, `token.alias-type-mismatch` | A `{group.token}` alias is broken | Follow the chain named in the message. |
| `token.type-unsupported`, `token.color-space-unsupported`, `token.unit-unsupported` | A token type, colour space, or unit outside the supported subset (colours are sRGB; dimensions are `px`, not `rem`) | Convert it. |
| `a11y.contrast` (warning) | A pairing is below 4.5:1 (3:1 for focus) | Adjust colours. It does not block generation. |
| `font.license-unrecognized`, `font.not-packaged` (warnings) | Unknown font licence, or a family used by tokens but not packaged | Check redistribution rights; or accept the fallback stack. |
| `workspace.not-empty` | `init` target has files | Choose a new or empty folder. |
| `workspace.overlaps-foundation`, `workspace.unsafe` | Workspace is inside the checkout, contains it, or is a drive root or home folder | Pick a different location. |
| `workspace.not-initialized` | No `.toolkit/workspace.json` | Run `init` first. |
| `workspace.id-mismatch` | `workspace_id` changed after `init` | Restore the original id; see [section 6](#6-rebranding-later-versus-changing-technical-identity). |
| `path.reparse-point`, `workspace.reparse-point` | A symlink or junction is in the write path | Remove it; the generator never writes through links. |
| conflict `managed-modified`, `unmanaged-at-managed-path`, `retired-modified` | See [section 5](#5-ownership-rules) | Revert, delete, or move your change. |
| `foundation.downgrade`, `manifest.schema-too-new`, `workspace.schema-too-new` | Workspace was written by a newer foundation | Update the foundation checkout. |
| `output.ironpython-syntax`, `output.ps1-non-ascii`, `output.external-resource` | A generated file failed a safety check | Report it as a foundation bug; do not hand-edit the output. |
| `web-app.typecheck-not-run` (info) | The generated TypeScript is run by Node's type stripping and never type-checked | Nothing to fix; optionally `npm install -D typescript @types/node` and `npx tsc` in `apps/<namespace>-web`. |
| `output.toml-invalid` | A generated `pyproject.toml` does not parse | Report it as a foundation bug; do not hand-edit the output. |
| `revit-addin.invalid-identifier` (warning) | `technical.namespace` or `technical.pyrevit.extension` is a C# reserved word | Pick another value if your own add-in code names it; the generated files still build. |
| `governance.ruleset-not-applied` (info) | Ruleset is only a file | Apply it, [section 8](#8-put-the-workspace-in-git-and-github). |
| `mcp-bridge.not-live-verified`, `ui-kit.not-live-verified`, `web-host.not-live-verified`, `revit-addin.not-live-verified` (info) | Not run in Revit yet | True for everyone today; run the live check. |

Other notes:

- **A `.ps1` script is blocked.** Some workstations run script control that
  blocks PowerShell files. Everything you need has a plain-command equivalent:
  use the Python CLI (`python -m toolkit_cli ...`), `git config`, and `pyrevit
  extensions paths add`. The helper scripts under `scripts\` only wrap those.
- **A render reports a conflict you did not expect.** Run `render --dry-run
  --format json` and read `plan.actions[]`; the conflict's `reason` says which
  case it is.
- **Run `python -m toolkit_cli doctor --profile authoring`** to check the Python
  and tooling environment. Use `--profile revit-host` on the Revit machine.
- **The `web-host` window does not open.** The host uses the WebView2 files that
  Revit 2024 and later ship beside `Revit.exe` (nothing is bundled), and the
  Microsoft Edge WebView2 Runtime installed on the machine. The tool names what is
  missing in a message and in `%LOCALAPPDATA%\<namespace>\logs\web.log`. On Revit
  2022 or 2023, which ship no WebView2 files, your firm must supply a matching
  set itself and point `<NAMESPACE>_WEBVIEW2_DIR` (the namespace in capitals) at
  the folder; the foundation neither ships nor downloads it. Details: spec
  section 8.5.
- **Something looks wrong in Revit.** Capture it as live-check evidence
  (a failure is still evidence) rather than editing generated files.
