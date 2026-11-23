"""Offline behavior regression. Synthetic authentication only; never read real environment."""

import io
import json
import stat
import struct
import sys
import tempfile
import unittest
import urllib.request
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import hi3d_api as cli
import hi3d_client as transport
import hi3d_jobs as jobs
from hi3d_artifacts import HttpsRedirect, download_job, fetch, unpack, validate_glb
from hi3d_jobs import adopt_job, job_outcome, query_job, submit_job, wait_job
from hi3d_parameters import build_plan, multipart
from hi3d_storage import load, public_record, save


def reply(data, code=200):
    return 200, {"code": code, "data": data, "msg": "synthetic-sensitive-response"}


class FakeClient:
    def __init__(self, responses=()):
        self.responses = iter(responses)
        self.calls = []
        self.auth_count = 0

    def auth(self):
        self.auth_count += 1

    def request(self, path, method="GET", *args, **kwargs):
        self.calls.append((path, method))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


class Response(io.BytesIO):
    status = 200


class Opener:
    def __init__(self, bodies):
        self.bodies = iter(bodies)
        self.requests = []

    def open(self, request, **kwargs):
        self.requests.append(request)
        value = next(self.bodies)
        return Response(
            json.dumps(value).encode() if isinstance(value, dict) else value
        )


def glb_bytes():
    payload = b'{"asset":{"version":"2.0"}}'
    payload += b" " * (-len(payload) % 4)
    return (
        struct.pack("<4sIIII", b"glTF", 2, 20 + len(payload), len(payload), 0x4E4F534A)
        + payload
    )


class Tests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.image = self.root / "front.png"
        # Planning validates type/size/hash, not pixel decoding.
        self.image.write_bytes(b"synthetic-image")
        self.mesh = self.root / "model.glb"
        self.mesh.write_bytes(glb_bytes())
        self.job = self.root / "job.json"

    def plan(self, **kwargs):
        return build_plan("model", images=[self.image], **kwargs)

    def test_offline_commands_never_construct_client(self):
        factory = lambda: self.fail("offline command attempted authentication")
        for arguments in (
            ["defaults"],
            [
                "submit",
                "model",
                "--image",
                str(self.image),
                "--job",
                str(self.job),
                "--dry-run",
            ],
        ):
            result, code = cli.execute(cli.parser().parse_args(arguments), factory)
            self.assertEqual(code, 0)
            self.assertFalse(self.job.exists())
        result, code = cli.execute(
            cli.parser().parse_args(
                ["adopt", "model", "task-1", "--job", str(self.job)]
            ),
            factory,
        )
        self.assertEqual(result["job"]["task_id"], "task-1")

    def test_only_uppercase_environment_contract_using_fake_mapping(self):
        class Environment:
            def __init__(self):
                self.names = []

            def get(self, name):
                self.names.append(name)
                return {"HI3D_AK": "synthetic-ak", "HI3D_SK": "synthetic-sk"}.get(name)

        fake = Environment()
        # Replace the module's os object. Never copy/enumerate the process environment.
        with patch.object(transport, "os", SimpleNamespace(environ=fake)):
            self.assertEqual(
                transport.environment_credentials(), ("synthetic-ak", "synthetic-sk")
            )
        self.assertEqual(fake.names, ["HI3D_AK", "HI3D_SK"])
        with (
            patch.object(transport, "os", SimpleNamespace(environ={})),
            self.assertRaises(RuntimeError),
        ):
            transport.environment_credentials()

    def test_client_is_lazy_and_auth_fixed_origin(self):
        opener = Opener([{"code": 200, "data": {"accessToken": "synthetic-token"}}])
        with patch.object(
            transport,
            "environment_credentials",
            return_value=("synthetic-ak", "synthetic-sk"),
        ) as auth:
            client = transport.Client(opener)
            auth.assert_not_called()
            client.auth()
        self.assertEqual(
            opener.requests[0].full_url, transport.BASE + "/open-api/v1/auth/token"
        )
        self.assertTrue(
            opener.requests[0].get_header("Authorization").startswith("Basic ")
        )
        self.assertIsNone(
            transport.NoRedirect().redirect_request(
                None, None, 302, "", {}, "https://storage.example"
            )
        )

    def test_post_401_never_replayed(self):
        client = transport.Client()
        client._token = "synthetic-token"
        with (
            patch.object(client, "_http", return_value=(401, {"code": 401})) as http,
            patch.object(client, "auth") as auth,
        ):
            client.request(transport.CREATE["model"], "POST", b"form")
        self.assertEqual(http.call_count, 1)
        auth.assert_not_called()

    def test_get_401_refreshes_at_most_once(self):
        client = transport.Client()
        client._token = "synthetic-token"
        with (
            patch.object(client, "_http", return_value=(401, {"code": 401})) as http,
            patch.object(client, "auth") as auth,
        ):
            client.request(transport.QUERY["model"])
        self.assertEqual(http.call_count, 2)
        self.assertEqual(auth.call_count, 1)

    def test_balance_validation(self):
        client = transport.Client()
        for value in (True, None, "NaN", "infinity", "not-a-number"):
            with (
                patch.object(
                    client, "request", return_value=reply({"totalBalance": value})
                ),
                self.assertRaises(ValueError),
            ):
                client.balance()
        with patch.object(
            client, "request", return_value=reply({"totalBalance": "15.5"})
        ):
            self.assertEqual(client.balance()["totalBalance"], "15.5")

    def test_multiview_order_and_parameter_override(self):
        left = self.root / "left.png"
        left.write_bytes(b"left-view")
        plan = build_plan(
            "model",
            images=[left, self.image],
            views="left,front",
            overrides=["resolution=2048master", "face=5000000"],
        )
        self.assertEqual(plan["parameters"]["multi_images_bit"], "1010")
        self.assertEqual(plan["files"][0]["path"], str(self.image.resolve()))
        self.assertEqual(plan["parameters"]["face"], 5000000)
        with self.assertRaises(ValueError):
            build_plan("model", images=[left, self.image], views="left,back")

    def test_plan_rejects_invalid_values_and_unknown_fields(self):
        for overrides in (
            ["face=nan"],
            ["face=99999"],
            ["shading=0.15"],
            ["unknown=value"],
            ["pbr=true"],
            ["model=hitem3dv2.1"],
            ["format=bmp"],
        ):
            with (
                self.subTest(overrides=overrides),
                self.assertRaises((ValueError, TypeError)),
            ):
                self.plan(overrides=overrides)

    def test_geometry_and_texturing_modes(self):
        self.assertNotIn("pbr", self.plan(overrides=["request_type=1"])["parameters"])
        self.assertEqual(
            len(self.plan(mesh=self.mesh, overrides=["request_type=2"])["files"]), 2
        )
        for kwargs in (
            {"mesh": self.mesh},
            {"overrides": ["request_type=2"]},
            {
                "mesh": self.mesh,
                "overrides": [
                    "request_type=2",
                    "model=hitem3dv2.1",
                    "resolution=1536fast",
                ],
            },
        ):
            with self.assertRaises(ValueError):
                self.plan(**kwargs)

    def test_relief_split_multicolor_contracts(self):
        relief = build_plan(
            "relief", images=[self.image], overrides=["rmbg=0", "format=glb"]
        )
        self.assertEqual(relief["parameters"]["format"], 4)
        self.assertNotIn("degree_rmbg", relief["parameters"])
        general = build_plan("split", mesh=self.mesh, overrides=["model=general"])
        self.assertNotIn("part", general["parameters"])
        self.assertEqual(general["parameters"]["level"], "medium")
        no_joint = build_plan("split", mesh=self.mesh, overrides=["joint=none"])
        self.assertNotIn("merge", no_joint["parameters"])
        colors = build_plan(
            "multicolor", mesh=self.mesh, overrides=["number_color=0", "format=3mf"]
        )
        self.assertEqual(colors["parameters"]["format"], 6)
        with self.assertRaises(ValueError):
            build_plan(
                "relief",
                images=[self.image],
                image_url="https://example.test/input.png",
            )

    def test_input_integrity_checked_before_auth_or_intent(self):
        planned = self.plan()
        self.image.write_bytes(b"changed")
        client = FakeClient()
        with self.assertRaises(ValueError):
            submit_job(client, self.job, planned)
        self.assertEqual(client.auth_count, 0)
        self.assertFalse(self.job.exists())

    def test_multipart_uses_verified_bytes(self):
        planned = self.plan()
        with multipart(planned["parameters"], planned["files"]) as (
            stream,
            content_type,
            length,
        ):
            body = stream.read()
        self.assertEqual(length, len(body))
        self.assertIn(self.image.read_bytes(), body)
        self.assertNotIn(str(self.image).encode(), body)
        self.assertIn("boundary=", content_type)

    def test_submit_reuses_exact_job_without_auth_or_post(self):
        client = FakeClient([reply({"task_id": "task-1"})])
        planned = self.plan()
        self.assertFalse(submit_job(client, self.job, planned)["reused"])
        self.assertTrue(submit_job(client, self.job, planned)["reused"])
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.auth_count, 1)
        with self.assertRaises(ValueError):
            submit_job(client, self.job, self.plan(overrides=["face=100000"]))

    def test_official_shape_id_survives_submit_query_download(self):
        task_id = "a" * 32 + ".jjewelry-aigc-merchant-api.Synthetic_1-2"
        client = FakeClient(
            [
                reply({"task_id": task_id}),
                reply({"state": "processing"}),
                reply(
                    {
                        "state": "success",
                        "url": "https://storage.test/result.glb?signature=synthetic",
                    }
                ),
            ]
        )
        result = submit_job(client, self.job, self.plan())
        self.assertEqual(result["job"]["state"], "queueing")
        self.assertEqual(load(self.job)["task_id"], task_id)
        self.assertTrue(submit_job(client, self.job, self.plan())["reused"])
        query_job(client, self.job)

        def fetcher(url, target):
            return fetch(url, target, Opener([glb_bytes()]))

        result = download_job(client, self.job, self.root / "download", fetcher)
        self.assertFalse(result["cached"])
        self.assertEqual([method for _, method in client.calls], ["POST", "GET", "GET"])
        self.assertTrue(
            all(path.endswith("task_id=" + task_id) for path, _ in client.calls[1:])
        )
        self.assertNotIn("signature", self.job.read_text())

    def test_live_submit_with_complete_parameters_needs_no_extra_gate(self):
        client = FakeClient([reply({"task_id": "task-1"})])
        result, code = cli.execute(
            cli.parser().parse_args(
                [
                    "submit",
                    "model",
                    "--image",
                    str(self.image),
                    "--job",
                    str(self.job),
                    "--set",
                    "model_type=v3.0:quality",
                    "--set",
                    "generation_type=both",
                ]
            ),
            lambda: client,
        )
        self.assertEqual(code, 0)
        self.assertEqual(result["job"]["task_id"], "task-1")
        self.assertEqual([method for _, method in client.calls], ["POST"])

    def test_adopt_preserves_dotted_identifier_and_rejects_unsafe_values(self):
        task_id = "Synthetic.jjewelry-aigc-api.KeepCase_12-34"
        factory = lambda: self.fail("adopt attempted authentication")
        result, code = cli.execute(
            cli.parser().parse_args(
                ["adopt", "model", task_id, "--job", str(self.job)]
            ),
            factory,
        )
        self.assertEqual(code, 0)
        self.assertEqual(result["job"]["task_id"], task_id)
        self.assertEqual(load(self.job)["task_id"], task_id)
        for value in (
            None,
            12,
            "",
            "a" * 201,
            "task/id",
            "task?token=x",
            "task\n",
            " task",
            "任务",
        ):
            with (
                self.subTest(value_type=type(value).__name__),
                self.assertRaises(ValueError),
            ):
                jobs.task_identifier(value)

    def test_id_checkpoint_survives_failure_before_state_update(self):
        task_id = "Synthetic.jjewelry-aigc-api.Checkpoint"
        client = FakeClient(
            [reply({"task_id": task_id}), reply({"state": "processing"})]
        )

        def interrupted_save(path, value, exclusive=False):
            save(path, value, exclusive)
            if value.get("task_id") and value["state"] == "submitting":
                raise KeyboardInterrupt("synthetic interruption after ID checkpoint")

        with (
            patch.object(jobs, "save", side_effect=interrupted_save),
            self.assertRaises(KeyboardInterrupt),
        ):
            submit_job(client, self.job, self.plan())
        self.assertEqual(load(self.job)["task_id"], task_id)
        self.assertEqual(load(self.job)["state"], "submitting")
        self.assertTrue(submit_job(client, self.job, self.plan())["reused"])
        self.assertEqual(query_job(client, self.job)[0]["state"], "processing")
        self.assertEqual([method for _, method in client.calls], ["POST", "GET"])

    def test_invalid_response_id_reports_stage_without_response_or_replay(self):
        client = FakeClient(
            [reply({"task_id": "https://storage.test/?signature=synthetic"})]
        )
        result = submit_job(client, self.job, self.plan())
        self.assertEqual(
            result["job"]["error"],
            {"type": "ValueError", "phase": "task_id_validation"},
        )
        self.assertEqual(result["job"]["state"], "submission_uncertain")
        self.assertNotIn("synthetic", self.job.read_text())
        self.assertTrue(submit_job(client, self.job, self.plan())["reused"])
        self.assertEqual(len(client.calls), 1)

    def test_ambiguous_submission_persists_and_never_resubmits(self):
        for index, response in enumerate(
            (
                TimeoutError("synthetic-sensitive-response"),
                reply({}),
                reply(None),
                (500, {"code": 500, "msg": "synthetic-sensitive-response"}),
            )
        ):
            with self.subTest(response_type=type(response).__name__):
                job_path = self.root / (str(index) + "-uncertain.json")
                client = FakeClient([response])
                first = submit_job(client, job_path, self.plan())
                self.assertEqual(first["job"]["state"], "submission_uncertain")
                self.assertEqual(job_outcome(first["job"])[1], 2)
                submit_job(client, job_path, self.plan())
                self.assertEqual(len(client.calls), 1)
                self.assertNotIn("synthetic-sensitive-response", job_path.read_text())

    def test_auth_failure_has_no_submission_intent(self):
        client = FakeClient()
        with (
            patch.object(client, "auth", side_effect=RuntimeError("synthetic")),
            self.assertRaises(RuntimeError),
        ):
            submit_job(client, self.job, self.plan())
        self.assertFalse(self.job.exists())
        self.assertEqual(client.calls, [])

    def test_adopt_all_routes_without_task_creation(self):
        for kind, route in transport.QUERY.items():
            path = self.root / (kind + ".json")
            adopt_job(kind, "task-1", path)
            client = FakeClient([reply({"state": "processing"})])
            job, _ = query_job(client, path)
            self.assertEqual(job["state"], "processing")
            self.assertEqual(client.calls, [(route + "?task_id=task-1", "GET")])

    def test_bad_query_cannot_reuse_stale_success(self):
        adopt_job("model", "task-1", self.job)
        client = FakeClient(
            [
                reply({"state": "success"}),
                reply({"state": "unknown", "url": "https://example.test/model.glb"}),
            ]
        )
        query_job(client, self.job)
        with self.assertRaises(ValueError):
            download_job(client, self.job, self.root / "output")
        self.assertEqual(job_outcome(load(self.job)), ("attention", 2))

    def test_wait_reports_failure_and_bounded_pending(self):
        adopt_job("model", "task-1", self.job)
        result, code = wait_job(
            FakeClient([reply({"state": "failed"})]), self.job, seconds=0
        )
        self.assertEqual((result["result"], code), ("failed", 1))
        clock_value = [0]

        def sleep(seconds):
            clock_value[0] += seconds

        client = FakeClient([reply({"state": "processing"})] * 3)
        result, code = wait_job(
            client,
            self.job,
            seconds=10,
            interval=5,
            clock=lambda: clock_value[0],
            sleep=sleep,
        )
        self.assertEqual((result["result"], code), ("pending", 0))
        self.assertEqual(clock_value[0], 10)
        self.assertEqual(len(client.calls), 3)

    def test_reports_remove_signed_queries_and_sensitive_fields(self):
        value = {
            "HI3D_AK": "synthetic-ak",
            "url": "https://storage.test/model.glb?signature=synthetic-signature#fragment",
        }
        output = json.dumps(public_record(value))
        self.assertNotIn("synthetic-ak", output)
        self.assertNotIn("synthetic-signature", output)
        self.assertNotIn("fragment", output)
        plan = build_plan(
            "relief",
            image_url="https://example.test/input.png?signature=synthetic-signature",
        )
        client = FakeClient(
            [reply({"task_id": "task-1", "accessToken": "synthetic-token"})]
        )
        submit_job(client, self.job, plan)
        self.assertNotIn("synthetic-signature", self.job.read_text())
        self.assertNotIn("synthetic-token", self.job.read_text())

    def test_download_never_sends_auth_or_overwrites(self):
        opener = Opener([glb_bytes()])
        target = self.root / "download.glb"
        fetch("https://storage.test/model.glb?signature=synthetic", target, opener)
        self.assertIsNone(opener.requests[0].get_header("Authorization"))
        self.assertEqual(target.read_bytes(), glb_bytes())
        with self.assertRaises(FileExistsError):
            fetch("https://storage.test/model.glb", target, opener)
        with self.assertRaises(ValueError):
            fetch("http://storage.test/model.glb", self.root / "new.glb", opener)
        with self.assertRaises(ValueError):
            HttpsRedirect().redirect_request(
                urllib.request.Request("https://storage.test/model.glb"),
                None,
                302,
                "",
                {},
                "http://storage.test/model.glb",
            )

    def test_invalid_glb_does_not_create_destination(self):
        target = self.root / "invalid.glb"
        with self.assertRaises(ValueError):
            fetch(
                "https://storage.test/model.glb",
                target,
                Opener([b"<html>not a model</html>"]),
            )
        self.assertFalse(target.exists())
        self.assertEqual(list(self.root.glob(".download-*")), [])
        validate_glb(self.mesh)

    def test_zip_rejects_traversal_symlinks_and_duplicates_before_extraction(self):
        for index, name in enumerate(
            (
                "../escape",
                "/absolute",
                "folder\\escape",
                "C:escape",
                "symlink",
                "duplicate",
            )
        ):
            archive = self.root / (str(index) + ".zip")
            with zipfile.ZipFile(archive, "w") as output:
                if name == "duplicate":
                    output.writestr("folder/file", b"first")
                    name = "folder/./file"
                info = zipfile.ZipInfo(name)
                if name == "symlink":
                    info.external_attr = (stat.S_IFLNK | 0o777) << 16
                output.writestr(info, b"payload")
            destination = self.root / ("extract-" + str(index))
            with self.assertRaises(ValueError):
                unpack(archive, destination)
            self.assertFalse(destination.exists())

    def test_artifact_cache_checks_extracted_content(self):
        adopt_job("model", "task-1", self.job)
        archive_bytes = io.BytesIO()
        with zipfile.ZipFile(archive_bytes, "w") as archive:
            archive.writestr("model.glb", glb_bytes())
        client = FakeClient(
            [
                reply(
                    {
                        "state": "success",
                        "url": "https://storage.test/result.zip?signature=synthetic-signature",
                    }
                )
            ]
        )

        def fetcher(url, target):
            return fetch(url, target, Opener([archive_bytes.getvalue()]))

        output = self.root / "artifacts"
        first = download_job(client, self.job, output, fetcher)
        self.assertFalse(first["cached"])
        self.assertTrue(download_job(FakeClient(), self.job, output)["cached"])
        self.assertNotIn("synthetic-signature", self.job.read_text())
        Path(first["artifact"]["files"][0]["path"]).write_bytes(b"edited")
        with self.assertRaises(ValueError):
            download_job(FakeClient(), self.job, output)

    def test_local_record_is_exclusive_and_private(self):
        save(self.job, {"state": "created"}, exclusive=True)
        with self.assertRaises(FileExistsError):
            save(self.job, {"state": "changed"}, exclusive=True)
        self.assertEqual(load(self.job)["state"], "created")
        self.assertEqual(stat.S_IMODE(self.job.stat().st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()
