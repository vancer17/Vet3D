"""Run only in a complete materialized workflow bundle, not adjacent repo sources."""
import copy
import json
from pathlib import Path
import sys
import unittest

ENTRY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENTRY / "scripts"))
import reference_review_core as core


class PrintablePolicyTests(unittest.TestCase):
    def setUp(self):
        self.policies = [json.loads((ENTRY / "references" / name).read_text())
                         for name in ("review-base.json", "image-review-policy.json")]

    def test_hair_items_required_in_all_branches_and_materials(self):
        hair = {"hair_mass", "carved_flow", "hair_microdetail", "unsupported_fringe", "eyelash_removal"}
        for mode, pose in (("head", "current"), ("front", "aligned"),
                           ("four-views", "aligned"), ("four-views", "current")):
            views = core.views_for(mode, pose)
            for material in ("natural", "gray-resin", "colored-matte-resin"):
                with self.subTest(mode=mode, pose=pose, material=material):
                    matrix = core.criteria_for(mode, material, self.policies, pose)
                    keys = {c["key"] for c in matrix}
                    self.assertTrue({v + "/" + h for v in views for h in hair} <= keys)
                    flow_rule = next(c for c in self.policies[1]["criteria"] if c["id"] == "carved_flow")
                    for criterion in (c for c in matrix if c["id"] == "carved_flow"):
                        self.assertEqual(criterion["pass_when"], flow_rule["pass_when"])
                        self.assertEqual(criterion["repair"], flow_rule["repair"])
                    self.assertEqual(material == "colored-matte-resin",
                                     any(c["id"] == "matte_eyes" for c in matrix))
                    self.assertEqual(mode == "four-views", "set/ear_hair_consistency" in keys)
                    if mode == "four-views" and pose == "current" and material == "colored-matte-resin":
                        self.assertEqual(len(matrix), 49)
                        self.assertTrue({v + "/matte_eyes" for v in views} <= keys)

    def test_flow_policy_change_invalidates_workflow_not_generic_review(self):
        snapshot = {"manifest": {"mode": "front", "appearance": "natural"},
                    "files": [{"role": "image/front"}]}
        evaluator = {"name": "synthetic", "version": "1"}
        before = core.make_request(snapshot, self.policies, evaluator, {})
        generic = core.make_request(snapshot, self.policies[:1], evaluator, {})
        response = core.response_template(before)
        for check in response["checks"]:
            check.update(status="pass", rating=3, observation="Synthetic fixture only.",
                         evidence=snapshot["files"])
        self.assertFalse(core.assess(before, response)["failed"])
        changed = copy.deepcopy(self.policies)
        flow_rule = next(c for c in changed[1]["criteria"] if c["id"] == "carved_flow")
        flow_rule["repair"] += " Synthetic policy revision for invalidation testing."
        after = core.make_request(snapshot, changed, evaluator, {})
        self.assertNotEqual(before["request_id"], after["request_id"])
        with self.assertRaisesRegex(ValueError, "Stale or foreign review"):
            core.assess(after, response)
        self.assertEqual(generic, core.make_request(snapshot, changed[:1], evaluator, {}))
        self.assertEqual(before, core.make_request(snapshot, self.policies, evaluator, {}))

    def test_obvious_false_lashes_and_unmerged_wisps_block_handoff(self):
        # Host observations are fixtures; this tests the gate, not an image detector.
        for criterion in ("eyelash_removal", "hair_microdetail", "unsupported_fringe"):
            for status, rating, state in (("fail", 0, "needs_revision"),
                                          ("uncertain", None, "needs_review"),
                                          ("not_checked", None, "needs_review")):
                with self.subTest(criterion=criterion, status=status):
                    q, r = self.ear_review("aligned")
                    key = "front/" + criterion
                    item = next(c for c in r["checks"] if c["key"] == key)
                    item.update(status=status, rating=rating,
                                observation="Synthetic: obvious artificial lash fans or unmerged fine wisps remain.")
                    d = core.assess(q, r)
                    self.assertEqual(d["state"], state)
                    self.assertFalse(d["approved"])
                    with self.assertRaisesRegex(ValueError, "cannot bypass"):
                        core.assess(q, r, confirmation={"schema": 1, "review_id": d["review_id"],
                            "decision": "approve", "reviewer": "fixture-human", "note": "Test only"})
                    r["checks"].remove(item)
                    with self.assertRaisesRegex(ValueError, "required checks"):
                        core.assess(q, r)

    def test_eyelash_policy_invalidates_prior_review_not_generic_policy(self):
        q, _ = self.ear_review("aligned")
        old = copy.deepcopy(self.policies)
        old[1]["revision"] = "7"
        old_rule = next(c for c in old[1]["criteria"] if c["id"] == "eyelash_removal")
        old_rule["pass_when"] = "Remove all upper and lower eyelashes, including natural lashes."
        old_q = core.make_request(q["snapshot"], old, q["evaluator"], {})
        with self.assertRaisesRegex(ValueError, "Stale or foreign review"):
            core.assess(q, core.response_template(old_q))
        self.assertEqual(core.make_request(q["snapshot"], old[:1], q["evaluator"], {}),
                         core.make_request(q["snapshot"], self.policies[:1], q["evaluator"], {}))

    def test_natural_lashes_and_original_makeup_can_pass_without_auto_approval(self):
        # Synthetic host judgement only: no image detector or real approval is implied.
        q, r = self.ear_review("aligned")
        item = next(c for c in r["checks"] if c["key"] == "front/eyelash_removal")
        item.update(status="pass", rating=3, observation=(
            "Synthetic: natural upper/lower lashes remain, without obvious false-lash fans; "
            "original bold eyeliner, eyeshadow and lip color are preserved."))
        decision = core.assess(q, r)
        self.assertEqual(decision["failed"], [])
        self.assertEqual(decision["state"], "awaiting_confirmation")
        self.assertFalse(decision["approved"])

    def test_current_lost_roll_fails_despite_high_total(self):
        snapshot = {"manifest": {"mode": "four-views", "pose_mode": "current",
                                  "appearance": "colored-matte-resin"},
                    "files": [{"role": "source"}] + [{"role": "image/" + v} for v in core.RELATIVE_VIEWS]}
        q = core.make_request(snapshot, self.policies, {"name": "synthetic", "version": "1"}, {})
        r = core.response_template(q)
        for c in r["checks"]:
            c.update(status="pass", rating=3, observation="Synthetic fixture, not a visual detector.",
                     evidence=snapshot["files"])
        next(c for c in r["checks"] if c["key"] == "view_0/preserve_roll").update(status="fail", rating=0)
        decision = core.assess(q, r)
        self.assertEqual(decision["state"], "needs_revision")
        self.assertGreater(decision["ordinal_points"], 0.95 * decision["ordinal_max"])
        self.assertFalse(decision["approved"])

    def test_aligned_side_failure_blocks_workflow_handoff(self):
        snapshot = {"manifest": {"mode": "four-views", "pose_mode": "aligned",
                                  "view_convention": "screen-nose-direction-v1",
                                  "appearance": "colored-matte-resin"},
                    "files": [{"role": "image/" + v} for v in ("front", "right", "back", "left")]}
        q = core.make_request(snapshot, self.policies, {"name": "synthetic", "version": "1"}, {})
        self.assertEqual(q["view_frame"]["sheet_rows"], [["front", "right"], ["back", "left"]])
        r = core.response_template(q)
        for c in r["checks"]:
            c.update(status="pass", rating=3, observation="Synthetic fixture only.",
                     evidence=snapshot["files"])
        next(c for c in r["checks"] if c["key"] == "right/view").update(
            status="fail", rating=0, observation="Synthetic wrong-side fixture: nose points image-left.")
        decision = core.assess(q, r)
        self.assertEqual(decision["failed"], ["right/view"])
        self.assertFalse(decision["approved"])
        with self.assertRaisesRegex(ValueError, "cannot bypass"):
            core.assess(q, r, confirmation={"schema": 1, "review_id": decision["review_id"],
                "decision": "approve", "reviewer": "fixture-human", "note": "Test only"})
        del snapshot["manifest"]["view_convention"]
        with self.assertRaisesRegex(ValueError, "view_convention"):
            core.make_request(snapshot, self.policies, {"name": "synthetic", "version": "1"}, {})

    def ear_review(self, pose):
        views = core.views_for("four-views", pose)
        snapshot = {"manifest": {"mode": "four-views", "pose_mode": pose,
                                  "view_convention": "screen-nose-direction-v1",
                                  "appearance": "natural"},
                    "files": [{"role": "source"}] + [{"role": "image/" + v} for v in views]}
        request = core.make_request(snapshot, self.policies, {"name": "synthetic", "version": "1"}, {})
        response = core.response_template(request)
        for check in response["checks"]:
            check.update(status="pass", rating=3, observation="Synthetic review fixture only.",
                         evidence=snapshot["files"])
        return request, response

    def test_covered_ears_pass_without_exposure_requirement(self):
        # The host supplies visual observations. This tests the gate, not image recognition.
        for pose in ("aligned", "current"):
            for observation in (
                "Synthetic: both ears fully covered; the same hair masses and occlusion agree in all four views.",
                "Synthetic: partial coverage agrees; only natural viewpoint changes reveal more of the same ear.",
            ):
                with self.subTest(pose=pose, observation=observation):
                    q, r = self.ear_review(pose)
                    next(c for c in r["checks"] if c["key"] == "set/ear_hair_consistency")["observation"] = observation
                    d = core.assess(q, r)
                    self.assertEqual(d["state"], "awaiting_confirmation")
                    self.assertEqual(d["failed"], [])
                    approved = core.assess(q, r, confirmation={"schema": 1, "review_id": d["review_id"],
                        "decision": "approve", "reviewer": "fixture-human", "note": "Synthetic test only"})
                    self.assertTrue(approved["approved"])

    def test_ear_contradiction_or_uncertainty_blocks_even_with_high_total(self):
        key = "set/ear_hair_consistency"
        for pose in ("aligned", "current"):
            for status, rating, state in (("fail", 1, "needs_revision"),
                                           ("uncertain", None, "needs_review"),
                                           ("not_checked", None, "needs_review")):
                with self.subTest(pose=pose, status=status):
                    q, r = self.ear_review(pose)
                    check = next(c for c in r["checks"] if c["key"] == key)
                    check.update(status=status, rating=rating,
                        observation="Synthetic: front covering hair disappears in profile, exposing the ear.")
                    d = core.assess(q, r)
                    self.assertEqual(d["state"], state)
                    self.assertGreater(d["ordinal_points"], .95 * d["ordinal_max"])
                    self.assertFalse(d["approved"])
                    with self.assertRaisesRegex(ValueError, "cannot bypass"):
                        core.assess(q, r, confirmation={"schema": 1, "review_id": d["review_id"],
                            "decision": "approve", "reviewer": "fixture-human", "note": "Test only"})
                    if status == "fail":
                        self.assertEqual(core.assess(q, r, retry_counts={key: 2})["state"], "stop_for_user")

    def test_ear_requires_complete_evidence_and_invalidates_old_review(self):
        key = "set/ear_hair_consistency"
        for pose in ("aligned", "current"):
            q, r = self.ear_review(pose)
            check = next(c for c in r["checks"] if c["key"] == key)
            check["evidence"] = [{"role": "image/" + core.views_for("four-views", pose)[0]}]
            with self.assertRaisesRegex(ValueError, "evidence missing"):
                core.assess(q, r)
            r["checks"].remove(check)
            with self.assertRaisesRegex(ValueError, "required checks"):
                core.assess(q, r)
            old = copy.deepcopy(self.policies)
            old[1]["revision"] = "4"
            old[1]["criteria"] = [c for c in old[1]["criteria"] if c["id"] != "ear_hair_consistency"]
            old_q = core.make_request(q["snapshot"], old, q["evaluator"], {})
            with self.assertRaisesRegex(ValueError, "Stale or foreign review"):
                core.assess(q, core.response_template(old_q))
            self.assertEqual(core.make_request(q["snapshot"], old[:1], q["evaluator"], {}),
                             core.make_request(q["snapshot"], self.policies[:1], q["evaluator"], {}))

    def test_missing_carved_flow_cannot_hide_behind_hair_mass(self):
        matrix = core.criteria_for("front", "colored-matte-resin", self.policies)
        snapshot = {"manifest": {"mode": "front", "appearance": "colored-matte-resin"},
                    "files": [{"role": "image/front"}]}
        q = core.make_request(snapshot, self.policies, {"name": "synthetic", "version": "1"}, {})
        r = core.response_template(q)
        for check in r["checks"]:
            check.update(status="pass", rating=3, observation="Synthetic fixture only.",
                         evidence=[{"role": "image/front"}])
        flow = next(c for c in r["checks"] if c["key"] == "front/carved_flow")
        flow.update(status="fail", rating=1)
        d = core.assess(q, r)
        self.assertEqual(d["state"], "needs_revision")
        self.assertGreater(d["ordinal_points"], 0.9 * d["ordinal_max"])
        self.assertFalse(d["approved"])
        self.assertEqual(d["failed"], ["front/carved_flow"])
        r["checks"].remove(flow)
        with self.assertRaisesRegex(ValueError, "checks"):
            core.assess(q, r)


if __name__ == "__main__":
    unittest.main()
