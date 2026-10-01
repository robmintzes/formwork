"""US English spelling check (and optional fix) for Formwork's own text.

Usage:
    python tools/us_english.py           # report British spellings; exit 1 if any
    python tools/us_english.py --fix     # rewrite them in place, preserving case

Covers tracked text files. Third-party texts (font licenses, vendored
notices) and verbatim historical records are excluded, and identifiers owned
by other APIs (for example Python's ``asyncio.CancelledError``) are never
touched.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

US_SPELLING = {
    "colour": "color", "colours": "colors", "coloured": "colored", "colouring": "coloring",
    "licence": "license", "licences": "licenses",
    "behaviour": "behavior", "behaviours": "behaviors", "behavioural": "behavioral",
    "organisation": "organization", "organisations": "organizations",
    "organise": "organize", "organised": "organized", "organising": "organizing",
    "normalise": "normalize", "normalised": "normalized", "normalises": "normalizes",
    "normalising": "normalizing", "normalisation": "normalization",
    "recognise": "recognize", "recognised": "recognized", "recognises": "recognizes",
    "initialise": "initialize", "initialised": "initialized", "initialisation": "initialization",
    "serialise": "serialize", "serialised": "serialized", "serialisation": "serialization",
    "summarise": "summarize", "summarised": "summarized", "summarises": "summarizes",
    "customise": "customize", "customised": "customized", "customisation": "customization",
    "optimise": "optimize", "optimised": "optimized", "optimisation": "optimization",
    "prioritise": "prioritize", "minimise": "minimize", "maximise": "maximize",
    "utilise": "utilize", "realise": "realize", "realised": "realized",
    "emphasise": "emphasize", "analyse": "analyze", "analysed": "analyzed",
    "localise": "localize", "localised": "localized", "localisation": "localization",
    "authorise": "authorize", "authorised": "authorized", "authorisation": "authorization",
    "neutralise": "neutralize", "neutralised": "neutralized", "neutralisation": "neutralization",
    "favour": "favor", "favours": "favors", "honour": "honor",
    "neighbour": "neighbor", "neighbours": "neighbors",
    "centre": "center", "centred": "centered", "centres": "centers",
    "metre": "meter", "metres": "meters",
    "grey": "gray", "greys": "grays",
    "catalogue": "catalog", "catalogues": "catalogs",
    "labelled": "labeled", "labelling": "labeling",
    "cancelled": "canceled", "cancelling": "canceling",
    "modelled": "modeled", "modelling": "modeling",
    "travelled": "traveled", "programme": "program", "artefact": "artifact", "artefacts": "artifacts",
    "whilst": "while", "amongst": "among", "judgement": "judgment",
    "fulfil": "fulfill", "enrol": "enroll", "defence": "defense", "offence": "offense",
    "sceptical": "skeptical", "learnt": "learned", "spelt": "spelled",
}
WORD = re.compile(r"\b(" + "|".join(sorted(US_SPELLING, key=len, reverse=True)) + r")\b", re.IGNORECASE)
# Identifiers defined by other projects keep their own spelling: Python's
# asyncio/concurrent CancelledError and the Revit API's Result.Cancelled enum
# member (Autodesk spells it the British way; changing it breaks the build).
PROTECTED = re.compile(r"CancelledError|Result\.Cancelled\b")
TEXT_SUFFIXES = {
    ".md", ".py", ".js", ".ts", ".css", ".html", ".json", ".tmpl", ".xaml", ".yml", ".yaml",
    ".toml", ".ps1", ".cs", ".txt", ".csv", ".svg",
}
EXCLUDED = (
    "docs/handoffs/claude-foundation-prompt-2026-09-30.md",  # verbatim historical brief
    "toolkit_engine/resources/",  # third-party license texts
)
EXCLUDED_NAMES = {"OFL.txt", "LICENSE"}


def tracked_files() -> list[Path]:
    output = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    files = []
    for rel in output.splitlines():
        path = ROOT / rel
        if path.suffix.lower() not in TEXT_SUFFIXES or path.name in EXCLUDED_NAMES:
            continue
        if rel.startswith(EXCLUDED) or rel == "tools/us_english.py":
            continue
        files.append(path)
    return files


def _match_case(original: str, replacement: str) -> str:
    if original.isupper():
        return replacement.upper()
    if original[0].isupper():
        return replacement[0].upper() + replacement[1:]
    return replacement


def scan(text: str) -> list[tuple[int, str]]:
    findings = []
    for number, line in enumerate(text.splitlines(), 1):
        stripped = PROTECTED.sub("", line)
        for match in WORD.finditer(stripped):
            findings.append((number, match.group(0)))
    return findings


def fix(text: str) -> str:
    def replace_line(line: str) -> str:
        parts = PROTECTED.split(line)
        tokens = PROTECTED.findall(line)
        fixed = [WORD.sub(lambda m: _match_case(m.group(0), US_SPELLING[m.group(0).lower()]), part) for part in parts]
        out = fixed[0]
        for token, part in zip(tokens, fixed[1:]):
            out += token + part
        return out

    return "".join(replace_line(line) for line in text.splitlines(keepends=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fix", action="store_true")
    args = parser.parse_args(argv)
    total = 0
    for path in tracked_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        findings = scan(text)
        if not findings:
            continue
        total += len(findings)
        rel = path.relative_to(ROOT).as_posix()
        if args.fix:
            path.write_bytes(fix(text).encode("utf-8"))
            print("fixed {} ({})".format(rel, len(findings)))
        else:
            for number, word in findings:
                print("{}:{}: '{}' -> '{}'".format(rel, number, word, US_SPELLING[word.lower()]))
    if not args.fix and total:
        print("{} British spelling(s); run python tools/us_english.py --fix".format(total), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
