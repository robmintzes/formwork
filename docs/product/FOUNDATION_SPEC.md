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

The product is **Formwork**, a BIMxBert project **[confirmed]**
([ADR 0008](../decisions/0008-product-name.md)). The code names followed in
0.3.0 ([ADR 0010](../decisions/0010-cli-package-rename.md)): `formwork_engine`,
`formwork_cli`, `formwork_wizard`, and the `.formwork/` state folder.

---

## 1. Product boundaries

| Boundary | Lives in | Owner | Contents |
| --- | --- | --- | --- |
| Reusable foundation | this repository | foundation maintainers | `formwork_engine/` (generator), `formwork_cli/` (commands), `schemas/`, validators, templates, docs |
| Firm configuration | `firm/` inside a firm workspace | the adopting firm | `firm.json`, a DTCG token file, brand assets, font files and their licenses |
| Platform adapters | `formwork_engine/adapters/` | foundation maintainers | pure functions: resolved profile -> rendered files for one surface |
| Generated firm workspace | a separate directory/repository | the adopting firm | managed generated files, seeded files the firm then owns, firm-owned tools, `.formwork/manifest.json` |

**[confirmed]** A firm's repository is a *generated workspace*, separate from the
foundation; the foundation checkout is never mutated by generation
([ADR 0002](../decisions/0002-generated-workspace-model.md)). A GitHub template
repository may later provide the "Use this template" starting point; it would
contain an initialized workspace, not the foundation source.

**[confirmed]** One foundation repository while boundaries settle. Profiles that
ship with the foundation live in `profiles/<profile-id>/` and are *inputs* only;
`formwork init` copies one into a new workspace's `firm/` folder.

**[confirmed]** BIMxBert is the default, complete profile. A fictional firm
profile with a different logo, palette, typography, and component treatments
proves identity is data.

### 1.1 Runtime separation

- Generator, CLI, and future wizard service: **CPython 3.10+, standard library
  only** **[proposed]** ([ADR 0001](../decisions/0001-engine-placement-and-stack.md)).
  Same constraint as the existing `formwork_cli`.
- Generated pyRevit code: **IronPython 2.7-compatible syntax** (pyRevit 6.5.5's
  default engine on the reference workstation is IronPython 2.7.12). Generated
  Python is checked with the existing conservative AST guard; only live
  execution proves compatibility.
- Generated WPF XAML: loose ResourceDictionaries usable by `XamlReader.Parse`
  from pyRevit or PowerShell. The only compiled output is the opt-in `revit-addin` surface
  (section 8.3), which is built by the user's own .NET SDK; the engine never compiles.
- Generated application starters (section 8.4): the `python-app` CLI is stdlib-only
  CPython 3.10+; the `web-app` is erasable TypeScript that Node 22.18+ runs directly.
  Neither needs an install step, and the engine never runs either.
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
| `ui-kit` | themed WPF dialog kit in the firm extension (`lib/<namespace>_ui`): result, chooser, selector, controls, icons, plus a read-only `UI Kit Demo` button (section 8.2) | static key-resolution and runtime-contract tests, a native WPF render of every dialog **and** a live Revit/pyRevit run |
| `web-host` | HTML tool host for pyRevit in the firm extension (`lib/<namespace>_web`): WebView2 in a WPF window using the WebView2 assemblies that ship with Revit, bridge, session helpers, token-built assets, plus a read-only `Web Tool Demo` button (section 8.5) | pure-module and static tests, a browser render with a stub bridge **and** a live Revit/pyRevit run on each supported Revit version (no WebView2 window has been opened in Revit) |
| `revit-addin` | C# Revit add-in starter under `addins/<Extension>.Addin/`: SDK-style project, ribbon button, read-only command with a themed WPF window, manifest with a stable `AddInId`, README (section 8.3) | `dotnet build` succeeds offline against the installed Revit API (build evidence) **and** the add-in loads and its command runs in a live Revit (host evidence); neither implies the other |
| `python-app` | stdlib-only Python CLI under `apps/<namespace>-report/` that renders a CSV or JSON table as a branded offline HTML report: PEP 621 project, `src/<namespace>_report`, generated `theme.css`, unittest suite, sample table, README (section 8.4) | the generated unittest suite and the CLI on the sample table pass in CPython (tested by the engine's suite); host-independent, so no Revit run applies |
| `web-app` | dependency-free TypeScript web starter under `apps/<namespace>-web/`: loopback-only `node:http` static server, `node:test` suite, branded app shell, generated `theme.css`, packaged fonts, README (section 8.4) | the generated `node --test` suite passes on Node 22.18+ (tested by the engine's suite when Node is present); types are **not** checked (no `tsc`) |

The adapter interface (section 6) is shared, so each later surface is an addition, not a special case.
Further surfaces are tracked in the [backlog](BACKLOG.md).

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
| `namespace` | `^[a-z][a-z0-9]{1,23}$` | CSS custom-property and XAML key prefixes, Python package (`<namespace>_report`) and npm package (`<namespace>-web`) names, Revit add-in root namespace |
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
  copied with the font. Licenses outside a known-redistributable list
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
  components 0-1. Other color spaces are rejected in v1. If `hex` is present it
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

| Class | Examples | Generator behavior |
| --- | --- | --- |
| **input** | `firm/**` | read only. Never written after `init`. |
| **managed** | extension manifest, sample bundle, theme/controls XAML, guide HTML, copied fonts, notices | written and hash-tracked. Regenerated from inputs every run. |
| **seed** | `docs/toolbar/toolbar_spec.md`, workspace `README.md`, `.gitattributes` | written only when absent; afterwards firm-owned and never rewritten. A deliberately deleted seed is not recreated. |
| **firm-owned** | anything not listed in the manifest, e.g. a custom pushbutton | never read for writing, never moved or deleted. |
| **retired** | a managed path no longer produced (e.g. after a renamed tab) | deleted only if its content still matches the manifest hash; otherwise a conflict. |

Override/extension files: in v1 the overrides are the firm's own inputs (tokens,
appearance) and firm-owned files. Template-level overrides are backlog item B9.

### 4.2 Manifest (`.formwork/manifest.json`)

```json
{
  "schema_version": 1,
  "kind": "formwork-generation-manifest",
  "foundation_version": "0.3.0-alpha.1",
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
bytes. `.formwork/workspace.json` (written by `init`) holds `workspace_id` and
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
   even create `.formwork/`).
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
  `.formwork/workspace.json` with a matching `workspace_id`.
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
  explicit `formwork config migrate` (backlog B13). v1 has no migrations.
- State folder: workspaces rendered before 0.3.0 keep state in `.toolkit/`.
  Reads accept it, along with its `toolkit-*` `kind` values; a dry run reports
  `plan.state_migration`; the first applied render renames the folder to
  `.formwork/` before writing. If both folders exist, the render refuses
  (`workspace.state-ambiguous`). `.toolkit/` stays reserved for outputs
  ([ADR 0010](../decisions/0010-cli-package-rename.md)).

### 4.7 Overrides (`firm/overrides/`)

A firm that wants to own the content of one managed file puts its version at
`firm/overrides/<workspace-relative path>`. On render:

- the override replaces the generated content (CRLF is normalized for text);
  output checks still run on it, so a broken override blocks the render;
- the manifest entry records `override: true` and `generated_sha256` (the hash
  of what the generator would have written);
- when a later render produces different generated content,
  `override.upstream-changed` warns and the override is kept;
- `override.orphan` (no generated file at that path) and `override.not-managed`
  (the path is a seed, which already belongs to the firm) are errors;
- deleting the override restores the generated content on the next render.

Overrides are always read from the workspace's own `firm/`, including when a
client (the wizard) plans with draft inputs, so a plan never proposes reverting
an override. Editing a managed file in place remains a conflict; overrides
are the supported way to keep a customization.

---

## 5. Commands

Added to the existing `formwork` CLI (`python -m formwork_cli`; the deprecated
`python -m toolkit_cli` alias forwards to it until 0.4.0), keeping its
conventions: argparse, `--format text|json`, `--output`, no interactive prompts
required.

| Command | Purpose |
| --- | --- |
| `formwork config validate --firm <dir>` | validate `firm.json`, tokens, assets, fonts; print diagnostics |
| `formwork init --profile <dir> --workspace <dir>` | create a workspace, copy a profile into `firm/`, write `.formwork/workspace.json`; does not render |
| `formwork render --workspace <dir> [--dry-run]` | plan and (unless dry-run) apply generation |
| `formwork validate --workspace <dir> [--skip-tests]` | workspace matches its inputs; bundle, spec, and safety validators; the firm's own `tests/` |
| `formwork serve [--port N] [--no-open]` | the local onboarding wizard (section 7) |
| `formwork verify workspace --workspace <dir> --manual-checks <file> --revit-version <year>` | record redacted live-host evidence for a generated workspace |
| existing `formwork doctor`, `formwork verify revit` | unchanged |

Exit codes: `0` success (including a no-change run and a clean dry-run); `1`
blocked (invalid configuration or conflicts); `2` cannot run (usage, unsafe
path, I/O error). JSON reports carry `schema_version`, `kind`,
`formwork_version`, `diagnostics[]` (`code`, `severity`, `location`, `message`,
`hint`), and for render a `plan.actions[]` list and `summary`. Reports contain
workspace-relative paths only.

Planned later: `formwork install` and `formwork config migrate` (needed only
once a schema v2 exists).

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

## 7. Wizard and agent clients (implemented: `formwork_wizard/`)

- Wizard: a local browser UI served by `formwork serve` over the same engine
  functions ([ADR 0006](../decisions/0006-wizard-stack.md)). It edits an
  in-memory draft of `firm/` inputs, validates and previews it with the
  engine, plans read-only against a workspace, and applies only after a
  passing plan. Tests cover the token, Host/Origin, traversal, body-size, and
  cookie-scoped preview rules.
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
`formwork_cli`, which a workspace does not contain. The foundation's
`formwork verify revit --repository <workspace> --routes-url http://127.0.0.1:48884/<namespace>`
is the live gate.

**Mandatory reset rule.** After clicking pyRevit Reload, do not call a route:
restart Revit or toggle pyRevit Routes off and back on before the first request.
Reloading extension code does not safely refresh the running Routes listener and
can destabilize or crash Revit. `--routes-reset-confirmed` on the verifier is a
human assertion that this reset happened; the tool cannot check it. Every render
reports `mcp-bridge.not-live-verified` (info) until live evidence is recorded.

### 8.2 UI kit (`ui-kit` surface)

Opt-in surface (`"ui-kit"` in `surfaces`) that requires `pyrevit-sample`: the kit
lives in the extension that surface generates and the demo button joins its
sample panel. All outputs are `managed`.

| Output | Notes |
| --- | --- |
| `extensions/<Extension>.extension/lib/<namespace>_ui/` | IronPython 2.7 package: `bootstrap`, `result_model` (ToolResult), `result_dialog` (M1), `chooser_dialog` (M0), `selection_dialog` (M2-lite). Importing the package loads no WPF, so `result_model` runs under plain CPython. |
| `.../<namespace>_ui/Theme.xaml`, `Controls.xaml`, `Icons.xaml` | `Theme.xaml` is the specimen's token dictionary (same `<Ns>.Color.Surface.Default` key scheme, shared logic in `wpf_common`). `Controls.xaml` is the specimen's styles plus field, check, radio, callout, progress, output log, titlebar, step, caption, hairline, section, stat-tile and list-box styles. `Icons.xaml` holds Lucide-derived line geometry (`<Ns>.Icon.*`). |
| `.../<namespace>_ui/ResultDialog.xaml`, `ChooserDialog.xaml`, `SelectionDialog.xaml` | Inverse-surface titlebar with the firm symbol, tool title, usage badge, close; no minimize on modal dialogs. Sizes: compact 560 wide for M0/M1, selector 640 x 560 with a 560 x 440 minimum. |
| `.../<namespace>_ui/fonts/<family>/`, `assets/symbol-inverse.png` | Packaged fonts (with their OFL texts) and the brand symbol, copied **into** the extension: pyRevit loads the extension folder, so extension code never reaches into the workspace's top-level `assets/`. |
| `extensions/<Extension>.extension/tests/test_ui_kit_contract.py` | Generated CPython test: parses every kit XAML file, resolves every `{DynamicResource}`/`{StaticResource}` key and every key named in kit Python, checks the `x:Name` elements the code uses, and exercises `ToolResult`, `normalize_options` and the selector filter. |
| `.../<Panel>.panel/UIKitDemo.pushbutton/`, `docs/toolbar/tools/ui-kit-demo.md` | Read-only demo: validate context, chooser, selector over up to 50 view names, result dialog. No transactions. Its entry appears in `docs/toolbar/spec.d/foundation-sample.md` only when the surface is enabled; without it that fragment is unchanged. |

**Fonts, one mechanism.** `Theme.xaml` names packaged fonts by relative URI
(`fonts/<family>/#<Family>`); `bootstrap.apply_theme` parses it with a
`ParserContext` whose `BaseUri` is the package folder, so the URIs resolve to the
copies shipped in the extension. There is no separate font registration step. A
workspace path containing `#` would break the URI.

**Labels.** WPF has no text transform, so the firm's button and badge label-case
choices are applied to generated XAML text and, through `bootstrap.button_text`
and `badge_text`, to text a dialog sets at run time. Caller-supplied captions go
through the same helpers.

**Transaction rule.** Collect input, show the input dialog, run **one short
Transaction** (rollback on failure), then show the M1 result dialog after the
Transaction has finished. A dialog is never shown while a Transaction is open.

**Module families.** Covered: M0 (chooser), M1 (result), M2-lite (searchable
single or multiple selection over `(label, value)` pairs). Not ported: M2 with
detail panes and the M3-M7 families that need a WebView2 host. The WebView2 host is the
`web-host` surface (section 8.5); it references the WebView2 assemblies Revit ships, so
no DLL is redistributed here ([backlog](BACKLOG.md), B20). The licensed Adobe/office
fonts used by the source UI are never packaged; fonts come from the firm profile.

**Notices.** Icon geometry derives from Lucide (ISC, portions MIT from Feather).
The license texts are added to `THIRD_PARTY_NOTICES.md` by the always-on `common`
adapter whenever the surface is enabled, independent of branding. Origin and
changes of the ported code are in [RELEASE_RECORD.md](RELEASE_RECORD.md) (R05).
Every render reports `ui-kit.not-live-verified` (info) until a live Revit run is
recorded.

### 8.3 Revit add-in starter (`revit-addin` surface)

Opt-in surface (`"revit-addin"` in `surfaces`). It needs no other surface: the theme
comes from the shared `wpf_common` code, not from `wpf-specimen` or `ui-kit`. All
outputs are `managed`, under `addins/<Extension>.Addin/` (`<Extension>` is
`technical.pyrevit.extension`).

| Output | Notes |
| --- | --- |
| `<Extension>.Addin.csproj` | SDK-style, `UseWPF`, nullable, `LangVersion latest`, no `PackageReference`, so restore works offline. `RevitVersion` (default 2026) picks the Revit API folder and the target framework; `RevitInstallDir` defaults to `C:\Program Files\Autodesk\Revit <year>\`. `RevitAPI.dll` and `RevitAPIUI.dll` are referenced with `Private=false`. Output goes to `bin\<Configuration>\<year>\`. |
| `App.cs`, `HelloCommand.cs`, `SummaryWindow.cs`, `ThemeResources.cs` | `IExternalApplication` adds a ribbon button; the `IExternalCommand` is `[Transaction(TransactionMode.ReadOnly)]` and creates no Transaction: no document -> TaskDialog, family document -> TaskDialog, otherwise it counts non-template views and shows a themed window. Namespace `<Ns>.Addin` (`technical.namespace`, PascalCase). |
| `<Extension>.Addin.addin` | Application manifest; `<Assembly>` is `<Extension>.Addin\<Extension>.Addin.dll`, relative to the folder the manifest is installed in. |
| `Resources/Theme.xaml`, `Controls.xaml`, `SummaryWindow.xaml`, brand symbol PNGs, 32 px and 16 px ribbon icons | Theme and Controls are the UI kit's dictionaries (same `<Ns>.*` keys). Embedded in the DLL as text and parsed at run time with `XamlReader`, the loader the pyRevit kit uses, instead of markup compilation: no WPF XAML compiler pass, and packaged fonts resolve by relative URI against the folder that holds the DLL (`fonts/<family>/`, copied beside it by the build). The ribbon icons are drawn by the engine, deterministically. |
| `README.md`, `.gitignore` | Build and install steps, supported versions, what is unverified; `bin/` and `obj/` ignored. |

**Stable identity.** `AddInId` is `uuid5(<foundation constant>, technical.workspace_id + ":revit-addin")`
(`formwork_engine.adapters.revit_addin.FOUNDATION_ADDIN_NAMESPACE`), uppercase. It depends on nothing a
rebrand touches, so re-rendering or changing `identity` never changes it; changing `workspace_id` does.
Assembly name, root namespace, `VendorId` (`technical.namespace`) and the manifest class name are technical
identity too. Display strings (product, company, window text, manifest `<Name>`) follow `identity`.

**Ribbon and pyRevit.** The add-in creates the tab named `technical.pyrevit.tab` and tolerates it already
existing. Its panel is `<sample_panel> Add-in`, so it never matches the pyRevit panel on a same-named tab.
If the tab exists but the API cannot address it, the panel falls back to Revit's Add-Ins tab. Coexistence of
a pyRevit tab and a compiled add-in panel on one tab has not been seen in a live session.

**Supported Revit versions.** 2025, 2026 and 2027. Autodesk moved Revit 2025 and 2026 from .NET 8 to .NET 10
in the 2025.5 and 2026.5 updates (Revit 2027 is .NET 10), and an add-in built for one runtime does not load in
the other. The project chooses `net10.0-windows` for 2027 and, for 2025/2026, when the installed
`AdApplicationFrame.runtimeconfig.json` names `net10.0`; otherwise `net8.0-windows`. `-p:RevitTargetFramework`
overrides. Any other `RevitVersion` stops with `FWADDIN001`, a bad framework with `FWADDIN003`, a missing
Revit install with `FWADDIN002`. **Revit 2024 is excluded**: it hosts .NET Framework 4.8, whose reference
assemblies are not part of a default SDK install and would have to be downloaded, which the offline-build
rule forbids. The .NET 8 branch compiles only against a pre-update host and is untested here.

**Build evidence is not host evidence.** `tests/test_revit_addin_surface.py` runs `dotnet build` offline for
both shipped profiles against the Revit API installed on the machine (skipped with a stated reason when
`dotnet` or `RevitAPI.dll` is absent). The window's XAML was also rendered natively once in a throwaway
harness; that harness is not part of the suite.
A successful compile proves the code matches that API; it does not prove Revit loads the add-in, shows the
ribbon button, or runs the command. Every render reports `revit-addin.not-live-verified` (info) until a live
run is recorded, and `revit-addin.invalid-identifier` (warning) when `technical.namespace` or
`technical.pyrevit.extension` is a C# reserved word. All-users manifest locations changed in Revit 2027;
see [docs/memory/revit-2027.md](../memory/revit-2027.md) and the generated README.

### 8.4 Application starters (`python-app` and `web-app` surfaces)

Two opt-in surfaces, each standalone (no other surface required, none depends on Revit). Everything is `managed`,
under `apps/`. Both build their stylesheet with the shared `formwork_engine.adapters.web_theme` helpers (tokens as
`--<ns>-*` custom properties, then the same component rules as the HTML guide), so a button, badge or table
heading here matches the guide. The HTML guide's output is unchanged by that refactor.

**`python-app`: `apps/<namespace>-report/`.** A CPython 3.10+ standard-library CLI:
`python -m <namespace>_report report INPUT --output OUT.html [--title T] [--status-column C]`, run from the app folder
with `PYTHONPATH=src` (or `pip install -e .`, optional). `INPUT` is a CSV (header row first) or a JSON list of objects.
The output is one portable HTML file in the "report console" style: masthead with the inverse wordmark, a metric
strip (rows, columns, distinct statuses), the table (sortable-looking headers via CSS only, no script), status pills,
and a footer with the support link and a notices pointer.

| Output | Notes |
| --- | --- |
| `pyproject.toml` | PEP 621, setuptools backend declared but not needed to run; name `<namespace>-report`, no dependencies, console script of the same name, package data `theme.css` and `assets/*.svg`. Parsed with `tomllib` by the output checks. |
| `src/<namespace>_report/{__init__,__main__,cli,render}.py` | argparse CLI (exit 2 with a one-line message on bad input); `render.py` HTML-escapes every value from the input, embeds `theme.css` verbatim in a `<style>` element and the brand SVGs as data URIs when each is at most 256 KB (otherwise it copies them to `assets/` beside the report), and references no URL except the support link. |
| `src/<namespace>_report/branding.py` | Display name, short name, logo alt and support URL baked in from `identity` (the only file that carries them); package and command names come from `technical.namespace` and survive a rebrand. |
| `src/<namespace>_report/theme.css`, `assets/*.svg` | Generated stylesheet, brand wordmark (inverse) and symbol (light). No fonts are packaged: a report uses the token font stack and falls back to system fonts, because a single portable file should not inline font binaries. |
| `tests/test_report.py`, `sample.csv`, `README.md`, `.gitignore` | unittest suite (escaping, no external loads, status pills, CLI), a fictional sheet index, run instructions. |

**`web-app`: `apps/<namespace>-web/`.** A TypeScript starter that Node runs by stripping types, so there is
**no install step** (no `npm install`, no build). Requires Node 22.18+ (type stripping is on by default there;
22.6 to 22.17 need `--experimental-strip-types`). The TypeScript is erasable syntax only: no enums, namespaces,
parameter properties or decorators. Browsers cannot run TypeScript, so client code is plain JavaScript.

| Output | Notes |
| --- | --- |
| `package.json` | `"type": "module"`, `start` is `node server.ts`, `test` is `node --test`, no dependencies, `engines.node` `>=22.18`. |
| `server.ts` | `node:http` static server bound to 127.0.0.1 only, port from `PORT` (default 5173), serves `public/` through a fixed content-type map. Rejects non-GET (405 with `Allow: GET`), traversal (`..`, `%2e%2e`, encoded separators, backslashes, colons, dot-files, symbolic links that resolve outside `public/`) with 404. Every response sends `Content-Security-Policy: default-src 'self'` and `X-Content-Type-Options: nosniff`. Starts only when run directly, so tests import it. |
| `test/server.test.ts` | `node:test` and `node:assert`: ephemeral-port server, headers, loopback bind, traversal sent as raw request targets (fetch would normalize `..` away), method rejection, and a no-inline-script/style check on the shell. |
| `public/index.html`, `theme.css`, `app.js` | Branded shell (inverse wordmark band, a card with primary and secondary buttons, selectable chips, status badges, support footer). No inline script or style, which the CSP would block. |
| `public/assets/*.svg`, `public/fonts/<family>/*` | Brand SVGs; packaged fonts with their license files, referenced by `@font-face` in `theme.css`. |
| `tsconfig.json`, `README.md`, `.gitignore` | `tsconfig.json` is for editors only (`erasableSyntaxOnly`); type-checking needs the optional `npm install -D typescript @types/node`. |

**Checks.** `.toml` outputs must parse (`output.toml-invalid`; skipped on CPython 3.10, which has no `tomllib`).
`.ts`, `.js` and `.mjs` outputs are scanned for network loads: `import ... from "http(s)://..."` or
`"//..."`, dynamic `import("...")` and `fetch("...")` of the same shapes (`output.external-resource`). Loopback
addresses (`127.0.0.1`, `localhost`, `[::1]`) are exempt because the generated server tests call the server they
start. The scan is a guard, not a JavaScript parser.

**Evidence and gaps.** The engine's suite generates both profiles, runs the generated Python suite and CLI, and runs
`node --test` in the generated web app when a suitable Node is on PATH (skipped, with the reason, otherwise). Every
render reports `web-app.typecheck-not-run` (info): `tsc` is neither installed nor run, so a type error would not
be caught. There is no `python-app` verification diagnostic because the app does not touch Revit.

### 8.5 Web tool host (`web-host` surface)

Opt-in surface (`"web-host"` in `surfaces`) that requires `pyrevit-sample`: the host
lives in the extension that surface generates and the demo button joins its sample
panel. It is the HTML counterpart of the WPF kit (8.2) and does not need it. All
outputs are `managed`. Ported from the Rockwell `rgdt_web` library under ADR 0005
(R06); the WebView2 assemblies are **not** ported, see "Host assemblies" below.

| Output | Notes |
| --- | --- |
| `extensions/<Extension>.extension/lib/<namespace>_web/` | IronPython 2.7 package. Pure (importable under CPython): `bridge` (`expose`, `Bridge`, JSON dispatch with IronPython 2 text and byte hardening, an error envelope that carries a message and never a traceback), `session` (`ToolSession`: cancel flag, `run_chunked` with `progress` events), `log` (pyRevit output plus `%LOCALAPPDATA%\<namespace>\logs\web.log`), `compat` (`eid_int`, `eid`), `webview2_support` (assembly search, native-loader probe, navigation policy, plain-language messages). Needs WPF: `host` (`WebToolWindow`, `WebView2HostError`). Importing the package loads nothing. |
| `.../<namespace>_web/ShellWindow.xaml` | A bare window around the `WebView2` control; standard OS chrome, the page carries the branding. |
| `.../<namespace>_web/assets/bridge.js`, `tool-ui.js`, `tool.css`, `symbol-light.svg`, `fonts/<family>/` | Served at `https://<namespace>-assets.test/`. `bridge.js` is `window.<namespace>` (`call`, `on`, `off`, `close`, `hosted`); `tool-ui.js` is `window.<namespace>ui` (`setState`, `setProgress`, `copyText`, `wireCopyButtons`, `startCountdown`, `primaryAction`, usage badge). `tool.css` is built from the firm's tokens by `web_theme` (tokens as `--<namespace>-*`, the shared button and badge rules) plus the shell: tool header with the firm symbol, numbered steps, metrics, filter field, fixed table, progress, log, notices, action row. Packaged fonts and their licenses are copied here. No file contains an absolute URL except the two virtual hosts. |
| `.../<Panel>.panel/WebToolDemo.pushbutton/` (`bundle.yaml`, `script.py`, `tool.html`, `tool.js`, light and dark 96 px icons), `docs/toolbar/tools/web-tool-demo.md` | Read-only M5 report console. It validates the document first (no document: message and quiet exit; family document: alert), then `init_data` counts views and view templates by `View.ViewType` (one `FilteredElementCollector`, no transaction). The page shows four metrics, a fixed table with status pills, a client-side filter, an activity log and a **Copy summary** action that uses the browser clipboard API; there is no export and nothing writes. Its entry appears in `docs/toolbar/spec.d/foundation-sample.md` only when the surface is enabled; without it that fragment is byte-identical to before. |

**Host assemblies: what was found, and the design that follows.** The Rockwell
library vendors version-matched WPF wrappers (`Microsoft.Web.WebView2.Wpf.dll` and a
native loader, one folder per Revit-bundled Core version) and selects one at run
time. Its README gives four reasons: (1) Revit loads its own Core, so a vendored Wpf is
paired with whichever Core assembly resolution hands it, and a mixed pair throws
`MissingMethodException`; (2) the Wpf that Revit 2024 bundles (SDK 1.0.1343.22) is
broken against its own Core; (3) Revit 2022 and 2023 ship no WebView2 at all; (4)
deployed DLLs must not be locked, hence a shadow copy. Checked on this workstation
(offline, by file inspection and .NET reflection; nothing was downloaded or run in
Revit):

| Revit | Core, Wpf, WinForms version | `WebView2Loader.dll` |
| --- | --- | --- |
| 2024 | 1.0.1343.22 | only in `runtimes\win-x64\native\` |
| 2025 | 1.0.2045.28 | beside `Revit.exe` and in `runtimes\win-x64\native\` |
| 2026, 2027 | 1.0.2478.35 | beside `Revit.exe`, in `runtimes\win-x64\native\` and in `Sentiment\` |

- **Every installed Revit 2024-2027 ships the Core and Wpf assemblies**, in the folder
  of `Revit.exe`. A running Revit 2026 on this workstation had Core, Wpf and
  `WebView2Loader.dll` loaded from that folder, so Revit itself uses them in process.
  The generated host references those files and finds the folder at run time from the
  running process (`Process.MainModule.FileName`), never from a written path.
- **The source's PATH change for Revit 2024 is unnecessary.** Its README says 2024
  ships no loader, which is true of the program folder itself. The managed Core also
  probes `runtimes\win-<arch>\native` relative to its own location (IL of
  `CoreWebView2Environment.LoadWebView2LoaderDll` and `GetProcessArchSubFolder` in both
  1.0.1343.22 and 1.0.2478.35; 2478 also tries the app-domain base and running-DLL
  folders), and 2024 ships a loader there. The host changes nothing about `PATH` and
  only logs where the loader is.
- **The 1.0.1343.22 defect is real, and it has one location.** A MemberRef sweep of
  its Wpf assembly (264 resolve) leaves exactly one that does not: the 5-argument
  `CoreWebView2EnvironmentOptions` constructor, called from
  `CoreWebView2CreationProperties.CreateEnvironmentAsync`. The control reaches that
  method only when `CreationProperties` is set and no environment was passed to
  `EnsureCoreWebView2Async`. The Wpf assemblies of Revit 2025 and later are .NET builds
  that a .NET Framework harness cannot sweep; they are same-version pairs that Revit
  loads itself.
- **Design.** The host never sets `CreationProperties`. It creates the environment with
  `CoreWebView2Environment.CreateAsync(None, <user data folder>, None)` (a Core method
  present in every shipped version), marshals the result to the UI thread and passes it
  to `EnsureCoreWebView2Async`. That avoids the one broken path on 2024 and uses the same
  code on every release. No DLL is vendored, so there is no shadow copy, no version table
  and no pin list to maintain, and a Revit update changes nothing in Formwork. The
  user data folder is `%LOCALAPPDATA%\<namespace>\WebView2\<Core version>`: Revit
  releases that run side by side use different SDK defaults, which WebView2 rejects when
  they share one folder.
- **Loading.** `ensure_webview2_assemblies` keeps any Core or Wpf assembly Revit already
  loaded (the loaded one wins, as in the source), otherwise loads the file from the Revit
  folder, otherwise from the override folder. It logs each assembly's version and path and
  warns when the Core and Wpf versions differ. A failure raises `WebView2HostError` with a
  message naming the missing files and the folders searched; the tool's `main` shows it
  and exits. An initialization failure or the 20-second watchdog shows a message that
  names the Edge WebView2 Runtime as the likely cause.
- **Residual cases a firm handles itself.** (a) Revit 2022 and 2023 ship no WebView2:
  the firm obtains a matching Core and Wpf set (and the loader, beside them or under
  `runtimes\win-x64\native`) from the `Microsoft.Web.WebView2` package under its own
  license review, avoids SDK 1.0.1343.22, and points `<NAMESPACE>_WEBVIEW2_DIR` (the
  namespace in capitals) at the folder. Formwork ships and downloads nothing, and this
  surface is built and tested for 2024 and later. (b) The Evergreen WebView2 Runtime must
  be installed and not blocked by policy; a fixed-version runtime is chosen with
  `WEBVIEW2_BROWSER_EXECUTABLE_FOLDER`. (c) If another add-in loaded a different Core or
  Wpf first, that assembly wins; the log shows the versions. The pairing risk in the
  source's reason (1) is reduced (the host uses only the Core API plus
  `EnsureCoreWebView2Async`) but not removed.

**Security posture.** The page can load only from two virtual hosts, one per folder
(WebView2 maps a single folder to a host name): `https://<namespace>-tool.test/` for the
tool's own folder and `https://<namespace>-assets.test/` for the package's `assets`
folder. `.test` is reserved (RFC 6761); Microsoft advises against `.local` because it
can delay navigations. A mapping serves http and https, iframes and workers, and needs a
reload to change. The tool host is mapped `Deny` (nothing outside the page reads it);
the assets host is mapped `Allow` because the stylesheet's `@font-face` requests are CORS
fetches from the tool page's origin. A tool's folder is readable by that tool's own
origin, `script.py` included, so it must hold nothing secret.

- `NavigationStarting` and `FrameNavigationStarting` cancel anything that is not `https`
  on those two hosts (an anchored full-match pattern with a literal host and no port,
  user information or backslash, so a parser that disagrees with the browser gains
  nothing); `NewWindowRequested` is handled (no window), `DownloadStarting` is
  canceled, `PermissionRequested` is denied. The first three are required: if they
  cannot be attached the host closes the window rather than load the page.
- `WebMessageReceived` drops a message whose source is not an allowed address.
- DevTools, default context menus, status bar, zoom control, browser accelerator keys,
  autofill and password save are off (`allow_devtools = True` in a subclass is the
  developer switch).
- The demo page carries `Content-Security-Policy: default-src 'self'
  https://<namespace>-assets.test https://<namespace>-tool.test; base-uri 'none';
  object-src 'none'; form-action 'none'` and has no inline script or style, no inline
  handler, no `eval` and no markup built from data. The offline output check
  (`output.external-resource`) exempts exactly the two names
  `https://<namespace>-tool.test` and `https://<namespace>-assets.test`; any other
  address still fails.
- The user data folder is under `%LOCALAPPDATA%`, never beside `Revit.exe`.

**Bridge and session.** Requests are `{id, method, args | kwargs}`; replies are
`{id, ok, result}` or `{id, ok: false, error}`; events are `{event, data}`. Only methods
marked `@expose` and not starting with an underscore are callable.
`ToolSession.run_chunked` returns the shared result shape (`status`, `summary`, `counts`,
`log`, `items`) and emits `progress` events. WebView2 events are not reentrant, so a
cancel cannot arrive while one handler runs: `cancel` is honoured only by a tool that
returns to the message loop between chunks (the module says so). A tool that changes the
model keeps one short transaction per chunk, with rollback, and never holds one across
input; the demo has none.

**Not ported from the source.** Picking (`pick_point`, `pick_element`, `pick_elements`,
hide-while-picking `go_modeless` and `go_modal`), the page close-guard
(`swallow_escape`), `external_event.MarshaledCallable`, the vendored-DLL selection,
shadow cache and broken-SDK pin table, the `rgUI` motion primitives, `gate`, the grouped
check list, `countUp` and `reveal`, the Lucide usage icons (a text badge only, so no icon
notice is needed), and the M2, M3, M4, M6 and M7 scaffolds. The host supports those
families; Formwork does not ship a scaffold for them.

**Evidence and gaps.** `tests/test_web_host_surface.py` generates both profiles and
imports the pure modules under CPython (dispatch, error envelopes, non-ASCII round trip,
chunking and cancel, log, assembly search, navigation policy), checks every file for
external URLs, inline code and foreign names, asserts the design on the source of
`host.py` (no fixed Revit path, no `CreationProperties`, policy handlers present and
attached before navigation), runs `bridge.js` and `tool-ui.js` against stubs in Node when
it is present and, on a machine with Revit installed, finds Core, Wpf and a native
loader in every installed Revit 2024 or later. The page was also viewed in a browser
with a stub bridge. **Not verified**: any WebView2 window opened in Revit; the
IronPython delegate conversions (`System.Action[Task]`, `ContinueWith`), event attach through `__iadd__`, and the
`EnsureCoreWebView2Async` overload under IronPython 2.7; the `.test` mapping, the `Deny`
and `Allow` access kinds, the CSP and clipboard writes inside WebView2; Escape handling
with browser accelerator keys off; the Wpf assemblies of Revit 2025 and later; behavior
next to other add-ins' Core versions; the per-Core-version data folder. Every render
reports `web-host.not-live-verified` (info) until a live run is recorded.

## 9. Notices, attribution, and provenance

- Foundation code is MIT (copyright Rob Mintzes). Every workspace receives a
  managed `THIRD_PARTY_NOTICES.md` listing the foundation license and each
  packaged font with its license file, independent of branding.
- The BIMxBert name and marks are **not** licensed under MIT **[confirmed]**;
  `profiles/bimxbert/NOTICE-brand.md` says so and is copied into BIMxBert
  workspaces. Adopters replace the profile.
- Tool `__author__` and bundle `author` use `identity.author`. Original
  contributor attribution lives in provenance and release records, never in
  rebranded output, and rebranding cannot remove notices (they are not derived
  from display identity).
- Imported items are recorded in [RELEASE_RECORD.md](RELEASE_RECORD.md) with
  source, hash, changes, license, and verification.
- Rob-authored Rockwell repository material may be ported under the scoped
  permission in [ADR 0005](../decisions/0005-source-extraction-and-assets.md);
  each port is recorded in the release record with source commit, files, and
  changes (R05, the `ui-kit` surface; R06, the `web-host` surface). Earlier code was written
  from concepts only and is unchanged.

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
| Live host | - | `formwork verify revit` on Revit 2026 + pyRevit 6.5.5 + IronPython 2.7.12, Windows 11 **[proposed combination]**, recorded in `docs/verification/MATRIX.md` |

Host support is claimed only after the last row has recorded evidence.
