# 文件信息：L1-05 标准配置来源及冻结部署边界的验收。
# 作用：验证真实 YAML、dotenv、环境覆盖、原预算类型和失败前无目录副作用。
# 证据边界：只证明配置装配语义，不证明解释器、容器、供应商或业务能力就绪。
"""通过公开入口验证部署配置，不另维护字段或默认值镜像。"""

from dataclasses import FrozenInstanceError
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from vet3d.adapters import ResourceLimits
from vet3d.bootstrap import load_settings
from vet3d.operations import DiagnosticLimits

_YAML = """workspaces:
  root: workspaces
  max_file_operations: 3
files:
  input_root: inputs
  max_file_bytes: 1024
resources:
  root: resources
  source_root: sources
  max_readers: 2
  limits:
    max_manifest_bytes: 8192
    max_files: 5
    max_file_bytes: 1024
    max_total_bytes: 4096
diagnostics:
  root: logs
interpreters:
  - runtime: Blender Python
    path: tools/blender
"""


class SettingsTests(unittest.TestCase):
    """核对来源覆盖和部署边界，避免把配置的存在当作执行能力。"""

    def setUp(self) -> None:
        """为每个用例提供独立文件来源并清空环境变量影响。"""
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.base = Path(self._temporary.name)
        self.config = self.base / "config.yaml"
        self.config.write_text(_YAML, encoding="utf-8")
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_sources_merge_in_order_and_preserve_unoverridden_fields(self) -> None:
        """验证显式覆盖、环境、dotenv、YAML 及原默认值的完整顺序。"""
        dotenv = self.base / ".env"
        dotenv.write_text("VET3D_WORKSPACES__MAX_FILE_OPERATIONS=4\nVET3D_FILES__MAX_FILE_BYTES=2048\n", encoding="utf-8")
        os.environ["VET3D_WORKSPACES__MAX_FILE_OPERATIONS"] = "5"
        os.environ["VET3D_RESOURCES__LIMITS__MAX_FILES"] = "7"
        parsed = load_settings(
            self.config, env_file=Path(".env"), overrides={"workspaces": {"max_file_operations": 6}},
        )
        self.assertEqual(parsed.workspaces.max_file_operations, 6)
        self.assertEqual(parsed.workspaces.root, self.base / "workspaces")
        self.assertEqual(parsed.files.max_file_bytes, 2048)
        self.assertEqual(parsed.resources.limits.max_files, 7)
        self.assertEqual(parsed.resources.limits.max_manifest_bytes, 8192)
        self.assertEqual(parsed.diagnostics.limits, DiagnosticLimits())
        self.assertEqual(load_settings(self.config, env_file=dotenv).workspaces.max_file_operations, 5)
        del os.environ["VET3D_WORKSPACES__MAX_FILE_OPERATIONS"]
        self.assertEqual(load_settings(self.config, env_file=dotenv).workspaces.max_file_operations, 4)
        self.assertEqual(load_settings(self.config).workspaces.max_file_operations, 3)

    def test_dotenv_is_never_discovered_implicitly(self) -> None:
        """工作目录与配置目录中的 .env 都只有显式选择后才参与加载。"""
        (self.base / ".env").write_text("VET3D_FILES__MAX_FILE_BYTES=99\n", encoding="utf-8")
        with patch("os.getcwd", return_value=str(self.base)):
            parsed = load_settings(Path("config.yaml"))
        self.assertEqual(parsed.files.max_file_bytes, 1024)

    def test_paths_are_config_relative_frozen_and_not_resolved_through_links(self) -> None:
        """路径冻结不创建目录、不依赖后续 cwd，也不把链接换成其他位置。"""
        external = self.base / "external"
        external.mkdir()
        (self.base / "workspaces").symlink_to(external, target_is_directory=True)
        parsed = load_settings(self.config)
        self.assertEqual(parsed.workspaces.root, self.base / "workspaces")
        self.assertEqual(parsed.interpreters[0].path, self.base / "tools" / "blender")
        self.assertFalse(parsed.diagnostics.root.exists())
        with patch("os.getcwd", return_value="/"):
            self.assertEqual(parsed.files.input_root, self.base / "inputs")
        with self.assertRaises(ValidationError):
            parsed.files.max_file_bytes = 2
        with self.assertRaises(ValidationError):
            parsed.workspaces = parsed.workspaces
        with self.assertRaises(FrozenInstanceError):
            setattr(parsed.resources.limits, "max_files", 2)

    def test_loads_are_independent_and_original_budget_objects_are_reused(self) -> None:
        """每次来源绑定独立，已校验预算不生成镜像记录或改变其身份。"""
        other = self.base / "other"
        other.mkdir()
        other_config = other / "config.yaml"
        other_config.write_text(_YAML, encoding="utf-8")
        limits = ResourceLimits(max_manifest_bytes=2048, max_files=2, max_file_bytes=512, max_total_bytes=1024)
        diagnostics = DiagnosticLimits()
        first = load_settings(self.config, overrides={"resources": {"limits": limits}, "diagnostics": {"limits": diagnostics}})
        second = load_settings(other_config)
        self.assertIs(first.resources.limits, limits)
        self.assertIs(first.diagnostics.limits, diagnostics)
        self.assertEqual(first.workspaces.root, self.base / "workspaces")
        self.assertEqual(second.workspaces.root, other / "workspaces")

    def test_invalid_integer_inputs_are_rejected_before_storage(self) -> None:
        """布尔、浮点、负值及非数字文本不能绕过原限额校验。"""
        for invalid in (True, False, 1.0, 0, -1, "false", "1.0"):
            with self.subTest(value=invalid):
                with self.assertRaises(ValidationError):
                    load_settings(self.config, overrides={"files": {"max_file_bytes": invalid}})
                with self.assertRaises(ValidationError):
                    load_settings(self.config, overrides={"resources": {"limits": {"max_files": invalid}}})
                with self.assertRaises(ValidationError):
                    load_settings(self.config, overrides={"diagnostics": {"limits": {"queue_capacity": invalid}}})
        self.assertEqual(tuple(self.base.iterdir()), (self.config,))

    def test_unknown_fields_and_loader_overrides_are_rejected(self) -> None:
        """错拼字段在 YAML、dotenv、覆盖参数及预算映射中都不会静默忽略。"""
        self.config.write_text(_YAML + "misspelled: true\n", encoding="utf-8")
        with self.assertRaises(ValidationError):
            load_settings(self.config)
        self.config.write_text(_YAML, encoding="utf-8")
        dotenv = self.base / ".env"
        dotenv.write_text("VET3D_UNKNOWN_FIELD=1\n", encoding="utf-8")
        with self.assertRaises(ValidationError):
            load_settings(self.config, env_file=dotenv)
        for overrides in ({"_env_file": dotenv}, {"unknown": 1}, {"resources": {"limits": {"max_filez": 2}}}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                load_settings(self.config, overrides=overrides)

    def test_roots_cannot_overlap_or_cover_configuration(self) -> None:
        """不同目录职责不能被相同或嵌套配置合并为过宽可写范围。"""
        for root in ("inputs", "inputs/nested", ".", "/", "config.yaml", "../escape"):
            with self.subTest(root=root), self.assertRaises(ValidationError):
                load_settings(self.config, overrides={"diagnostics": {"root": root}})
        dotenv_root = self.base / "logs"
        dotenv_root.mkdir()
        dotenv = dotenv_root / ".env"
        dotenv.write_text("", encoding="utf-8")
        with self.assertRaises(ValidationError):
            load_settings(self.config, env_file=dotenv)

    def test_explicit_missing_sources_do_not_fall_back_to_defaults(self) -> None:
        """显式来源缺失不退回环境或默认值，不创建缺失文件。"""
        with self.assertRaises(FileNotFoundError):
            load_settings(self.base / "missing.yaml")
        with self.assertRaises(FileNotFoundError):
            load_settings(self.config, env_file=self.base / "missing.env")
        self.assertEqual(tuple(self.base.iterdir()), (self.config,))

    def test_runtime_names_are_exact_unique_and_locations_are_only_candidates(self) -> None:
        """候选解释器无需存在，名称不折叠大小写、不建立就绪枚举。"""
        parsed = load_settings(self.config)
        self.assertEqual(parsed.interpreters[0].runtime, "Blender Python")
        self.assertFalse(parsed.interpreters[0].path.exists())
        with self.assertRaises(ValidationError):
            load_settings(self.config, overrides={"interpreters": [
                {"runtime": "Blender Python", "path": "one"}, {"runtime": "Blender Python", "path": "two"},
            ]})
        with self.assertRaises(ValidationError):
            load_settings(self.config, overrides={"interpreters": [{"runtime": " ", "path": "one"}]})


if __name__ == "__main__":
    unittest.main()
