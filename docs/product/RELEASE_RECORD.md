# Release record - imported material

Every item that entered this repository from outside its own authored code.
Updated September 30, 2026 (America/New_York). See
[ADR 0005](../decisions/0005-source-extraction-and-assets.md).

## R01 - BIMxBert marks (profiles/bimxbert/assets/*.svg)

- **Source:** `BIMxBert Design System (1).zip`, supplied by Rob Mintzes;
  ZIP SHA-256 `A14229EA785966CFB3C36D44CDA120F7F03577CFB282478DA58A9C0A301956E3`.
  Authored by Rob Mintzes with Claude Design.
- **Selected files and original SHA-256:**

  | Original | SHA-256 | Imported as |
  | --- | --- | --- |
  | `exports/illustrator/BIMxBert-wordmark-light.svg` | `e99892184f402a75b27075b17579e408371020953f79b5a1690b9c45993a7102` | `wordmark-light.svg` |
  | `exports/illustrator/BIMxBert-wordmark-inverse.svg` | `7ae94f8091610a941fd6ed57118678ccaeec35c6635d0afe90e01d98edce3579` | `wordmark-inverse.svg` |
  | `exports/illustrator/BIMxBert-symbol-light.svg` | `6ec58242e91ad13ae3a05f43742ae804767398d3739f7762d325a084f7075e56` | `symbol-light.svg` |
  | `exports/illustrator/BIMxBert-symbol-inverse.svg` | `3d6e4948adda0663ce291abab0c869d5cf30bd26ae1b03478531a88bc3fee2d2` | `symbol-inverse.svg` |

- **Changes:** removed the embedded `<metadata>` C2PA/Content Credentials
  manifest and its namespace declaration; paths and fills unchanged. PNG
  variants were rasterized from the cleaned SVGs with headless Microsoft Edge
  (wordmark 480x202, symbol 240x160, transparent background).
- **Release scope / license:** Rob's own brand, approved for this public
  repository on 2026-09-30. **Not MIT-licensed**; see
  `profiles/bimxbert/NOTICE-brand.md`.
- **Verification:** well-formed XML; engine SVG safety checks pass; rendered in
  browser and native WPF specimens.

## R02 - BIMxBert token values (profiles/bimxbert/tokens.tokens.json)

- **Source:** same ZIP, `themes/bimxbert.css` and `tokens/scale.css` (values
  only: neutral and brand ramps, status colors, type scale, spacing).
- **Changes:** transcribed into DTCG 2025.10 structured data; semantic roles
  re-mapped to the foundation contract (`color.action.*` added). WPF and CSS
  now share one value per token (the export's WPF dictionary was 2 DIP smaller).
- **License:** factual values from Rob's design system; covered by the
  repository MIT license as data, while the BIMxBert brand itself remains
  reserved.

## R03 - Fonts (profiles/bimxbert/fonts/)

Downloaded 2026-09-30 with Rob's approval. All SIL Open Font License 1.1.

| Family | Source | Files (SHA-256) |
| --- | --- | --- |
| Barlow Condensed | `https://raw.githubusercontent.com/google/fonts/main/ofl/barlowcondensed/` | Medium `262bd143292ce479ee0cd09a42b47ab173fca8e9c6eb5ed0b5c8a845bc371d17`; SemiBold `7b619d14bc2327509a9ef32b0890f709626f7ecc9ff61191c2a4314c5499d2d9`; OFL.txt `186d750eb496a4c17a76385f82be6aea2ac1cf2de074a811d63786cf374ea73f` |
| Geist | `https://github.com/vercel/geist-font/releases/download/v1.7.2/geist-font-v1.7.2.zip` (zip SHA-256 `7fc800d2ac6b92844895196e5041aca55d814c15db70c44f79b3b83ab82b04e2`) | Regular `5c8968eafb98a4c4f47033daf29e38e284a6f2a82eb017d171ab040fe7c4b615`; Medium `0090e004725f6f64b841715b4167920580f883fcf9b67fc6d744089103fec101`; SemiBold `612ec98df33935354f39e81e54101656961ab6e5549f64b63eb57868ba7bab8d`; OFL.txt `c683bfbcc7e087f5d37a54ef628f10387c451a83ddc459b151403a164ac46c90` |
| Geist Mono | same release zip | Regular `42d8ad2e610238e64e8abfcde3037c63f7850a73928742b7ab7229d897bcb155`; Medium `90b15711dc3779b2e64e8aff5228154dd019a90bce4947549c4a8a8a43f2ac25`; OFL.txt (same text as Geist) |

- **Changes:** none (static TTF instances copied byte-for-byte).
- **Verification:** typographic family names read from the `name` table
  (`Barlow Condensed`, `Geist`, `Geist Mono`); fonts resolve offline in
  headless Edge and in native WPF via relative font URIs.

## R04 - Quillmoor Studio profile (profiles/quillmoor/)

Independently authored for this repository on 2026-09-30; fictional firm, no
external source. Marks are simple vector drawings plus SVG text set in
Georgia (a system font, not packaged). MIT with the rest of the repository.

## R05 - Rockwell tool UI kit (`ui-kit` surface)

Ported 2026-09-30 under Rob Mintzes's scoped permission (ADR 0005). Rob authored
the source. Written into `formwork_engine/adapters/ui_kit.py`,
`formwork_engine/adapters/wpf_common.py`, and `formwork_engine/templates/ui_kit/`.

- **Source repository:** Rockwell Group `design-technology`, commit
  `96fbafeada60d3c62b632b8d8014242cb9ef2fd9` (working tree had only untracked
  files; none of the sources below were modified).
- **Source files used** (paths below `DT Tools/DT Tools.extension/` unless
  noted; SHA-256):

  | Source file | SHA-256 | Became |
  | --- | --- | --- |
  | `lib/rgdt_ui/bootstrap.py` | `284800bc20af95ecc9a7fdc3e6ca604ccf6237d9d24ca8bc78427d74e10780fb` | `bootstrap.py` (rewritten, see below) |
  | `lib/rgdt_ui/result_model.py` | `1ee754afa56bcc44c4fe52ed1f9c2ea3ce6b382c26200bb0d6bacc27ff149a19` | `result_model.py` (near-verbatim) |
  | `lib/rgdt_ui/result_dialog.py` | `6f0ffeb17914af22de4a22b98eb4e54d3921f0ec92abc94761b7daee54ec73d1` | `result_dialog.py` |
  | `lib/rgdt_ui/RgdtResultDialog.xaml` | `2fa4fd09a4c9c816c0f40849a45ca8b0f590bfeafa1ed785bfb6ea84b28b7bc8` | `ResultDialog.xaml` |
  | `lib/rgdt_ui/chooser_dialog.py` | `bf8c2c33af703dfc87a46f68878d49dc0a418eebbc33cd78a3cccb62a88813a3` | `chooser_dialog.py` (`normalize_options` unchanged in behavior) |
  | `lib/rgdt_ui/RgdtChooserDialog.xaml` | `6b4ae684b4d0e3f2f36c3e90ffcb165afcc4b3b6ab1dd80365eda31b6bab77d4` | `ChooserDialog.xaml` |
  | `DT Tools.tab/Template.panel/Match Extents.pushbutton/selection_dialog.py` | `9475133c1abc6356076486967f910cb22d01a8e0d1118eb1e686e6092c95146e` | `selection_dialog.py` (generalized to M2-lite) |
  | `DT Tools.tab/Template.panel/Match Extents.pushbutton/RgdtSelectionDialog.xaml` | `0346fbc172a26f54781cd82746b561444aa9165aad3b8385d390c26c7f2dd8a3` | `SelectionDialog.xaml` |
  | `lib/rgdt_ui/RGDT.Icons.xaml` | `baea07c9c3aa08eca71b7f1328425a634774d2cd266554385f22aeff2a96e7e7` | `Icons.xaml` (geometry unchanged, re-keyed) |
  | `lib/rgdt_ui/RGDT.Controls.xaml` | `e9811a1c44221fe8b69109f51acc45b8b149c0f0872dfd06bb8454a5cfe451a8` | extra styles in `Controls.xaml` (subset, re-derived from tokens) |
  | `lib/rgdt_ui/RGDT.Theme.Light.xaml` | `f49bedee592643aba96fe33119f19f4274d293baaa7eb71ac61b95846441d78c` | structure only; values come from the firm's tokens |
  | `lib/rgdt_ui/tests/test_result_model.py`, `test_chooser_dialog_contract.py`, `test_result_dialog_contract.py` | `7330e234...`, `4301c023...`, `5e88d552...` | concepts adapted into the generated `test_ui_kit_contract.py` and `tests/test_ui_kit_surface.py` |
  | repository `docs/design/rgdt/tool-ui-modules.md`, `component-recipes.md` | `caa46c29...`, `9b83f701...` | module families, size classes, button order, usage-badge wording, transaction rule |

- **Neutralization and rewrites:**
  - `Rgdt`/`rgdt`/`RGDT` identifiers became the firm namespace: XAML keys use
    `pascal(technical.namespace)` (`<Ns>.Titlebar`, `<Ns>.Color.Surface.Default`),
    the Python package is `technical.namespace + "_ui"`. Window and class names
    lost the prefix (`ResultDialog`, `ChooserDialog`, `SelectionDialog`).
  - The source's flat token names (`SurfaceDefault`, `TextPrimary`, `FsBody`) are
    replaced by the foundation's generated token keys; the source's hand-written
    light theme is gone. Controls reuse the specimen's styles and shape rules
    (`wpf_common`), so appearance choices (button shape and fill, badge style,
    label case) drive the dialogs.
  - Font registration (`register_fonts`, a shared fonts folder outside the
    extension) is replaced by relative font URIs in `Theme.xaml` resolved through
    the parser's `BaseUri`; packaged fonts are copied into the extension.
  - Titlebar mark: the source's vector initial mark is replaced by the firm's
    packaged `symbol-inverse.png`, set from `bootstrap.set_brand_mark`.
  - Implicit-relative imports became package-qualified imports with
    `from __future__ import absolute_import`; the `ModuleNotFoundError` guard in
    the package `__init__` was removed (Python 3 only name); the package imports
    nothing that needs WPF.
  - The result dialog honours its countdown only for the `one-time` usage; the
    selector gained `tool_name`, `eyebrow` and `usage` arguments in place of
    hard-coded Match Extents text and uses one list model for single and multi
    selection; every dynamic caption goes through label-case helpers.
  - New: control families not in the specimen (callouts, progress, steps, stat
    tiles, hairline, section) re-expressed against firm tokens; the demo button,
    its docs and icons; the generated contract test.
- **Exclusions:** IvyPresto, Proxima Nova, Auger Mono, Cartograph (Adobe or
  office-licensed); Rockwell and RGDT names, logos, the initial-mark vector, the
  wordmark and brand-header XAML; the WebView2 host package (`rgdt_web`) and its
  DLLs (deferred, backlog B20); internal paths and deployment destinations;
  project and client data and fixtures; `check_theme.py` (a source-repo linter
  for its own theme keys).
- **License notice:** `RGDT.Icons.xaml` carried Lucide geometry. Lucide is ISC
  (portions MIT from Feather); the license texts live in
  `formwork_engine/resources/LUCIDE_LICENSE.txt` and are added to every
  workspace's `THIRD_PARTY_NOTICES.md` when `ui-kit` is enabled. Code is MIT with
  the rest of the repository.
- **Verification:** `tests/test_ui_kit_surface.py` (key resolution against the
  generated dictionaries, typo-catching negative test, no source names in any
  generated kit file, IronPython syntax guard, stubbed import of every module,
  foundation validators, repeat render is a no-op, appearance propagation) and
  the generated `test_ui_kit_contract.py` in both profiles. Native WPF renders of
  every dialog and a control gallery for both profiles are in
  `docs/verification/foundation-generator/ui-kit-*.png` (packaged Barlow
  Condensed, Geist and Geist Mono resolved through the `BaseUri` mechanism;
  Quillmoor uses system fonts). **Not run in Revit/pyRevit**: `WPFWindow`
  loading, `clr` references, event handlers and `Window.GetWindow(...).DragMove()`
  are unverified there.

## R06 - Rockwell web tool host (`web-host` surface)

Ported 2026-10-01 under Rob Mintzes's scoped permission (ADR 0005). Rob authored
the source. Written into `formwork_engine/adapters/web_host.py` and
`formwork_engine/templates/web_host/`.

- **Source repository:** Rockwell Group `design-technology`, commit
  `96fbafeada60d3c62b632b8d8014242cb9ef2fd9` (the working tree had untracked files
  only; none of the sources below were modified).
- **Source files used** (paths below `DT Tools/DT Tools.extension/lib/` unless noted;
  SHA-256):

  | Source file | SHA-256 | Became |
  | --- | --- | --- |
  | `rgdt_web/bridge.py` | `5bfe4875148f10679c1d1a65c7b5983c3c3314f0fbd52de39efa770039a82cab` | `bridge.py` (text and byte hardening kept; envelope no longer carries a traceback; request validation, `on_error` callback) |
  | `rgdt_web/session.py` | `53ee021c56c7140ff11c05aee72320950853577dba121bcbeb16efc937ef34b5` | `session.py` (`ToolSession`; same chunking and result shape; comments reduced to the corrected threading statement) |
  | `rgdt_web/log.py` | `3e0ca559b5f3970f8661ad87cea5281375122cf3aea0bb0678d21ecf2898f303` | `log.py` (firm-namespaced folder; truncation instead of rename and delete) |
  | `rgdt_web/RgdtWebView.py` | `1e7b030faf6009d895d79e2614891f35e05e4ac76ff7e51b00aeccc1de0bdef7` | `host.py` (rewritten, see below) |
  | `rgdt_web/RgdtWebViewShell.xaml` | `a87f5b28c208c65a3ebb1cd788076b258d6f5e16c5553fa8b6f8e5c3363ff7f1` | `ShellWindow.xaml` |
  | `rgdt_web/assets/rgdt-bridge.js` | `291cbbaeef3bc11e8bacc5a0dbeb47b1b1d5ff6bab7b18b45cf37bda5be6650b` | `assets/bridge.js` (plain-browser detection, positional arguments, no traceback field) |
  | `rgdt_web/__init__.py` | `da723f88edad86c296ce866098f87b046bb889e2dd16d136b6f53c584432b5b4` | concept only: the package `__init__` loads nothing instead of swallowing an import error |
  | `rgdt_web/dlls/README.md` | `c7d8b1317c7d478df501d4e1c879bf2c5441b266c8c714a06d68436bd8062ca5` | read for the reasons the source vendors wrappers; nothing copied (see section 8.5) |
  | `rg_compat.py` | `1f10f0e7c21c81f575188d915607e699258303dd5917dc3506a191607c76a503` | `compat.py` (`eid_int`, `eid`, near-verbatim) |
  | `rgdt-design-system/rgdt-ui.js` | `3311076af50ebfd10461a136e7791c65a899565b8dd2dee885547ef762dabbc3` | `assets/tool-ui.js` (lifecycle state, progress, copy, countdown, `primaryAction`, usage badge; the rest not ported) |
  | `rgdt-design-system/rgdt-components.css` | `d30c76c9674f700c3608306460a520df88a1682fc0ca9768144723994b6e95b2` | structure and class roles only; `assets/tool.css` is re-derived from the firm's tokens |
  | `rgdt-design-system/specimens/m5-report.html`, `m5_report_host.py` | `abd8e7bcfef071ebcf3ba59a0423d63b5118a8e8637bb89438a60e0d2ecf877a`, `e138e93d1812dec03dca7d84ad6741436c1d176689ad352cb773e75633def303` | layout and behavior of the report console (`tool.html`, `tool.js`); none of its fake data or text |
  | `DT Tools.tab/Template.panel/View Templates.pulldown/CopyViewTemplateSettings.pushbutton/script.py` | `3b7681d5dac3ee748da34c08c968b84ca2d9e74e09426656005c56b95929e345` | the `init_data` and window-subclass pattern only; its write behavior is not ported |
  | `rgdt_web/external_event.py` | `111198d09633697364472e3133bf2ceef6a99d0e5efbf2b1f37bf4c1294374ec` | read; not ported (no picks or worker threads in the demo) |
  | repository `docs/design/rgdt/tool-ui-modules.md` | `caa46c296cdc5d203efdd6560aa6969e72b05b3cff83e45792cf4237c01bcc98` | module families, size classes, action-row order, lifecycle states, button morph, platform rubric |

- **Neutralization and rewrites:**
  - `Rgdt`/`rgdt`/`rg-` identifiers became the firm namespace: Python package
    `technical.namespace + "_web"`, JavaScript globals `window.<namespace>` and
    `window.<namespace>ui`, custom properties `--<namespace>-*`, log folder
    `%LOCALAPPDATA%\<namespace>\`. Class and file names lost the prefix (`WebToolWindow`,
    `ShellWindow.xaml`, `bridge.js`, `tool-ui.js`, `tool.css`); CSS classes are unprefixed
    (`.tool-header`, `.step`, `.metrics`, `.tbl`, `.log`, with the shared `.btn` and `.badge`).
  - The source's `rgdt.local` and `rgdt-assets.local` virtual hosts became
    `<namespace>-tool.test` and `<namespace>-assets.test`. The source mapped the design
    system folder and the assets folder and navigated tools as `file:///`; the host maps
    the tool's own folder and the package assets folder and navigates to `https://`, and
    refuses every other address.
  - `host.py` is a rewrite, not an edit. The vendored-DLL selection, shadow cache,
    broken-SDK pin table and `PATH` change are gone (the host uses Revit's own assemblies
    and creates the WebView2 environment itself, section 8.5). New: the navigation,
    new-window, download and permission policy, a source check on incoming messages, a
    fail-closed policy attach, the per-Core-version data folder, `WebView2HostError`,
    assembly search in `webview2_support.py`. Kept: the modeless window pumped by a
    `DispatcherFrame`, `show_dialog` redirected to `show`, Escape closing the window, one
    guarded reload after a renderer failure, the pre-initialization message queue and the
    initialization watchdog (message text rewritten).
  - The source's shared design-system fonts and Adobe typefaces are replaced by the
    firm's packaged fonts, resolved through `tool.css`.
  - Inline `style`, `onclick` and `onerror` fallbacks in the source pages are gone; the
    page loads scripts and styles by URL under a strict CSP meta tag.
  - New: the `Web Tool Demo` button (script, page, icons, document) and its spec entry;
    `webview2_support.py` and the log, bridge and session tests.
- **Exclusions:** every WebView2 binary (`rgdt_web/dlls/`, including the vendored Wpf,
  Core and `WebView2Loader.dll` folders, none copied, none downloaded); IvyPresto,
  Proxima Nova, Auger Mono, Cartograph (Adobe or office-licensed) and the design-system
  font folder; Rockwell and RGDT names, wordmarks, initial marks and logos; internal
  paths (`G:\...`, `D:\design-technology`) and the `%LOCALAPPDATA%\RGDT` folders (a
  firm-namespaced folder replaces them); project and client data, including the
  specimen's fake sheet paths; Lucide icon geometry (the usage badge is text only);
  the picking primitives, `external_event.py`, the page close-guard, `rgUI` motion
  primitives, `gate` and the grouped check list.
- **License notice:** nothing third-party was added: no Lucide geometry, no vendored
  binary. Code is MIT with the rest of the repository.
- **Verification:** `tests/test_web_host_surface.py` (both profiles generated; pure
  modules imported under CPython and exercised: dispatch, unknown method, exceptions as
  message-only envelopes, non-ASCII round trip, chunking and cancel, log, assembly search
  and navigation policy; generated files checked for external URLs, inline code, foreign
  names and ASCII; design assertions on `host.py`; `bridge.js` and `tool-ui.js` run
  against stubs in Node; Core, Wpf and a native loader found in every installed Revit
  2024 or later; foundation validators; repeat render is a no-op; fragment byte-identical
  without the surface). The page was rendered in headless Edge with a stub bridge for both
  profiles. Offline inspection of the Revit 2024-2027 WebView2 files is recorded in
  section 8.5. **Not run in Revit/pyRevit**: no WebView2 window has been opened, the host
  class has not been imported under IronPython, and the IronPython delegate conversions
  and the WebView2 policy handlers are unverified there.

## Not imported

Rockwell Group `design-technology` repository: beyond R05 and R06, reference only
(ADR 0005). From the BIMxBert ZIP: React/JSX components,
provisional XAML, uploads (RGDT sources), PDFs, exploratory boards, and
`support.js`.
