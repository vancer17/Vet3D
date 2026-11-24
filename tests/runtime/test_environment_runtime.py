# 文件信息：L2-01 固定资源、真实解释器及 Operations 交接验证。
# 作用：核对原快照关联、重新观察、机器输出和诊断故障边界。
# 证据边界：合成资源从不执行；真实 CPU 探针不证明动物质量或执行隔离。
"""通过公开装配入口验证有限环境观察，不复制内部状态定义。"""

import contextlib
from dataclasses import asdict
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from vet3d.adapters import LocalDiagnosticFiles, ResourceLimits, build_resource_bundle
from vet3d.bootstrap import initialize_operations, load_settings, open_operations
from vet3d.operations import EnvironmentObservation, ProbeLimits, RequirementStatus
from vet3d.resources import ResourceKey, ResourceReference


def _fixture(base: Path, *, version: str = "3.14") -> tuple[Path, ResourceReference]:
    """构建一个含 Python 要求的真实固定资源包及宿主配置。

    :param base: 本例唯一拥有的临时目录。
    :param version: 原资源声明，不在装配时改写。
    :returns: 配置文件和实际构建清单对应的根资源身份。
    """
    for name in ("inputs", "sources", "author"):
        (base / name).mkdir(mode=0o700)
    payload = base / "author" / "payload"
    payload.mkdir(mode=0o700)
    script = payload / "never-run.py"
    script.write_text("raise RuntimeError('resource must never execute')\n", encoding="utf-8")
    script.chmod(0o600)
    metadata = {
        "purpose": "环境要求交接夹具", "source": "本测试自研",
        "inputs": "不执行", "outputs": "无", "overwrite": "禁止覆盖",
        "failure": "不执行资源脚本", "adoption": "独立实现", "priority": "首期",
        "evidence": "只核对环境，不验证建模",
    }
    spec = {
        "schema_version": 1,
        "resources": [{
            "kind": "script", "key": "fixture.python", "entry": "never-run.py",
            "files": ["never-run.py"], "dependencies": [], "metadata": metadata,
            "interpreter": {"runtime": "Python", "version": version, "dependencies": ["sqlite3"]},
        }],
    }
    declaration = base / "author" / "resource-spec.json"
    declaration.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    declaration.chmod(0o600)
    limits = ResourceLimits(max_manifest_bytes=16384, max_files=4, max_file_bytes=4096, max_total_bytes=8192)
    snapshot = build_resource_bundle(base / "author", base / "sources" / "fixture", limits=limits)
    config = base / "config.yaml"
    config.write_text(json.dumps({
        "workspaces": {"root": "workspaces"},
        "files": {"input_root": "inputs", "max_file_bytes": 4096},
        "resources": {"root": "resources", "source_root": "sources", "limits": asdict(limits)},
        "diagnostics": {"root": "logs"},
        "interpreters": [{"runtime": "Python", "path": sys.executable}],
    }), encoding="utf-8")
    return config, ResourceReference(snapshot, ResourceKey("fixture.python"))


class EnvironmentRuntimeTests(unittest.IsolatedAsyncioTestCase):
    """原资源身份贯穿实际装配，进程重开只产生新的环境证据。"""

    async def asyncSetUp(self) -> None:
        """准备独立资源源和配置，禁止外部 VET3D 配置干扰本例。"""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.config, self.reference = _fixture(self.base)
        environment = patch.dict(os.environ, {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        output = contextlib.redirect_stderr(io.StringIO())
        output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)

    async def test_fixed_resource_real_observation_and_fresh_check_after_reopen(self) -> None:
        """安装不等于可执行；沿原引用取得真实观察，重开不复用旧运行事实。"""
        settings = load_settings(self.config)
        runtime = await initialize_operations(settings)
        self.addAsyncCleanup(runtime.aclose)
        with self.assertRaises((OSError, ValueError)):
            await runtime.check_environment(self.reference)
        await runtime.resources.install("fixture", self.reference.snapshot)
        first = await runtime.check_environment(self.reference)
        self.assertEqual(first.root, self.reference)
        self.assertEqual(first.status, RequirementStatus.SATISFIED)
        observation = first.checks[0].evidence
        self.assertIsInstance(observation, EnvironmentObservation)
        assert isinstance(observation, EnvironmentObservation)
        self.assertEqual(observation.python_version, sys.version_info[:3])
        self.assertTrue(observation.cpu_check)
        second = await runtime.check_environment(self.reference)
        self.assertIsNot(first.checks[0].evidence, second.checks[0].evidence)
        self.assertGreaterEqual(second.observed_at, first.observed_at)
        await runtime.aclose()
        with self.assertRaises(RuntimeError):
            await runtime.check_environment(self.reference)
        reopened = await open_operations(settings)
        self.addAsyncCleanup(reopened.aclose)
        third = await reopened.check_environment(self.reference)
        self.assertEqual(third.root, first.root)
        self.assertNotEqual(third.runtime_id, first.runtime_id)
        self.assertEqual(third.status, RequirementStatus.SATISFIED)

    async def test_diagnostic_write_failure_does_not_replace_actual_observation(self) -> None:
        """诊断落盘异常只进入诊断损失，不把真实环境满足改成业务失败。"""
        runtime = await initialize_operations(load_settings(self.config))
        self.addAsyncCleanup(runtime.aclose)
        await runtime.resources.install("fixture", self.reference.snapshot)
        with patch.object(LocalDiagnosticFiles, "append", side_effect=OSError("受控诊断故障")):
            result = await runtime.check_environment(self.reference)
            self.assertEqual(result.status, RequirementStatus.SATISFIED)
            status = await runtime.aclose()
        self.assertIsNotNone(status.write_error)

    async def test_cli_delivers_original_resource_and_rejects_partial_identity(self) -> None:
        """仓库外命令返回原快照及真实观察，缺失身份不能触发隐式选择。"""
        runtime = await initialize_operations(load_settings(self.config))
        await runtime.resources.install("fixture", self.reference.snapshot)
        await runtime.aclose()
        command = [sys.executable, "-B", "-c", "from vet3d.host import operations_main; raise SystemExit(operations_main())"]
        result = subprocess.run(
            [*command, "--config", str(self.config), "--check-environment", self.reference.key.value,
             "--snapshot-sha256", self.reference.snapshot.sha256,
             "--snapshot-size", str(self.reference.snapshot.byte_size)],
            cwd=self.base, capture_output=True, text=True, timeout=20, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        response = json.loads(result.stdout)
        self.assertEqual(response["environment"]["root"], asdict(self.reference))
        self.assertEqual(response["environment"]["runtime_id"], response["runtime_id"])
        self.assertIsNone(response["environment"]["checks"][0]["failure"])
        invalid = subprocess.run(
            [*command, "--config", str(self.config), "--check-environment", self.reference.key.value],
            cwd=self.base, capture_output=True, text=True, timeout=20, check=False,
        )
        self.assertEqual(invalid.returncode, 2)
        self.assertEqual(invalid.stdout, "")

    async def test_missing_candidate_is_not_installed_resource_success(self) -> None:
        """原资源已安装且可读，候选缺失仍返回明确不可判定证据。"""
        settings = load_settings(self.config, overrides={"interpreters": []})
        runtime = await initialize_operations(settings)
        self.addAsyncCleanup(runtime.aclose)
        await runtime.resources.install("fixture", self.reference.snapshot)
        report = await runtime.check_environment(self.reference)
        self.assertEqual(report.status, RequirementStatus.INDETERMINATE)
        self.assertEqual(report.root, self.reference)


class EnvironmentSettingsTests(unittest.TestCase):
    """部署限额保持唯一来源，环境覆盖只影响探针资源预算。"""

    def test_original_limits_priority_and_invalid_values(self) -> None:
        """复用原预算实例，拒绝布尔、未知字段和非正数，无存储副作用。"""
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            base = Path(directory)
            config, _ = _fixture(base)
            limits = ProbeLimits(max_concurrency=1)
            parsed = load_settings(config, overrides={"environment_probe": limits})
            self.assertIs(parsed.environment_probe, limits)
            os.environ["VET3D_ENVIRONMENT_PROBE__MAX_CONCURRENCY"] = "3"
            self.assertEqual(load_settings(config).environment_probe.max_concurrency, 3)
            for invalid in ({"timeout_seconds": True}, {"max_output_bytes": 0}, {"ready": True}):
                with self.subTest(value=invalid), self.assertRaises(ValidationError):
                    load_settings(config, overrides={"environment_probe": invalid})
            self.assertFalse((base / "workspaces").exists())
