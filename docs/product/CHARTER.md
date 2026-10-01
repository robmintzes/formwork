# Design technology foundation - product charter

Status: draft for Rob Mintzes's review. Updated September 30, 2026.
Working product name: **BIMxBert Foundry**. The permanent name is undecided;
this proposal does not rename the repository.

## Purpose

Give architecture, engineering, and design firms a reusable, open-source,
agent-neutral foundation for establishing their own design technology
repository. A firm should be able to configure its identity, generate its
workspace, and develop tools with consistent interfaces, documentation,
governance, and verification.

## Confirmed intent

Rob wants BIMxBert to provide the default brand, with adopting firms replacing
the visible product identity with their own. Supported surfaces should grow to
include pyRevit toolbars, compiled Revit add-ins, standalone applications, and
branded guides. An approachable onboarding wizard should collect logos, color
and style choices and apply them across applicable surfaces. Agent-assisted
setup should be available without binding the foundation to one AI vendor.

The existing Rockwell Group design-technology repository and BIMxBert design
system export are candidate sources. Rob reports that Cassie Nozil supports
the open-source direction. The specific release inventory and applicable
license/attribution records still need to be documented.

## First user and first outcome

The first user is a design technology lead establishing a firm workspace on a
Windows workstation. The first release demonstrates that a versioned firm
configuration can generate a read-only pyRevit sample, a WPF UI specimen, and
an HTML guide with consistent branding. It also demonstrates safe regeneration
after both brand changes and the addition of a firm-owned custom tool.

## Proposed engineering decisions

- Keep one repository while the product boundaries are still being established.
- Separate reusable foundation code, firm configuration, platform adapters,
  and the generated firm workspace.
- Make the wizard and agent integrations clients of the same deterministic
  generator and validators. Initial development centers on the generator;
  the approachable wizard remains a required product outcome.
- Use neutral semantic token/component identifiers. BIMxBert is a complete
  default profile rather than a hard-coded dependency in every component.
- Separate mutable display branding from stable repository, package, assembly,
  and tool identifiers. Rebranding must not silently change technical identity.
- Track generated-file ownership and foundation versions. Preview changes,
  preserve custom work, detect conflicts, and support configuration migrations.
- Support onboarding without an AI subscription. Agent instructions and
  optional client adapters share the same canonical project rules.
- Keep source/license attribution in the appropriate records while replacing
  visible branding. Preserve required notices through generation and updates.

## Initial boundaries

The first demo covers three representative surfaces and one declared
Windows/Revit/pyRevit combination. A WPF specimen proves styling separately;
live host verification proves the sample tool's supported behavior.

Additional application starter kits, broad host/version support, automatic
upstream upgrades, managed firm-wide deployment, remote MCP, and host write
operations belong to later milestones. Initial branding applies to components
and assets the kit owns; native host UI retains its platform constraints.

## Success criteria

- Two distinct brand profiles generate consistent, locally usable outputs.
- Adopter-facing output contains the adopting firm's identity, including
  accessible labels, tool author metadata, documentation, and supported icons.
- Unchanged inputs produce no diff when generation is repeated.
- Brand changes preserve firm-owned code and report conflicts in generated files.
- Automated checks and recorded live host checks establish separate evidence.
- A maintainer can explain each imported asset's source, release scope, license,
  and contributor attribution.

## Next decisions

Review this scope and the [first milestone](FIRST_MILESTONE.md), confirm the
source disposition in the [inventory](SOURCE_INVENTORY.md), and select the
first supported host combination before implementation. Permanent naming and
desktop packaging can follow without delaying the architecture work.
