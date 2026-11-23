# 文件信息：L0-01 宿主安装入口与日志测试。
# 作用：通过独立进程和可观察输出检查非交互启动、拒绝及写入边界。
# 范围：不启动 BFF、网络监听、模型、数据库或后台工作进程。
"""验证宿主输出及导入行为，不把 CLI 通过当成 BFF 集成通过。"""

import contextlib
import io
import json
import logging
import os
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Sequence

from vet3d.bootstrap import configure_logging
from vet3d.host import main


class BrokenOutput(io.StringIO):
    """模拟调用方已经关闭的结果输出流。"""

    def write(self, text: str) -> int:
        """让结果写入显式失败。

        :param text: 宿主准备写出的结果文本。
        :raises OSError: 输出目的地已不可写。
        """
        raise OSError("结果接收端已关闭")


class HostTests(unittest.TestCase):
    """验证安装后的应用入口和有界可见诊断。"""

    def setUp(self) -> None:
        """保存测试进程的日志配置，避免宿主初始化影响其他用例。"""
        self.logger = logging.getLogger("vet3d")
        self.previous_handlers = list(self.logger.handlers)
        self.previous_level = self.logger.level
        self.previous_propagation = self.logger.propagate

    def tearDown(self) -> None:
        """释放本用例创建的处理器并恢复原日志配置。"""
        for handler in list(self.logger.handlers):
            if handler not in self.previous_handlers:
                self.logger.removeHandler(handler)
                handler.close()
        self.logger.handlers = self.previous_handlers
        self.logger.setLevel(self.previous_level)
        self.logger.propagate = self.previous_propagation

    def run_cli(self, arguments: Sequence[str]) -> subprocess.CompletedProcess[str]:
        """在仓库外从已安装包启动 CLI，不注入源码搜索路径。

        :param arguments: 传给非交互入口的参数。
        :returns: 子进程退出状态及独立的标准输出、标准错误。
        """
        environment = dict(os.environ)
        environment.pop("PYTHONPATH", None)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        with tempfile.TemporaryDirectory(prefix="vet3d-host-test-") as directory:
            return subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "from vet3d.host import main; raise SystemExit(main())",
                    *arguments,
                ],
                cwd=directory,
                env=environment,
                input="",
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=15,
                check=False,
            )

    def test_installed_cli_returns_one_reply_without_interaction(self) -> None:
        """无 stdin 答复也能完成调用，标准输出只包含一份机器结果。"""
        text = "  猫的五向参考 🐈\n"
        result = self.run_cli(["--text", text])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"text": text})
        self.assertIn("demo_started", result.stderr)
        self.assertIn("demo_completed", result.stderr)

    def test_invalid_input_has_no_success_reply_or_traceback(self) -> None:
        """预期的输入拒绝返回非成功，不泄漏堆栈或输出空成功。"""
        result = self.run_cli(["--text", " \t"])
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertNotEqual(result.stderr, "")
        self.assertNotIn("Traceback", result.stderr)

    def test_package_import_does_not_initialize_runtime_resources(self) -> None:
        """导入公开包不会配置日志、增加线程或向当前目录写入文件。"""
        script = "\n".join(
            (
                "import json, logging, pathlib, threading",
                "before = (len(logging.getLogger().handlers), threading.active_count())",
                "import vet3d.application, vet3d.adapters, vet3d.bootstrap, vet3d.host",
                "after = (len(logging.getLogger().handlers), threading.active_count())",
                "print(json.dumps({'before': before, 'after': after,",
                "'handlers': len(logging.getLogger('vet3d').handlers),",
                "'files': [p.name for p in pathlib.Path('.').iterdir()]}))",
            )
        )
        environment = dict(os.environ)
        environment.pop("PYTHONPATH", None)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        with tempfile.TemporaryDirectory(prefix="vet3d-import-test-") as directory:
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=directory,
                env=environment,
                input="",
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=15,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["before"], data["after"])
        self.assertEqual(data["handlers"], 0)
        self.assertEqual(data["files"], [])
        self.assertEqual(result.stderr, "")

    def test_logging_is_not_duplicated_and_each_record_is_bounded(self) -> None:
        """重复初始化不会重复输出，超长记录的可见体积有上限。"""
        stream = io.StringIO()
        logger = logging.getLogger("vet3d")
        with contextlib.redirect_stderr(stream):
            configure_logging()
            configure_logging()
            logger.info("唯一事件")
            self.assertEqual(stream.getvalue().count("唯一事件"), 1)
            stream.seek(0)
            stream.truncate(0)
            logger.error("甲" * 10_000)
        self.assertLessEqual(len(stream.getvalue().removesuffix("\n")), 4096)

    def test_result_write_failure_is_not_reported_as_delivery_success(self) -> None:
        """结果写入失败返回失败，异常堆栈仅由宿主边界记录一次。"""
        diagnostics = io.StringIO()
        with contextlib.redirect_stdout(BrokenOutput()), contextlib.redirect_stderr(diagnostics):
            result = main(["--text", "写出失败"])
        self.assertEqual(result, 1)
        self.assertEqual(diagnostics.getvalue().count("Traceback (most recent call last)"), 1)

    def test_logging_write_failure_is_visible_to_the_caller(self) -> None:
        """日志写入不可用时抛出异常，不静默丢弃关键事件。"""
        with contextlib.redirect_stderr(BrokenOutput()):
            configure_logging()
            with self.assertRaises(OSError):
                logging.getLogger("vet3d").error("日志写入失败")
