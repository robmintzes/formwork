# Decision records

Short records of consequential choices. Status values: **accepted** (Rob
answered or confirmed), **proposed** (engineering choice made during work;
reversible until someone depends on it), **superseded**.

| ADR | Decision | Status |
| --- | --- | --- |
| [0001](0001-engine-placement-and-stack.md) | Engine package, stdlib CPython, stacked on PR #2 | accepted (branch base), proposed (stack) |
| [0002](0002-generated-workspace-model.md) | Firm repo is a generated workspace, not an in-place fork | accepted |
| [0003](0003-config-and-token-formats.md) | JSON firm config; DTCG 2025.10 subset for tokens | proposed |
| [0004](0004-generated-ownership-and-update-model.md) | Ownership classes, manifest, block-on-conflict, convergent apply | proposed |
| [0005](0005-source-extraction-and-assets.md) | Rockwell reuse with scoped records; BIMxBert marks reserved; OFL fonts vendored | accepted |
| [0006](0006-wizard-stack.md) | Wizard is a stdlib loopback service with static UI | proposed |
| [0007](0007-pyrevit-icon-contract.md) | 96x96 light/dark PNG icons; validator accepts 32 or 96 | proposed |
| [0008](0008-product-name.md) | Product name: Formwork, a BIMxBert project; repository robmintzes/formwork | accepted |
| [0009](0009-engine-distribution.md) | Engine distribution: pinned checkout now, PyPI `formwork-dt` after the live Revit gate | accepted |
| [0010](0010-cli-package-rename.md) | Rename `toolkit` to `formwork` in code; `.toolkit/` workspaces migrate on render | accepted |
