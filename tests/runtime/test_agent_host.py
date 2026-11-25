# 文件信息：L2-02 阶段 B 有限宿主的输入及信号交接测试。
# 作用：核对启动前拒绝、原生取消和退出语义，不启动真实模型或容器。
# 边界：宿主替身仅证明机械接入，不宣称建模、隔离或资源回收通过。
"""检查有限命令的实际调用边界及取消传递，不为薄包装凑覆盖率。"""

import asyncio
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import signal
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from vet3d.adapters import CodexAgentSession, NativeMessage, NativeSessionBinding
from vet3d.bootstrap import AgentRuntime
from vet3d.host import agent_main
from vet3d.identity import TaskId, TaskIdentity, WorkspaceId


class AgentHostTests(unittest.TestCase):
    """以有限宿主入口验证不应产生模型副作用的拒绝和停止分支。"""

    def setUp(self) -> None:
        """建立明确的目标文件和唯一任务，配置本身由装配替身提供。"""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.goal = self.root / "goal.txt"
        self.goal.write_text("独立任务目标", encoding="utf-8")
        self.continuation = self.root / "continuation.txt"
        self.continuation.write_text("独立追加要求", encoding="utf-8")
        self.task = TaskIdentity(TaskId(uuid4()), WorkspaceId(uuid4()))
        self.argv = ["--config", str(self.root / "config.yaml"),
                     "--workspace-id", str(self.task.workspace_id.value), "--task-id", str(self.task.id.value),
                     "--materials", str(self.root), "--goal-file", str(self.goal)]

    def test_nonpositive_and_nonfinite_deadlines_rejected_before_configuration(self) -> None:
        """无效期限在配置、目录及环境创建之前被命令行拒绝。"""
        with patch("vet3d.host.agent.load_settings") as load:
            for value in ("0", "-1", "nan", "inf"):
                with self.subTest(value=value), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                    agent_main([*self.argv, "--turn-timeout-seconds", value])
                self.assertEqual(error.exception.code, 2)
            load.assert_not_called()

    def test_unicode_blank_goal_rejected_before_storage_or_runtime_open(self) -> None:
        """Unicode 空白不能等到创建执行环境后才当作无效目标。"""
        self.goal.write_text("\u3000\u2003\n", encoding="utf-8")
        with patch("vet3d.host.agent.load_settings"), patch("vet3d.host.agent.open_operations", new=AsyncMock()) as opened:
            self.assertEqual(agent_main(self.argv), 2)
            opened.assert_not_awaited()

    def test_native_failed_result_does_not_trigger_continuation_or_quality_pass(self) -> None:
        """失败保留原生错误，不自动追加请求或把输出写成业务通过。"""
        session = MagicMock(spec=CodexAgentSession)
        session.binding = NativeSessionBinding(self.task, "native/thread")
        session.run = AsyncMock(return_value={"id": "turn/original", "status": "failed", "error": {"message": "native failure"}})
        owner = MagicMock(spec=AgentRuntime)
        owner.__aenter__.return_value = owner
        owner.__aexit__.return_value = False
        owner.open_session = AsyncMock(return_value=session)
        operations = MagicMock()
        operations.__aenter__.return_value = operations
        operations.__aexit__.return_value = False
        output = io.StringIO()
        with patch("vet3d.host.agent.load_settings"), patch("vet3d.host.agent.open_operations", new=AsyncMock(return_value=operations)), patch(
            "vet3d.host.agent.AgentRuntime", return_value=owner,
        ), redirect_stdout(output):
            code = agent_main([*self.argv, "--continue-file", str(self.continuation)])
        self.assertEqual(code, 1)
        self.assertEqual(session.run.await_count, 1)
        result = json.loads(output.getvalue())
        self.assertEqual(result["turn"]["error"], {"message": "native failure"})
        self.assertEqual(result["quality_assessment"], "not_run")
        self.assertFalse(result["formal_assets_registered"])
        owner.__aexit__.assert_awaited_once()

    def test_stop_signal_uses_native_cancel_and_skips_continuation(self) -> None:
        """TERM 和 INT 都传递到原生取消，重复信号不打断关闭或追加新轮。"""
        for signum, expected_code in ((signal.SIGTERM, 143), (signal.SIGINT, 130)):
            with self.subTest(signal=signum):
                handlers: dict[int, Callable[[], None]] = {}
                cancelled = asyncio.Event()
                session = MagicMock(spec=CodexAgentSession)
                session.binding = NativeSessionBinding(self.task, "native/thread")

                def install(number: int, callback: Callable[[], None]) -> None:
                    """保存宿主实际注册的信号回调，避免向测试进程发送系统信号。

                    :param number: 原信号编号。
                    :param callback: 宿主交给事件循环的回调。
                    """
                    handlers[number] = callback

                async def cancel() -> None:
                    """模拟原生取消受理，不生成另一轮或直接结束宿主任务。"""
                    cancelled.set()

                async def run(goal: str, **kwargs: object) -> NativeMessage:
                    """在原轮次运行期间触发已注册的停止回调。

                    :param goal: 原任务目标。
                    :param kwargs: 原观察与 Skill 参数。
                    :returns: 原生中断终态。
                    """
                    handlers[signum]()
                    handlers[signum]()
                    await asyncio.wait_for(cancelled.wait(), 0.5)
                    return {"id": "turn/original", "status": "interrupted"}

                session.cancel = AsyncMock(side_effect=cancel)
                session.run = AsyncMock(side_effect=run)
                owner = MagicMock(spec=AgentRuntime)
                owner.__aenter__.return_value = owner
                owner.__aexit__.return_value = False
                owner.open_session = AsyncMock(return_value=session)
                operations = MagicMock()
                operations.__aenter__.return_value = operations
                operations.__aexit__.return_value = False
                with patch("vet3d.host.agent.load_settings"), patch("vet3d.host.agent.open_operations", new=AsyncMock(return_value=operations)), patch(
                    "vet3d.host.agent.AgentRuntime", return_value=owner,
                ), patch("asyncio.unix_events._UnixSelectorEventLoop.add_signal_handler", side_effect=install), patch(
                    "asyncio.unix_events._UnixSelectorEventLoop.remove_signal_handler", return_value=True,
                ), redirect_stdout(io.StringIO()):
                    code = agent_main([*self.argv, "--continue-file", str(self.continuation)])
                self.assertEqual(code, expected_code)
                session.cancel.assert_awaited_once()
                self.assertEqual(session.run.await_count, 1)
                owner.__aexit__.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
