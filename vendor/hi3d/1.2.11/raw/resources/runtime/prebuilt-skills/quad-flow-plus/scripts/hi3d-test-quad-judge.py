import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("judge", Path(__file__).with_name("hi3d-quad-judge.py"))
judge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(judge)


class JudgeTests(unittest.TestCase):
    def metrics(self, **changes):
        values = {"forward_error": 0, "backward_error": 0, "min_angle": 90, "max_aspect": 1,
                  "max_normal_degrees": 0, "max_uv_stretch": 1, "closed_loops": True,
                  "nonquad": 0, "nonmanifold": 0}
        values.update(changes)
        return values

    def test_flat_gray_floor_is_one(self):
        result = judge.predict({"epsilon": 0.001, "regions": [{"id": "flat", "kind": "gray", "faces": 64, "area": 16}]})
        self.assertEqual(result["regions"][0]["aggressive"], 1)

    def test_red_is_kept(self):
        result = judge.predict({"epsilon": 0.001, "regions": [{"id": "edge", "kind": "red", "faces": 20, "area": 1}]})
        self.assertEqual(result["totals"]["aggressive"], 20)

    def test_unknown_kinds_are_rejected(self):
        for kind in ("blue", "RED", " red", "red ", "grey", "", None, True, False, 0, 1, [], {}, ["red"]):
            with self.subTest(kind=kind, mode="predict"):
                region = {"id": "edge", "kind": kind, "faces": 64, "area": 1}
                with self.assertRaisesRegex(ValueError, "kind"):
                    judge.predict({"epsilon": 0.01, "regions": [region]})
            for forward_error in (0, 1):
                with self.subTest(kind=kind, mode="verdict", forward_error=forward_error):
                    item = {"id": "edge", "kind": kind, "probe": True, "faces": 12, "level": 4,
                            "metrics": self.metrics(forward_error=forward_error)}
                    with self.assertRaisesRegex(ValueError, "kind"):
                        judge.verdict({"epsilon": 0.01, "regions": [item]})

    def test_valid_kinds_preserve_protection(self):
        for kind, floor in (("gray", 1), ("yellow", 1), ("red", 64)):
            with self.subTest(kind=kind):
                result = judge.predict({"epsilon": 0.01, "regions": [
                    {"id": "panel", "kind": kind, "faces": 64, "area": 1}]})["regions"][0]
                self.assertEqual(result["kind"], kind)
                self.assertEqual(result["aggressive"], floor)
                if kind == "red":
                    self.assertEqual(result["recommended"], 64)
                    self.assertEqual(result["conservative"], 64)
                    self.assertEqual(result["limit"], "protected")

    def test_omitted_kind_keeps_gray_default(self):
        region = {"id": "panel", "faces": 64, "area": 1}
        implicit = judge.predict({"epsilon": 0.01, "regions": [region]})
        explicit = judge.predict({"epsilon": 0.01, "regions": [dict(region, kind="gray")]})
        self.assertEqual(implicit, explicit)

    def test_boundary_segments_require_integers_even_for_red(self):
        for kind in ("gray", "yellow", "red"):
            for value in (4.5, "4.5", 3, 0, -1, True, False, None, [], {}, float("nan"), float("inf")):
                with self.subTest(kind=kind, value=value):
                    region = {"id": "panel", "kind": kind, "faces": 64, "area": 1, "boundary_segments": value}
                    with self.assertRaisesRegex(ValueError, "boundary_segments"):
                        judge.predict({"epsilon": 0.01, "regions": [region]})

    def test_boundary_segments_accept_integral_representations(self):
        for value in (17, 17.0, "17", "17.0"):
            with self.subTest(value=value):
                result = judge.predict({"epsilon": 0.01, "regions": [
                    {"id": "panel", "faces": 64, "area": 1, "boundary_segments": value}]})["regions"][0]
                self.assertEqual(result["aggressive"], 2)
                self.assertEqual(result["limit"], "boundary")

    def test_curvature_raises_floor(self):
        result = judge.predict({"epsilon": 0.1, "regions": [{"id": "curve", "kind": "gray", "faces": 400, "area": 4, "max_curvature": 10}]})
        self.assertEqual(result["regions"][0]["aggressive"], 50)

    def test_probe_success_updates_floor(self):
        result = judge.verdict({"epsilon": 0.01, "regions": [{"id": "flat", "probe": True, "level": 8, "faces": 1, "metrics": self.metrics()}]})
        self.assertIs(result["regions"][0]["probe"], True)
        self.assertEqual(result["regions"][0]["learned_floor"], 1)

    def test_probe_requires_boolean_before_decision(self):
        for probe in ("false", "true", "False", "0", "", None, 0, 1, 0.0, 1.0, -1, [], {}, [False], {"value": False}, float("nan"), float("inf")):
            for forward_error in (0, 1):
                for face_fields in ({}, {"faces": 12}):
                    with self.subTest(probe=probe, forward_error=forward_error, face_fields=face_fields):
                        item = {"id": "panel", "probe": probe, "level": 4,
                                "metrics": self.metrics(forward_error=forward_error), **face_fields}
                        with self.assertRaisesRegex(ValueError, "probe"):
                            judge.verdict({"epsilon": 0.01, "regions": [item]})

    def test_verdict_rejects_invalid_face_counts_before_decision(self):
        for value in (1.5, "1.5", 0, -1, True, False, None, float("nan"), float("inf")):
            for probe in (True, False):
                for forward_error in (0, 1):
                    with self.subTest(value=value, probe=probe, forward_error=forward_error):
                        item = {"id": "panel", "probe": probe, "level": 4, "faces": value,
                                "metrics": self.metrics(forward_error=forward_error)}
                        with self.assertRaisesRegex(ValueError, "faces"):
                            judge.verdict({"epsilon": 0.01, "regions": [item]})

    def test_probe_requires_face_count(self):
        for forward_error in (0, 1):
            with self.subTest(forward_error=forward_error):
                item = {"id": "panel", "probe": True, "level": 4,
                        "metrics": self.metrics(forward_error=forward_error)}
                with self.assertRaisesRegex(ValueError, "faces"):
                    judge.verdict({"epsilon": 0.01, "regions": [item]})

    def test_probe_floor_is_integer_and_reusable_by_predict(self):
        for value in (1, 12, 12.0, "12", "12.0"):
            with self.subTest(value=value):
                verdict = judge.verdict({"epsilon": 0.01, "regions": [
                    {"id": "panel", "probe": True, "level": 4, "faces": value, "metrics": self.metrics()}]})
                learned_floor = json.loads(json.dumps(verdict))["regions"][0]["learned_floor"]
                self.assertIs(type(learned_floor), int)
                self.assertEqual(learned_floor, int(float(value)))
                prediction = judge.predict({"epsilon": 0.01, "regions": [
                    {"id": "panel", "kind": "gray", "faces": 64, "area": 1, "learned_floor": learned_floor}]})
                self.assertEqual(prediction["regions"][0]["aggressive"], learned_floor)

    def test_nonprobe_does_not_learn_floor(self):
        for probe_fields in ({}, {"probe": False}):
            for face_fields in ({}, {"faces": 12}):
                for forward_error in (0, 1):
                    with self.subTest(probe_fields=probe_fields, face_fields=face_fields, forward_error=forward_error):
                        item = {"id": "panel", "level": 4, "metrics": self.metrics(forward_error=forward_error),
                                **probe_fields, **face_fields}
                        result = judge.verdict({"epsilon": 0.01, "regions": [item]})["regions"][0]
                        self.assertIs(result["probe"], False)
                        self.assertEqual(result["action"], "rollback_refine" if forward_error else "accept")
                        self.assertIsNone(result["learned_floor"])

    def test_failed_probe_does_not_learn_floor(self):
        result = judge.verdict({"epsilon": 0.01, "regions": [
            {"id": "panel", "probe": True, "level": 4, "faces": 12,
             "metrics": self.metrics(max_aspect=12)}]})["regions"][0]
        self.assertEqual(result["action"], "rollback_refine")
        self.assertIsNone(result["learned_floor"])

    def test_predict_rejects_invalid_face_counts_and_learned_floor(self):
        for field in ("faces", "learned_floor"):
            for kind in ("gray", "yellow", "red"):
                for value in (1.5, "1.5", 0, -1, True, None, float("nan"), float("inf")):
                    with self.subTest(field=field, kind=kind, value=value):
                        region = {"id": "panel", "kind": kind, "faces": 64, "area": 1, field: value}
                        with self.assertRaisesRegex(ValueError, field):
                            judge.predict({"epsilon": 0.01, "regions": [region]})

    def test_stretch_refines_one_level(self):
        result = judge.verdict({"epsilon": 0.01, "regions": [{"id": "panel", "level": 4, "metrics": self.metrics(max_aspect=12)}]})
        self.assertEqual(result["regions"][0]["action"], "rollback_refine")
        self.assertEqual(result["regions"][0]["next_level"], 3)

    def test_level_requires_allowed_integer_before_decision(self):
        for level in (4.5, "4.5", 0, -1, 5, 7, 9, True, False, None, [], {}, "", float("nan"), float("inf")):
            for forward_error in (0, 1):
                with self.subTest(level=level, forward_error=forward_error):
                    item = {"id": "panel", "level": level, "metrics": self.metrics(forward_error=forward_error)}
                    with self.assertRaisesRegex(ValueError, "level"):
                        judge.verdict({"epsilon": 0.01, "regions": [item]})

    def test_valid_levels_keep_refinement_order(self):
        levels = (8, 6, 4, 3, 2, 1)
        for index, level in enumerate(levels):
            for value in (level, float(level), str(level), str(float(level))):
                for forward_error in (0, 1):
                    with self.subTest(value=value, forward_error=forward_error):
                        item = {"id": "panel", "level": value, "metrics": self.metrics(forward_error=forward_error)}
                        result = judge.verdict({"epsilon": 0.01, "regions": [item]})["regions"][0]
                        self.assertIs(type(result["level"]), int)
                        self.assertEqual(result["level"], level)
                        if not forward_error:
                            self.assertEqual(result["action"], "accept")
                            self.assertEqual(result["next_level"], level)
                        elif level == 1:
                            self.assertEqual(result["action"], "keep_previous")
                            self.assertIsNone(result["next_level"])
                        else:
                            self.assertEqual(result["action"], "rollback_refine")
                            self.assertEqual(result["next_level"], levels[index + 1])

    def test_finest_failure_keeps_previous(self):
        result = judge.verdict({"epsilon": 0.01, "regions": [{"id": "panel", "level": 1, "metrics": self.metrics(forward_error=1)}]})
        self.assertEqual(result["regions"][0]["action"], "keep_previous")

    def test_missing_quality_metrics_are_rejected(self):
        for name in ("max_normal_degrees", "max_uv_stretch", "closed_loops", "nonquad", "nonmanifold"):
            with self.subTest(name=name):
                metrics = self.metrics()
                del metrics[name]
                with self.assertRaises(ValueError):
                    judge.verdict({"epsilon": 0.01, "regions": [{"id": "panel", "level": 4, "metrics": metrics}]})

    def test_yellow_zero_curvature_without_span(self):
        result = judge.predict({"epsilon": 0.001, "regions": [{"id": "soft", "kind": "yellow", "faces": 16, "area": 4}]})
        self.assertEqual(result["regions"][0]["aggressive"], 1)

    def test_invalid_budget_is_rejected(self):
        with self.assertRaises(ValueError):
            judge.predict({"epsilon": 0, "regions": []})

    def test_cli_rejects_invalid_kind_and_probe_without_partial_output(self):
        prediction = {"id": "edge", "kind": "red", "faces": 64, "area": 1}
        candidate = {"id": "panel", "probe": True, "level": 4, "faces": 12, "metrics": self.metrics()}
        cases = (("predict", prediction, "kind", "RED"), ("verdict", candidate, "kind", "unknown"),
                 ("verdict", candidate, "probe", "false"), ("verdict", candidate, "probe", 0))
        for mode, valid, field, invalid in cases:
            with self.subTest(mode=mode, field=field, invalid=invalid):
                with tempfile.TemporaryDirectory(prefix="hi3d-quad-judge-") as directory:
                    input_path = Path(directory) / "hi3d-input.json"
                    output_path = Path(directory) / "hi3d-output.json"
                    data = {"epsilon": 0.01, "regions": [valid, dict(valid, **{field: invalid})]}
                    input_path.write_text(json.dumps(data), encoding="utf-8")
                    process = subprocess.run([sys.executable, "-B", str(Path(judge.__file__).resolve()),
                                              mode, str(input_path), str(output_path)],
                                             capture_output=True, text=True, timeout=10)
                    self.assertEqual(process.returncode, 2, process.stderr)
                    self.assertIn("invalid input:", process.stderr)
                    self.assertIn(field, process.stderr)
                    self.assertEqual(process.stdout, "")
                    self.assertFalse(output_path.exists())

    def test_box_like_without_cavity_aligns(self):
        result = judge.route(self.route_input())
        self.assertEqual(result["route"], "primitive_align")

    def route_input(self, **changes):
        values = {"primitive": "cube", "primitive_silhouette_iou": [0.98, 0.99, 0.97], "cavity_status": "absent",
                  "cavity_evidence": {"method": "cross_sections", "scope": "panel", "record": "sample sections show a solid plate"}}
        values.update(changes)
        return values

    def align_input(self, **changes):
        values = {"iteration": 1, "faces": 3000, "v5_faces": 171459, "gray_yellow_max": 0.0005,
                  "silhouette_iou": [0.999, 0.999, 0.999], "silhouette_max_error": 0.0005,
                  "bad_red": 0, "bad_gray_yellow": 0, "epsilon": 0.00075,
                  "local_attempts": 0, "stalled": False, "fallback_validated": True, "metrics": self.metrics()}
        values.update(changes)
        return values

    def test_verified_cavity_uses_baseline(self):
        result = judge.route(self.route_input(cavity_status="present"))
        self.assertEqual(result["route"], "v5_baseline")
        self.assertIn("internal_cavity", result["reasons"])

    def test_route_requires_measurements(self):
        with self.assertRaises(ValueError):
            judge.route({"primitive": "cube"})

    def test_bbox_depth_does_not_establish_cavity(self):
        with self.assertRaises(ValueError):
            judge.route(self.route_input(cavity_status="present", cavity_evidence={"method": "bbox_depth", "scope": "assembly", "record": "12cm from bounding box"}))

    def test_large_red_area_does_not_force_fallback(self):
        self.assertEqual(judge.route(self.route_input(red_area_ratio=0.81))["route"], "primitive_align")

    def test_unknown_geometry_and_assembly_are_inspected(self):
        self.assertEqual(judge.route(self.route_input(cavity_status="unknown"))["route"], "inspect_geometry")
        self.assertEqual(judge.route(self.route_input(decomposition_needed=True))["route"], "inspect_components")

    def test_views_are_required_and_worst_view_controls_route(self):
        with self.assertRaises(ValueError):
            judge.route(self.route_input(primitive_silhouette_iou=0.99))
        self.assertEqual(judge.route(self.route_input(primitive_silhouette_iou=[0.99, 0.99, 0.7]))["route"], "v5_baseline")

    def test_align_prefers_local_red_then_gray_yellow(self):
        self.assertEqual(judge.align_step(self.align_input(bad_red=3, bad_gray_yellow=2))["action"], "add_closed_lines_red")
        self.assertEqual(judge.align_step(self.align_input(bad_gray_yellow=2))["action"], "add_closed_lines_gray_yellow")

    def test_low_percentiles_cannot_hide_worst_error(self):
        result = judge.align_step(self.align_input(metrics=self.metrics(backward_error=0.004), backward_p95=0.0001, gray_yellow_p95=0.0001))
        self.assertNotEqual(result["action"], "accept")
        self.assertIn("error", result["failures"])

    def test_align_cannot_bypass_quality_metrics(self):
        for name in ("max_normal_degrees", "max_uv_stretch", "closed_loops", "nonquad", "nonmanifold"):
            with self.subTest(name=name):
                metrics = self.metrics()
                del metrics[name]
                with self.assertRaises(ValueError):
                    judge.align_step(self.align_input(metrics=metrics))

    def test_geometry_match_with_bad_uv_is_not_accepted(self):
        result = judge.align_step(self.align_input(metrics=self.metrics(max_uv_stretch=4)))
        self.assertEqual(result["action"], "repair_quality")
        self.assertIn("uv", result["failures"])

    def test_uniform_refinement_only_after_local_stall(self):
        candidate = self.align_input(bad_red=10, stalled=True)
        self.assertEqual(judge.align_step(candidate)["action"], "add_closed_lines_red")
        self.assertEqual(judge.align_step(dict(candidate, local_attempts=2))["action"], "uniform_refine")

    def test_budget_is_checked_before_acceptance(self):
        self.assertEqual(judge.align_step(self.align_input(faces=200000))["action"], "fallback_v5")
        self.assertEqual(judge.align_step(self.align_input(next_faces=200000))["action"], "fallback_v5")
        self.assertEqual(judge.align_step(self.align_input(faces=200000, fallback_validated=False))["action"], "keep_best_review")

    def test_accept_requires_all_checks(self):
        self.assertEqual(judge.align_step(self.align_input())["action"], "accept")
        self.assertNotEqual(judge.align_step(self.align_input(silhouette_max_error=0.002))["action"], "accept")

    def test_invalid_measurements_do_not_pass(self):
        for value in (True, float("nan"), float("inf"), -1):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    judge.align_step(self.align_input(gray_yellow_max=value))
        with self.assertRaises(ValueError):
            judge.route(self.route_input(primitive_silhouette_iou=[1.1, 0.99, 0.99]))


if __name__ == "__main__":
    unittest.main()
