# 文件信息：L2-02 有限任务环境的管理边界机械测试。
# 作用：验证绝对期限、原环境恢复、所有权清理及授权材料的创建前拒绝。
# 边界：替身不证明真实 Docker 隔离、权限或进程停止；真实证据单独记录。
"""覆盖环境管理的高价值故障与所有权边界，不调用模型。"""

from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from vet3d.adapters import CodexDockerEnvironment, CodexEnvironmentCreationError


class CodexEnvironmentTests(unittest.TestCase):
    """核对有限宿主环境期限及清理的实际语义。"""

    def test_invalid_lifetime_rejected_before_docker(self) -> None:
        """无效期限不创建任何容器或网络。"""
        with patch("vet3d.adapters.codex_environment.subprocess.run") as run:
            for lifetime in (0, -1, 86401, True):
                with self.subTest(lifetime=lifetime), self.assertRaises(ValueError):
                    CodexDockerEnvironment.create(
                        image_id="test", codex_package=Path("missing"), control_home=Path("missing"),
                        task_materials=Path("missing"), lifetime_seconds=lifetime,
                    )
            run.assert_not_called()

    def test_material_link_rejected_before_docker(self) -> None:
        """材料中的链接不能把未授权目录交给执行环境。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "package/bin").mkdir(parents=True)
            (root / "package/bin/codex").touch()
            (root / "home").mkdir()
            (root / "materials").mkdir()
            (root / "materials/link").symlink_to(root / "home", target_is_directory=True)
            with patch("vet3d.adapters.codex_environment.subprocess.run") as run, self.assertRaises(ValueError):
                CodexDockerEnvironment.create(
                    image_id="test", codex_package=root / "package", control_home=root / "home",
                    task_materials=root / "materials",
                )
            run.assert_not_called()

    def test_expired_environment_cannot_resume_even_if_container_exists(self) -> None:
        """环境过期后不能重新启动空环境或延长原实例期限。"""
        environment = CodexDockerEnvironment("default", int(time.time()) - 1)
        with patch("vet3d.adapters.codex_environment.subprocess.run") as run, self.assertRaises(RuntimeError):
            environment.require_running()
        run.assert_not_called()

    def test_require_running_checks_only_original_executor(self) -> None:
        """控制进程可以已经退出，恢复前仍须确认原执行容器与所有权。"""
        environment = CodexDockerEnvironment("default", int(time.time()) + 60)
        with patch.object(CodexDockerEnvironment, "_owns", return_value=True) as owns, patch.object(
            CodexDockerEnvironment, "_docker", return_value="true",
        ) as docker:
            environment.require_running()
        owns.assert_called_once_with("container", environment.executor_name)
        docker.assert_called_once_with("inspect", "--format", "{{.State.Running}}", environment.executor_name)

    def test_stop_does_not_report_success_for_unconfirmed_running_container(self) -> None:
        """停止请求受理不能替代容器已经退出。"""
        environment = CodexDockerEnvironment("default", int(time.time()) + 60)
        with patch.object(CodexDockerEnvironment, "_owns", return_value=True), patch.object(
            CodexDockerEnvironment, "_docker", side_effect=["", "true"],
        ), self.assertRaises(RuntimeError):
            environment.stop_control()

    def test_cleanup_does_not_remove_unowned_resources(self) -> None:
        """同名资源所有权不符时不执行停止或删除。"""
        environment = CodexDockerEnvironment("default", int(time.time()) + 60)
        with patch.object(CodexDockerEnvironment, "_owns", return_value=False), patch.object(
            CodexDockerEnvironment, "_docker",
        ) as docker:
            environment.stop_control()
            environment.cleanup()
        docker.assert_not_called()

    def test_failed_create_and_cleanup_preserve_original_environment(self) -> None:
        """创建与清理同时失败时，调用方仍能取得原环境重试清理。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "package/bin").mkdir(parents=True)
            (root / "package/bin/codex").touch()
            (root / "home").mkdir()
            (root / "materials").mkdir()
            with patch.object(CodexDockerEnvironment, "_docker", side_effect=RuntimeError("unavailable")):
                with self.assertRaises(CodexEnvironmentCreationError) as caught:
                    CodexDockerEnvironment.create(
                        image_id="test", codex_package=root / "package", control_home=root / "home",
                        task_materials=root / "materials",
                    )
        self.assertIsInstance(caught.exception.environment, CodexDockerEnvironment)
        self.assertEqual(len(caught.exception.failures.exceptions), 2)
        with patch.object(CodexDockerEnvironment, "_owns", return_value=False):
            caught.exception.environment.cleanup()

    def test_original_deadline_and_readonly_resources_are_in_both_start_commands(self) -> None:
        """控制重开沿原截止时间，受管资源在内核层只读而非仅 chmod。"""
        calls: list[tuple[str, ...]] = []

        def run(args: tuple[str, ...], **kwargs: object) -> subprocess.CompletedProcess[str]:
            """记录受信管理参数，不执行 Docker。

            :param args: 实际构造的管理命令。
            :param kwargs: 子进程选项。
            :returns: 装配所需的最小机械回包。
            """
            calls.append(args)
            return subprocess.CompletedProcess(args, 0, "172.28.0.2" if args[3:4] == ("inspect",) else "", "")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "package/bin").mkdir(parents=True)
            (root / "package/bin/codex").touch()
            (root / "home").mkdir()
            (root / "materials/resources").mkdir(parents=True)
            with patch("vet3d.adapters.codex_environment.subprocess.run", side_effect=run), patch.object(
                CodexDockerEnvironment, "require_running",
            ), patch("vet3d.adapters.codex_environment.time.time", return_value=1000):
                environment = CodexDockerEnvironment.create(
                    image_id="test", codex_package=root / "package", control_home=root / "home",
                    task_materials=root / "materials", lifetime_seconds=100, docker_context="default",
                )
        created = [args for args in calls if args[3:4] == ("create",)]
        self.assertEqual(len(created), 2)
        for args in created:
            self.assertIn("--pull=never", args)
            self.assertIn("1100", args)
            self.assertIn("--clear-groups", args)
            self.assertIn("--user", args)
            self.assertIn("0:0", args)
            self.assertIn("--init", args)
        executor = next(args for args in created if environment.executor_name in args)
        self.assertTrue(any("target=/work/resources,readonly" in value for value in executor))
        self.assertEqual(environment.control_argv[:3], ("docker", "--context", "default"))
        self.assertEqual(environment.deadline_epoch, 1100)


if __name__ == "__main__":
    unittest.main()
