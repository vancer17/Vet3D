# 文件信息：L2-01 探针清理失败时的 Operations 关闭交接测试。
# 作用：验证原探针现场保留与独立存储、诊断释放分别发生，有限宿主不会遗留诊断线程。
# 证据边界：故障注入发生在真实 Python 已退出之后，不证明失控进程或宿主强杀恢复。
"""检查清理失败的真实所有权范围，不把一个所有者的失败扩散为无关资源泄漏。"""

import contextlib
from dataclasses import asdict
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from vet3d.adapters import LocalEnvironmentProbe, ResourceLimits, build_resource_bundle
from vet3d.bootstrap import initialize_operations, is_diagnostics_active, load_settings, open_operations
from vet3d.operations import ProbeError, ProbeFailure, RequirementStatus
from vet3d.resources import ResourceKey, ResourceReference


def _fixture(base: Path) -> tuple[Path, ResourceReference]:
    """建立本测试独立的真实资源包和有限宿主配置。

    :param base: 测试唯一拥有的临时目录。
    :returns: 配置文件及构建所得的原资源引用。
    """
    for name in ("inputs", "sources", "author"):
        (base / name).mkdir(mode=0o700)
    payload = base / "author" / "payload"
    payload.mkdir(mode=0o700)
    source = payload / "never-execute.py"
    source.write_text("raise RuntimeError('resource must never execute')\n", encoding="utf-8")
    source.chmod(0o600)
    metadata = {
        "purpose": "关闭故障交接测试", "source": "Vet3D 测试源", "inputs": "无",
        "outputs": "无", "overwrite": "禁止", "failure": "不执行声明入口",
        "adoption": "独立实现", "priority": "首期", "evidence": "仅环境观察及故障注入",
    }
    specification = base / "author" / "resource-spec.json"
    specification.write_text(json.dumps({
        "schema_version": 1, "resources": [{
            "kind": "script", "key": "fixture.cleanup", "entry": "never-execute.py",
            "files": ["never-execute.py"], "dependencies": [], "metadata": metadata,
            "interpreter": {"runtime": "Python", "version": "3.14", "dependencies": ["sqlite3"]},
        }],
    }, ensure_ascii=False), encoding="utf-8")
    specification.chmod(0o600)
    limits = ResourceLimits(max_manifest_bytes=8192, max_files=4, max_file_bytes=1024, max_total_bytes=4096)
    snapshot = build_resource_bundle(base / "author", base / "sources" / "fixture", limits=limits)
    configuration = base / "settings.yaml"
    configuration.write_text(json.dumps({
        "workspaces": {"root": "workspaces"}, "files": {"input_root": "inputs", "max_file_bytes": 1024},
        "resources": {"root": "resources", "source_root": "sources", "limits": asdict(limits)},
        "diagnostics": {"root": "logs"},
        "interpreters": [{"runtime": "Python", "path": sys.executable}],
    }), encoding="utf-8")
    return configuration, ResourceReference(snapshot, ResourceKey("fixture.cleanup"))


class EnvironmentShutdownFailureTests(unittest.IsolatedAsyncioTestCase):
    """原探针失败保留其现场，独立存储和诊断仍必须有明确终止结果。"""

    async def test_cleanup_failure_preserves_probe_scene_and_releases_independent_owners(self) -> None:
        """实际探针清理报错后不返回观察，关闭聚合错误且释放独立根与诊断线程。"""
        with (
            tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {}, clear=True),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            base = Path(temporary)
            configuration, reference = _fixture(base)
            settings = load_settings(configuration)
            runtime = await initialize_operations(settings)
            marker = base / "probe-directory.txt"
            source = (
                "from pathlib import Path\n"
                f"Path({str(marker)!r}).write_text(str(Path.cwd()), encoding='utf-8')\n"
                + LocalEnvironmentProbe._payload("Python")
            )
            try:
                await runtime.resources.install("fixture", reference.snapshot)
                with (
                    patch.object(LocalEnvironmentProbe, "_payload", return_value=source),
                    patch.object(LocalEnvironmentProbe, "_cleanup", side_effect=OSError("测试清理确认故障")),
                ):
                    report = await runtime.check_environment(reference)
                self.assertEqual(report.status, RequirementStatus.INDETERMINATE)
                self.assertEqual(report.checks[0].evidence, ProbeFailure("cleanup_failed"))
                directory = Path(marker.read_text(encoding="utf-8"))
                self.assertTrue(directory.is_dir())
                frozen = await runtime.check_environment(reference)
                self.assertEqual(frozen.checks[0].evidence, ProbeFailure("closed"))
                with self.assertRaises(ExceptionGroup) as caught:
                    await runtime.aclose()
                self.assertTrue(any(
                    isinstance(error, ProbeError) and error.reason == "cleanup_failed"
                    for error in caught.exception.exceptions
                ))
                self.assertFalse(is_diagnostics_active())
                self.assertEqual([thread.name for thread in threading.enumerate() if thread.name.startswith("vet3d")], [])
                self.assertTrue(directory.is_dir())
                reopened = await open_operations(settings)
                try:
                    fresh = await reopened.check_environment(reference)
                    self.assertEqual(fresh.status, RequirementStatus.SATISFIED)
                    self.assertNotEqual(fresh.runtime_id, report.runtime_id)
                    self.assertEqual(fresh.root, report.root)
                    self.assertTrue(directory.is_dir())
                finally:
                    await reopened.aclose()
            finally:
                # 断言失败也关闭独立所有者，测试不能把非 daemon 线程留给运行器。
                await runtime.workspaces.aclose()
                await runtime.resources.aclose()
                await runtime.diagnostics.aclose()
                if marker.exists():
                    directory = Path(marker.read_text(encoding="utf-8"))
                    if directory.exists():
                        shutil.rmtree(directory)
