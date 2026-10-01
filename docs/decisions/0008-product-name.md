# ADR 0008 - Product name: Formwork

Status: **accepted** (Rob, 2026-10-01).

## Decision

The product is **Formwork**, presented as "Formwork, a BIMxBert project".

- GitHub repository: `robmintzes/formwork` (renamed from
  `pyrevit-toolbar-template`; GitHub redirects the old URLs).
- Python distribution name, when published: `formwork-dt` (bare `formwork` is
  taken on PyPI by an unrelated project).
- CLI and package names stay `toolkit` / `toolkit_*` for now. Renaming them to
  `formwork` is a separate change with a compatibility shim (backlog B21).

## Why not "BIMxBert Foundry"

- **The product exists to make its default brand disappear.** Firms run their
  own identity on it. Naming the product after the default brand puts the
  wrong name on every adopter's tooling.
- **Licensing.** The BIMxBert name and marks are reserved (not MIT). A reserved
  mark inside the product name would attach a trademark question to every
  fork and redistribution.
- **Adoption.** A neutral name with BIMxBert as steward credit avoids the
  "personal side project" reading while keeping Rob's brand visible.
- **"Foundry" is crowded:** Palantir Foundry, Azure AI Foundry, Foundry VTT,
  and the Ethereum Foundry toolkit.

## Why Formwork

In concrete construction, formwork is the temporary mold that gives a
permanent structure its shape and is then stripped away. That is this
product's model:

- the foundation shapes a firm's workspace;
- the default brand is stripped out on adoption;
- the firm's own identity remains.

The word is architectural, short as a command, and legible to AEC readers.
The largest namesake found was a small PHP CMS (`getformwork/formwork`), with
no major-project collision.

## Unchanged on purpose

- The `revit-addin` AddInId namespace constant, which contains the old repository
  string. It is the fixed seed for every firm's stable add-in GUID; changing it
  would re-roll every generated add-in identity.
- Historical handoff and review documents, which record the names in use at
  the time.
