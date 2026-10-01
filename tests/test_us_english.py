"""Formwork's own text uses US English (tools/us_english.py)."""

from __future__ import annotations

import contextlib
import io
from pathlib import Path
import sys
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import us_english  # noqa: E402


class UsEnglishTests(unittest.TestCase):
    def test_repository_text_uses_us_spelling(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = us_english.main([])
        self.assertEqual(code, 0, "British spellings found (run python tools/us_english.py --fix):\n" + out.getvalue())

    def test_fix_preserves_case_and_foreign_identifiers(self) -> None:
        text = "Colour and type; COLOUR; colours were cancelled. except asyncio.CancelledError: return Result.Cancelled;\n"
        self.assertEqual(
            us_english.fix(text),
            "Color and type; COLOR; colors were canceled. except asyncio.CancelledError: return Result.Cancelled;\n",
        )


if __name__ == "__main__":
    unittest.main()
