# 文件信息：L1-05 有限宿主在关闭中收到真实 SIGTERM 的进程级回归验收。
# 作用：在真实存储关闭被受控延迟时发出信号，核对退出码、线程排空和新进程重开。
# 证据边界：延迟只存在于测试；本例不证明强制 SIGKILL、容器停机预算或执行沙箱隔离。
"""验证取消等待与实际资源释放的区别，不给产品加入测试延迟配置。"""

import asyncio
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from vet3d.bootstrap import DiagnosticRuntime, OperationsRuntime, WorkspaceRuntime
from vet3d.host import operations_main
from vet3d.operations import DiagnosticStatus


def _run_signal_child(config: Path) -> int:
    """在子进程的真实关闭阶段发出一次 SIGTERM，并回报实际线程状态。

    :param config: 本例独立临时存储的配置文件。
    :returns: 原宿主的退出码；正常收到 SIGTERM 时为一百四十三。
    """
    entered = threading.Event()
    released = threading.Event()
    observed_cancel = threading.Event()
    storage_closed = threading.Event()
    early_diagnostic_close: list[bool] = []
    original_close = WorkspaceRuntime._close_storage
    original_wait = OperationsRuntime.aclose
    original_workspace_wait = WorkspaceRuntime.aclose
    original_diagnostic_close = DiagnosticRuntime.aclose

    def held_close(owner: WorkspaceRuntime) -> None:
        """让真实关闭保留根锁，直到宿主已观察到取消。

        :param owner: 原工作区宿主，不替换其实际关闭逻辑。
        """
        entered.set()
        if not released.wait(5):
            raise TimeoutError("测试未观察到关闭等待取消")
        original_close(owner)
        storage_closed.set()

    def notice_cancel() -> None:
        """给清理协程一次调度机会，再允许真实存储关闭，显露错误的提前诊断关闭。"""
        observed_cancel.set()
        asyncio.get_running_loop().call_later(0.05, released.set)

    async def observed_wait(owner: OperationsRuntime) -> DiagnosticStatus:
        """只观察原关闭等待的取消，然后继续由产品负责排空。

        :param owner: 本次有限宿主的实际资源所有者。
        :returns: 正常情况下原关闭的诊断状态。
        :raises asyncio.CancelledError: 原等待受到真实信号取消。
        """
        try:
            return await original_wait(owner)
        except asyncio.CancelledError:
            notice_cancel()
            raise

    async def observed_workspace_wait(owner: WorkspaceRuntime) -> None:
        """观察部分初始化失败清理中的取消，不替换原存储关闭。

        :param owner: 已实际初始化但尚未组成完整 OperationsRuntime 的工作区宿主。
        :raises asyncio.CancelledError: 原清理等待被真实信号取消。
        """
        try:
            await original_workspace_wait(owner)
        except asyncio.CancelledError:
            notice_cancel()
            raise

    async def observed_diagnostic_close(owner: DiagnosticRuntime) -> DiagnosticStatus:
        """记录诊断是否在真实存储释放之前就停止接收。

        :param owner: 本次实际诊断所有者。
        :returns: 原诊断关闭的结果，不改变其线程或队列行为。
        """
        early_diagnostic_close.append(not storage_closed.is_set())
        return await original_diagnostic_close(owner)

    def send_signal() -> None:
        """等待真实工作线程进入关闭，再向本进程发送 SIGTERM。"""
        if entered.wait(5):
            os.kill(os.getpid(), signal.SIGTERM)

    sender = threading.Thread(target=send_signal, name="signal-test-sender")
    sender.start()
    with (
        patch.object(WorkspaceRuntime, "_close_storage", held_close),
        patch.object(OperationsRuntime, "aclose", observed_wait),
        patch.object(WorkspaceRuntime, "aclose", observed_workspace_wait),
        patch.object(DiagnosticRuntime, "aclose", observed_diagnostic_close),
    ):
        result = operations_main(["--config", str(config), "--initialize"])
    sender.join(timeout=5)
    print(json.dumps({
        "signal_observed": observed_cancel.is_set(),
        "diagnostics_closed_before_storage": any(early_diagnostic_close),
        "remaining_workers": [thread.name for thread in threading.enumerate() if thread.name.startswith("vet3d")],
    }), flush=True)
    return result


class OperationsSignalTests(unittest.TestCase):
    """以独立进程核对有限命令不会在诊断线程仍存活时报告退出。"""

    def _configuration(self, base: Path) -> Path:
        """创建本例独立的真实输入目录及 YAML 配置，不预建受管存储。

        :param base: 当前用例唯一的临时目录。
        :returns: 由子进程独立读取的配置文件。
        """
        for name in ("inputs", "sources"):
            (base / name).mkdir(mode=0o700)
        config = base / "settings.yaml"
        config.write_text(json.dumps({
            "workspaces": {"root": "workspaces"},
            "files": {"input_root": "inputs", "max_file_bytes": 1024},
            "resources": {
                "root": "resources", "source_root": "sources",
                "limits": {
                    "max_manifest_bytes": 8192, "max_files": 5,
                    "max_file_bytes": 1024, "max_total_bytes": 4096,
                },
            },
            "diagnostics": {"root": "logs"},
        }), encoding="utf-8")
        return config

    def _interrupt(self, config: Path) -> None:
        """在独立进程核对真实 SIGTERM、关闭顺序和工作线程排空。

        :param config: 本例配置文件，资源根可为正常或故意错误的权限。
        """
        environment = {key: value for key, value in os.environ.items() if not key.upper().startswith("VET3D_")}
        interrupted = subprocess.run(
            [sys.executable, "-B", str(Path(__file__).absolute()), "--signal-child", str(config)],
            capture_output=True, text=True, timeout=15, check=False, env=environment,
        )
        self.assertEqual(interrupted.returncode, 143, interrupted.stderr)
        observed = json.loads(interrupted.stdout)
        self.assertTrue(observed["signal_observed"])
        self.assertEqual(observed["remaining_workers"], [])
        self.assertFalse(observed["diagnostics_closed_before_storage"])

    def test_sigterm_during_close_drains_workers_and_allows_fresh_process_open(self) -> None:
        """实际取消关闭等待后返回一百四十三，释放原锁并允许新进程重开。"""
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            config = self._configuration(base)
            self._interrupt(config)
            environment = {key: value for key, value in os.environ.items() if not key.upper().startswith("VET3D_")}
            reopened = subprocess.run(
                [
                    sys.executable, "-B", "-c",
                    "from vet3d.host import operations_main; raise SystemExit(operations_main())",
                    "--config", str(config),
                ],
                capture_output=True, text=True, timeout=15, check=False, env=environment,
            )
            self.assertEqual(reopened.returncode, 0, reopened.stderr)
            summary = json.loads(reopened.stdout)
            self.assertEqual(summary["operation"], "open")
            self.assertEqual(summary["diagnostics"], {"dropped_records": 0, "write_error": None})

    def test_sigterm_during_partial_initialization_cleanup_keeps_diagnostics_until_storage_closes(self) -> None:
        """资源根权限失败后的清理仍排空工作区，然后关闭诊断并返回信号码。"""
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            config = self._configuration(base)
            bad_root = base / "resources"
            bad_root.mkdir(mode=0o700)
            bad_root.chmod(0o755)
            self._interrupt(config)
            self.assertTrue((base / "workspaces").is_dir())
            self.assertEqual(tuple(bad_root.iterdir()), ())


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--signal-child":
        raise SystemExit(_run_signal_child(Path(sys.argv[2])))
    unittest.main()
