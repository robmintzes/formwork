# Array Along Path / BIMxBert motion pilot

Branch: `robmintzes/bimxbert-array-motion`.

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
  The ribbon launcher uses static 32px light/dark icons. `docs/design/motion.md`
  explains the platform boundary and Motion/GSAP recommendations.
- Browser callbacks only accept plain placement data. The HTML closes before
  copying/rotating inside the original pyRevit command context. One transaction;
  finite/count validation, document/source staleness checks, actual commit status,
  rollback on errors, and shared generated result dialog after completion.
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

1. Reload pyRevit in the local sandbox and test with a disposable project:
   select contiguous detail/model curves; select a point-located family/group;
   match count/spacing/offset/alignment/scatter to preview; original unchanged;
   Undo once restores the pre-run model. Repeat with a copy/rotation failure.
2. Record live evidence. The new tool is **sandbox**, not production-verified.
   The previous live Web Tool Demo result verifies the host, not this write tool.
3. Revit 2024/2025/2027 and the embedded CPython engine have not run this tool.
   Python 2/3 syntax checks and mock tests cannot establish live compatibility.
4. Preview is XY plan projection. Non-horizontal path geometry needs particular
   scrutiny in Revit. Mesh hull and bounding-box fallbacks are disclosed.
5. If the workflow must keep its window open during placement, add a genuinely
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
