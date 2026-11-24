# 文件信息：L1-05 配置、真实存储和诊断的上层装配验证。
# 作用：验证原身份交接、重开、失败清理和有限宿主，不复写已有存储内部测试。
# 证据边界：文件为合成字节，生成使用既有替身，不代表 Blender、BFF 或动物质量。
"""从公开入口验证实际配置消费及诊断与业务事实的分离。"""

import asyncio
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from vet3d.adapters import LocalDiagnosticFiles
from vet3d.artifacts import ContentFingerprint, FileReference
from vet3d.bootstrap import (
    initialize_operations, is_diagnostics_active, load_settings, open_operations,
    run_reconstruction_probe,
)
from vet3d.identity import ArtifactId, ArtifactIdentity, TaskIdentity, WorkspaceId
from vet3d.resources import InterpreterRequirement


def _configuration(base: Path) -> Path:
    """写出隔离的合法 YAML 子集，保留独立输入与资源来源目录。

    :param base: 当前测试拥有的临时父目录。
    :returns: 唯一配置入口使用的实际文件。
    """
    for name in ("inputs", "sources"):
        (base / name).mkdir(mode=0o700)
    value = {
        "workspaces": {"root": "workspaces"},
        "files": {"input_root": "inputs", "max_file_bytes": 4096},
        "resources": {
            "root": "resources", "source_root": "sources", "max_readers": 1,
            "limits": {"max_manifest_bytes": 8192, "max_files": 4, "max_file_bytes": 4096, "max_total_bytes": 8192},
        },
        "diagnostics": {"root": "logs"},
        "interpreters": [{"runtime": "Blender Python", "path": "not-installed/blender"}],
    }
    path = base / "config.yaml"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


class OperationsRuntimeTests(unittest.IsolatedAsyncioTestCase):
    """通过真实文件、原身份及替身生成消费方检查完整装配。"""

    async def asyncSetUp(self) -> None:
        """创建配置与已完成上传的暂存根，隔离进程环境和诊断输出。"""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.config = _configuration(self.base)
        environment = patch.dict(os.environ, {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        self.settings = load_settings(self.config)
        stream = contextlib.redirect_stderr(io.StringIO())
        stream.__enter__()
        self.addCleanup(stream.__exit__, None, None, None)

    async def test_real_storage_and_correlated_diagnostics_reopen(self) -> None:
        """登记真实文件后重开同一资产；诊断只回读保留窗口中的原关联。"""
        runtime = await initialize_operations(self.settings)
        self.addAsyncCleanup(runtime.aclose)
        workspace = WorkspaceId(uuid4())
        other = WorkspaceId(uuid4())
        await runtime.workspaces.create(workspace_id=workspace, display_name="第一工作区")
        await runtime.workspaces.create(workspace_id=other, display_name="第二工作区")
        payload = b"real stored bytes, no animal evidence"
        source = self.settings.files.input_root / "input.bin"
        source.write_bytes(payload)
        source.chmod(0o600)
        artifact = ArtifactIdentity(ArtifactId(uuid4()), workspace)
        reference = FileReference(artifact.id, ContentFingerprint(hashlib.sha256(payload).hexdigest(), len(payload)))
        files = await runtime.files(workspace)
        await files.store_new(artifact, reference, source.name)
        catalog = await runtime.artifacts(workspace)
        registered = await catalog.register(artifact, reference)
        records = await runtime.diagnostics.reader.read_workspace(workspace)
        self.assertTrue(records.records)
        self.assertTrue(all(item.workspace_id == workspace for item in records.records))
        self.assertTrue(any(item.artifact_id == artifact.id for item in records.records))
        self.assertEqual(records.status.dropped_records, 0)
        old_runtime_id = runtime.diagnostics.runtime_id
        status = await runtime.aclose()
        self.assertIsNone(status.write_error)
        self.assertFalse(is_diagnostics_active())
        with self.assertRaises(RuntimeError):
            await runtime.files(workspace)
        reopened = await open_operations(self.settings)
        self.addAsyncCleanup(reopened.aclose)
        recovered = await reopened.artifacts(workspace)
        self.assertEqual(await recovered.resolve(artifact.id), registered)
        retained = await reopened.diagnostics.reader.read_workspace(workspace)
        self.assertTrue(any(item.runtime_id == old_runtime_id for item in retained.records))
        self.assertNotEqual(old_runtime_id, reopened.diagnostics.runtime_id)

    async def test_real_consumer_task_association_and_output_failure_do_not_change_result(self) -> None:
        """实际生成消费方的结构化关联可查询；诊断落盘故障不阻止原提交。"""
        runtime = await initialize_operations(self.settings)
        self.addAsyncCleanup(runtime.aclose)
        results = await run_reconstruction_probe()
        task = results[0].request.task
        read = await runtime.diagnostics.reader.read_task(task)
        self.assertEqual({item.attempt_id for item in read.records}, {item.request.attempt.id for item in results})
        self.assertTrue(all(item.workspace_id == task.workspace_id and item.task_id == task.id for item in read.records))
        wrong_workspace = TaskIdentity(task.id, WorkspaceId(uuid4()))
        self.assertEqual((await runtime.diagnostics.reader.read_task(wrong_workspace)).records, ())
        with patch.object(LocalDiagnosticFiles, "append", side_effect=OSError("模拟日志写入故障")):
            second_results = await run_reconstruction_probe()
            observed = await runtime.diagnostics.reader.read_task(second_results[0].request.task)
            self.assertIsNotNone(observed.status.write_error)
            self.assertGreater(observed.status.dropped_records, 0)
        self.assertEqual(len(second_results), 2)
        self.assertTrue(all(result.outputs for result in second_results))

    async def test_interpreter_location_is_exact_declaration_not_executable_fact(self) -> None:
        """定位返回未安装的配置位置，版本与名称不同均不自动替换解释器。"""
        runtime = await initialize_operations(self.settings)
        self.addAsyncCleanup(runtime.aclose)
        requirement = InterpreterRequirement("Blender Python", "version deliberately not probed", ())
        self.assertEqual(runtime.configured_interpreter(requirement), self.base / "not-installed/blender")
        self.assertFalse((self.base / "not-installed/blender").exists())
        self.assertIsNone(runtime.configured_interpreter(InterpreterRequirement("python", "any", ())))

    async def test_partial_startup_releases_owners_without_repair_or_atomic_claim(self) -> None:
        """资源根拒绝时已建工作区保留，所有者释放且不自动删除或修复。"""
        self.settings.resources.root.mkdir(mode=0o755)
        with self.assertRaises((OSError, ValueError)):
            await initialize_operations(self.settings)
        self.assertFalse(is_diagnostics_active())
        self.assertTrue(self.settings.workspaces.root.is_dir())
        self.assertEqual(self.settings.resources.root.stat().st_mode & 0o777, 0o755)
        with self.assertRaises((OSError, ValueError)):
            await open_operations(self.settings)
        self.assertFalse(is_diagnostics_active())


class OperationsCommandTests(unittest.TestCase):
    """从仓库外调用实际安装入口，观察明确的有限命令副作用。"""

    def test_initialization_reopen_and_missing_configuration_have_distinct_results(self) -> None:
        """显式初始化后正常重开，缺失配置失败且不输出伪成功。"""
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            config = _configuration(base)
            command = [sys.executable, "-B", "-c", "from vet3d.host import operations_main; raise SystemExit(operations_main())"]
            environment = {key: value for key, value in os.environ.items() if not key.startswith("VET3D_")}
            environment.pop("PYTHONPATH", None)
            outputs = []
            for extra in (["--initialize"], []):
                result = subprocess.run(
                    [*command, "--config", str(config), *extra], cwd=base,
                    env=environment, capture_output=True, text=True, encoding="utf-8", timeout=20, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                outputs.append(json.loads(result.stdout))
                self.assertIn("operations_stopped", result.stderr)
            self.assertEqual([item["operation"] for item in outputs], ["initialize", "open"])
            self.assertNotEqual(outputs[0]["runtime_id"], outputs[1]["runtime_id"])
            self.assertTrue(all(item["quality_assessment"] == "not_run" for item in outputs))
            invalid = subprocess.run(
                [*command, "--config", str(base / "missing.yaml")], cwd=base, env=environment,
                capture_output=True, text=True, encoding="utf-8", timeout=20, check=False,
            )
            self.assertEqual(invalid.returncode, 1)
            self.assertEqual(invalid.stdout, "")
            self.assertIn("FileNotFoundError", invalid.stderr)
