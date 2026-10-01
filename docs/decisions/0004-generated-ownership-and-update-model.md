# ADR 0004 - Ownership classes and update model

Status: **proposed**.

## Decision

- Five classes: input (`firm/`), managed, seed, firm-owned (unlisted), retired.
  Defined in [FOUNDATION_SPEC section 4](../product/FOUNDATION_SPEC.md#4-generated-ownership-and-update-model).
- A deterministic manifest (no timestamps, sorted keys, relative paths) records
  foundation version, input hash, and per-file ownership and hash.
- Any conflict blocks the entire apply; nothing is written.
- Apply writes each file atomically (temp + `os.replace`) and the manifest last.
  It is convergent rather than transactional: a re-run after a crash adopts
  files that already hold the new content.
- Text hashes normalize CRLF to LF.
- Deletion is limited to hash-verified, manifest-owned files; no recursive
  removal; reparse points abort.

## Alternatives rejected

- **Region markers inside shared files** (generated sections in a firm-edited
  file): fragile under hand edits and hard to diff. The toolbar spec is split
  instead: a seeded firm-owned `toolbar_spec.md` plus managed fragments in
  `docs/toolbar/spec.d/` that the validator concatenates.
- **Apply non-conflicting files and skip conflicts**: leaves a half-rebranded
  workspace.
- **Staging directory + directory swap**: Windows cannot atomically swap a
  directory that firm-owned files share, and it would require moving firm code.
- **Three-way merge of managed files**: valuable later for template upgrades;
  premature before override rules exist.
