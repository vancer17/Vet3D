"""Offline observable-behavior checks for the task timing journal."""

from datetime import datetime
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "parts_timing", Path(__file__).resolve().parents[1] / "scripts" / "timing.py"
)
timing = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(timing)


class TimingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def events(self):
        return [json.loads(line) for line in (self.root / "timings.jsonl").read_text().splitlines()]

    def external(self, **updates):
        record = dict(
            task_id="task", attempt_id="attempt", stage="visual_review",
            status="completed", started_at="2026-09-09T09:00:00+08:00",
            ended_at="2026-09-09T09:00:07+08:00", elapsed_seconds=6.75,
            timing_method="external_measured",
        )
        record.update(updates)
        return record

    def test_running_event_precedes_work_and_total_does_not_sum_nested_stages(self):
        with patch.object(timing.time, "monotonic", side_effect=[0, 1, 2, 8, 9, 10]):
            recorder = timing.StageRecorder(self.root, "task", "attempt", "prior")
            with recorder.stage("build") as record:
                start = self.events()[-1]
                self.assertEqual(start["status"], "running")
                self.assertIsNone(start["ended_at"])
                self.assertIsNone(start["elapsed_seconds"])
                with recorder.stage("module"):
                    pass
            self.assertEqual(record["status"], "completed")
            summary = recorder.finish("completed")
        self.assertEqual(summary["elapsed_seconds"], 10)
        self.assertEqual(sum(item["elapsed_seconds"] for item in summary["stages"]), 14)
        self.assertEqual([e["status"] for e in self.events()], ["running", "running", "completed", "completed"])
        self.assertEqual(len(summary["stages"]), 2)
        self.assertEqual(json.loads((self.root / "timing_summary.json").read_text()), summary)
        for event in self.events():
            self.assertEqual(event["previous_attempt_id"], "prior")
            for key in ("started_at", "ended_at", "recorded_at"):
                if event[key] is not None:
                    self.assertEqual(datetime.fromisoformat(event[key]).utcoffset().total_seconds(), 0)

    def test_exceptions_keep_identity_and_record_failure_or_interruption(self):
        cases = [(ValueError("invalid"), "failed"), (BaseException("base"), "failed"),
                 (KeyboardInterrupt(), "interrupted"), (SystemExit(2), "interrupted")]
        for index, (error, status) in enumerate(cases):
            with self.subTest(error=type(error).__name__):
                recorder = timing.StageRecorder(self.root, "task", "attempt-" + str(index))
                caught = None
                try:
                    with recorder.stage("build"):
                        raise error
                except BaseException as exc:
                    caught = exc
                self.assertIs(caught, error)
                self.assertEqual(self.events()[-1]["status"], status)
                self.assertGreaterEqual(self.events()[-1]["elapsed_seconds"], 0)
                summary = recorder.finish(status)
                self.assertEqual(summary["stages"][0]["error_type"], type(error).__name__)
        self.assertEqual(len(self.events()), 8)

    def test_skipped_stage_has_no_fabricated_execution_interval(self):
        recorder = timing.StageRecorder(self.root, "task", "attempt")
        skipped = recorder.skip("export", "Preview mode")
        summary = recorder.finish("completed")
        self.assertEqual(skipped["status"], "skipped")
        for field in ("started_at", "ended_at", "elapsed_seconds"):
            self.assertIsNone(skipped[field])
        self.assertEqual(skipped["reason"], "Preview mode")
        self.assertEqual(summary["stages"], [skipped])
        self.assertEqual(len(self.events()), 1)

    def test_external_records_normalize_timezone_and_keep_measured_duration(self):
        record = timing.record_external_stage(self.root, self.external())
        self.assertEqual(record["started_at"], "2026-09-09T01:00:00+00:00")
        self.assertEqual(record["elapsed_seconds"], 6.75)
        unknown = timing.record_external_stage(self.root, self.external(
            stage="manual_build", status="interrupted", ended_at=None,
            elapsed_seconds=None, missing_reason="Observer lost connection before the end",
        ))
        self.assertIsNone(unknown["ended_at"])
        self.assertIsNone(unknown["elapsed_seconds"])
        self.assertEqual(len(self.events()), 2)
        self.assertFalse((self.root / "timing_summary.json").exists())

    def test_invalid_external_records_do_not_change_journal(self):
        timing.record_external_stage(self.root, self.external())
        previous = (self.root / "timings.jsonl").read_bytes()
        invalid = [
            {"elapsed_seconds": -1}, {"elapsed_seconds": float("nan")},
            {"elapsed_seconds": float("inf")}, {"elapsed_seconds": True},
            {"elapsed_seconds": None}, {"ended_at": None},
            {"started_at": "2026-09-09T09:00:00"},
            {"ended_at": "2026-09-08T09:00:00+08:00"},
            {"status": "running"}, {"task_id": ""},
            {"status": "skipped", "reason": "Not requested"},
        ]
        for updates in invalid:
            with self.subTest(updates=updates):
                with self.assertRaises(ValueError):
                    timing.record_external_stage(self.root, self.external(**updates))
                self.assertEqual((self.root / "timings.jsonl").read_bytes(), previous)

    def test_preflight_can_be_included_with_real_process_start(self):
        with patch.object(timing.time, "monotonic", side_effect=[15, 20]):
            recorder = timing.StageRecorder(
                self.root, "task", "attempt", "prior",
                started_at="2026-09-09T01:00:00+00:00", started_clock=10,
            )
            preflight = self.external(stage="preflight", ended_at="2026-09-09T09:00:05+08:00", elapsed_seconds=5)
            for field in ("task_id", "attempt_id"):
                preflight.pop(field)
            recorded = recorder.add_record(preflight)
            summary = recorder.finish("completed")
        self.assertEqual(recorded["previous_attempt_id"], "prior")
        self.assertEqual(summary["started_at"], "2026-09-09T01:00:00+00:00")
        self.assertEqual(summary["elapsed_seconds"], 10)
        self.assertEqual(summary["stages"], [recorded])

    def test_attempt_identity_is_explicit_and_existing_history_is_retained(self):
        first = timing.StageRecorder(self.root, "task", "attempt-1")
        first.skip("export", "Not requested")
        first.finish("completed")
        second = timing.StageRecorder(self.root, "task", "attempt-2", "attempt-1")
        with self.assertRaises(ValueError):
            second.add_record(self.external())
        second.skip("export", "Still not requested")
        summary = second.finish("completed")
        self.assertEqual([e["attempt_id"] for e in self.events()], ["attempt-1", "attempt-2"])
        self.assertEqual(len(summary["stages"]), 1)
        self.assertEqual(summary["previous_attempt_id"], "attempt-1")
        self.assertIs(second.finish("completed"), summary)
        with self.assertRaises(RuntimeError):
            second.skip("late", "After finish")

    def test_atomic_write_failure_preserves_previous_complete_files(self):
        recorder = timing.StageRecorder(self.root, "task", "attempt")
        recorder.skip("export", "Not requested")
        previous = (self.root / "timings.jsonl").read_bytes()
        with patch.object(timing.os, "replace", side_effect=OSError("replace unavailable")):
            with self.assertRaises(OSError):
                recorder.skip("review", "Not requested")
        self.assertEqual((self.root / "timings.jsonl").read_bytes(), previous)
        self.assertEqual(list(self.root.glob("*.tmp")), [])
        recorder.finish("completed")
        saved = (self.root / "timing_summary.json").read_bytes()
        next_attempt = timing.StageRecorder(self.root, "task", "next", "attempt")
        with patch.object(timing.os, "replace", side_effect=OSError("replace unavailable")):
            with self.assertRaises(OSError):
                next_attempt.finish("failed")
        self.assertEqual((self.root / "timing_summary.json").read_bytes(), saved)

    def test_journal_failure_does_not_replace_original_stage_exception(self):
        recorder = timing.StageRecorder(self.root, "task", "attempt")
        original = KeyboardInterrupt()
        caught = None
        real_replace = timing.os.replace
        replacements = 0

        def fail_final_replace(source, target):
            nonlocal replacements
            replacements += 1
            if replacements > 1:
                raise OSError("replace unavailable")
            return real_replace(source, target)

        with patch.object(timing.os, "replace", side_effect=fail_final_replace):
            try:
                with recorder.stage("build"):
                    raise original
            except BaseException as error:
                caught = error
        self.assertIs(caught, original)
        self.assertEqual(recorder.records[-1]["status"], "interrupted")
        self.assertEqual([event["status"] for event in self.events()], ["running"])

    def test_start_pair_and_finishing_during_running_stage_are_rejected(self):
        with self.assertRaises(ValueError):
            timing.StageRecorder(self.root, "task", "attempt", started_clock=0)
        with patch.object(timing.time, "monotonic", return_value=5):
            with self.assertRaises(ValueError):
                timing.StageRecorder(self.root, "task", "attempt", started_at="2026-09-09T01:00:00+00:00", started_clock=6)
        recorder = timing.StageRecorder(self.root, "task", "attempt")
        with recorder.stage("build"):
            with self.assertRaises(RuntimeError):
                recorder.finish("completed")
        recorder.finish("completed")


if __name__ == "__main__":
    unittest.main()
