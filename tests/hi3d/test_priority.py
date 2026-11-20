# 文件信息
# 本文件从归档发行锁和抽离范围调用优先级派生 CLI，核对首批依赖和输入校验。
# 所有派生产物和篡改输入都保存在测试临时目录。
"""验证 Hi3D 资源迁移优先级的离线命令契约。"""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


REPO = Path(__file__).resolve().parents[2]
CLI = REPO / "scripts" / "hi3d" / "derive-priority.py"
RELEASE = REPO / "docs" / "hi3d" / "upstream" / "1.2.11"
INVENTORY = RELEASE / "inventory"
EXTRACTION = RELEASE / "extraction" / "extraction.json"
SCOPE = RELEASE / "extraction" / "priority.scope.json"
P0_PRIORITY = RELEASE / "extraction" / "priority.json"
P1_SCOPE = RELEASE / "extraction" / "p1" / "priority.scope.json"
OUTPUT_NAMES = ("priority.json", "priority.md")
PREBUILT = "runtime/prebuilt-skills/"
RUN_TOOLS = PREBUILT + ".dependency-run-tools/scripts/"
CONFIG_RUNTIME = RUN_TOOLS + "config_runtime.py"
PATH_SAFETY = RUN_TOOLS + "path_safety.py"
ARTIFACT_REFS = RUN_TOOLS + "artifact_refs.py"
SESSION_SCHEMA = RUN_TOOLS + "session_schema.py"
BLENDER_WRAPPER = PREBUILT + ".dependency-blender-tools/scripts/execute.py"
PCG_LOADER = "runtime/support/pcg_yaml.py"


class PriorityTests(unittest.TestCase):
    """核对实际发行数据派生的路径闭包和双产物发布。"""

    def setUp(self) -> None:
        """分配独立的派生工作目录和输出位置。"""
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.output = self.root / "priority"

    def run_priority(
        self,
        *,
        extraction: Path = EXTRACTION,
        scope: Path = SCOPE,
        p0_priority: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """从仓库外启动正式入口，沿用已锁定的版本信息。

        :param extraction: 待核对的抽离范围文件。
        :param scope: 声明优先级入口和依赖的范围文件。
        :param p0_priority: 派生 P1 时所依据的 P0 清单。
        :return: 包含退出码和诊断信息的进程结果。
        """
        p1_args = ["--p0-priority", str(p0_priority)] if p0_priority is not None else []
        return subprocess.run(
            [
                sys.executable,
                "-B",
                str(CLI),
                "--inventory-dir",
                str(INVENTORY),
                "--extraction",
                str(extraction),
                "--scope",
                str(scope),
                "--output-dir",
                str(self.output),
                *p1_args,
            ],
            cwd=self.root,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def assert_no_publication(self, result: subprocess.CompletedProcess[str]) -> None:
        """确认非法输入在任一成品发布前失败。

        :param result: 使用非法输入执行正式入口的结果。
        """
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(any((self.output / name).exists() for name in OUTPUT_NAMES))

    def test_locked_paths_produce_repeatable_priority_outputs(self) -> None:
        """验证代表性的必需路径、发布范围和重跑字节稳定性。"""
        result = self.run_priority()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        first = {name: (self.output / name).read_bytes() for name in OUTPUT_NAMES}
        manifest = json.loads(first["priority.json"])
        p0 = manifest["p0"]
        files = p0["files"]

        for entry, required in ((CONFIG_RUNTIME, PATH_SAFETY), (ARTIFACT_REFS, SESSION_SCHEMA)):
            with self.subTest(entry=entry, required=required):
                self.assertEqual(files[entry]["kind"], "archive")
                self.assertIn(required, files[entry]["requires"])
                self.assertEqual(files[required]["kind"], "archive")
        self.assertEqual(files[BLENDER_WRAPPER]["kind"], "archive")
        self.assertEqual(files[PCG_LOADER]["kind"], "evidence")
        self.assertIn(BLENDER_WRAPPER, {path for group in p0["groups"].values() for path in group["entries"]})
        pilot = set(manifest["p1"]["pilot"])
        self.assertTrue(pilot)
        deferred = set(json.loads(SCOPE.read_bytes())["deferred"])
        self.assertTrue(deferred)
        archived = {path for path, record in files.items() if record["kind"] == "archive"}
        self.assertTrue(deferred.isdisjoint(archived | pilot))
        markdown = first["priority.md"].decode("utf-8")
        self.assertIn("P0", markdown)
        self.assertIn("P1", markdown)
        self.assertIn(BLENDER_WRAPPER, markdown)

        repeated = self.run_priority()
        self.assertEqual(repeated.returncode, 0, repeated.stdout + repeated.stderr)
        self.assertEqual({name: (self.output / name).read_bytes() for name in OUTPUT_NAMES}, first)

    def test_missing_declared_dependency_prevents_publication(self) -> None:
        """验证范围新增未锁定的依赖路径时无法发布优先级产物。"""
        content = json.loads(SCOPE.read_bytes())
        missing = RUN_TOOLS + "does-not-exist.py"
        content["files"][CONFIG_RUNTIME]["requires"].append(missing)
        scope = self.root / "invalid.scope.json"
        scope.write_text(json.dumps(content, ensure_ascii=False) + "\n", encoding="utf-8")

        result = self.run_priority(scope=scope)
        self.assert_no_publication(result)
        self.assertIn(missing, result.stderr)

    def test_tampered_extraction_candidate_prevents_publication(self) -> None:
        """验证抽离范围即使沿用原锁身份，候选变化也会被拒绝。"""
        content = json.loads(EXTRACTION.read_bytes())
        content["candidates"]["prebuilt"].remove(PREBUILT + "water-feature/scripts/run.py")
        extraction = self.root / "invalid.extraction.json"
        extraction.write_text(json.dumps(content, ensure_ascii=False) + "\n", encoding="utf-8")

        result = self.run_priority(extraction=extraction)
        self.assert_no_publication(result)
        self.assertRegex(result.stderr, r"(?i)extraction|抽离")

    def test_p1_keeps_p0_receipt_identity_and_derives_pilot_closure(self) -> None:
        """验证 P1 续接已发布的 P0 并保留试点中的本地闭包。"""
        before = P0_PRIORITY.read_bytes()
        result = self.run_priority(scope=P1_SCOPE, p0_priority=P0_PRIORITY)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        output = {name: (self.output / name).read_bytes() for name in OUTPUT_NAMES}
        manifest = json.loads(output["priority.json"])
        self.assertEqual(manifest["p0_priority_sha256"], hashlib.sha256(before).hexdigest())
        self.assertEqual(P0_PRIORITY.read_bytes(), before)
        self.assertEqual(set(path.name for path in self.output.iterdir()), set(OUTPUT_NAMES))
        files = manifest["p1"]["files"]
        copies = {path for path, file in files.items() if file["kind"] == "archive"}
        self.assertEqual(copies & {BLENDER_WRAPPER}, set())
        self.assertTrue(set(json.loads(before)["p1"]["pilot"]) <= copies)
        source_views = PREBUILT + ".dependency-model-preview/scripts/source_views.py"
        preview_scene = PREBUILT + ".dependency-model-preview/scripts/preview_scene.py"
        self.assertIn(preview_scene, files[source_views]["requires"])
        self.assertIn(preview_scene, copies)

        repeated = self.run_priority(scope=P1_SCOPE, p0_priority=P0_PRIORITY)
        self.assertEqual(repeated.returncode, 0, repeated.stdout + repeated.stderr)
        self.assertEqual({name: (self.output / name).read_bytes() for name in OUTPUT_NAMES}, output)

    def test_p1_rejects_modified_p0_priority(self) -> None:
        """验证 P0 清单发生偏移时，P1 在写入前失败。"""
        p0 = self.root / "priority.json"
        p0.write_bytes(P0_PRIORITY.read_bytes() + b" ")
        (self.root / SCOPE.name).write_bytes(SCOPE.read_bytes())

        result = self.run_priority(scope=P1_SCOPE, p0_priority=p0)
        self.assert_no_publication(result)
        self.assertIn("P0 priority", result.stderr)
