# ADR 0003 - JSON firm configuration; DTCG subset for tokens

Status: **proposed**.

## Decision

- Firm configuration is JSON (`firm/firm.json`) with a published JSON Schema
  for editor completion. JSON is read and written by the standard library, so
  the wizard can save configuration without a YAML or TOML writer dependency.
  The cost is no comments; `x-` keys and `profile.description` carry notes.
- Tokens use the DTCG Format Module 2025.10 (Stable Final Community Group
  Report, 2025-10-28; https://www.designtokens.org/tr/2025.10/format/) as the
  interchange basis, restricted to `color` (sRGB), `dimension` (`px`),
  `fontFamily`, `fontWeight`, and `number`, with curly-brace aliases.
- Behavior/treatment enums (button and badge styles, decorations) live in
  `firm.json` `appearance`, not in tokens: they are choices, not values.

## Deviations from DTCG, and why

| Deviation | Reason |
| --- | --- |
| `rem` rejected | WPF has no root font size; one absolute DIP value per token avoids hidden platform offsets. |
| Non-sRGB color spaces rejected | WPF and the CSS outputs consume sRGB; conversion is out of scope for v1. |
| `$ref`, `$extends`, `$root` rejected | Not needed by v1 profiles; rejecting explicitly is safer than partial support. |
| Composite types rejected | Typography/border/shadow composites are expressed by separate role tokens in v1. |

Each rejection has its own diagnostic code so a file from another DTCG tool
fails loudly instead of losing data.

## Vocabulary

Role names follow the BIMxBert export's neutral `ui-*` contract where it is
clear (surface/text/line/accent/status), with `color.action.*` added so button
treatments are explicit per profile. The Rockwell CSS-variable names are not
reused.
