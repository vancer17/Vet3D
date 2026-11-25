# 文件信息：L2-02 阶段 A 原生关联和 JSONL 接入的机械协议测试。
# 作用：以独立 Python stdio 替身验证身份错配、回执、限额、断连及不重发。
# 边界：不调用模型，不证明真实 Agent、自主修复、视觉反馈或隔离已经通过。
"""只验证实验消费者的机械边界，真实闭环另行取得证据。"""

import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from uuid import uuid4

from vet3d.experiments import (
    AppServerStdioClient, NativeMessage, NativeProtocolError, NativeResponseError,
    NativeSessionBinding, run_native_turn,
)
from vet3d.identity import TaskId, TaskIdentity, WorkspaceId


_SERVER = '''# 文件信息：本测试唯一的机械 stdio 替身，不调用模型或工具。
import json
import os
from pathlib import Path
import sys
import time

mode, record = sys.argv[1:]

def emit(message: dict[str, object]) -> None:
    """写出一条机械响应。

    :param message: 测试指定的 JSON 对象。
    """
    print(json.dumps(message), flush=True)

for line in sys.stdin:
    message = json.loads(line)
    with Path(record).open("a", encoding="utf-8") as output:
        output.write(json.dumps({"pid": os.getpid(), "message": message}) + "\\n")
    method = message.get("method")
    if method == "initialize":
        emit({"id": message["id"] + (1 if mode == "start-error" else 0), "result": {"testOnly": True}})
    elif method == "initialized":
        continue
    elif method is None:
        continue
    elif mode == "disconnect":
        sys.exit(3)
    elif mode == "wrong-id":
        emit({"id": message["id"] + 1, "result": {}})
    elif mode == "long":
        print("x" * 4096, flush=True)
    elif mode == "timeout":
        for index in range(40):
            emit({"method": "future/progress", "params": {"index": index}})
            time.sleep(0.05)
    elif mode == "flood":
        for index in range(129):
            emit({"method": "future/progress", "params": {"index": index}})
        emit({"id": message["id"], "result": {}})
    elif mode == "approval":
        emit({"id": "native-request", "method": "item/commandExecution/requestApproval", "params": {}})
    elif mode == "remote-error":
        emit({"id": message["id"], "error": {"code": -32000, "message": "synthetic rejection"}})
    elif mode.startswith("run-"):
        params = message["params"]
        if method == "turn/start":
            emit({"id": message["id"], "result": {"turn": {"id": "turn/native", "status": "inProgress"}}})
            if mode == "run-unknown":
                emit({"method": "future/success", "params": {
                    "threadId": params["threadId"], "turnId": "turn/native", "status": "completed",
                }})
            else:
                if mode == "run-prior-usage":
                    emit({"method": "thread/tokenUsage/updated", "params": {
                        "threadId": params["threadId"], "turnId": "previous-turn", "tokenUsage": {},
                    }})
                terminal = {"threadId": params["threadId"], "turn": {"id": "turn/native", "status": "completed"}}
                if mode == "run-missing-thread":
                    del terminal["threadId"]
                elif mode == "run-wrong-thread":
                    terminal["threadId"] = "another-thread"
                elif mode == "run-missing-turn":
                    terminal["turn"] = {"status": "completed"}
                elif mode == "run-wrong-turn":
                    terminal["turn"]["id"] = "another-turn"
                elif mode == "run-failed":
                    terminal["turn"] = {"id": "turn/native", "status": "failed", "error": {
                        "message": "synthetic model failure", "codexErrorInfo": "internalServerError",
                    }}
                emit({"method": "turn/completed", "params": terminal})
        elif method == "turn/interrupt":
            emit({"id": message["id"], "result": {}})
            emit({"method": "turn/completed", "params": {
                "threadId": params["threadId"], "turn": {"id": params["turnId"], "status": "interrupted"},
            }})
    else:
        emit({"method": "future/notice", "params": {"text": "raw-feedback", "image": {"url": "synthetic-image"}}})
        emit({"id": message["id"], "result": message["params"]})
'''


class NativeSessionBindingTests(unittest.TestCase):
    """核对原 TaskIdentity 与不透明原生标识，不增加影子会话或工具状态。"""

    def setUp(self) -> None:
        """准备原业务任务和故意不采用 UUID 的原生线程。"""
        self.task = TaskIdentity(TaskId(uuid4()), WorkspaceId(uuid4()))
        self.binding = NativeSessionBinding(self.task, "native/thread-A")

    def test_original_task_and_thread_are_preserved_for_resume(self) -> None:
        """恢复沿原线程核对，不能把另一线程关联到同一任务。"""
        self.assertIs(self.binding.task, self.task)
        self.binding.validate_thread("native/thread-A")
        with self.assertRaises(NativeProtocolError):
            self.binding.validate_thread("native/thread-B")
        with self.assertRaises(NativeProtocolError):
            NativeSessionBinding(self.task, "")

    def test_wrong_thread_and_turn_in_native_events_are_rejected(self) -> None:
        """直接或嵌套原生标识错配均拒绝，item 不转换成业务身份。"""
        good: NativeMessage = {"method": "item/completed", "params": {
            "threadId": "native/thread-A", "turnId": "turn/native", "item": {"id": "item/native"},
        }}
        self.binding.validate_event(good, turn_id="turn/native")
        wrong: tuple[NativeMessage, ...] = (
            {"method": "turn/completed", "params": {"threadId": "other", "turn": {"id": "turn/native"}}},
            {"method": "item/completed", "params": {"turnId": "other"}},
            {"method": "turn/completed", "params": {"turn": {"id": "other"}}},
        )
        for event in wrong:
            with self.subTest(event=event), self.assertRaises(NativeProtocolError):
                self.binding.validate_event(event, turn_id="turn/native")

    def test_unknown_event_is_not_rewritten_or_promoted_to_success(self) -> None:
        """未知通知只检查已有关联，不添加业务状态或删除原始字段。"""
        event: NativeMessage = {"method": "future/unknown", "params": {"newField": ["opaque"]}}
        before = json.dumps(event)
        self.binding.validate_event(event)
        self.assertEqual(json.dumps(event), before)


class NativeStdioTests(unittest.IsolatedAsyncioTestCase):
    """用真实独立进程验证串行协议，替身仍不能证明真实运行时行为。"""

    async def asyncSetUp(self) -> None:
        """创建本测试私有记录位置及待关闭客户端集合。"""
        self.temporary = tempfile.TemporaryDirectory(prefix="vet3d-native-protocol-")
        self.root = Path(self.temporary.name)
        self.record = self.root / "received.jsonl"
        self.clients: list[AppServerStdioClient] = []

    async def asyncTearDown(self) -> None:
        """回收本测试启动的客户端后移除临时机械记录。"""
        for client in self.clients:
            await client.aclose()
        self.temporary.cleanup()

    async def _start(self, mode: str, *, timeout: float = 1.0) -> AppServerStdioClient:
        """装配不继承凭证的机械替身，限制单行反馈。

        :param mode: 替身测试分支，不是产品架构配置。
        :param timeout: 一次完整请求的测试期限。
        :returns: 完成握手的客户端。
        """
        client = await AppServerStdioClient.start(
            (sys.executable, "-u", "-c", _SERVER, mode, str(self.record)),
            cwd=self.root, env={"PATH": os.defpath}, max_line_bytes=1024,
            read_timeout_seconds=timeout,
        )
        self.clients.append(client)
        return client

    def _messages(self) -> list[dict[str, object]]:
        """读取本测试实际到达替身的请求，不推导原生执行状态。

        :returns: 记录中的实际消息对象。
        """
        values: list[dict[str, object]] = []
        for line in self.record.read_text(encoding="utf-8").splitlines():
            value: dict[str, object] = json.loads(line)
            message = value["message"]
            if isinstance(message, dict):
                values.append(message)
        return values

    async def test_handshake_and_unknown_feedback_preserve_native_content(self) -> None:
        """握手按原协议完成，未知通知和图像字段不被业务摘要替换。"""
        client = await self._start("normal")
        result = await client.request("thread/resume", {"threadId": "native/thread-A"})
        self.assertEqual(result, {"threadId": "native/thread-A"})
        self.assertEqual(await client.next_event(), {
            "method": "future/notice",
            "params": {"text": "raw-feedback", "image": {"url": "synthetic-image"}},
        })
        self.assertEqual(client.initialization, {"testOnly": True})
        await client.aclose()
        self.assertEqual([value.get("method") for value in self._messages()], [
            "initialize", "initialized", "thread/resume",
        ])

    async def test_wrong_reply_and_disconnect_invalidate_without_resubmission(self) -> None:
        """错回执或断连后不重发原请求，也不在结果不明连接上继续提交。"""
        for mode in ("wrong-id", "disconnect"):
            with self.subTest(mode=mode):
                client = await self._start(mode)
                with self.assertRaises(NativeProtocolError):
                    await client.request("turn/start", {"threadId": "original"})
                with self.assertRaises(NativeProtocolError):
                    await client.request("turn/start", {"threadId": "original"})
                await client.aclose()
        self.assertEqual(sum(value.get("method") == "turn/start" for value in self._messages()), 2)

    async def test_cancelled_notification_wait_keeps_original_connection(self) -> None:
        """取消空等通知不等于取消原生任务，连接仍能发送显式协议请求。"""
        client = await self._start("normal")
        waiting = asyncio.create_task(client.next_event())
        await asyncio.sleep(0)
        waiting.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await waiting
        self.assertEqual(await client.request("turn/interrupt", {"threadId": "original"}), {
            "threadId": "original",
        })

    async def test_notifications_do_not_extend_request_deadline(self) -> None:
        """持续通知不能延长整体请求期限，超时后不会自动重交。"""
        client = await self._start("timeout", timeout=0.25)
        started = time.monotonic()
        with self.assertRaises(TimeoutError):
            await client.request("turn/start", {})
        self.assertLess(time.monotonic() - started, 1.0)
        with self.assertRaises(NativeProtocolError):
            await client.request("turn/start", {})
        await client.aclose()
        self.assertEqual(sum(value.get("method") == "turn/start" for value in self._messages()), 1)

    async def test_line_and_pending_notification_limits_fail_explicitly(self) -> None:
        """单行或通知队列超限明确失败，不截断成成功回执。"""
        for mode in ("long", "flood"):
            with self.subTest(mode=mode):
                client = await self._start(mode)
                with self.assertRaises(NativeProtocolError):
                    await client.request("turn/start", {})
                await client.aclose()

    async def test_server_interaction_receives_error_and_stops_experiment(self) -> None:
        """未实现的审批请求返回错误，不批准或让服务端无限等待。"""
        client = await self._start("approval")
        with self.assertRaisesRegex(NativeProtocolError, "未支持的服务端交互"):
            await client.request("turn/start", {})
        await client.aclose()
        replies = [value for value in self._messages() if value.get("id") == "native-request"]
        self.assertEqual(len(replies), 1)
        self.assertIn("error", replies[0])
        self.assertNotIn("result", replies[0])

    async def test_matched_remote_error_is_not_success_or_implicit_retry(self) -> None:
        """匹配请求的原生错误保留原内容，后续显式请求仍可使用连接。"""
        client = await self._start("remote-error")
        for _ in range(2):
            with self.assertRaises(NativeResponseError) as caught:
                await client.request("thread/resume", {"threadId": "missing"})
            self.assertEqual(caught.exception.error, {"code": -32000, "message": "synthetic rejection"})
        await client.aclose()
        self.assertEqual(sum(value.get("method") == "thread/resume" for value in self._messages()), 2)

    async def test_failed_handshake_reaps_its_connection_process(self) -> None:
        """启动握手失败也回收本客户端进程，不遗留伪成功客户端。"""
        with self.assertRaises(NativeProtocolError):
            await self._start("start-error")
        records = [json.loads(line) for line in self.record.read_text(encoding="utf-8").splitlines()]
        with self.assertRaises(ProcessLookupError):
            os.kill(records[0]["pid"], 0)

    async def test_runner_rejects_missing_or_wrong_terminal_associations(self) -> None:
        """终态缺失或错配原线程及轮次时拒绝，不用成功字段绕过关联。"""
        binding = NativeSessionBinding(TaskIdentity(TaskId(uuid4()), WorkspaceId(uuid4())), "native/thread-A")
        for mode in ("run-missing-thread", "run-wrong-thread", "run-missing-turn", "run-wrong-turn"):
            with self.subTest(mode=mode):
                client = await self._start(mode)
                with self.assertRaises(NativeProtocolError):
                    await run_native_turn(client, binding, "本次实验目标", timeout_seconds=1.0)
                await client.aclose()
        self.assertEqual(sum(value.get("method") == "turn/start" for value in self._messages()), 4)
        self.assertFalse(any(value.get("method") == "turn/interrupt" for value in self._messages()))

    async def test_runner_unknown_success_times_out_and_interrupts_original_turn_once(self) -> None:
        """未知成功通知不完成实验；超时只中断原轮次一次，不重新建模。"""
        client = await self._start("run-unknown")
        binding = NativeSessionBinding(TaskIdentity(TaskId(uuid4()), WorkspaceId(uuid4())), "native/thread-A")
        observation = await run_native_turn(client, binding, "唯一目标", timeout_seconds=0.05)
        self.assertTrue(observation.interruption_requested)
        self.assertEqual(observation.turn, {"id": "turn/native", "status": "interrupted"})
        self.assertEqual(observation.event_counts, {"future/success": 1, "turn/completed": 1})
        await client.aclose()
        starts = [value for value in self._messages() if value.get("method") == "turn/start"]
        interrupts = [value for value in self._messages() if value.get("method") == "turn/interrupt"]
        self.assertEqual(len(starts), 1)
        self.assertEqual(len(interrupts), 1)
        self.assertEqual(interrupts[0]["params"], {"threadId": binding.thread_id, "turnId": "turn/native"})

    async def test_runner_keeps_failed_terminal_and_original_error(self) -> None:
        """原生 failed 及错误证据原样交接，不转换成业务通过或自动修复。"""
        client = await self._start("run-failed")
        binding = NativeSessionBinding(TaskIdentity(TaskId(uuid4()), WorkspaceId(uuid4())), "native/thread-A")
        observation = await run_native_turn(client, binding, "唯一目标", timeout_seconds=1.0)
        self.assertEqual(observation.turn, {
            "id": "turn/native", "status": "failed",
            "error": {"message": "synthetic model failure", "codexErrorInfo": "internalServerError"},
        })
        self.assertFalse(observation.interruption_requested)
        await client.aclose()
        self.assertEqual([value.get("method") for value in self._messages()], [
            "initialize", "initialized", "turn/start",
        ])

    async def test_prior_turn_usage_after_resume_does_not_complete_current_turn(self) -> None:
        """恢复后的线程用量可引用此前轮次，不能误作当前执行终态或关联冲突。"""
        client = await self._start("run-prior-usage")
        binding = NativeSessionBinding(TaskIdentity(TaskId(uuid4()), WorkspaceId(uuid4())), "native/thread-A")
        observation = await run_native_turn(client, binding, "独立追加要求", timeout_seconds=1.0)
        self.assertEqual(observation.turn, {"id": "turn/native", "status": "completed"})
        self.assertEqual(observation.event_counts, {"thread/tokenUsage/updated": 1, "turn/completed": 1})


if __name__ == "__main__":
    unittest.main()
