import contextlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest


SKILL_DIR = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "build_viewer", SKILL_DIR / "scripts" / "build_viewer.py"
)
build_viewer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_viewer)


def make_glb(document):
    payload = json.dumps(document, separators=(",", ":")).encode("utf-8")
    payload += b" " * ((-len(payload)) % 4)
    total_size = 20 + len(payload)
    return (
        struct.pack("<4sII", b"glTF", 2, total_size)
        + struct.pack("<II", len(payload), build_viewer.JSON_CHUNK_TYPE)
        + payload
    )


class BuildViewerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.model = self.root / "case.glb"
        self.model.write_bytes(make_glb({"asset": {"version": "2.0"}, "meshes": [{}]}))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_builds_bilingual_page_without_overwriting(self):
        output = self.root / "viewer.html"
        result = build_viewer.build_viewer(
            self.model,
            output,
            "en",
            "0deg 90deg 105%",
            "180deg 90deg 105%",
            SKILL_DIR / "assets",
        )
        page = output.read_text(encoding="utf-8")
        self.assertIn("Phone Case · 3D Viewer", page)
        self.assertIn("0deg 90deg 105%", page)
        self.assertNotIn("__MODEL_DATA__", page)
        self.assertEqual(result["model"], "case.glb")
        self.assertTrue(result["viewer_requires_network"])
        with self.assertRaisesRegex(build_viewer.ViewerError, "Output exists"):
            build_viewer.build_viewer(
                self.model,
                output,
                "en",
                "0deg 90deg 105%",
                "180deg 90deg 105%",
                SKILL_DIR / "assets",
            )

    def test_rejects_invalid_orbit(self):
        with self.assertRaisesRegex(build_viewer.ViewerError, "three safe"):
            build_viewer.validate_orbit('0deg 90deg "bad"')

    def test_rejects_truncated_glb(self):
        with self.assertRaisesRegex(build_viewer.ViewerError, "Truncated"):
            build_viewer.parse_glb_document(b"glTF")

    def test_rejects_external_resources(self):
        self.model.write_bytes(
            make_glb(
                {
                    "asset": {"version": "2.0"},
                    "meshes": [{}],
                    "images": [{"uri": "texture.png"}],
                }
            )
        )
        with self.assertRaisesRegex(build_viewer.ViewerError, "external resources"):
            build_viewer.load_glb(self.model)

    def test_cli_requires_both_orbits(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                build_viewer.parse_args(
                    ["--model", str(self.model), "--output", str(self.root / "v.html")]
                )
        self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
