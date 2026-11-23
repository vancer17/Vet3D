"""Synthetic contract tests. They do not test visual model accuracy."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import reference_review as io
import reference_review_core as core

BASE = SCRIPTS.parent / "references/review-base.json"


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        # Arbitrary bytes exercise provenance only, explicitly not image decoding.
        for name in ("original", "head", "front", "left", "back", "right", "prompt", "example", *core.RELATIVE_VIEWS):
            (self.root / name).write_text(name, encoding="utf-8")
        self.manifest = self.root / "manifest.json"
        self.data = {"schema": 1, "mode": "four-views", "source": "original",
                     "view_convention": core.ALIGNED_VIEW_CONVENTION,
                     "images": {v: v for v in core.VIEWS["four-views"]},
                     "prompts": {v: "prompt" for v in core.VIEWS["four-views"]},
                     "generation_inputs": {v: ["original"] for v in core.VIEWS["four-views"]},
                     "neck_crop": "short neck", "appearance": "natural",
                     "required_shape_constraints": "", "examples": []}
        self.save()
        self.evaluator = {"name": "synthetic-test-not-a-detector", "version": "1"}

    def save(self):
        self.manifest.write_text(json.dumps(self.data), encoding="utf-8")

    def request(self, policy=None):
        return io.prepare(self.manifest, BASE, policy, self.evaluator)

    def passed(self, request):
        response = core.response_template(request)
        criteria = {c["key"]: c for c in request["criteria"]}
        for c in response["checks"]:
            view = c["key"].split("/")[0]
            views = request["view_frame"]["views"] if view == "set" else [view]
            evidence = [{"role": "image/" + v, "box": [0, 0, 1, 1]} for v in views]
            if criteria[c["key"]].get("compare_source"):
                evidence.append({"role": "source"})
            c.update(status="pass", rating=2, observation="Synthetic fixture observation, not a real visual review.",
                     evidence=evidence)
        return response

    def current(self):
        self.data.pop("view_convention", None)
        self.data.update(pose_mode="current",
                         images={v: v for v in core.RELATIVE_VIEWS},
                         prompts={v: "prompt" for v in core.RELATIVE_VIEWS},
                         generation_inputs={v: ["original"] for v in core.RELATIVE_VIEWS})
        self.save()
        return self.request()

    def test_pose_defaults_and_current_matrix(self):
        legacy = self.request()
        self.assertEqual(legacy["view_frame"]["pose_mode"], "aligned")
        self.assertEqual(len(legacy["criteria"]), 23)
        self.assertEqual(core.resolve_pose("head"), "current")
        q = self.current()
        keys = {c["key"] for c in q["criteria"]}
        self.assertEqual(len(keys), 24)
        self.assertTrue({"view_0/preserve_" + axis for axis in ("yaw", "pitch", "roll")} <= keys)
        self.assertTrue({v + "/relative_view" for v in core.RELATIVE_VIEWS[1:]} <= keys)
        self.assertTrue({"set/consistency", "set/frozen_pose"} <= keys)
        self.assertFalse({c["id"] for c in q["criteria"]} & {"yaw", "pitch", "roll", "view"})
        self.assertFalse(q["view_frame"]["calibrated"])
        self.assertEqual(q["view_frame"]["orbit_degrees"], dict(zip(core.RELATIVE_VIEWS, (0, 90, 180, 270))))
        self.assertEqual(core.assess(q, self.passed(q))["state"], "awaiting_confirmation")

    def test_aligned_sheet_and_profile_directions(self):
        q = self.request()
        frame = q["view_frame"]
        self.assertEqual(frame["views"], ["front", "right", "back", "left"])
        self.assertEqual(frame["sheet_rows"], [["front", "right"], ["back", "left"]])
        self.assertEqual(frame["profile_nose_direction"],
                         {"right": "image-right", "left": "image-left"})
        self.assertEqual(frame["orbit_degrees"], {"front": 0, "right": 90, "back": 180, "left": 270})
        self.assertEqual(frame["view_convention"], "screen-nose-direction-v1")
        current = self.current()["view_frame"]
        self.assertEqual(current["sheet_rows"], [["view_0", "view_90"], ["view_180", "view_270"]])
        self.assertNotIn("profile_nose_direction", current)
        self.assertNotIn("view_convention", current)

    def test_unconfirmed_legacy_side_names_are_rejected(self):
        for convention in (None, "camera-side", ""):
            with self.subTest(convention=convention):
                if convention is None:
                    self.data.pop("view_convention", None)
                else:
                    self.data["view_convention"] = convention
                self.save()
                with self.assertRaisesRegex(ValueError, "view_convention"):
                    self.request()

    def test_side_remapping_invalidates_old_review(self):
        old = self.request()
        # Existing bytes are kept; the actual prompt/input provenance follows its image.
        self.data["prompts"].update(left="left", right="right")
        self.data["generation_inputs"].update(left=["left"], right=["right"])
        for field in ("images", "prompts", "generation_inputs"):
            values = self.data[field]
            values["left"], values["right"] = values["right"], values["left"]
        self.save()
        q = self.request()
        with self.assertRaisesRegex(ValueError, "Stale"):
            core.assess(q, self.passed(old))
        files = {f["role"]: Path(f["path"]).name for f in q["snapshot"]["files"]}
        self.assertEqual(files["image/right"], "left")
        self.assertEqual(files["prompt/right"], "left")
        self.assertEqual(files["generation/right/0"], "left")

    def test_current_requires_source_and_all_view_evidence(self):
        q = self.current()
        for key in ("view_0/preserve_yaw", "view_0/preserve_pitch", "view_0/preserve_roll", "set/frozen_pose"):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "evidence missing"):
                r = self.passed(q)
                c = next(c for c in r["checks"] if c["key"] == key)
                c["evidence"] = [e for e in c["evidence"] if e["role"] != "source"]
                core.assess(q, r)
        r = self.passed(q)
        c = next(c for c in r["checks"] if c["key"] == "set/frozen_pose")
        c["evidence"] = [e for e in c["evidence"] if e["role"] != "image/view_270"]
        with self.assertRaisesRegex(ValueError, "evidence missing"):
            core.assess(q, r)
        r = self.passed(q)
        r["checks"] = [c for c in r["checks"] if c["key"] != "view_0/preserve_roll"]
        with self.assertRaisesRegex(ValueError, "checks"):
            core.assess(q, r)

    def test_pose_change_invalidates_and_wrong_labels_are_rejected(self):
        old = self.request()
        self.data["pose_mode"] = "current"
        self.save()
        with self.assertRaisesRegex(ValueError, "Exact view mapping"):
            self.request()
        q = self.current()
        self.assertNotEqual(old["request_id"], q["request_id"])
        with self.assertRaisesRegex(ValueError, "Stale"):
            core.assess(q, self.passed(old))
        self.data["pose_mode"] = "aligned"
        self.save()
        with self.assertRaisesRegex(ValueError, "Exact view mapping"):
            self.request()
        for mode, pose in (("head", "aligned"), ("front", "current"), ("four-views", "invalid")):
            with self.subTest(mode=mode, pose=pose), self.assertRaises(ValueError):
                core.views_for(mode, pose)

    def test_current_cli_templates_are_unapproved_and_report_pose(self):
        self.current()
        args = [sys.executable, str(SCRIPTS / "reference_review.py"), "--manifest", str(self.manifest),
                "--base-policy", str(BASE), "--evaluator", "synthetic-cli", "--evaluator-version", "1"]
        response = self.root / "template.json"
        subprocess.run(args + ["prepare", "--output", str(self.root / "request.json"),
                               "--response", str(response)], check=True, capture_output=True)
        result = subprocess.run(args + ["check", "--response", str(response),
                                       "--output", str(self.root / "decision.json"),
                                       "--html", str(self.root / "review.html")], capture_output=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(io.read_json(self.root / "decision.json")["state"], "needs_review")
        self.assertIn("current / reference-relative", (self.root / "review.html").read_text())

    def test_no_model_self_approval_and_bound_human_approval(self):
        q = self.request()
        r = self.passed(q)
        r["approved"] = True  # Irrelevant evaluator-authored top-level claim.
        d = core.assess(q, r)
        self.assertEqual(d["state"], "awaiting_confirmation")
        confirmation = {"schema": 1, "review_id": d["review_id"], "decision": "approve",
                        "reviewer": "fixture-human", "note": "Test only"}
        self.assertTrue(core.assess(q, r, confirmation=confirmation)["approved"])
        r["checks"][0]["observation"] += " changed"
        with self.assertRaisesRegex(ValueError, "confirmation"):
            core.assess(q, r, confirmation=confirmation)

    def test_fail_uncertain_missing_and_empty_fail_closed(self):
        q = self.request()
        self.assertEqual(core.assess(q, core.response_template(q))["state"], "needs_review")
        for status, rating, expected in (("fail", 1, "needs_revision"), ("uncertain", None, "needs_review")):
            r = self.passed(q)
            r["checks"][0].update(status=status, rating=rating)
            self.assertEqual(core.assess(q, r)["state"], expected)
            d = core.assess(q, r)
            with self.assertRaisesRegex(ValueError, "cannot bypass"):
                core.assess(q, r, confirmation={"schema": 1, "review_id": d["review_id"],
                    "decision": "approve", "reviewer": "test", "note": "Test"})
        for checks in ([], self.passed(q)["checks"][:-1], self.passed(q)["checks"] * 2):
            r = self.passed(q)
            r["checks"] = checks
            with self.assertRaisesRegex(ValueError, "checks"):
                core.assess(q, r)

    def test_evidence_and_rating_validation(self):
        q = self.request()
        changes = [{"rating": True}, {"rating": float("nan")}, {"rating": 4},
                   {"status": "passed"}, {"observation": " "}, {"evidence": []},
                   {"evidence": [{"role": "image/back"}]},
                   {"evidence": [{"role": "image/front", "box": [0.7, 0, 0.1, 1]}]}]
        # First row is front identity.
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                r = self.passed(q)
                r["checks"][0].update(change)
                core.assess(q, r)

    def test_retry_limit_and_no_uncertain_auto_regeneration(self):
        q = self.request()
        r = self.passed(q)
        r["checks"][0].update(status="fail", rating=0)
        key = r["checks"][0]["key"]
        self.assertEqual(core.assess(q, r, {key: 1})["state"], "needs_revision")
        self.assertEqual(core.assess(q, r, {key: 2})["state"], "stop_for_user")
        r["checks"][0].update(status="uncertain", rating=None)
        self.assertEqual(core.assess(q, r)["repair_proposals"], [])

    def test_stale_files_prompts_source_generation_and_examples(self):
        self.data["examples"] = [{"path": "example", "criterion": "shape", "verdict": "positive", "note": "style only"}]
        self.save()
        for name in ("original", "front", "prompt", "example"):
            before = self.request()
            (self.root / name).write_text(name + "-changed")
            after = self.request()
            self.assertNotEqual(before["request_id"], after["request_id"])
            with self.assertRaisesRegex(ValueError, "Stale"):
                core.assess(after, self.passed(before))
        self.data["generation_inputs"]["front"] = ["example"]
        before = self.request()
        self.save()
        self.assertNotEqual(before["request_id"], self.request()["request_id"])

    def test_policy_evaluator_and_shared_source_invalidation(self):
        q = self.request()
        changed = copy.deepcopy(q["policies"])
        changed[0]["revision"] += "-changed"
        q2 = core.make_request(q["snapshot"], changed, q["evaluator"], q["implementation"])
        self.assertNotEqual(q["request_id"], q2["request_id"])
        self.evaluator["version"] = "2"
        self.assertNotEqual(q["request_id"], self.request()["request_id"])
        # Materialize the actual source, mutate only shared core, execute its real adapter.
        for name in ("reference_review_core.py", "reference_review.py"):
            (self.root / name).write_bytes((SCRIPTS / name).read_bytes())
        args = [sys.executable, str(self.root / "reference_review.py"), "prepare", "--manifest", str(self.manifest),
                "--base-policy", str(BASE), "--evaluator", "test", "--evaluator-version", "1"]
        subprocess.run(args + ["--output", str(self.root / "q1.json")], check=True, capture_output=True)
        with (self.root / "reference_review_core.py").open("a") as stream:
            stream.write("\n# changed implementation\n")
        subprocess.run(args + ["--output", str(self.root / "q2.json")], check=True, capture_output=True)
        self.assertNotEqual(io.read_json(self.root / "q1.json")["request_id"],
                            io.read_json(self.root / "q2.json")["request_id"])
        # No downstream job/cache is touched by preparing a reference review.
        self.assertFalse((self.root / "jobs").exists())

    def test_independent_branch_matrix(self):
        for mode in ("head", "front"):
            self.data.update(mode=mode, images={mode: mode}, prompts={mode: "prompt"},
                             generation_inputs={mode: ["original"]})
            self.save()
            q = self.request()
            keys = {c["key"] for c in q["criteria"]}
            self.assertNotIn("set/consistency", keys)
            self.assertEqual(mode == "head", "head/original_pose" in keys)
            self.assertEqual(mode == "front", "front/yaw" in keys)

    def test_html_is_escaped_and_write_does_not_overwrite(self):
        q = self.request()
        r = self.passed(q)
        r["checks"][0]["observation"] = "<script>alert('not executed')</script>"
        page = io.report_html(q, r, core.assess(q, r))
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)
        io.write_json(self.root / "report.json", {})
        with self.assertRaises(FileExistsError):
            io.write_json(self.root / "report.json", {"overwritten": True})


if __name__ == "__main__":
    unittest.main()
