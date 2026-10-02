# Motion in pyRevit tools

Array Along Path is the first BIMxBert motion pilot. The interaction surface is
HTML/CSS/SVG in WebView2; the Revit ribbon launches it with a static icon. Revit's
supported ribbon API exposes native controls, images, tooltips and contextual
help, not an HTML button surface. Keep animation inside the tool workspace.
See Autodesk's [ribbon API guide](https://help.autodesk.com/cloudhelp/2025/ENU/Revit-API/files/Revit_API_Developers_Guide/Introduction/Add_In_Integration/Revit_API_Revit_API_Developers_Guide_Introduction_Add_In_Integration_Ribbon_Panels_and_Controls_html.html).

## Choice for this pilot

Use CSS transitions for control states and native Web Animations for short,
interruptible geometry transitions. This keeps the generated extension offline
without adding a build step. A small `ToolMotion` adapter owns timing, cancellation
and reduced motion. If we outgrow it, the rest of the tool need not change.
The [Web Animations API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Animations_API)
supports timed DOM animation; CSS and the motion toggle both respect the user's
reduced-motion preference.
When system reduced motion is active, the user can explicitly choose **Preview
motion** for this window; a later system preference change clears that override.

| Approach | Where I would use it | Decision |
| --- | --- | --- |
| CSS + Web Animations | State changes, reveal, bounded SVG station movement | Implemented; adequate for this tool |
| [Motion JavaScript](https://motion.dev/docs/animate) | Spring gestures, independent transforms, more intricate interactive transitions | Preferred next dependency if actual complexity warrants it; React is unnecessary |
| [GSAP timelines](https://gsap.com/docs/v3/GSAP/gsap.timeline()) | Long, coordinated sequences with playhead control | Strong for demonstration choreography; more machinery than this operational tool needs |

Motion's mini implementation delegates HTML/SVG style animation to native browser
APIs; its hybrid implementation adds independent transforms, SVG path support and
sequences. This pilot uses the same underlying browser capability directly.
No claim of library-wide performance superiority is intended; measured interaction
cost and maintainability should decide a later switch.

## Behavior implemented

- The spacing/count indicator travels between modes; field labels crossfade.
- Small arrays move between preview positions and new stations enter with bounded
  stagger. Slider updates coalesce to animation frames. Above 150 stations, preview
  updates are immediate and no per-station animation is created.
- Expandable scatter controls reveal their fields; re-roll rotates its glyph and
  changes the deterministic seed. The same settings and seed reproduce placements.
- Trace path draws the polyline once and reveals stations. It is explicitly
  user-triggered; nothing runs continuously while the modeler works.
- Primary-action arrows and registration marks respond to hover and press.
  The label changes on submission, and browser simulation reports itself as such.
- Orientation checkmarks draw/erase and their square controls briefly compress
  and settle on change. Native checkbox semantics and keyboard operation remain.
- Keyboard/pointer pane resizing persists per user; narrow windows stack preview
  and controls. Keyboard users can pan, zoom, fit and inspect the preview.

Motion must describe what changed. It must not claim a Revit commit, imply progress
we have not measured, or hide errors. Browser `execute` accepts a bounded plan;
after the window closes, Python performs the transaction in the original pyRevit
command context and checks the actual commit status. Browser callbacks never
modify the model. See Autodesk's [transaction context rules](https://help.autodesk.com/cloudhelp/2024/ENU/Revit-API/files/Revit_API_Developers_Guide/Basic_Interaction_with_Revit_Elements/Revit_API_Revit_API_Developers_Guide_Basic_Interaction_with_Revit_Elements_Transactions_html.html).

## Verification boundary

Browser review: 1280, 768 and 390 pixels, controls, invalid input, seeded math,
preview cap, keyboard separator, reduced motion and simulation. Python tests
exercise commit/rollback using mocks. These checks cannot prove Revit API behavior.
The toolbar entry remains sandbox until a live Revit placement, rollback and Undo
run is recorded in the tool handoff.
