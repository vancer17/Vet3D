# 文件信息：L2-01 固定环境探针的真实 Linux 进程与失败边界验证。
# 作用：以受信有限脚本检查真实双管读取、进程组终止、并发准入与关闭排空。
# 证据边界：替换固定载荷只用于机械故障注入，不证明不可信代码隔离或动物质量。
"""验证原进程实际停止后才返回取消、期限和协议结果。"""

import asyncio
from collections.abc import Generator
from contextlib import contextmanager
import json
import logging
import os
import shutil
from pathlib import Path
import sys
import tempfile
from typing import Any
import unittest
from unittest.mock import patch

from vet3d.adapters import LocalEnvironmentProbe
from vet3d.operations import ProbeError, ProbeLimits


def _record() -> str:
    """生成机械协议的合法载荷，不把夹具值当成实际环境版本证据。

    :returns: 可由固定测试进程输出的完整协议行。
    """
    return "VET3D_ENVIRONMENT_V1=" + json.dumps({
        "python_version": [3, 14, 6], "blender_version": None,
        "dependencies": ["sqlite3"], "cpu_check": True, "platform": "Linux", "machine": "x86_64",
    })


def _running(pid: int) -> bool:
    """独立读取测试进程状态，僵尸已停止执行而等待系统父进程回收。

    :param pid: 本用例实际记录的子进程身份。
    :returns: 该 PID 仍有可运行进程时为真。
    """
    try:
        text = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except FileNotFoundError:
        return False
    return text[text.rfind(")") + 2:].split()[0] not in ("Z", "X")


@contextmanager
def _payload(source: str) -> Generator[None]:
    """在测试范围替换产品固定载荷，不给公共端口添加任意代码参数。

    :param source: 测试维护的可信故障注入脚本。
    :yields: 当前用例的固定载荷替换作用域。
    """
    with patch.object(LocalEnvironmentProbe, "_payload", return_value=source):
        yield


class _BrokenLog(logging.Handler):
    """模拟诊断接收失败，避免把日志异常误作环境观察失败。"""

    def emit(self, record: logging.LogRecord) -> None:
        """在诊断边界抛出固定异常。

        :param record: 原适配器记录的有限事件。
        :raises OSError: 模拟日志介质不可写。
        """
        raise OSError("测试诊断故障")


class EnvironmentProbeTests(unittest.IsolatedAsyncioTestCase):
    """通过真实进程核对有限探针所有权，而不是仅验证 mock 调用次数。"""

    def _probe(self, **limits: int) -> LocalEnvironmentProbe:
        """装配实际 Python 候选及本例明确的有限预算。

        :param limits: 只覆盖唯一 ProbeLimits 中的实际部署预算。
        :returns: 尚未启动任何进程的具体探针所有者。
        """
        return LocalEnvironmentProbe({"Python": Path(sys.executable)}, limits=ProbeLimits(**limits))

    async def _wait_file(self, path: Path) -> None:
        """等待本例子进程写出确定的就绪证据，不依赖固定启动延迟。

        :param path: 本次独立临时目录中的证据文件。
        """
        async with asyncio.timeout(5):
            while not path.exists():
                await asyncio.sleep(0.01)

    async def test_real_python_reports_actual_version_and_sqlite_cpu_check(self) -> None:
        """实际独立 Python 回报自身版本、SQLite 运算和当前平台。"""
        probe = self._probe()
        try:
            observation = await probe.observe("Python")
            self.assertEqual(observation.python_version, tuple(sys.version_info[:3]))
            self.assertIsNone(observation.blender_version)
            self.assertEqual(observation.dependencies, ("sqlite3",))
            self.assertTrue(observation.cpu_check)
            self.assertEqual(observation.executable, sys.executable)
            self.assertEqual(observation.platform, "Linux")
        finally:
            await probe.aclose()

    async def test_missing_candidate_and_unsupported_name_do_not_fallback(self) -> None:
        """缺少精确候选及未知环境都明确失败，不回退宿主或 PATH。"""
        probe = self._probe()
        try:
            for runtime, reason in (("Blender Python", "not_configured"), ("python", "unsupported_runtime")):
                with self.subTest(runtime=runtime), self.assertRaises(ProbeError) as caught:
                    await probe.observe(runtime)
                self.assertEqual(caught.exception.reason, reason)
        finally:
            await probe.aclose()

    async def test_missing_executable_and_zero_exit_without_protocol_are_distinct(self) -> None:
        """无法启动和仅退出零但没有实际观察是两种具体失败。"""
        for candidate, reason in ((Path("/missing-vet3d-python"), "start_failed"), (Path("/bin/true"), "invalid_output")):
            probe = LocalEnvironmentProbe({"Python": candidate}, limits=ProbeLimits())
            try:
                with self.subTest(candidate=candidate), self.assertRaises(ProbeError) as caught:
                    await probe.observe("Python")
                self.assertEqual(caught.exception.reason, reason)
            finally:
                await probe.aclose()

    async def test_wrong_interpreter_cannot_satisfy_blender(self) -> None:
        """把普通 Python 配为 Blender 不会因候选存在而得到 Blender 观察。"""
        probe = LocalEnvironmentProbe({"Blender Python": Path(sys.executable)}, limits=ProbeLimits())
        try:
            with self.assertRaises(ProbeError) as caught:
                await probe.observe("Blender Python")
            self.assertEqual(caught.exception.reason, "nonzero_exit")
        finally:
            await probe.aclose()

    async def test_duplicate_or_malformed_output_never_returns_observation(self) -> None:
        """重复、非法 JSON 和错误版本形状在协议边界拒绝。"""
        for output in (
            _record() + "\n" + _record(), "VET3D_ENVIRONMENT_V1={",
            _record().replace("[3, 14, 6]", "[true, 14, 6]"),
            _record().replace('"cpu_check": true', '"cpu_check": false, "cpu_check": true'),
            _record().replace('"cpu_check": true', '"cpu_check": NaN'),
        ):
            probe = self._probe()
            try:
                with _payload(f"print({output!r}, flush=True)"), self.assertRaises(ProbeError) as caught:
                    await probe.observe("Python")
                self.assertEqual(caught.exception.reason, "invalid_output")
            finally:
                await probe.aclose()

    async def test_missing_sqlite_preserves_python_version_and_cpu_observation(self) -> None:
        """固定 SQLite 检查缺依赖时仍报告 Python 观察，缺项由上层单向核对。"""
        probe = self._probe()
        source = LocalEnvironmentProbe._payload("Python").replace("    import sqlite3", "    raise ImportError('fixture')")
        try:
            with _payload(source):
                observation = await probe.observe("Python")
            self.assertEqual(observation.python_version, tuple(sys.version_info[:3]))
            self.assertEqual(observation.dependencies, ())
            self.assertTrue(observation.cpu_check)
        finally:
            await probe.aclose()

    async def test_no_user_environment_or_credentials_are_inherited(self) -> None:
        """真实子进程不会继承宿主用户配置、Python 路径或无关凭证变量。"""
        probe = self._probe()
        source = (
            "import os, sys\n"
            "assert 'VET3D_TEST_SECRET' not in os.environ\n"
            "assert 'PYTHONPATH' not in os.environ\n"
            "assert sys.flags.isolated and sys.flags.dont_write_bytecode\n"
            f"print({_record()!r})\n"
        )
        try:
            with patch.dict(os.environ, {"VET3D_TEST_SECRET": "private", "PYTHONPATH": "/untrusted"}), _payload(source):
                observation = await probe.observe("Python")
            self.assertTrue(observation.cpu_check)
        finally:
            await probe.aclose()

    async def test_output_budget_counts_both_pipes_and_drains_after_overflow(self) -> None:
        """各管道单独低于预算但合计超量时，终止原组并排空后报告超限。"""
        probe = self._probe(max_output_bytes=40000, terminate_grace_seconds=1)
        try:
            source = "import os\nos.write(1, b'x' * 30000)\nos.write(2, b'y' * 30000)\n"
            with _payload(source), self.assertRaises(ProbeError) as caught:
                await probe.observe("Python")
            self.assertEqual(caught.exception.reason, "output_limit")
            observation = await probe.observe("Python")
            self.assertTrue(observation.cpu_check)
        finally:
            await probe.aclose()

    async def test_timeout_reaps_ignoring_term_process_and_removes_private_directory(self) -> None:
        """实际超时后先升级终止忽略 TERM 的进程，再释放其临时目录。"""
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "started.json"
            source = (
                "import json, os, pathlib, signal, time\n"
                "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
                f"pathlib.Path({str(marker)!r}).write_text(json.dumps([os.getpid(), str(pathlib.Path.cwd())]))\n"
                "while True: time.sleep(1)\n"
            )
            probe = self._probe(timeout_seconds=1, terminate_grace_seconds=1)
            try:
                with _payload(source), self.assertRaises(ProbeError) as caught:
                    await probe.observe("Python")
                self.assertEqual(caught.exception.reason, "timeout")
                pid, directory = json.loads(marker.read_text(encoding="utf-8"))
                self.assertFalse(_running(pid))
                self.assertFalse(Path(directory).exists())
            finally:
                await probe.aclose()

    async def test_cancel_terminates_child_tree_before_releasing_capacity(self) -> None:
        """取消沿原组终止父子进程，宽限内仍占用唯一并发名额。"""
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "started.json"
            source = (
                "import json, os, pathlib, signal, time\n"
                "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
                "child = os.fork()\n"
                "if child:\n"
                f"    pathlib.Path({str(marker)!r}).write_text(json.dumps([os.getpid(), child]))\n"
                "while True: time.sleep(1)\n"
            )
            probe = self._probe(max_concurrency=1, terminate_grace_seconds=1)
            try:
                with _payload(source):
                    task = asyncio.create_task(probe.observe("Python"))
                    await self._wait_file(marker)
                    pids = json.loads(marker.read_text(encoding="utf-8"))
                    task.cancel()
                    await asyncio.sleep(0.05)
                    with self.assertRaises(ProbeError) as caught:
                        await probe.observe("Python")
                    self.assertEqual(caught.exception.reason, "busy")
                    task.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await task
                    self.assertTrue(all(not _running(pid) for pid in pids))
                self.assertTrue((await probe.observe("Python")).cpu_check)
            finally:
                await probe.aclose()

    async def test_successful_parent_still_cleans_remaining_child_group(self) -> None:
        """主进程正常退出并关闭输出不允许遗留继续运行的同组子进程。"""
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "child"
            source = (
                "import os, pathlib, signal, time\n"
                "child = os.fork()\n"
                "if child == 0:\n"
                "    os.close(1)\n"
                "    os.close(2)\n"
                "    signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
                "    while True: time.sleep(1)\n"
                f"pathlib.Path({str(marker)!r}).write_text(str(child))\n"
                f"print({_record()!r}, flush=True)\n"
            )
            probe = self._probe(terminate_grace_seconds=1)
            try:
                with _payload(source):
                    self.assertTrue((await probe.observe("Python")).cpu_check)
                self.assertFalse(_running(int(marker.read_text(encoding="utf-8"))))
            finally:
                await probe.aclose()

    async def test_cleanup_failure_preserves_directory_and_freezes_owner(self) -> None:
        """未能证明清理完成时保留实际目录，拒绝新调用且关闭不能报告成功。"""
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "directory"
            source = (
                "import pathlib\n"
                f"pathlib.Path({str(marker)!r}).write_text(str(pathlib.Path.cwd()))\n"
                f"print({_record()!r}, flush=True)\n"
            )
            probe = self._probe()
            with _payload(source), patch.object(LocalEnvironmentProbe, "_cleanup", side_effect=OSError("fixture")):
                with self.assertRaises(ProbeError) as caught:
                    await probe.observe("Python")
            self.assertEqual(caught.exception.reason, "cleanup_failed")
            directory = Path(marker.read_text(encoding="utf-8"))
            try:
                self.assertTrue(directory.is_dir())
                with self.assertRaises(ProbeError) as closed:
                    await probe.observe("Python")
                self.assertEqual(closed.exception.reason, "closed")
                with self.assertRaises(ProbeError) as failed_close:
                    await probe.aclose()
                self.assertEqual(failed_close.exception.reason, "cleanup_failed")
            finally:
                # 本夹具主进程已正常退出，仅人为阻断清理；测试自行移除已核对的临时目录。
                shutil.rmtree(directory)

    async def test_cancel_during_start_waits_original_handle_before_cleanup(self) -> None:
        """创建进程已经开始但句柄尚未交付时，取消仍等到原句柄再清理。"""
        probe = self._probe(terminate_grace_seconds=1)
        created = asyncio.Event()
        release = asyncio.Event()
        processes: list[asyncio.subprocess.Process] = []
        original = asyncio.create_subprocess_exec

        async def held_start(program: str, *args: str, **kwargs: Any) -> asyncio.subprocess.Process:
            """延迟交付已经创建的真实进程，暴露启动取消时所有权缺口。

            :param program: 原适配器指定的解释器位置。
            :param args: 原固定探针参数。
            :param kwargs: 标准库原进程创建参数，保持原样。
            :returns: 原实际进程句柄，不重新启动。
            """
            process = await original(program, *args, **kwargs)
            processes.append(process)
            created.set()
            await release.wait()
            return process

        try:
            with patch.object(asyncio, "create_subprocess_exec", held_start), _payload("import time\ntime.sleep(10)\n"):
                task = asyncio.create_task(probe.observe("Python"))
                await asyncio.wait_for(created.wait(), 5)
                task.cancel()
                await asyncio.sleep(0.05)
                self.assertFalse(task.done())
                release.set()
                with self.assertRaises(asyncio.CancelledError):
                    await task
            self.assertEqual(len(processes), 1)
            self.assertFalse(_running(processes[0].pid))
        finally:
            release.set()
            await probe.aclose()

    async def test_parallel_probes_use_independent_working_directories(self) -> None:
        """同一实例并行探针各自创建目录，不能覆盖彼此中间文件。"""
        with tempfile.TemporaryDirectory() as temporary:
            source = (
                "import os, pathlib, time\n"
                f"pathlib.Path({temporary!r}, str(os.getpid())).write_text(str(pathlib.Path.cwd()))\n"
                "time.sleep(0.15)\n"
                f"print({_record()!r})\n"
            )
            probe = self._probe()
            try:
                with _payload(source):
                    observations = await asyncio.gather(probe.observe("Python"), probe.observe("Python"))
                directories = [Path(path.read_text(encoding="utf-8")) for path in Path(temporary).iterdir()]
                self.assertEqual(len(set(directories)), 2)
                self.assertTrue(all(not directory.exists() for directory in directories))
                self.assertTrue(all(observation.cpu_check for observation in observations))
            finally:
                await probe.aclose()

    async def test_close_stops_admission_and_waits_inflight_probe(self) -> None:
        """关闭取消正在运行的原探针，所有者完成后拒绝新调用。"""
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "pid"
            source = (
                "import os, pathlib, time\n"
                f"pathlib.Path({str(marker)!r}).write_text(str(os.getpid()))\n"
                "time.sleep(10)\n"
            )
            probe = self._probe(terminate_grace_seconds=1)
            with _payload(source):
                task = asyncio.create_task(probe.observe("Python"))
                await self._wait_file(marker)
                await probe.aclose()
                with self.assertRaises(asyncio.CancelledError):
                    await task
            self.assertFalse(_running(int(marker.read_text(encoding="utf-8"))))
            with self.assertRaises(ProbeError) as caught:
                await probe.observe("Python")
            self.assertEqual(caught.exception.reason, "closed")

    async def test_cancelled_close_waiter_does_not_abandon_original_process(self) -> None:
        """关闭等待被取消后原清理继续，下一次关闭等待同一实际终态。"""
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "pid"
            source = (
                "import os, pathlib, signal, time\n"
                "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
                f"pathlib.Path({str(marker)!r}).write_text(str(os.getpid()))\n"
                "time.sleep(10)\n"
            )
            probe = self._probe(terminate_grace_seconds=1)
            with _payload(source):
                observation = asyncio.create_task(probe.observe("Python"))
                await self._wait_file(marker)
                closing = asyncio.create_task(probe.aclose())
                await asyncio.sleep(0.05)
                closing.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await closing
                self.assertTrue(_running(int(marker.read_text(encoding="utf-8"))))
                await probe.aclose()
                with self.assertRaises(asyncio.CancelledError):
                    await observation
            self.assertFalse(_running(int(marker.read_text(encoding="utf-8"))))

    async def test_diagnostic_failure_does_not_override_real_observation(self) -> None:
        """诊断输出异常仍完成真实自检和清理，排障故障单独写向 stderr。"""
        probe = self._probe()
        logger = logging.getLogger("vet3d")
        handler = _BrokenLog()
        original_level = logger.level
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        try:
            with patch.object(sys, "stderr") as stderr:
                observation = await probe.observe("Python")
                self.assertTrue(observation.cpu_check)
                self.assertTrue(stderr.write.called)
        finally:
            logger.removeHandler(handler)
            logger.setLevel(original_level)
            handler.close()
            await probe.aclose()
