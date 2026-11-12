"""Tests for the offline documentation screenshot generator."""

import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import render_doc_screens as rds  # noqa: E402

EXPECTED = {
    "produktion", "verbrauch", "einspeisung", "bezug",
    "hausakku-charging", "hausakku-discharging", "hausakku-idle",
    "verlauf-produktion", "verlauf-verbrauch", "prognose",
    "login-noetig", "kontingent-aufgebraucht",
}


def _no_network(*args, **kwargs):
    raise AssertionError("network access attempted")


class DocScreensTest(unittest.TestCase):
    def _run(self, out):
        with mock.patch.object(socket.socket, "connect", _no_network), \
                mock.patch.object(socket, "create_connection", _no_network):
            self.assertEqual(rds.main(out), 0)

    def test_writes_twelve_valid_images(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            self._run(tmp)
            names = {p.stem for p in Path(tmp).glob("*.png")}
            self.assertEqual(names, EXPECTED)
            for path in Path(tmp).glob("*.png"):
                img = Image.open(path)
                self.assertEqual(img.size, (1000, 488))
                self.assertNotEqual(img.convert("L").getextrema(), (255, 255))

    def test_deterministic(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            self._run(a)
            self._run(b)
            for name in EXPECTED:
                self.assertEqual(
                    (Path(a) / f"{name}.png").read_bytes(),
                    (Path(b) / f"{name}.png").read_bytes(),
                    name,
                )

    def test_committed_images_carry_no_metadata(self):
        # The internals scan skips tracked binary files, so the committed
        # screenshots must contain image data only (no text/EXIF chunks).
        import struct
        files = sorted((ROOT / "docs" / "screens").glob("*.png"))
        self.assertEqual({p.stem for p in files}, EXPECTED)
        for path in files:
            data = path.read_bytes()
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n", path.name)
            pos, chunks = 8, []
            while pos < len(data):
                length, kind = struct.unpack(">I4s", data[pos:pos + 8])
                chunks.append(kind.decode("ascii"))
                pos += 12 + length
            self.assertEqual(pos, len(data), path.name)  # nothing after IEND
            self.assertEqual(set(chunks), {"IHDR", "IDAT", "IEND"}, path.name)


if __name__ == "__main__":
    unittest.main()
