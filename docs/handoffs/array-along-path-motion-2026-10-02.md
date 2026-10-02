# Array Along Path / BIMxBert motion pilot

Branch: `robmintzes/bimxbert-array-motion`.
Draft PR: [#10](https://github.com/robmintzes/formwork/pull/10).

## State

- Ported source geometry and deterministic SVG preview from `design-technology`
  into an opt-in `array-along-path` generator surface; BIMxBert enables it.
  Author/marks/fonts/theme come from the firm profile. Source provenance is R07
  in `docs/product/RELEASE_RECORD.md`; no external source library is needed.
- Generated ribbon placement: BIMxBert / Elements / Array Along Path.
  The local sandbox `D:\Live Check\BIMxBert` now includes the tool and passes
  static workspace validation. Its existing inputs and generated files matched
  before the change; only the new surface was added. Original firm.json backup:
  `.logs/array-motion-live-firm-before.json`. pyRevit Reload remains a human step.
- HTML controls and preview use CSS/native Web Animations, with bounded stagger,
  mode-indicator travel, field reveal, re-roll feedback and explicit path tracing.
  Markup revision: compact title/header with logo at upper right; adjacent Close
  and Place copies actions; animated Orientation checkmarks; original outline
  and label fixed at its actual anchor. By count means new copies and includes
  the starting offset copy whenever it is a new location; actual source overlaps
  are excluded. Slider default 1–50 with adjustable, persisted maximum up to 2000.
  The ribbon launcher uses static 32px light/dark icons. `docs/design/motion.md`
  explains the platform boundary and Motion/GSAP recommendations.
- Browser callbacks only accept plain placement data. The HTML closes before
  copying/rotating inside the original pyRevit command context. One transaction;
  finite/count validation, document/source staleness checks, actual commit status,
  rollback on errors, and shared generated result dialog after completion.
- Result text now states copies placed along the path length, distribution,
  side offset, orientation, optional variation, source overlaps and Undo in plain
  language. No raw settings dictionary is displayed.
- Shared `selection_guide.SelectionGuide` in the generated UI kit wraps native
  picks with firm-local fonts/colors/wordmark, tool/step labels and Finish/Esc
  instructions. It docks against the active UIView with DPI conversion and closes
  on cancellation/errors before the preview or transaction. Stock prompt fallback
  preserves selection if the branded window cannot load. Source provenance is R08.
  Authoring guidance requires this component for all future tools with native picks.
- Browser review at 1280/768/390: input changes, invalid-input gating, seeded
  scatter, simulation, no horizontal overflow, keyboard pane sizing/persistence,
  reduced motion. No JavaScript errors after adding the local favicon.
- Tests in `tests/test_array_along_path.py`: two-profile rendering, concrete spec,
  repeat render, dependency requirements, seeded math, 2000-station cap, anchor
  exclusion, malformed/non-finite plans, transaction commit/rollback using mocks.
- Verification: 319 repository tests, 11 extension tests and 18 MCP server tests
  passed. The MCP suite used an isolated environment with its declared MCP 2
  dependencies; the workstation's global MCP 1 package could not collect it.
  All root validators, US English check and diff whitespace check passed.

## Open

1. Reload pyRevit in the local sandbox and test the revised behavior:
   guide sits below ribbon/view tabs in light/dark canvas and at target DPI;
   step changes and Escape cleanup; preselected path starts with source step;
   count + offset includes the first copy beside the unchanged original;
   the result states readable settings and actual placed count.
2. Complete the disposable-project checks:
   select contiguous detail/model curves; select a point-located family/group;
   match count/spacing/offset/alignment/scatter to preview; original unchanged;
   Undo once restores the pre-run model. Repeat with a copy/rotation failure.
3. Rob's screenshots show committed Array Along Path runs and the prior result
   dialog. Revised count/results/guide behavior, rollback and Undo remain unverified
   inside Revit. The tool remains **sandbox**, not production-verified. Cylance
   blocked the native PowerShell screenshot harness; no native guide render is claimed.
4. Revit 2024/2025/2027 and the embedded CPython engine have not run this tool.
   Python 2/3 syntax checks and mock tests cannot establish live compatibility.
5. Preview is XY plan projection. Non-horizontal path geometry needs particular
   scrutiny in Revit. Mesh hull and bounding-box fallbacks are disclosed.
6. If the workflow must keep its window open during placement, add a genuinely
   asynchronous ExternalEvent lifecycle. Do not reintroduce direct transactions
   in WebMessageReceived or block Revit waiting for an ExternalEvent.

## Incremental Edit Log

- 2026-10-02: Registered the tool contract before creating templates. Started
  from current origin/main on Rob's task branch and installed local branch guards.
- 2026-10-02: Extracted source geometry/preview under the existing scoped reuse
  permission; removed source bootstrap, marks, fonts and dependencies. New adapter
  generates theme, original icons, offline assets, tool spec and guide.
- 2026-10-02: Changed browser execution to plan submission with post-close writes;
  added bounded validation, stale-source rejection, failure preprocessing and
  commit-status checks. Preview and transaction both exclude anchor duplicates.
- 2026-10-02: Added contextual native motion, responsive panes, keyboard access,
  resize persistence and reduced-motion handling. Explicit Preview motion opt-in
  supports design review when the user's system disables animation by default.
- 2026-10-02: Browser review caught shared main/footer width limits and camera
  fitting after resize; fixed both. Validator review caught duplicate tab metadata
  in the new fragment; retained only the Elements panel/tool entry.
- 2026-10-02: Added 9 focused regression tests and verified local sandbox generation.
  Revit placement/Undo remains outstanding; no project was modified during review.
- 2026-10-02: Full repository/extension/MCP suites passed. Captured desktop,
  tablet, mobile and scatter browser screenshots and a short motion demonstration.
- 2026-10-02: Final visual review fixed primary-action arrow/count spacing;
  reran the 9 focused tests, sandbox validation and browser checks. Committed
  responsive screenshots in `docs/verification/array-along-path/`; the local
  demonstration video is `output/playwright/array-along-path-motion.webm`.
- 2026-10-02: Applied Rob's two screenshot markups. Removed the extra tagline,
  moved the logo/title/Close, added a fixed Original overlay and animated native
  checkboxes. Changed count distribution to new copies after the path start;
  range selector, typed-count expansion, persistence and overlap reporting.
  Updated math checks passed (9 focused tests); Edge review passed at 1280/768/390,
  including 2000 copies, keyboard operation and reduced motion. Refreshed evidence;
  new local video `output/playwright/array-markups-motion.webm`. Sandbox regenerated.
  User screenshots establish preview review, not successful placement/rollback/Undo.
- 2026-10-02: Applied the subsequent live-run screenshots. Replaced the internal
  settings dump with readable execution evidence; count includes the start when
  offset/scatter creates a new location, while retaining N new copies at the source
  anchor. Added a shared brand-aware selection guide and generator dependency,
  resource/lifecycle/DPI tests and authoring rules. Edge checked 1/24/2000 new
  copies with/without side offset; first offset position matches spacing mode,
  original remains fixed, and console has zero errors/warnings. Sandbox regenerated.
  Native appearance capture was blocked by Cylance; live guide/Undo checks remain.
- 2026-10-02: All 325 repository tests passed; 15 Array/guide tests passed after
  final wording edits. Root validators, US English and diff checks passed; the
  local Revit sandbox validates with no render drift.
- 2026-10-02: Generated extension testing exposed an overbroad MCP read-only
  check that scanned all toolbar tools. Restricted it to bridge/startup code;
  added combined Array/bridge coverage and a negative injected-bridge-transaction
  case. All 32 Array/guide/MCP tests and 23 generated extension tests pass.
