# First milestone - prove configurable branding

Status: proposed acceptance contract. Updated September 30, 2026.

## Demo

Generate a firm workspace from a BIMxBert profile, then generate a separate
workspace for a fictional firm with visibly different branding. Both use the
same generator and reusable components. Each contains:

1. A read-only pyRevit sample with registered toolbar metadata and branded assets.
2. A WPF UI specimen demonstrating a logo, typography, primary/secondary
   buttons, selected/disabled states, and semantic status badges.
3. A locally usable HTML tool guide with the same configured identity.

The WPF specimen is a separate style-verification surface initially. Integration
into live Revit is accepted only after its own host checks. No new ribbon tool
is implemented before its entry exists in the toolbar specification.

## Configuration and generated ownership

Define the versioned project schema and token schema before writing the
generator. Required configuration covers firm identity, stable identifiers,
logo assets, semantic colors, typography, component styles, selected surfaces,
maintainers, and metadata/support destinations.

Generated output records its foundation version, input/profile identity,
managed files, and content hashes. Firm-owned custom code has an explicitly
separate location. The generator provides validation, a dry-run diff, staged
output, and safe repeat execution. It reports modifications to managed files
as conflicts rather than replacing them silently.

## Acceptance checks

| Check | Passing evidence |
| --- | --- |
| Two brands | BIMxBert and a fictional firm have visibly distinct logos, palettes, and component treatments across all three surfaces. |
| Complete replacement | Adopter-facing UI, accessibility labels, metadata, supported assets, and guides use the fictional firm's identity. Required license/provenance notices remain intact. |
| Repeat execution | The same profile and foundation version produce no file diff on the second generation. |
| Change propagation | Changing the palette and button/badge styles updates every applicable generated surface and reports unsupported choices. |
| Custom tool preservation | A firm-owned tool added between runs retains identical content after regeneration. |
| Conflict handling | An edited managed file is reported as a conflict; the generator leaves existing content intact. |
| Offline use | The generated specimens and tool assets load without a CDN or AI client. |
| Visual checks | Browser rendering and native Windows WPF rendering are inspected separately, including focus, contrast, and missing-font behavior. |
| Live host checks | One declared Windows/Revit/pyRevit combination has recorded evidence for ribbon load, document contexts, sample behavior, and clean exits. |

## Implementation order

1. Integrate the policy/stabilization prerequisites and record the source
   extraction scope. PR merges remain the human maintainer's decision.
2. Define schemas, output ownership, logo slots, and platform token mappings.
3. Implement the shared generator and representative surface adapters.
4. Demonstrate the acceptance checks with two profiles and a custom tool.
5. Build the approachable onboarding wizard over the proven generator, with
   live previews and the same validation/dry-run behavior.

Wizard design can be sketched alongside the schemas, but it must not grow a
second implementation of generation or validation. Additional languages,
templates, host versions, and deployment channels follow this first proof.
