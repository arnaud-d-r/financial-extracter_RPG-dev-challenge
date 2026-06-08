from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from extractors.parse_images import parse_images


REPO_ROOT = Path(__file__).resolve().parents[1]


class FakeImageContext:
    size = (640, 480)
    mode = "RGB"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class ParseImagesTests(unittest.TestCase):
    def test_parse_images_uses_filename_and_image_metadata(self) -> None:
        fake_pil = types.SimpleNamespace(Image=types.SimpleNamespace(open=lambda path: FakeImageContext()))

        with tempfile.TemporaryDirectory() as temp_dir:
            image_file = Path(temp_dir) / "receipt.png"
            image_file.write_bytes(b"placeholder")

            with patch.dict(sys.modules, {"PIL": fake_pil, "PIL.Image": fake_pil.Image}):
                result = parse_images(image_file)

        self.assertEqual(result.source_file, "receipt.png")
        self.assertEqual(result.records[0].vendor, "receipt")
        self.assertEqual(result.records[0].metadata, {"size": (640, 480), "mode": "RGB"})
        self.assertEqual(result.warnings, ["OCR/vLLM integration not wired yet"])

    def test_parse_images_reads_real_receipt(self) -> None:
        image_file = REPO_ROOT / "shoebox" / "receipts" / "parking.jpeg"

        result = parse_images(image_file)

        self.assertEqual(result.source_file, "parking.jpeg")
        self.assertEqual(result.records[0].vendor, "parking")
        self.assertEqual(result.records[0].metadata["size"], (1408, 768))
        self.assertEqual(result.records[0].metadata["mode"], "RGB")


if __name__ == "__main__":
    unittest.main()
