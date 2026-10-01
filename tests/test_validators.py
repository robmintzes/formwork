from __future__ import annotations

import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from validators.check_bundle_structure import validate_bundle_structure
from validators.validate_toolbar_spec import validate_toolbar_spec


class ValidatorFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.button = (
            self.root
            / "extensions"
            / "TestTools.extension"
            / "TestToolsTab.tab"
            / "TestToolsPanel.panel"
            / "HelloButton.pushbutton"
        )
        self.button.mkdir(parents=True)
        extension_manifest = self.button.parents[2] / "extension.json"
        extension_manifest.write_text(
            json.dumps({"name": "TestTools", "author": "Test Firm"}),
            encoding="utf-8",
        )
        (self.button / "script.py").write_text("print('hello')\n", encoding="utf-8")
        self._write_bundle()
        self._write_png(self.button / "icon.png", 32, 32)

        guide = self.root / "docs" / "toolbar" / "tools" / "hello-button.md"
        guide.parent.mkdir(parents=True)
        guide.write_text("# Hello Button\n\nRead-only example.\n", encoding="utf-8")
        self._write_spec()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _write_bundle(self, title: str = "Hello Button", author: str = "Test Firm") -> None:
        (self.button / "bundle.yaml").write_text(
            f"title: {title}\ntooltip: Read-only example.\nauthor: {author}\n",
            encoding="utf-8",
        )

    def _write_spec(
        self,
        *,
        risk: str = "Low",
        lifecycle: str = "sandbox",
        tool_type: str = "PushButton",
    ) -> None:
        relative_button = self.button.relative_to(self.root).as_posix()
        relative_extension = self.button.parents[2].relative_to(self.root).as_posix()
        relative_tab = self.button.parents[1].relative_to(self.root).as_posix()
        spec = self.root / "docs" / "toolbar" / "toolbar_spec.md"
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text(
            "# Toolbar\n\n"
            "```yaml\n"
            "tab:\n"
            "  id: test-tools\n"
            "  display_name: Test Tools\n"
            "  purpose: tests\n"
            "  audience: developers\n"
            "  lifecycle_stage: sandbox\n"
            f"  repo_extension_path: {relative_extension}\n"
            f"  source_path: {relative_tab}\n"
            "```\n\n"
            "```yaml\n"
            "tools:\n"
            "  - id: hello-button\n"
            "    display_name: Hello Button\n"
            f"    type: {tool_type}\n"
            "    category: utility\n"
            f"    risk: {risk}\n"
            f"    lifecycle_stage: {lifecycle}\n"
            "    description: Read-only example.\n"
            f"    source_path: {relative_button}\n"
            "    requires_confirmation: false\n"
            "```\n",
            encoding="utf-8",
        )

    @staticmethod
    def _png_chunk(name: bytes, payload: bytes) -> bytes:
        checksum = zlib.crc32(name)
        checksum = zlib.crc32(payload, checksum) & 0xFFFFFFFF
        return (
            struct.pack(">I", len(payload))
            + name
            + payload
            + struct.pack(">I", checksum)
        )

    @classmethod
    def _write_png(cls, path: Path, width: int, height: int) -> None:
        header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
        rows = b"".join(b"\x00" + (b"\x00" * width * 4) for _ in range(height))
        path.write_bytes(
            b"\x89PNG\r\n\x1a\n"
            + cls._png_chunk(b"IHDR", header)
            + cls._png_chunk(b"IDAT", zlib.compress(rows))
            + cls._png_chunk(b"IEND", b"")
        )

    def test_valid_fixture_passes_both_validators(self) -> None:
        bundle_errors, bundle_warnings = validate_bundle_structure(self.root)
        _, spec_errors = validate_toolbar_spec(self.root)

        self.assertEqual([], bundle_errors)
        self.assertEqual([], bundle_warnings)
        self.assertEqual([], spec_errors)

    def test_bundle_validator_reports_missing_icon_and_author(self) -> None:
        (self.button / "icon.png").unlink()
        self._write_bundle(author="")

        errors, _ = validate_bundle_structure(self.root)
        report = "\n".join(errors)

        self.assertIn("icon.png", report)
        self.assertIn("non-empty 'author'", report)

    def test_bundle_validator_rejects_wrong_icon_dimensions(self) -> None:
        self._write_png(self.button / "icon.png", 64, 64)

        errors, _ = validate_bundle_structure(self.root)

        self.assertIn("is 64x64; expected 32x32", "\n".join(errors))

    def test_bundle_validator_rejects_truncated_png(self) -> None:
        (self.button / "icon.png").write_bytes(
            b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR"
        )

        errors, _ = validate_bundle_structure(self.root)

        self.assertIn("truncated", "\n".join(errors))

    def test_bundle_validator_rejects_invalid_compressed_image_data(self) -> None:
        header = struct.pack(">IIBBBBB", 32, 32, 8, 6, 0, 0, 0)
        (self.button / "icon.png").write_bytes(
            b"\x89PNG\r\n\x1a\n"
            + self._png_chunk(b"IHDR", header)
            + self._png_chunk(b"IDAT", b"not-zlib-data")
            + self._png_chunk(b"IEND", b"")
        )

        errors, _ = validate_bundle_structure(self.root)

        self.assertIn("zlib", "\n".join(errors))

    def test_bundle_validator_accepts_valid_indexed_color_png(self) -> None:
        header = struct.pack(">IIBBBBB", 32, 32, 8, 3, 0, 0, 0)
        rows = b"".join(b"\x00" + (b"\x00" * 32) for _ in range(32))
        (self.button / "icon.png").write_bytes(
            b"\x89PNG\r\n\x1a\n"
            + self._png_chunk(b"IHDR", header)
            + self._png_chunk(b"PLTE", b"\x00\x00\x00\xff\xff\xff")
            + self._png_chunk(b"IDAT", zlib.compress(rows))
            + self._png_chunk(b"IEND", b"")
        )

        errors, _ = validate_bundle_structure(self.root)

        self.assertEqual([], errors)

    def test_spec_validator_rejects_invalid_risk_and_lifecycle(self) -> None:
        self._write_spec(risk="Catastrophic", lifecycle="done")

        _, errors = validate_toolbar_spec(self.root)
        report = "\n".join(errors)

        self.assertIn("[risk]", report)
        self.assertIn("[lifecycle]", report)

    def test_spec_validator_reports_bundle_title_and_guide_drift(self) -> None:
        self._write_bundle(title="Different Title")
        (self.root / "docs" / "toolbar" / "tools" / "hello-button.md").unlink()

        _, errors = validate_toolbar_spec(self.root)
        report = "\n".join(errors)

        self.assertIn("[bundle-title]", report)
        self.assertIn("[docs]", report)

    def test_spec_validator_rejects_type_folder_mismatch(self) -> None:
        self._write_spec(tool_type="URLButton")

        _, errors = validate_toolbar_spec(self.root)

        self.assertIn("[type-path]", "\n".join(errors))

    def test_spec_validator_rejects_stale_tab_extension_path(self) -> None:
        spec_path = self.root / "docs" / "toolbar" / "toolbar_spec.md"
        spec_text = spec_path.read_text(encoding="utf-8").replace(
            "extensions/TestTools.extension",
            "extensions/Missing.extension",
        )
        spec_path.write_text(spec_text, encoding="utf-8")

        _, errors = validate_toolbar_spec(self.root)

        self.assertIn("[tab-stale]", "\n".join(errors))

    def test_spec_validator_reports_tab_folder_without_metadata(self) -> None:
        second_tab = self.button.parents[2] / "SecondTab.tab"
        second_tab.mkdir()

        _, errors = validate_toolbar_spec(self.root)

        self.assertIn("[tab-missing]", "\n".join(errors))


if __name__ == "__main__":
    unittest.main()
