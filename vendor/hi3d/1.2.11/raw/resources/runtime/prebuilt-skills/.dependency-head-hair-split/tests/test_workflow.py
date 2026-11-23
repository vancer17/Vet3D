"""Offline behavior tests; no network, real credentials or user artifacts."""
import argparse
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import workflow
import build_html
import graphcut
from apply_labels import run as export, transfer_labels
from graphcut import solve
from label_texture import sample
from partition import read, validate
from timing import StageRecorder


def fixture(path, *, index_type=5123, interleaved=False):
    """Independent minimal GLB builder, with a real embedded two-tone image."""
    vertices = np.array([[x/12, y/12, 0] for y in range(13) for x in range(13)], dtype="<f4")
    faces = []
    for y in range(12):
        for x in range(12):
            a = y*13+x
            faces.extend([[a,a+1,a+14],[a,a+14,a+13]])
    faces = np.array(faces, dtype={5121:"u1",5123:"<u2",5125:"<u4"}[index_type])
    pixels = np.zeros((8,8,3), np.uint8)
    pixels[:,4:] = 255
    encoded = io.BytesIO()
    Image.fromarray(pixels).save(encoded, format="PNG")
    data, views, accessors = bytearray(), [], []
    def view(raw, stride=None):
        data.extend(b"\0"*(-len(data)%4))
        result = {"buffer":0,"byteOffset":len(data),"byteLength":len(raw)}
        if stride:
            result["byteStride"] = stride
        views.append(result)
        data.extend(raw)
        return len(views)-1
    uv = vertices[:,:2].copy()
    if interleaved:
        v = view(np.column_stack([vertices,uv]).astype("<f4").tobytes(),20)
        accessors.extend([{"bufferView":v,"componentType":5126,"count":len(vertices),"type":"VEC3"},
                          {"bufferView":v,"byteOffset":12,"componentType":5126,"count":len(vertices),"type":"VEC2"}])
    else:
        for arr,kind in ((vertices,"VEC3"),(uv,"VEC2")):
            accessors.append({"bufferView":view(arr.tobytes()),"componentType":5126,"count":len(vertices),"type":kind})
    accessors.append({"bufferView":view(faces.tobytes()),"componentType":index_type,"count":faces.size,"type":"SCALAR"})
    image_view = view(encoded.getvalue())
    doc = {"asset":{"version":"2.0"},"buffers":[{"byteLength":len(data)}],
           "bufferViews":views,"accessors":accessors,"images":[{"bufferView":image_view,"mimeType":"image/png"}],
           "textures":[{"source":0,"sampler":0}],"samplers":[{"wrapS":33071,"wrapT":33071}],
           "materials":[{"pbrMetallicRoughness":{"baseColorTexture":{"index":0}}}],
           "meshes":[{"primitives":[{"attributes":{"POSITION":0,"TEXCOORD_0":1},"indices":2,"material":0}]}],
           "nodes":[{"mesh":0,"translation":[1,2,3]}],"scenes":[{"nodes":[0]}],"scene":0}
    meta = json.dumps(doc).encode()
    meta += b" "*(-len(meta)%4)
    data.extend(b"\0"*(-len(data)%4))
    body = struct.pack("<I4s",len(meta),b"JSON")+meta+struct.pack("<I4s",len(data),b"BIN\0")+data
    path.write_bytes(struct.pack("<4sII",b"glTF",2,len(body)+12)+body)
    return vertices,faces


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root/"source.glb"
        self.v,self.f = fixture(self.source)

    def tearDown(self):
        self.tmp.cleanup()

    def test_sample_stride_and_index_widths(self):
        for kind in (5121,5123,5125):
            fixture(self.source,index_type=kind,interleaved=True)
            v,f,labels,report = sample(self.source,.5)
            expected = (v[f].mean(1)[:,0]>.5).astype(int)
            np.testing.assert_array_equal(labels,expected)
            self.assertEqual(report["threshold"],.5)

    def test_cut_and_lossless_export(self):
        v,f,initial,_ = sample(self.source)
        labels,stats = solve(v,f,initial)
        self.assertEqual(stats["cut_value"],stats["flow_value"])
        self.assertEqual(set(labels),{0,1})
        np.save(self.root/"labels.npy",labels)
        before = self.source.read_bytes()
        export(argparse.Namespace(source=self.source,label_mesh=self.source,
            labels=self.root/"labels.npy",output_dir=self.root/"parts",tolerance=1e-6))
        report = json.loads((self.root/"parts/report.json").read_text())
        self.assertEqual(report["triangles"]["total"],len(f))
        self.assertEqual(report["triangles"]["head"]+report["triangles"]["hair"],len(f))
        self.assertEqual(before,self.source.read_bytes())
        self.assertTrue(report["verified_original_binary_and_materials"])

    def test_permuted_faces_map(self):
        labels = np.arange(len(self.f))%2
        order = np.arange(len(self.f))[::-1]
        result,report = transfer_labels(self.v,self.f,self.v,self.f[order],labels[order],1e-6)
        np.testing.assert_array_equal(result,labels)
        self.assertEqual(report["mode"],"triangle_centers")

    def test_changed_geometry_rejected(self):
        labels = np.arange(len(self.f))%2
        with self.assertRaises(ValueError):
            transfer_labels(self.v,self.f,self.v+1,self.f,labels,1e-6)
        with self.assertRaises(ValueError):
            transfer_labels(self.v,self.f,self.v,self.f[:-1],labels[:-1],1e-6)

    def test_invalid_texture_and_container(self):
        for threshold in (float("nan"),0,1):
            with self.assertRaises(ValueError):
                sample(self.source,threshold)
        doc,binary = read(self.source)
        doc["meshes"].append(doc["meshes"][0])
        with self.assertRaises(ValueError):
            validate(doc,binary)
        self.source.write_bytes(self.source.read_bytes()[:-1])
        with self.assertRaises(ValueError):
            read(self.source)

    def test_dropped_labels_rejected(self):
        labels = np.arange(len(self.f))%2
        labels[0] = -1
        np.save(self.root/"labels.npy",labels)
        with self.assertRaises(ValueError):
            export(argparse.Namespace(source=self.source,label_mesh=self.source,
                labels=self.root/"labels.npy",output_dir=self.root/"parts",tolerance=1e-6))
        self.assertFalse((self.root/"parts/report.json").exists())

    def test_cache_inputs_artifacts_and_shared_code(self):
        inputs = {"mesh":self.source}
        key = workflow.fingerprint("split",inputs,{"threshold":.5})
        stage = self.root/"stage"
        self.assertFalse(workflow.cached(stage,key))
        stage.mkdir()
        (stage/"artifact.txt").write_text("complete")
        workflow.publish(stage,key)
        self.assertTrue(workflow.cached(stage,key))
        prepare = workflow.fingerprint("prepare",inputs,{})
        original_digest = workflow.digest
        with patch.object(workflow,"digest",side_effect=lambda path:
                "changed" if Path(path).name == "glb_clips.py" else original_digest(path)):
            changed = workflow.fingerprint("split",inputs,{"threshold":.5})
            # Parser code affects split but does not invalidate unrelated rendering.
            self.assertEqual(prepare,workflow.fingerprint("prepare",inputs,{}))
        with self.assertRaises(ValueError):
            workflow.cached(stage,changed)
        (stage/"artifact.txt").write_text("corrupt")
        with self.assertRaises(ValueError):
            workflow.cached(stage,key)

    def test_timeout_records_interrupted_and_no_retry(self):
        stage = self.root/"budget"
        stage.mkdir()
        recorder = StageRecorder(self.root,"test","attempt")
        with self.assertRaises(SystemExit) as caught:
            with recorder.stage("split"):
                workflow.bounded([sys.executable,"-c","import time; time.sleep(5)"],stage,.05)
        self.assertEqual(caught.exception.code,3)
        recorder.finish("interrupted")
        self.assertEqual(json.loads((stage/"heartbeat.json").read_text())["status"],"timeout")
        self.assertEqual(recorder.records[0]["status"],"interrupted")

    def test_api_plan_and_resume_are_explicit(self):
        api = self.root/"api"
        (api/"scripts").mkdir(parents=True)
        (api/"scripts/hi3d_api.py").write_text("# mock tool path; never executed")
        args = argparse.Namespace(api_dir=api,command="plan",mesh=self.source,
            label_image=self.source,job=self.root/"job.json",resolution="2048quality",
            session=None)
        command = workflow.api_command(args)
        self.assertIn("--dry-run",command)
        self.assertIn("request_type=2",command)
        args.command = "submit"
        command = workflow.api_command(args)
        self.assertNotIn("--dry-run",command)
        self.assertNotIn("--billing-grant",command)
        args.command = "query"
        with self.assertRaises(FileNotFoundError):
            workflow.api_command(args)
        args.job.write_text('{"task_id":"existing.task.id","state":"processing"}')
        self.assertEqual(workflow.api_command(args)[2:4],["query","--job"])
        self.assertIn("existing.task.id",args.job.read_text())

    def test_local_cli_cache_does_not_restart_kernel(self):
        args = argparse.Namespace(command="split",run_dir=self.root/"run",
            mesh=self.source,label_mesh=self.source,threshold=.5,tolerance=1e-6,max_seconds=300,confirmed_cut=True)
        recorder = StageRecorder(args.run_dir,"test","one")
        workflow.local(args,recorder)
        recorder.finish("completed")
        recorder = StageRecorder(args.run_dir,"test","two")
        with patch.object(workflow,"bounded",side_effect=AssertionError("must not restart")):
            workflow.local(args,recorder)
        recorder.finish("completed")
        self.assertEqual(recorder.records[0]["status"],"skipped")
        reply = json.loads((args.run_dir/"tool_result.json").read_text())
        self.assertEqual(reply["artifacts"],[])

    def test_cut_requires_explicit_choice_before_any_output(self):
        for confirmed, threshold in ((False, .5), (True, None)):
            args = argparse.Namespace(command="split", run_dir=self.root/"blocked",
                mesh=self.source, label_mesh=self.source, threshold=threshold, confirmed_cut=confirmed)
            with self.assertRaisesRegex(ValueError, "Deliver workflow.py html first"):
                workflow.local(args, None)
            self.assertFalse(args.run_dir.exists())

    def test_html_preparation_does_not_cut_and_preserves_world_coordinates(self):
        with patch.object(graphcut, "maximum_flow", side_effect=AssertionError("HTML must not cut")):
            arrays, meta, image = build_html.prepare(self.source, self.source, .5)
            path = build_html.build(self.source, self.source, self.root/"html", .5)
        np.testing.assert_allclose(arrays["positions"], self.v + [1, 2, 3])
        np.testing.assert_array_equal(arrays["faces"], self.f)
        self.assertEqual(meta["material"]["filename"], "original.png")
        self.assertTrue(image.startswith(b"\x89PNG"))
        self.assertFalse(meta["mincut_executed"])
        self.assertEqual(meta["state"], "awaiting_user_action")
        self.assertEqual({p.name for p in path.parent.iterdir()}, {"head-hair-split.html", "manifest.json"})
        manifest = json.loads((path.parent/"manifest.json").read_text())
        self.assertEqual(manifest["htmlSha256"], workflow.digest(path))

    def test_html_cli_handoff_and_viewer_source_invalidation(self):
        args = argparse.Namespace(command="html", run_dir=self.root/"interactive",
            mesh=self.source, label_mesh=self.source, threshold=.5, tolerance=1e-6, max_seconds=300)
        recorder = StageRecorder(args.run_dir, "test", "html")
        workflow.local(args, recorder)
        recorder.finish("completed")
        reply = json.loads((args.run_dir/"tool_result.json").read_text())
        self.assertEqual(reply["next_checkpoint"], "handoff")
        self.assertEqual({a["output"] for a in reply["artifacts"]}, {"html", "manifest"})
        self.assertFalse((args.run_dir/"04_split").exists())
        self.assertFalse(list(args.run_dir.rglob("*.npy")))
        before = workflow.fingerprint("html", {"mesh": self.source}, {})
        split_before = workflow.fingerprint("split", {"mesh": self.source}, {})
        original = workflow.digest
        with patch.object(workflow, "digest", side_effect=lambda p:
                "changed" if Path(p).name == "cut.js" else original(p)):
            self.assertNotEqual(before, workflow.fingerprint("html", {"mesh": self.source}, {}))
            self.assertEqual(split_before, workflow.fingerprint("split", {"mesh": self.source}, {}))

    def test_browser_kernel_matches_python_and_exports_fbx(self):
        import subprocess
        html = build_html.build(self.source, self.source, self.root/"parity", .5)
        script = Path(__file__).with_name("check_browser_kernel.cjs")
        result = subprocess.run(["node", str(script), str(html)], capture_output=True, text=True, check=True, timeout=30)
        report = json.loads(result.stdout)
        for row in report["cuts"]:
            v, f, labels, _ = sample(self.source, row["threshold"])
            expected, stats = solve(v, f, labels)
            np.testing.assert_array_equal(row["labels"], expected)
            self.assertEqual(row["stats"]["flow_value"], stats["flow_value"])
        self.assertTrue(report["fbx_header_valid"])
        self.assertTrue(report["embedded_image_preserved"])
        self.assertEqual(report["no_boundary_labels"], [0, 1])


if __name__ == "__main__":
    unittest.main()
