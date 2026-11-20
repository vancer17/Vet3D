import json
from pathlib import Path
import unittest
import numpy as np
from sapiens2_landmarks import build_landmarks

ASSETS = Path(__file__).resolve().parents[1] / "assets/taro"


class MappingTests(unittest.TestCase):
    def setUp(self):
        self.mapping = ASSETS / "sapiens2_mapping.json"
        self.template = ASSETS / "template.npz"
        self.names = json.loads((ASSETS / "sapiens2_keypoint_names.json").read_text())
        self.points = np.full((308, 3), np.nan)
        for row in json.loads(self.mapping.read_text())["records"]:
            self.points[row["keypoint_id"]] = row["vertex_native"]
        self.scores = np.ones(308)

    def build(self):
        return build_landmarks(
            self.template, self.mapping, self.points, self.scores, self.names
        )

    def test_default_eyes_lips_and_missing_target(self):
        result = self.build()
        self.assertEqual(len(result), 68)
        self.assertEqual(len({x["vertex_index"] for x in result}), 68)
        self.points[96] = np.nan
        self.scores[97] = 0.1
        self.assertEqual(len(self.build()), 66)

    def test_changed_keypoint_definition_rejected(self):
        self.names["96"] = "different_semantics"
        with self.assertRaisesRegex(ValueError, "definition mismatch"):
            self.build()

    def test_wrong_template_and_invalid_target_rejected(self):
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            build_landmarks(
                ASSETS / "template_eyes.npz",
                self.mapping,
                self.points,
                self.scores,
                self.names,
            )
        self.points[:] = 0
        with self.assertRaisesRegex(ValueError, "non-collinear"):
            self.build()


if __name__ == "__main__":
    unittest.main()
