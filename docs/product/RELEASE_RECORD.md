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
- **Release scope / licence:** Rob's own brand, approved for this public
  repository on 2026-09-30. **Not MIT-licensed**; see
  `profiles/bimxbert/NOTICE-brand.md`.
- **Verification:** well-formed XML; engine SVG safety checks pass; rendered in
  browser and native WPF specimens.

## R02 - BIMxBert token values (profiles/bimxbert/tokens.tokens.json)

- **Source:** same ZIP, `themes/bimxbert.css` and `tokens/scale.css` (values
  only: neutral and brand ramps, status colours, type scale, spacing).
- **Changes:** transcribed into DTCG 2025.10 structured data; semantic roles
  re-mapped to the foundation contract (`color.action.*` added). WPF and CSS
  now share one value per token (the export's WPF dictionary was 2 DIP smaller).
- **Licence:** factual values from Rob's design system; covered by the
  repository MIT licence as data, while the BIMxBert brand itself remains
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

## Not imported

Rockwell Group `design-technology` repository: reference only, no files
copied (clean-room; ADR 0005). From the BIMxBert ZIP: React/JSX components,
provisional XAML, uploads (RGDT sources), PDFs, exploratory boards, and
`support.js`.
