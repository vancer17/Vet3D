# 文件信息：L2-01 有限环境检查 CLI 的真实 SIGTERM 与重开交接测试。
# 作用：在原探针父子进程运行时中断宿主，验证实际清理后退出及下一进程重新观察。
# 证据边界：固定载荷只在测试中替换；不证明宿主 SIGKILL 恢复、容器隔离或动物质量。
"""把操作系统信号、原进程所有权和资源重开连接为真实集成验证。"""

import asyncio
import contextlib
from dataclasses import asdict
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
from typing import cast
import unittest
from unittest.mock import patch

from vet3d.adapters import LocalEnvironmentProbe, ResourceLimits, build_resource_bundle
from vet3d.artifacts import ContentFingerprint
from vet3d.bootstrap import initialize_operations, load_settings
from vet3d.host import operations_main
from vet3d.resources import ResourceKey, ResourceReference


def _arguments(config: Path, reference: ResourceReference) -> list[str]:
    """从同一原引用生成有限命令的完整身份参数。

    :param config: 当前测试的明确配置文件。
    :param reference: 已真实安装的资源身份。
    :returns: 原资源键、清单摘要及字节数，不选择 latest。
    """
    return [
        "--config", str(config), "--check-environment", reference.key.value,
        "--snapshot-sha256", reference.snapshot.sha256,
        "--snapshot-size", str(reference.snapshot.byte_size),
    ]


def _running(pid: int) -> bool:
    """独立核对子孙是否仍能执行，已停止的僵尸等待系统父进程回收。

    :param pid: 本例实际载荷登记的进程 ID。
    :returns: 原进程仍处于非终止状态时为真。
    """
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except FileNotFoundError:
        return False
    return stat[stat.rfind(")") + 2:].split()[0] not in ("Z", "X")


def _run_child(config: Path, reference: ResourceReference, marker: Path) -> int:
    """让真实 CLI 在原探针父子就绪后收到 SIGTERM，不改变产品信号处理。

    :param config: 本例真实配置。
    :param reference: 已安装的确切资源身份。
    :param marker: 测试载荷写出的原进程组、子进程与临时目录证据。
    :returns: 产品 CLI 实际退出码，预期为一百四十三。
    """
    child_marker = marker.with_suffix(".child")
    descendant = (
        "import signal,time\nfrom pathlib import Path\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        f"Path({str(child_marker)!r}).write_text('ready', encoding='utf-8')\n"
        "time.sleep(30)\n"
    )
    payload = (
        "import json,os,signal,subprocess,sys,time\nfrom pathlib import Path\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        f"child = subprocess.Popen([sys.executable, '-I', '-B', '-c', {descendant!r}])\n"
        f"while not Path({str(child_marker)!r}).exists():\n    time.sleep(0.01)\n"
        f"Path({str(marker.with_suffix('.pending'))!r}).write_text(json.dumps({{'parent': os.getpid(), 'child': child.pid, "
        "'directory': str(Path.cwd())}), encoding='utf-8')\n"
        f"Path({str(marker.with_suffix('.pending'))!r}).replace({str(marker)!r})\n"
        "time.sleep(30)\n"
    )
    sent = threading.Event()

    def send_signal() -> None:
        """依据真实就绪文件发送信号，不用固定睡眠猜测子进程已经启动。"""
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if marker.exists():
                sent.set()
                os.kill(os.getpid(), signal.SIGTERM)
                return
            time.sleep(0.01)

    sender = threading.Thread(target=send_signal, name="environment-signal-test-sender")
    sender.start()
    output = io.StringIO()
    with patch.object(LocalEnvironmentProbe, "_payload", return_value=payload), contextlib.redirect_stdout(output):
        code = operations_main(_arguments(config, reference))
    sender.join(timeout=9)
    print(json.dumps({
        "signal_sent": sent.is_set(), "cli_stdout": output.getvalue(),
        "remaining_workers": [thread.name for thread in threading.enumerate() if thread.name.startswith("vet3d")],
    }), flush=True)
    return code


class EnvironmentSignalTests(unittest.TestCase):
    """验证非交互宿主实际停止原任务，下一进程只做新的独立观察。"""

    def _fixture(self, base: Path) -> tuple[Path, ResourceReference]:
        """通过公共构建和存储入口安装有运行要求的不可变资源。

        :param base: 本测试唯一拥有的临时根。
        :returns: 已有存储配置和原资源身份。
        """
        for name in ("inputs", "sources", "author"):
            (base / name).mkdir(mode=0o700)
        payload = base / "author" / "payload"
        payload.mkdir(mode=0o700)
        source = payload / "never-execute.py"
        source.write_text("raise RuntimeError('resource code must never execute')\n", encoding="utf-8")
        source.chmod(0o600)
        metadata = {
            "purpose": "信号交接测试", "source": "Vet3D 自研测试源", "inputs": "不执行",
            "outputs": "无", "overwrite": "禁止", "failure": "仅声明",
            "adoption": "独立实现", "priority": "首期", "evidence": "受信环境探针测试",
        }
        spec = base / "author" / "resource-spec.json"
        spec.write_text(json.dumps({
            "schema_version": 1, "resources": [{
                "kind": "script", "key": "fixture.signal", "entry": "never-execute.py",
                "files": ["never-execute.py"], "dependencies": [], "metadata": metadata,
                "interpreter": {"runtime": "Python", "version": "3.14", "dependencies": ["sqlite3"]},
            }],
        }, ensure_ascii=False), encoding="utf-8")
        spec.chmod(0o600)
        limits = ResourceLimits(max_manifest_bytes=8192, max_files=4, max_file_bytes=1024, max_total_bytes=4096)
        snapshot = build_resource_bundle(base / "author", base / "sources" / "signal", limits=limits)
        reference = ResourceReference(snapshot, ResourceKey("fixture.signal"))
        config = base / "settings.yaml"
        config.write_text(json.dumps({
            "workspaces": {"root": "workspaces"}, "files": {"input_root": "inputs", "max_file_bytes": 1024},
            "resources": {"root": "resources", "source_root": "sources", "limits": asdict(limits)},
            "diagnostics": {"root": "logs"},
            "interpreters": [{"runtime": "Python", "path": sys.executable}],
            "environment_probe": {"timeout_seconds": 15, "terminate_grace_seconds": 1},
        }), encoding="utf-8")

        async def install() -> None:
            """安装确切快照并释放原存储锁，后续 CLI 必须自行重开。"""
            runtime = await initialize_operations(load_settings(config))
            try:
                await runtime.resources.install("signal", snapshot)
            finally:
                await runtime.aclose()

        with contextlib.redirect_stderr(io.StringIO()):
            asyncio.run(install())
        return config, reference

    def test_sigterm_during_probe_stops_original_tree_and_reopen_observes_again(self) -> None:
        """真实 SIGTERM 返回 143 且无成功回执，原父子已停并允许新进程取得新证据。"""
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {}, clear=True):
            base = Path(temporary)
            config, reference = self._fixture(base)
            marker = base / "probe-processes.json"
            try:
                interrupted = subprocess.run(
                    [sys.executable, "-B", str(Path(__file__).absolute()), "--signal-child", str(config),
                     reference.key.value, reference.snapshot.sha256, str(reference.snapshot.byte_size), str(marker)],
                    capture_output=True, text=True, timeout=20, check=False,
                )
                self.assertEqual(interrupted.returncode, 143, interrupted.stderr)
                child_report = json.loads(interrupted.stdout)
                self.assertTrue(child_report["signal_sent"])
                self.assertEqual(child_report["cli_stdout"], "")
                self.assertEqual(child_report["remaining_workers"], [])
                processes = cast(dict[str, object], json.loads(marker.read_text(encoding="utf-8")))
                self.assertFalse(_running(cast(int, processes["parent"])))
                self.assertFalse(_running(cast(int, processes["child"])))
                self.assertFalse(Path(cast(str, processes["directory"])).exists())
                events = [json.loads(line) for line in (base / "logs" / "events.jsonl").read_text(encoding="utf-8").splitlines()]
                interrupted_runtime = events[0]["runtime_id"]
                reopened = subprocess.run(
                    [sys.executable, "-B", "-c", "from vet3d.host import operations_main; raise SystemExit(operations_main())",
                     *_arguments(config, reference)],
                    cwd=base, capture_output=True, text=True, timeout=20, check=False,
                )
                self.assertEqual(reopened.returncode, 0, reopened.stderr)
                report = json.loads(reopened.stdout)
                self.assertEqual(report["environment"]["status"], "satisfied")
                self.assertEqual(report["environment"]["root"], asdict(reference))
                self.assertNotEqual(report["runtime_id"], interrupted_runtime)
                self.assertEqual(report["environment"]["checks"][0]["observation"]["python_version"], list(sys.version_info[:3]))
            finally:
                # 测试断言失败时也只清理本例记录的原进程组，不影响其他任务。
                if marker.exists():
                    processes = cast(dict[str, object], json.loads(marker.read_text(encoding="utf-8")))
                    parent = cast(int, processes["parent"])
                    if _running(parent) or _running(cast(int, processes["child"])):
                        try:
                            os.killpg(parent, signal.SIGKILL)
                        except ProcessLookupError:
                            pass


if __name__ == "__main__":
    if len(sys.argv) == 7 and sys.argv[1] == "--signal-child":
        raise SystemExit(_run_child(
            Path(sys.argv[2]), ResourceReference(ContentFingerprint(sys.argv[4], int(sys.argv[5])), ResourceKey(sys.argv[3])),
            Path(sys.argv[6]),
        ))
    unittest.main()
