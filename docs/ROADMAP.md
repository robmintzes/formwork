# Formwork Roadmap

This project is intended to become a firm-neutral foundation for architecture,
engineering, and construction technology teams standing up their own governed
development environment. The pyRevit toolbar and Revit MCP bridge are the first
working vertical slice, not the entire product.

## Product direction

The public foundation should provide reusable engineering conventions,
validators, agent procedures, host-application adapters, and local deployment
tools. Each adopting firm should own a separate configuration layer containing
its name, visual identity, standards, tool catalog, approved AI clients, and
deployment policy.

Firm configuration must not be baked into the public base. The base should also
avoid favoring a particular AI coding vendor: vendor-specific files are thin
adapters over the same repository rules and skills.

## Setup wizard decision

A guided setup experience is worthwhile, but a desktop GUI is not the first
thing to build. The correct sequence is:

1. Define and version a declarative project configuration schema.
2. Build an idempotent command-line generator around that schema.
3. Add environment diagnostics, dry-run output, validation, and recovery.
4. Put an optional graphical wizard over the same commands only after the
   workflow is stable.

The transitional bootstrap scripts, which mutated one checkout through string
replacement, were retired on 2026-09-30. `formwork init` and `formwork render`
now create and reconcile a separate firm-owned workspace, show proposed
changes before writing, and are safe to run again. See
[FOUNDATION_SPEC.md](product/FOUNDATION_SPEC.md).

## Intended onboarding flow

The future CLI should expose a small sequence of composable commands:

```text
formwork doctor   -> inspect Git, Python, PowerShell, pyRevit, Revit, and ports
formwork init     -> collect or import firm configuration
formwork render   -> create or reconcile the firm-owned workspace
formwork validate -> run repository, extension, MCP, and configuration checks
formwork install  -> register local development integrations
formwork verify   -> guide and record live host-application smoke tests
```

Every command should support non-interactive automation. Interactive prompts are
a convenience layer, not a second implementation.

## Architecture boundaries

- **Public foundation:** neutral instructions, schemas, templates, validators,
  and adapter contracts.
- **Firm configuration:** branding, standards, deployment channels, enabled
  tools, and client-specific settings.
- **Generated workspace:** the firm-owned repository developers actually change
  and deploy.
- **Host adapters:** isolated integrations for Revit, Bluebeam, and future
  applications rather than one giant server with every permission imaginable.
- **Agent adapters:** generated configuration for supported clients, all derived
  from the same core rules and tool registry.

Keep this as one repository while those boundaries are still moving. Split
packages only when components genuinely need independent release cadences;
premature repository sprawl creates governance work without creating value.

## Delivery phases

### Phase 0 - Stabilize the vertical slice

- Make the sample toolbar read-only and neutral.
- Validate bundle metadata, icons, toolbar specs, and tool guides.
- Stabilize the localhost Revit MCP server on a supported SDK major version.
- Add generated-project, runtime-compatibility, and contract tests.
- Complete a documented live Revit/pyRevit verification matrix.

The portable `formwork doctor` command and redacted live-verification runner are
now implemented. Phase 0 remains open until their required checks pass in the
declared Windows/Revit/pyRevit combinations; authoring the harness on macOS is
not itself live-host evidence.

### Phase 1 - Configuration and generator core

- Define the project configuration schema and migration policy.
- Replace destructive bootstrap behavior with `doctor`, `init`, `render`, and
  `validate` commands. (Done 2026-09-30; bootstrap retired.)
- Support dry runs, deterministic output, actionable errors, and repeat runs.
- Generate neutral sample content plus optional firm-owned branding layers.

### Phase 2 - pyRevit development kit

- Create generators for buttons, panels, tests, icons, and documentation.
- Add a supported Revit/pyRevit/Python compatibility matrix.
- Provide packaging, release manifests, rollback guidance, and live-test
  evidence capture.

### Phase 3 - MCP adapter kit

- Define a shared tool contract, response envelope, risk model, and approval
  boundary for host integrations.
- Publish read-only reference adapters and test harnesses for Revit and one
  non-Revit application before generalizing further.
- Keep network bindings local by default; require authentication and transport
  policy before supporting remote access.

### Phase 4 - Distribution and community

- Add contributor guidance, governance, release notes, and upgrade policy.
- Provide example firm configurations that contain no proprietary standards.
- Evaluate an optional desktop wizard using the proven CLI and schema.

## Onboarding success criteria

On a fresh supported Windows workstation, a design-technology lead should be
able to generate a firm-owned repository, run all automated checks, load the
sample toolbar, and complete a read-only MCP health check without hand-editing
source files. The process must identify unsupported prerequisites and must not
claim success until the live host checks are recorded.

## Safety defaults

- Read-only host tools come first; write tools require explicit risk metadata,
  user confirmation, narrow transactions, and rollback behavior.
- Linked Revit documents remain read-only.
- Local MCP transports remain loopback-only until authentication and origin
  policy are implemented and tested.
- Secrets and firm data stay outside generated source control by default.
- Generated changes are previewable and recoverable.
