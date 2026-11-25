# 文件信息：L2-02 实验装配的模型凭证注入边界测试。
# 作用：验证凭证只由控制容器按变量名接收，错误输入在 Docker 资源创建前被拒绝。
# 边界：仅核对受信启动参数，不运行 Docker 或模型，不证明真实网络、认证及容器隔离。
"""以机械替身检查控制侧凭证交接，不宣称真实模型接入通过。"""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from vet3d.experiments import NativeAgentDockerEnvironment


class NativeAgentEnvironmentTests(unittest.TestCase):
    """核对具体实验装配中的凭证接收方及创建前校验。"""

    def test_api_key_is_passed_by_name_only_to_control_container(self) -> None:
        """控制侧得到凭证，执行侧和所有命令参数均不包含凭证值。"""
        calls: list[tuple[tuple[str, ...], dict[str, object]]] = []

        def run_command(args: tuple[str, ...], **kwargs: object) -> subprocess.CompletedProcess[str]:
            """记录具体 Docker 管理参数，返回机械地址而不启动容器。

            :param args: 受信装配生成的原始参数序列。
            :param kwargs: 子进程选项，包含控制侧显式环境。
            :returns: 足够完成装配的机械命令结果。
            """
            calls.append((args, kwargs))
            stdout = "172.28.0.2" if args[:2] == ("docker", "inspect") else ""
            return subprocess.CompletedProcess(args, 0, stdout, "")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package, home, materials = root / "package", root / "control", root / "materials"
            (package / "bin").mkdir(parents=True)
            (package / "bin/codex").touch()
            home.mkdir()
            materials.mkdir()
            with patch.dict(os.environ, {"VET3D_TEST_API_KEY": "synthetic-model-key"}), patch(
                "vet3d.experiments.native_agent_environment.subprocess.run", side_effect=run_command,
            ):
                NativeAgentDockerEnvironment.create(
                    image_id="synthetic-image", codex_package=package,
                    control_home=home, task_materials=materials,
                    model_api_key_env="VET3D_TEST_API_KEY",
                )

        created = [(args, options) for args, options in calls if args[:2] == ("docker", "create")]
        self.assertEqual(len(created), 2)
        for args, options in created:
            name = args[args.index("--name") + 1]
            env_args = [args[index + 1] for index, value in enumerate(args) if value == "--env"]
            if name.endswith("-control"):
                self.assertIn("VET3D_TEST_API_KEY", env_args)
                environment = options["env"]
                self.assertIsInstance(environment, dict)
                assert isinstance(environment, dict)
                self.assertEqual(environment["VET3D_TEST_API_KEY"], "synthetic-model-key")
            else:
                self.assertNotIn("VET3D_TEST_API_KEY", env_args)
            self.assertFalse(any("synthetic-model-key" in value for value in args))
        self.assertTrue(all("synthetic-model-key" not in str(args) for args, _ in calls))

    def test_invalid_or_missing_key_is_rejected_before_resource_creation(self) -> None:
        """缺失凭证、非法变量及宿主配置名不能触发任何 Docker 操作。"""
        with patch.dict(os.environ, {"EMPTY_API_KEY": ""}, clear=True), patch(
            "vet3d.experiments.native_agent_environment.subprocess.run",
        ) as run:
            for name in (
                "MISSING_API_KEY", "EMPTY_API_KEY", "HOME", "CODEX_HOME", "PATH",
                "HTTPS_PROXY", "NO_PROXY", "BAD-NAME_API_KEY", "KEY_API_KEY=value", "1_API_KEY",
            ):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    NativeAgentDockerEnvironment.create(
                        image_id="synthetic-image", codex_package=Path("not-created"),
                        control_home=Path("not-created"), task_materials=Path("not-created"),
                        model_api_key_env=name,
                    )
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
