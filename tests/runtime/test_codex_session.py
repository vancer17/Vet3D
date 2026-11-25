# 文件信息：L2-02 阶段 B 的原生会话机械边界测试。
# 作用：用实际 stdio 替身覆盖关联、继续、取消、期限和观察，不调用模型。
# 边界：这些测试不证明真实工具、图片理解、执行隔离或业务质量。
"""验证有限会话消费者的可观察行为，不同步另一份业务状态机。"""

import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from uuid import uuid4

from vet3d.adapters import AppServerStdioClient, CodexAgentSession, NativeMessage, NativeProtocolError, NativeSessionBinding
from vet3d.identity import TaskId, TaskIdentity, WorkspaceId


_SERVER = '''# 文件信息：会话测试的机械原生协议替身，不提供建模能力。
import json
from pathlib import Path
import sys
import time

mode, filename = sys.argv[1:]
turn_number = 0

def emit(value: dict[str, object]) -> None:
    """交付替身指定的原生对象。

    :param value: 待写出的 JSON 消息。
    """
    print(json.dumps(value), flush=True)

for line in sys.stdin:
    message = json.loads(line)
    with Path(filename).open("a", encoding="utf-8") as record:
        record.write(json.dumps(message) + "\\n")
    method = message.get("method")
    params = message.get("params", {})
    if method == "initialized" or method is None:
        continue
    if method == "initialize":
        emit({"id": message["id"], "result": {"mechanical": True}})
    elif method in ("thread/start", "thread/resume"):
        thread = "thread/other" if mode == "wrong-thread" else "thread/original"
        provider = "other" if mode == "wrong-provider" else "test-provider"
        emit({"id": message["id"], "result": {"model": "test-model", "modelProvider": provider,
                                               "thread": {"id": thread}}})
    elif method == "mcpServerStatus/list":
        tools = [{"name": "untrusted"}] if mode == "extensions" else []
        emit({"id": message["id"], "result": {"data": tools, "nextCursor": None}})
    elif method == "thread/read":
        thread = "other" if mode == "read-other" else params["threadId"]
        emit({"id": message["id"], "result": {"thread": {"id": thread, "turns": []}}})
    elif method == "turn/start":
        turn_number += 1
        turn_id = "turn/" + str(turn_number)
        if mode in ("slow-start", "start-timeout"):
            time.sleep(0.12)
        emit({"id": message["id"], "result": {"turn": {"id": turn_id, "status": "inProgress"}}})
        emit({"method": "item/started", "params": {"threadId": params["threadId"], "turnId": turn_id,
                                                   "item": {"id": "item/test", "type": "commandExecution"}}})
        if mode in ("wait", "slow-start", "never-terminal"):
            continue
        emit({"method": "thread/tokenUsage/updated", "params": {"threadId": params["threadId"],
                                                               "turnId": "prior-turn", "tokenUsage": {}}})
        emit({"method": "future/image-feedback", "params": {"threadId": params["threadId"],
             "payload": {"error": "原始错误", "image": "synthetic-native-image"}}})
        terminal_thread = "other" if mode == "terminal-other" else params["threadId"]
        terminal = {"id": turn_id, "status": "failed" if mode == "failed" else "completed"}
        if mode == "failed":
            terminal["error"] = {"message": "native model error"}
        emit({"method": "turn/completed", "params": {"threadId": terminal_thread, "turn": terminal}})
    elif method == "turn/interrupt":
        emit({"id": message["id"], "result": {}})
        if mode != "never-terminal":
            emit({"method": "turn/completed", "params": {"threadId": params["threadId"],
                  "turn": {"id": params["turnId"], "status": "interrupted"}}})
    elif method == "thread/backgroundTerminals/clean":
        if mode == "clean-error":
            emit({"id": message["id"], "error": {"code": -32000, "message": "cleanup failed"}})
        else:
            emit({"id": message["id"], "result": {}})
    else:
        emit({"id": message["id"], "result": {}})
'''


class CodexSessionTests(unittest.IsolatedAsyncioTestCase):
    """以真实子进程协议核对会话公共入口和必要恢复边界。"""

    async def asyncSetUp(self) -> None:
        """准备本例独立记录及已有任务身份，不创建产品注册。"""
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.record = self.root / "requests.jsonl"
        self.task = TaskIdentity(TaskId(uuid4()), WorkspaceId(uuid4()))
        self.clients: list[AppServerStdioClient] = []
        self.sessions: list[CodexAgentSession] = []

    async def asyncTearDown(self) -> None:
        """排空每例连接进程，不把替身关闭解释为真实隔离证据。"""
        for client in self.clients:
            await client.aclose()
        self.temporary.cleanup()

    async def _client(self, mode: str, *, timeout: float = 1.0) -> AppServerStdioClient:
        """启动指定故障模式的机械连接。

        :param mode: 本测试替身的分支。
        :param timeout: 单次协议等待期限，独立于会话总期限。
        :returns: 已握手的真实 stdio 客户端。
        """
        client = await AppServerStdioClient.start(
            (sys.executable, "-u", "-c", _SERVER, mode, str(self.record)),
            cwd=self.root, env={"PATH": os.defpath}, read_timeout_seconds=timeout,
        )
        self.clients.append(client)
        return client

    async def _open(self, mode: str = "normal", *, timeout: float = 1.0) -> CodexAgentSession:
        """为同一受信任务打开具体会话。

        :param mode: 机械故障分支。
        :param timeout: 总轮次等待期限。
        :returns: 完成回执与工具来源核对的会话。
        """
        session = await CodexAgentSession.open(
            await self._client(mode), self.task, environment_id="task-remote", cwd="/work",
            model="test-model", provider="test-provider", turn_timeout_seconds=timeout,
            interrupt_grace_seconds=0.3,
        )
        self.sessions.append(session)
        return session

    def _requests(self, method: str) -> list[NativeMessage]:
        """读取已到达替身的实际请求，检查是否发生重交。

        :param method: 需要核对的原生方法。
        :returns: 对应消息，不从测试计数推导模型能力。
        """
        messages: list[NativeMessage] = [json.loads(line) for line in self.record.read_text().splitlines()]
        return [message for message in messages if message.get("method") == method]

    async def test_continuation_preserves_native_feedback_and_rebinds_environment(self) -> None:
        """两轮使用原任务和原线程，原始错误及图片字段不被摘要替换。"""
        session = await self._open()
        events: list[NativeMessage] = []

        async def observe(event: NativeMessage) -> None:
            """保存测试消费者收到的原生通知。

            :param event: 会话交付的原通知内容。
            """
            events.append(event)

        first = await session.run("原始目标", on_event=observe, skill_name="material", skill_path="/work/skills/SKILL.md")
        second = await session.run("独立追加要求", on_event=observe)
        self.assertIs(session.binding.task, self.task)
        self.assertEqual(first, {"id": "turn/1", "status": "completed"})
        self.assertEqual(second, {"id": "turn/2", "status": "completed"})
        images = [event for event in events if event["method"] == "future/image-feedback"]
        self.assertEqual(len(images), 2)
        self.assertIn("原始错误", str(images[0]))
        self.assertIn("synthetic-native-image", str(images[0]))
        for request in self._requests("turn/start"):
            params = request["params"]
            assert isinstance(params, dict)
            self.assertEqual(params["threadId"], "thread/original")
            self.assertEqual(params["environments"], [{"environmentId": "task-remote", "cwd": "/work", "runtimeWorkspaceRoots": ["/work"]}])
        self.assertEqual(len(self._requests("thread/start")), 1)
        await session.aclose()

    async def test_external_cancel_while_reading_targets_original_turn_once(self) -> None:
        """外部取消不等待通知锁，同一轮多次取消只发一次请求。"""
        session = await self._open("wait")
        observed = asyncio.Event()

        async def observe(event: NativeMessage) -> None:
            """以首个工具通知确认轮次已受理。

            :param event: 原生通知。
            """
            if event.get("method") == "item/started":
                observed.set()

        running = asyncio.create_task(session.run("开始", on_event=observe))
        await asyncio.wait_for(observed.wait(), 1)
        with self.assertRaises(NativeProtocolError):
            await session.run("不应排队")
        with self.assertRaises(NativeProtocolError):
            session.ensure_resumable()
        await asyncio.wait_for(asyncio.gather(session.cancel(), session.cancel()), 0.5)
        self.assertEqual(await running, {"id": "turn/1", "status": "interrupted"})
        self.assertEqual(len(self._requests("turn/interrupt")), 1)
        self.assertEqual(self._requests("turn/interrupt")[0]["params"], {"threadId": "thread/original", "turnId": "turn/1"})
        await session.aclose()

    async def test_cancel_during_start_waits_for_original_receipt(self) -> None:
        """受理期间的取消不另起任务，拿到原轮次后才请求中断。"""
        session = await self._open("slow-start")
        running = asyncio.create_task(session.run("开始"))
        await asyncio.sleep(0.03)
        await session.cancel()
        self.assertEqual((await running)["status"], "interrupted")
        self.assertEqual(len(self._requests("turn/start")), 1)
        self.assertEqual(len(self._requests("turn/interrupt")), 1)
        await session.aclose()

    async def test_deadline_interrupts_and_missing_terminal_blocks_reuse(self) -> None:
        """超时只中断原轮，宽限后缺少终态不能再次提交或恢复。"""
        session = await self._open("never-terminal", timeout=0.04)
        with self.assertRaises(TimeoutError):
            await session.run("唯一目标")
        with self.assertRaises(NativeProtocolError):
            await session.run("不应重交")
        with self.assertRaises(NativeProtocolError):
            session.ensure_resumable()
        self.assertEqual(len(self._requests("turn/start")), 1)
        self.assertEqual(len(self._requests("turn/interrupt")), 1)
        self.assertEqual(await session.read(), {"thread": {"id": "thread/original", "turns": []}})
        with self.assertRaises(NativeProtocolError):
            session.ensure_resumable()
        await session.aclose()

    async def test_start_wait_counts_towards_deadline_without_blind_cancel(self) -> None:
        """提交等待也消耗期限，未知轮次时不编造取消或重发身份。"""
        session = await self._open("start-timeout", timeout=0.03)
        with self.assertRaises(TimeoutError):
            await session.run("唯一目标")
        self.assertEqual(len(self._requests("turn/start")), 1)
        self.assertEqual(self._requests("turn/interrupt"), [])
        with self.assertRaises(NativeProtocolError):
            await session.cancel()
        with self.assertRaises(BaseExceptionGroup):
            await session.aclose()

    async def test_resume_rejects_changed_identity_and_checks_provider(self) -> None:
        """恢复沿原线程与模型连接，拒绝回包替换和未授权扩展。"""
        binding = NativeSessionBinding(self.task, "thread/original")
        for mode in ("wrong-thread", "wrong-provider", "extensions"):
            with self.subTest(mode=mode), self.assertRaises(NativeProtocolError):
                await CodexAgentSession.resume(
                    await self._client(mode), binding, environment_id="task-remote", cwd="/work",
                    model="test-model", provider="test-provider",
                )
        self.assertEqual(self._requests("thread/start"), [])

    async def test_resume_uses_original_binding_and_next_turn_environment(self) -> None:
        """同环境恢复后下一轮显式绑定远端，不恢复到控制侧默认环境。"""
        binding = NativeSessionBinding(self.task, "thread/original")
        session = await CodexAgentSession.resume(
            await self._client("normal"), binding, environment_id="task-remote", cwd="/work",
            model="test-model", provider="test-provider",
        )
        self.assertIs(session.binding, binding)
        await session.run("独立追加")
        params = self._requests("turn/start")[0]["params"]
        assert isinstance(params, dict)
        self.assertEqual(params["environments"], [{"environmentId": "task-remote", "cwd": "/work", "runtimeWorkspaceRoots": ["/work"]}])
        await session.aclose()

    async def test_invalid_skill_is_rejected_before_turn_submission(self) -> None:
        """Skill 越界或不配套不能借原生输入进入其他目录。"""
        session = await self._open()
        for name, path in (("selected", "/elsewhere/SKILL.md"), (None, "/work/SKILL.md"), ("selected", "/work/../private/SKILL.md")):
            with self.subTest(path=path), self.assertRaises(ValueError):
                await session.run("目标", skill_name=name, skill_path=path)
        self.assertEqual(self._requests("turn/start"), [])
        await session.aclose()

    async def test_failed_native_turn_keeps_original_error_without_repair(self) -> None:
        """原生失败保留原错误，接入层不启动补救轮或产生通过结论。"""
        session = await self._open("failed")
        self.assertEqual(await session.run("目标"), {"id": "turn/1", "status": "failed", "error": {"message": "native model error"}})
        self.assertEqual(len(self._requests("turn/start")), 1)
        await session.aclose()

    async def test_cross_thread_terminal_invalidates_session(self) -> None:
        """另一任务的成功不能完成本任务，后续新轮必须拒绝。"""
        session = await self._open("terminal-other")
        with self.assertRaises(NativeProtocolError):
            await session.run("目标")
        with self.assertRaises(NativeProtocolError):
            await session.run("不可重交")
        await session.aclose()

    async def test_close_waits_for_running_turn_and_closes_even_when_clean_fails(self) -> None:
        """关闭先取消在途轮次；原生清理失败仍关闭连接并保留错误。"""
        session = await self._open("wait")
        running = asyncio.create_task(session.run("目标"))
        await asyncio.sleep(0.03)
        await session.aclose()
        self.assertEqual((await running)["status"], "interrupted")
        failing = await self._open("clean-error")
        with self.assertRaises(BaseExceptionGroup):
            await failing.aclose()
        with self.assertRaises(NativeProtocolError):
            await failing.read()

    async def test_terminal_observer_failure_preserves_confirmed_native_fact(self) -> None:
        """终态观察输出失败不能把已确认完成改写成执行未知。"""
        session = await self._open()

        async def fail_on_terminal(event: NativeMessage) -> None:
            """模拟宿主呈现终态时失败。

            :param event: 已经关联核对的原生通知。
            :raises RuntimeError: 终态事件的观察输出故障。
            """
            if event.get("method") == "turn/completed":
                raise RuntimeError("presentation failed")

        with self.assertRaisesRegex(RuntimeError, "presentation failed"):
            await session.run("目标", on_event=fail_on_terminal)
        self.assertEqual(session.last_terminal, {"id": "turn/1", "status": "completed"})
        projected = session.last_terminal
        assert projected is not None
        projected["status"] = "projection must not change native fact"
        self.assertEqual(session.last_terminal, {"id": "turn/1", "status": "completed"})
        session.ensure_resumable()
        self.assertEqual(len(self._requests("turn/start")), 1)
        await session.aclose()

    async def test_idle_notification_timeout_does_not_exhaust_turn_budget(self) -> None:
        """单次通知空等期限不提前中断仍有预算的原轮次。"""
        session = await CodexAgentSession.open(
            await self._client("wait", timeout=0.08), self.task,
            environment_id="task-remote", cwd="/work", model="test-model", provider="test-provider",
            turn_timeout_seconds=0.6, interrupt_grace_seconds=0.3,
        )
        running = asyncio.create_task(session.run("原生计算中"))
        await asyncio.sleep(0.2)
        self.assertFalse(running.done())
        self.assertEqual(self._requests("turn/interrupt"), [])
        await session.cancel()
        self.assertEqual((await running)["status"], "interrupted")
        await session.aclose()

    async def test_cancel_wakes_blocked_progress_observer(self) -> None:
        """外部取消可以终止缓慢的观察等待，不让宿主呈现阻塞原生中断。"""
        session = await self._open("wait")
        observed = asyncio.Event()

        async def slow_observer(event: NativeMessage) -> None:
            """模拟只在工具通知处阻塞的进度消费者。

            :param event: 原生通知，不参与模型反馈。
            """
            if event.get("method") == "item/started":
                observed.set()
                await asyncio.Event().wait()

        running = asyncio.create_task(session.run("目标", on_event=slow_observer))
        await asyncio.wait_for(observed.wait(), 0.5)
        await session.cancel()
        self.assertEqual((await asyncio.wait_for(running, 0.5))["status"], "interrupted")
        await session.aclose()

    async def test_read_rejects_another_thread_without_starting_a_turn(self) -> None:
        """原会话查询不接受另一线程，也不通过提交目标补齐结果。"""
        session = await self._open("read-other")
        with self.assertRaises(NativeProtocolError):
            await session.read()
        self.assertEqual(self._requests("turn/start"), [])
        await session.aclose()


if __name__ == "__main__":
    unittest.main()
