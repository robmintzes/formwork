# Foundation technical specification

Status: **v0.1 draft, implementation in progress.** Updated September 30, 2026.
Supersedes nothing; it refines the [charter](CHARTER.md), [source inventory](SOURCE_INVENTORY.md),
and [first milestone](FIRST_MILESTONE.md) into implementable contracts. Decisions
are recorded in [docs/decisions/](../decisions/README.md); the build order is the
[backlog](BACKLOG.md).

Labels used below:

- **[confirmed]** Rob's stated intent or an explicit answer from Rob.
- **[proposed]** an engineering choice made during specification; reversible.
- **[pending]** needs a human decision; independent work continues around it.

Working product name BIMxBert Foundry remains a proposal **[pending]**. Package
names in this document (`toolkit_engine`, `toolkit` CLI) are technical and
provisional; they do not rename the repository.

---

## 1. Product boundaries

| Boundary | Lives in | Owner | Contents |
| --- | --- | --- | --- |
| Reusable foundation | this repository | foundation maintainers | `toolkit_engine/` (generator), `toolkit_cli/` (commands), `schemas/`, validators, templates, docs |
| Firm configuration | `firm/` inside a firm workspace | the adopting firm | `firm.json`, a DTCG token file, brand assets, font files and their licences |
| Platform adapters | `toolkit_engine/adapters/` | foundation maintainers | pure functions: resolved profile -> rendered files for one surface |
| Generated firm workspace | a separate directory/repository | the adopting firm | managed generated files, seeded files the firm then owns, firm-owned tools, `.toolkit/manifest.json` |

**[confirmed]** A firm's repository is a *generated workspace*, separate from the
foundation; the foundation checkout is never mutated by generation
([ADR 0002](../decisions/0002-generated-workspace-model.md)). A GitHub template
repository may later provide the "Use this template" starting point; it would
contain an initialized workspace, not the foundation source.

**[confirmed]** One foundation repository while boundaries settle. Profiles that
ship with the foundation live in `profiles/<profile-id>/` and are *inputs* only;
`toolkit init` copies one into a new workspace's `firm/` folder.

**[confirmed]** BIMxBert is the default, complete profile. A fictional firm
profile with a different logo, palette, typography, and component treatments
proves identity is data.

### 1.1 Runtime separation

- Generator, CLI, and future wizard service: **CPython 3.10+, standard library
  only** **[proposed]** ([ADR 0001](../decisions/0001-engine-placement-and-stack.md)).
  Same constraint as the existing `toolkit_cli`.
- Generated pyRevit code: **IronPython 2.7-compatible syntax** (pyRevit 6.5.5's
  default engine on the reference workstation is IronPython 2.7.12). Generated
  Python is checked with the existing conservative AST guard; only live
  execution proves compatibility.
- Generated WPF XAML: loose ResourceDictionaries usable by `XamlReader.Parse`
  from pyRevit or PowerShell. No compiled assemblies in the first milestone.
- Generated HTML: one self-contained file per guide plus relative local assets;
  no network requests.

### 1.2 Initial supported surfaces

| Surface id | Output | Evidence required before a support claim |
| --- | --- | --- |
| `pyrevit-sample` | extension manifest, read-only Hello Button bundle (metadata, light/dark 96x96 icons), toolbar-spec fragment, tool doc | static validators **and** live Revit/pyRevit run on the declared combination |
| `wpf-specimen` | `Theme.xaml`, `Controls.xaml`, `Specimen.xaml`, PowerShell runner, bundled fonts | native Windows render (runner snapshot), inspected separately from browser output |
| `html-guide` | self-contained Hello Button guide with brand header and component specimen | browser render inspected; offline (no external URL) check automated |
| `governance` | agent instructions, branch policy, hooks, CI, ruleset (section 8) | hooks exercised in a temporary repository; ruleset activation is a maintainer action |
| `mcp-bridge` | read-only Revit MCP bridge: pyRevit Routes side in the firm extension, external FastMCP server, guide (section 8.1) | static checks and extension runtime tests **and** a live Revit/pyRevit run behind the mandatory reset rule |

Compiled Revit add-ins and Python/TypeScript app starters are later surfaces
([backlog](BACKLOG.md)). The adapter interface (section 6) is shared so those
are additions, not special cases.

---

## 2. Firm configuration contract (`firm/firm.json`)

JSON, UTF-8, validated by the engine; [schemas/firm-config.v1.schema.json](../../schemas/firm-config.v1.schema.json)
is published for editor completion **[proposed]** ([ADR 0003](../decisions/0003-config-and-token-formats.md)).
The engine is the authority; a test keeps the JSON Schema in step with it.

### 2.1 Top level

| Field | Type | Rules |
| --- | --- | --- |
| `schema_version` | integer | required; `1`. Higher -> error `config.schema-too-new` naming the minimum foundation version needed. Lower/absent -> error. |
| `profile` | object | `id` (kebab-case, 2-40), `description` (string), `fictional` (bool, default false). |
| `identity` | object | mutable display identity (2.2). |
| `technical` | object | stable technical identity (2.3). |
| `brand` | object | token file, asset slots, fonts (2.4). |
| `appearance` | object | component treatments (2.5). |
| `surfaces` | array of surface ids | non-empty, unique, known ids (1.2, section 8); `mcp-bridge` requires `pyrevit-sample`. |
| `governance` | object, optional | `required_approvals` 0-6 (section 8). |
| `maintainers` | array | each `{name, branch_prefix}`; prefix matches the branch-policy component rule. At least one. |
| keys starting `x-` | any | firm extension data; preserved, ignored by the engine. |

Unknown keys (not `x-`) anywhere in the contract are **errors** with a "did you
mean" hint when a close match exists. Strictness catches typos that would
otherwise silently fall back to defaults.

### 2.2 Display identity (`identity`) - safe to change any time

| Field | Rules | Used for |
| --- | --- | --- |
| `display_name` | 1-80 chars, no control chars | guide titles, specimen header, extension description |
| `short_name` | 1-24 chars | compact labels |
| `author` | 1-80 chars | `__author__`, `bundle.yaml author`, `extension.json author` |
| `logo_alt` | 1-80 chars | accessible name for logo images (`alt`, `AutomationProperties.Name`) |
| `links.support` | `https://` URL | `bundle.yaml help_url`, guide footer |
| `links.documentation` | optional `https://` URL | guide footer |

Display identity changes regenerate visible text only. They never change paths,
identifiers, or persistence keys.

### 2.3 Technical identity (`technical`) - stable, change deliberately

| Field | Rules | Used for |
| --- | --- | --- |
| `namespace` | `^[a-z][a-z0-9]{1,23}$` | CSS custom-property and XAML key prefixes, future Python package and assembly roots |
| `workspace_id` | kebab-case, 2-64 | manifest identity; refuses to render a workspace initialized for another id |
| `pyrevit.extension` | `^[A-Za-z][A-Za-z0-9]{0,39}$` | `<extension>.extension` folder |
| `pyrevit.tab` | letters, digits, single spaces; 1-40 | `<tab>.tab` folder (pyRevit shows the folder name) |
| `pyrevit.sample_panel` | same as `tab` | `<panel>.panel` folder for the foundation sample |

pyRevit derives command identity from bundle paths, so these folder names are
technical identity even though users see them. Renaming them is a migration
(old managed files become obsolete and are deleted only when unmodified), not a
rebrand. Not Windows reserved names, and not the template sample's own extension name.

### 2.4 Brand inputs (`brand`)

```json
"brand": {
  "tokens": "tokens.tokens.json",
  "assets": {
    "wordmark": {"light": {"svg": "assets/wordmark-light.svg", "png": "assets/wordmark-light.png"},
                 "inverse": {"svg": "...", "png": "..."}},
    "symbol":   {"light": {...}, "inverse": {...}}
  },
  "fonts": [{"family": "Geist",
             "files": [{"path": "fonts/geist/Geist-Regular.ttf", "weight": 400, "style": "normal"}],
             "license": "OFL-1.1", "license_file": "fonts/geist/OFL.txt",
             "source": "https://github.com/vercel/geist-font"}],
  "notices": ["NOTICE-brand.md"]
}
```

- Asset slots: `wordmark` and `symbol`, each with `light` (for light surfaces)
  and `inverse` (for dark/brand surfaces). Distinct files; the engine never
  derives one by recolouring another. `light` is required for both; `inverse`
  falls back to `light` with a warning `brand.inverse-fallback`.
- Formats: `svg` (HTML) and `png` (WPF, which has no native SVG). Both required
  for each supplied variant in v1. SVGs must not reference external resources or
  contain scripts; PNGs must pass the structural PNG check.
- All paths are relative to `firm/`, forward-slash, no `..`, and must exist.
- `fonts`: every font file the outputs reference. `license_file` is required and
  copied with the font. Licences outside a known-redistributable list
  (`OFL-1.1`, `Apache-2.0`, `MIT`) produce warning `font.license-unrecognized`.
  Families named by tokens but not packaged produce warning
  `font.not-packaged`; outputs then rely on the token's fallback stack.
- `notices`: brand-specific notice files copied verbatim into the workspace
  (for BIMxBert: the marks are not MIT-licensed).

### 2.5 Appearance (`appearance`)

Enumerated treatments that the wizard exposes as choices. Values feed adapters
together with tokens.

| Field | Values |
| --- | --- |
| `button.primary` | `solid`, `outline` |
| `button.secondary` | `outline`, `tonal`, `ghost` |
| `button.shape` | `square`, `rounded`, `pill` |
| `button.label_case` | `as-written`, `uppercase` |
| `badge.style` | `soft`, `solid`, `outline` |
| `badge.shape` | `square`, `rounded`, `pill` |
| `badge.label_case` | `as-written`, `uppercase` |
| `decorations.registration_marks` | boolean |

`rounded` uses token `radius.rounded`; `square` is 0; `pill` is half the
element height. An adapter that cannot express a choice reports
`adapter.unsupported-choice` (warning) and renders its documented fallback; for
example the WPF adapter renders no registration marks in v1.

---

## 3. Design token contract (`firm/<tokens>.tokens.json`)

Format: a **subset of the DTCG Format Module 2025.10** (Stable Final Community
Group Report, 2025-10-28) **[proposed]** ([ADR 0003](../decisions/0003-config-and-token-formats.md)).

### 3.1 Supported subset

- Tokens are objects with `$value`; groups are objects without it. `$type`
  inherits from the nearest group. `$description`, `$deprecated`, and
  `$extensions` are accepted; `$extensions` is preserved and otherwise ignored.
- Types: `color`, `dimension`, `fontFamily`, `fontWeight`, `number`.
  Other DTCG types are rejected with `token.type-unsupported` (not silently
  dropped).
- `color`: `{"colorSpace": "srgb", "components": [r, g, b], "alpha"?, "hex"?}`,
  components 0-1. Other colour spaces are rejected in v1. If `hex` is present it
  must agree with `components` (within one 8-bit step).
- `dimension`: `{"value": n, "unit": "px"}`. `rem` is rejected in v1 because WPF
  has no root font size; adapters need absolute device-independent pixels.
- Aliases: curly-brace `{group.token}` only, resolved transitively. JSON
  Pointer `$ref`, `$extends`, and `$root` are rejected in v1 with explicit
  codes. Missing targets, type mismatches, and cycles are errors that name the
  full chain.
- Names must not start with `$` or contain `{`, `}`, `.`.

### 3.2 Layers

- `palette.*` - primitives, free-form names, literal values.
- `color.*`, `font.*`, `font-weight.*`, `font-size.*`, `space.*`, `radius.*`,
  `stroke.*`, `size.*` - **semantic roles**, required by name (3.3), normally
  aliases into `palette`.
- Component treatments come from `appearance` (2.5) plus the `color.action.*`
  roles; there is no separate component token layer in v1.

### 3.3 Required roles

| Group | Tokens | Type |
| --- | --- | --- |
| `color.surface` | `default`, `card`, `sunken`, `inverse` | color |
| `color.text` | `primary`, `secondary`, `inverse` | color |
| `color.line` | `subtle`, `strong` | color |
| `color.accent` | `default`, `strong`, `soft` | color |
| `color.action.primary` | `bg`, `fg` | color |
| `color.action.secondary` | `bg`, `fg`, `border` | color |
| `color.focus` | `ring` | color |
| `color.status.{info,success,warning,danger}` | `fg`, `bg` | color |
| `font` | `display`, `body`, `label`, `code` | fontFamily (array = fallback stack) |
| `font-weight` | `display`, `body`, `strong`, `label` | fontWeight |
| `font-size` | `display`, `title`, `body`, `small`, `label`, `code` | dimension |
| `space` | `xs`, `sm`, `md`, `lg`, `xl` | dimension |
| `radius` | `rounded` | dimension |
| `stroke` | `hairline`, `control`, `focus` | dimension |
| `size` | `control-height` | dimension |
| `tracking` | `label` (em) | number |

Missing roles are errors. Extra semantic tokens are allowed and passed to
adapters that understand them.

### 3.4 Accessibility checks

WCAG 2.x contrast is computed for: text primary/secondary on surface default
and card; text inverse on surface inverse; action fg on action bg (both
variants); status fg on status bg; and focus ring against surface default (3:1).
Below 4.5:1 for text (3:1 for focus) produces warning `a11y.contrast` with the
ratio. Warnings do not block generation; the wizard surfaces them.

### 3.5 Platform mappings

| Token | CSS | WPF |
| --- | --- | --- |
| `color.surface.default` | `--<ns>-color-surface-default: #RRGGBB` | `SolidColorBrush x:Key="<Ns>.Color.Surface.Default"` (alpha -> `#AARRGGBB`) |
| `font.body` | `--<ns>-font-body: "Geist", "Segoe UI", sans-serif` | `FontFamily` key; packaged fonts registered at load time from a file URI |
| `font-size.body` | `--<ns>-font-size-body: 16px` | `sys:Double` key; same DIP value (no hidden platform offset) |
| `radius.rounded` + shape | resolved per component | `CornerRadius` per component style |
| `stroke.*` | `px` | `Thickness`/`sys:Double` |

Names are derived mechanically (`a.b-c` -> `--ns-a-b-c` / `Ns.A.BC`) and are
part of the adapter contract. If a platform needs different values (for
example a smaller WPF body size) the profile declares an explicit platform
token; adapters never silently offset values. (The BIMxBert export's WPF
dictionary runs 2 DIP smaller than its CSS; v1 profiles use one value.)

---

## 4. Generated ownership and update model

[ADR 0004](../decisions/0004-generated-ownership-and-update-model.md).

### 4.1 Ownership classes

| Class | Examples | Generator behaviour |
| --- | --- | --- |
| **input** | `firm/**` | read only. Never written after `init`. |
| **managed** | extension manifest, sample bundle, theme/controls XAML, guide HTML, copied fonts, notices | written and hash-tracked. Regenerated from inputs every run. |
| **seed** | `docs/toolbar/toolbar_spec.md`, workspace `README.md`, `.gitattributes` | written only when absent; afterwards firm-owned and never rewritten. A deliberately deleted seed is not recreated. |
| **firm-owned** | anything not listed in the manifest, e.g. a custom pushbutton | never read for writing, never moved or deleted. |
| **retired** | a managed path no longer produced (e.g. after a renamed tab) | deleted only if its content still matches the manifest hash; otherwise a conflict. |

Override/extension files: in v1 the overrides are the firm's own inputs (tokens,
appearance) and firm-owned files. Template-level overrides are backlog item B9.

### 4.2 Manifest (`.toolkit/manifest.json`)

```json
{
  "schema_version": 1,
  "kind": "toolkit-generation-manifest",
  "foundation_version": "0.2.0-alpha.1",
  "workspace_id": "bimxbert-design-technology",
  "profile_id": "bimxbert",
  "inputs_sha256": "<hash of canonicalized firm.json, token file, and every referenced input file>",
  "files": {
    "extensions/BIMxBert.extension/extension.json":
      {"ownership": "managed", "adapter": "pyrevit-sample", "sha256": "..."}
  }
}
```

Sorted keys, two-space indent, LF, no timestamps, no absolute paths, no user or
host names. Identical inputs and foundation version therefore produce identical
bytes. `.toolkit/workspace.json` (written by `init`) holds `workspace_id` and
`schema_version` and marks the directory as a workspace.

Text outputs are hashed after normalizing CRLF to LF so a Git `autocrlf`
checkout does not register as a modification. Outputs are written with LF and
the seeded `.gitattributes` requests LF.

### 4.3 Planning rules

For every desired managed path:

| On disk | In manifest | Disk vs manifest hash | Disk vs new content | Action |
| --- | --- | --- | --- | --- |
| absent | no | - | - | `create` |
| absent | yes | - | - | `restore` |
| present | yes | equal | equal | `unchanged` |
| present | yes | equal | differs | `update` |
| present | yes | differs | equal | `adopt` (record the new hash) |
| present | yes | differs | differs | **conflict** `managed-modified` |
| present | no | - | equal | `adopt` |
| present | no | - | differs | **conflict** `unmanaged-at-managed-path` |

Seeds: absent and never seeded -> `create`; otherwise `skip`. Retired managed
paths: matching hash -> `delete`; modified -> **conflict** `retired-modified`;
absent -> `forget`.

**Any conflict blocks the whole apply.** Nothing is written; the report lists
every conflict with its path, reason, and resolution options (revert the file,
delete it to accept regeneration, or move the customization to a firm-owned
path). Blocking is preferred over partial application because a half-applied
brand change is harder to diagnose than an unapplied one.

### 4.4 Apply semantics

1. Load and validate inputs. Errors stop here.
2. Render every enabled adapter **in memory**. Adapters are pure: same inputs ->
   same bytes, no clock, no environment, no absolute paths.
3. Validate rendered output before any write: XML well-formedness for XAML,
   JSON parse, PNG structure, no external URLs in HTML/SVG/CSS, path rules
   (4.5), case-insensitive path collisions, and IronPython syntax guard for
   generated Python.
4. Plan (4.3). `--dry-run` stops here and is strictly read-only (it does not
   even create `.toolkit/`).
5. Apply: each file is written to a temporary sibling and moved into place with
   `os.replace`; retired files are deleted after all writes; the manifest is
   replaced last.

Partial-failure semantics: apply is **not atomic across files, but convergent**.
If a write fails mid-run, already replaced files hold new content while the
manifest still describes the old state. The next run classifies those files as
`adopt` (disk equals new content) and completes the update. No conflicting or
firm-owned file is written in any failure mode. The engine never performs
recursive directory removal; empty directories left by retired files are
reported, not deleted.

### 4.5 Output safety

- Workspace root: resolved to an absolute path; must not be a drive root, the
  user's home directory, inside the foundation checkout, or contain it.
  `init` requires a missing or empty directory; `render` requires
  `.toolkit/workspace.json` with a matching `workspace_id`.
- Every output path is relative, POSIX-separated, without `.`/`..`, drive
  letters, or empty components; no component is a Windows reserved device name
  (`CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, `LPT1-9`, with or without extension),
  ends in a dot or space, or contains `<>:"|?*` or control characters; total
  length at most 200 characters.
- Before writing or deleting, every existing component between the root and
  the target is checked with `lstat`; symbolic links, junctions, and other
  reparse points abort the run (`path.reparse-point`).
- Paths with spaces are supported and tested.

### 4.6 Version compatibility

- Manifest `schema_version` newer than the engine supports -> refuse
  (`manifest.schema-too-new`).
- Manifest `foundation_version` newer than the running engine -> refuse
  (`foundation.downgrade`); upgrading is allowed and shows the diff.
- Config `schema_version` migrations are explicit functions `N -> N+1`, run in
  memory and shown in the plan; the firm's `firm.json` is rewritten only by an
  explicit `toolkit config migrate` (backlog B8). v1 has no migrations.

---

## 5. Commands

Added to the existing `toolkit` CLI (`python -m toolkit_cli`), keeping its
conventions: argparse, `--format text|json`, `--output`, no interactive prompts
required.

| Command | Purpose |
| --- | --- |
| `toolkit config validate --firm <dir>` | validate `firm.json`, tokens, assets, fonts; print diagnostics |
| `toolkit init --profile <dir> --workspace <dir>` | create a workspace, copy a profile into `firm/`, write `.toolkit/workspace.json`; does not render |
| `toolkit render --workspace <dir> [--dry-run]` | plan and (unless dry-run) apply generation |
| existing `toolkit doctor`, `toolkit verify revit` | unchanged |

Exit codes: `0` success (including a no-change run and a clean dry-run); `1`
blocked (invalid configuration or conflicts); `2` cannot run (usage, unsafe
path, I/O error). JSON reports carry `schema_version`, `kind`,
`toolkit_version`, `diagnostics[]` (`code`, `severity`, `location`, `message`,
`hint`), and for render a `plan.actions[]` list and `summary`. Reports contain
workspace-relative paths only.

Planned later: `toolkit validate --workspace` (run validators/tests in a
workspace), `toolkit install`, `toolkit config migrate`, `toolkit serve`
(wizard backend).

---

## 6. Adapter contract

```text
adapter.id: str                       # surface id
adapter.render(profile) -> RenderResult
RenderResult.files: list[OutputFile]  # path, bytes, ownership, text: bool
RenderResult.diagnostics: list[Diagnostic]
```

`profile` is the fully validated, alias-resolved input (identity, technical,
appearance, tokens, asset bytes, font metadata). Adapters may not touch the
filesystem. Two adapters may not emit the same path (checked). Shared outputs
(fonts, notices) come from a `common` adapter that is always enabled.

---

## 7. Wizard and agent clients (design only in this slice)

- Wizard: a local browser UI served by `toolkit serve` over the same engine
  functions **[proposed]** ([ADR 0006](../decisions/0006-wizard-stack.md)).
  Stdlib `http.server` bound to `127.0.0.1`, random port, a per-launch secret
  token required on every API request, `Host` and `Origin` validation, JSON-only
  bodies with a size cap, and writes limited to the selected workspace's
  `firm/` inputs and the engine's apply. Static assets ship with the
  foundation; no build step, no CDN. The Rockwell workbench's open loopback
  boundary (no origin check, whole-repo static serving) is explicitly not
  reused.
- Agents: call the same commands and read the JSON reports. Brand truth is the
  validated `firm/` input, never an agent's interpretation.
- Credentials and local secrets never appear in `firm/`; the wizard's session
  token is in memory only.

---

## 8. Agent neutrality and firm governance (`governance` surface)

Implemented as an opt-in surface (`"governance"` in `surfaces`):

| Output | Ownership | Notes |
| --- | --- | --- |
| `AGENTS.md` | managed | Canonical rules: ownership, branches, tool conventions, Revit safety, verification, handoffs; lists `maintainers`. |
| `CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md` | managed | Thin pointers to `AGENTS.md`, no rule text, so clients cannot drift. |
| `.agents/skills/pyrevit-tool/SKILL.md` | managed | Firm-neutral playbook using the workspace's paths and `<Ns>.*` WPF keys. |
| `docs/onboarding/BRANCH_POLICY.md` | managed | Maintainers, approval rule, hook install, ruleset activation. |
| `.github/workflows/development-policy.yml` | managed | Jobs `branch-policy` and `repository-validation` (the required checks). |
| `.github/rulesets/main-branch-ruleset.json` | managed | `required_approving_review_count` from `governance.required_approvals`. |
| `validators/*.py`, `.githooks/*`, `scripts/install-git-hooks.ps1` | managed | Vendored from the foundation with asserted substitutions (owner example, mandatory `-Owner`, `__author__`). A drifted source file fails generation. |
| `docs/agents/FIRM_RULES.md`, `docs/handoffs/INDEX.md` | seed | Firm-owned extensions of the rules. |

`governance.required_approvals` is optional. It defaults to 0 for one
maintainer and 1 otherwise, and the default is reported as
`governance.approvals-default`. A count that the listed maintainers cannot
satisfy warns `governance.approvals-unreachable`. Generating the ruleset does
not activate it; `governance.ruleset-not-applied` says so on every render.
The IronPython syntax guard applies only to `extensions/**.py`. Vendored
validators are CPython tooling.

### 8.1 MCP bridge (`mcp-bridge` surface)

Opt-in surface (`"mcp-bridge"` in `surfaces`) that requires `pyrevit-sample`
(config error `config.surface-requires` otherwise): the bridge lives inside the
extension that surface generates. It is a re-identified copy of the foundation's
read-only bridge, never a fork to maintain by hand.

| Output | Ownership | Notes |
| --- | --- | --- |
| `extensions/<Extension>.extension/startup.py`, `lib/revit_mcp_bridge/*.py` (12 modules) | managed | Registers GET-only pyRevit Routes; IronPython 2.7 syntax guard applies. Not tabs: `startup.py` and `lib/` are not registered in the toolbar spec. |
| `extensions/<Extension>.extension/tests/test_mcp_bridge_runtime.py` | managed | Generated (not vendored): pure-CPython runtime checks that need no Revit. |
| `servers/revit-mcp/mcp-server/**` (FastMCP server, `requirements.txt`, its pytest suite), `servers/revit-mcp/scripts/*.ps1`, `servers/revit-mcp/.gitignore` | managed | Loopback-only defaults and read-only tools preserved unchanged. |
| `docs/onboarding/MCP_GUIDE.md` | managed | Generated from a template using the firm's prefix; carries the reset rule below. |

Substitutions, all asserted by exact occurrence count (`VendoringError` on any
mismatch, so a changed foundation file fails generation instead of rendering
half-rebranded):

| Where | Foundation text | Becomes | Count |
| --- | --- | --- | --- |
| every bridge module and `startup.py` | `__author__ = "Template Author"` | `identity.author` | 1 per file |
| `routes_health.py`, `routes_project.py`, `routes_dispatch.py` | `routes.API("placeholder")` | `routes.API("<namespace>")` | 1 per file |
| `startup.py` | `"Placeholder extension loaded and MCP routes registered."` | log line naming `technical.extension` | 1 |
| `mcp-server/settings.py` | `(/placeholder)` comment, default URL `...:48884/placeholder"` | `/<namespace>` | 1 each |
| `mcp-server/tests/test_settings.py` | `/placeholder` URL literals | `/<namespace>` | 7 |

The Routes prefix derives from `technical.namespace` (stable technical identity),
so a rebrand never moves the URL; changing the namespace is a migration. The
adapter also fails when the foundation bridge or server directories gain or lose
a file it does not list. `servers/revit-mcp/mcp-server/live_probe.py` and its
test are deliberately not vendored: they import the foundation's own
`toolkit_cli`, which a workspace does not contain. The foundation's
`toolkit verify revit --repository <workspace> --routes-url http://127.0.0.1:48884/<namespace>`
is the live gate.

**Mandatory reset rule.** After clicking pyRevit Reload, do not call a route:
restart Revit or toggle pyRevit Routes off and back on before the first request.
Reloading extension code does not safely refresh the running Routes listener and
can destabilize or crash Revit. `--routes-reset-confirmed` on the verifier is a
human assertion that this reset happened; the tool cannot check it. Every render
reports `mcp-bridge.not-live-verified` (info) until live evidence is recorded.

## 9. Notices, attribution, and provenance

- Foundation code is MIT (copyright Rob Mintzes). Every workspace receives a
  managed `THIRD_PARTY_NOTICES.md` listing the foundation licence and each
  packaged font with its licence file, independent of branding.
- The BIMxBert name and marks are **not** licensed under MIT **[confirmed]**;
  `profiles/bimxbert/NOTICE-brand.md` says so and is copied into BIMxBert
  workspaces. Adopters replace the profile.
- Tool `__author__` and bundle `author` use `identity.author`. Original
  contributor attribution lives in provenance and release records, never in
  rebranded output, and rebranding cannot remove notices (they are not derived
  from display identity).
- Imported items are recorded in [RELEASE_RECORD.md](RELEASE_RECORD.md) with
  source, hash, changes, licence, and verification.
- **[proposed]** Rockwell repository material is used as reference for concepts
  only (module families, role vocabulary); no files are copied
  ([ADR 0005](../decisions/0005-source-extraction-and-assets.md)).

---

## 10. Evidence and acceptance

| Promise (FIRST_MILESTONE) | Automated evidence | Manual / host evidence |
| --- | --- | --- |
| Two distinct brands | both profiles render; test asserts differing palette, fonts, shapes, logos | browser and WPF snapshots reviewed |
| Complete replacement | fictional output contains no BIMxBert/Rob strings outside notices; author/help_url/alt text use fictional identity | - |
| Notices intact | notices present and byte-identical across a rebrand | - |
| Repeat execution | second render reports zero changes; workspace tree hash unchanged | - |
| Change propagation | palette/appearance change updates CSS, XAML, icons; unsupported choices reported | - |
| Custom tool preservation | firm-owned pushbutton byte-identical after rebrand | - |
| Conflict handling | edited managed file -> exit 1, file preserved, nothing else written | - |
| Offline | no external URLs in generated HTML/CSS/SVG/XAML | guide opened with network unavailable |
| Diagnostics | invalid configs produce coded diagnostics (cycle, missing role, bad path, unknown key, too-new schema) | - |
| Separate rendering checks | - | WPF runner snapshot on Windows; browser screenshot |
| Live host | - | `toolkit verify revit` on Revit 2026 + pyRevit 6.5.5 + IronPython 2.7.12, Windows 11 **[proposed combination]**, recorded in `docs/verification/MATRIX.md` |

Host support is claimed only after the last row has recorded evidence.
