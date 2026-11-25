# 文件信息：L2-02 阶段 B 的原生连接并发与停止边界测试。
# 作用：独立 stdio 替身核对通知等待、并发回执、取消和有界接收的对外行为。
# 边界：不调用模型或工具，不证明真实隔离、图像输入或建模质量。
"""验证单读取者的机械协议，避免进度消费阻塞原轮次取消。"""

import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from vet3d.adapters import AppServerStdioClient, NativeProtocolError


_SERVER = '''# 文件信息：仅服务机械协议测试的独立 stdio 替身。
# 边界：不执行工具，不提供业务状态或真实运行时证据。
import json
import sys
import time
from pathlib import Path

mode, record = sys.argv[1:]
first: dict[str, object] | None = None


def emit(message: dict[str, object]) -> None:
    """交付原始 JSON 消息，供消费者核对请求关联。

    :param message: 本机械场景的回执或通知。
    """
    print(json.dumps(message), flush=True)


for line in sys.stdin:
    message = json.loads(line)
    with Path(record).open("a", encoding="utf-8") as output:
        output.write(json.dumps(message) + "\\n")
    method = message.get("method")
    if method == "initialize":
        emit({"id": message["id"], "result": {"testOnly": True}})
    elif method == "initialized":
        continue
    elif mode == "out-of-order":
        if first is None:
            first = message
            emit({"method": "test/requestSeen", "params": {"method": method}})
        else:
            emit({"id": message["id"], "result": {"accepted": method}})
            emit({"method": "item/agentMessage/delta", "params": {
                "threadId": "native-thread", "turnId": "native-turn",
                "delta": "原始反馈", "extra": {"image": "native-image-reference"},
            }})
            emit({"id": first["id"], "result": {"accepted": first["method"]}})
            first = None
    elif mode == "pending":
        emit({"method": "test/requestSeen", "params": {"method": method}})
    elif mode == "flood":
        for index in range(5):
            emit({"method": "test/progress", "params": {"index": index}})
    elif mode in {"terminal-eof", "terminal-invalid"}:
        emit({"id": message["id"], "result": {"accepted": True}})
        emit({"method": "turn/completed", "params": {
            "threadId": "native-thread", "turn": {"id": "native-turn", "status": "completed"},
        }})
        if mode == "terminal-invalid":
            print("invalid-json", flush=True)
        break
    else:
        if "id" in message:
            emit({"id": message["id"], "result": message["params"]})
        emit({"method": "turn/completed", "params": {
            "threadId": "native-thread", "turn": {"id": "native-turn", "status": "interrupted"},
        }})
if mode == "slow-close":
    time.sleep(5)
'''


class CodexConcurrentProtocolTests(unittest.IsolatedAsyncioTestCase):
    """以真实管道验证连接协调；替身不承担模型或隔离验收。"""

    async def asyncSetUp(self) -> None:
        """创建私有机械记录目录和客户端回收列表。"""
        self.temporary = tempfile.TemporaryDirectory(prefix="vet3d-codex-protocol-")
        self.root = Path(self.temporary.name)
        self.record = self.root / "requests.jsonl"
        self.clients: list[AppServerStdioClient] = []

    async def asyncTearDown(self) -> None:
        """关闭本测试的连接进程后清理机械记录。"""
        for client in self.clients:
            await client.aclose()
        self.temporary.cleanup()

    async def _start(self, mode: str, *, events: int = 128) -> AppServerStdioClient:
        """装配不继承凭证的独立协议替身。

        :param mode: 机械反馈场景，不是产品运行模式。
        :param events: 本测试的通知缓冲数量上限。
        :returns: 完成握手的客户端。
        """
        client = await AppServerStdioClient.start(
            (sys.executable, "-u", "-c", _SERVER, mode, str(self.record)),
            cwd=self.root, env={"PATH": os.defpath}, read_timeout_seconds=3,
            max_line_bytes=2048, max_pending_events=events,
        )
        self.clients.append(client)
        return client

    def _methods(self) -> list[str]:
        """读取替身实际收到的方法，不从客户端意图推导已提交。

        :returns: 实际接收的原生方法顺序。
        """
        methods: list[str] = []
        for line in self.record.read_text(encoding="utf-8").splitlines():
            value: object = json.loads(line)
            assert isinstance(value, dict)
            method = value.get("method")
            if isinstance(method, str):
                methods.append(method)
        return methods

    async def test_notification_wait_does_not_block_interrupt_request(self) -> None:
        """等待进度时仍可发送取消并按原轮次取得终态。"""
        client = await self._start("normal")
        event = asyncio.create_task(client.next_event())
        await asyncio.sleep(0)
        reply = await asyncio.wait_for(client.request("turn/interrupt", {
            "threadId": "native-thread", "turnId": "native-turn",
        }), 1)
        self.assertEqual(reply, {"threadId": "native-thread", "turnId": "native-turn"})
        self.assertEqual((await event)["method"], "turn/completed")
        self.assertEqual(self._methods().count("turn/interrupt"), 1)

    async def test_out_of_order_responses_keep_request_and_native_feedback(self) -> None:
        """并发查询与取消各取自身回执，原生反馈字段保持原内容。"""
        client = await self._start("out-of-order")
        first = asyncio.create_task(client.request("thread/read", {"threadId": "native-thread"}))
        seen = await client.next_event()
        self.assertEqual(seen["params"], {"method": "thread/read"})
        second = await client.request("turn/interrupt", {"turnId": "native-turn"})
        self.assertEqual(second, {"accepted": "turn/interrupt"})
        self.assertEqual(await first, {"accepted": "thread/read"})
        self.assertEqual(await client.next_event(), {
            "method": "item/agentMessage/delta", "params": {
                "threadId": "native-thread", "turnId": "native-turn", "delta": "原始反馈",
                "extra": {"image": "native-image-reference"},
            },
        })

    async def test_cancelled_wait_does_not_lose_later_terminal(self) -> None:
        """取消空等通知仅结束本地等待，后到终态仍可读取。"""
        client = await self._start("normal")
        waiting = asyncio.create_task(client.next_event())
        await asyncio.sleep(0)
        waiting.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await waiting
        await client.request("turn/interrupt", {"turnId": "native-turn"})
        self.assertEqual((await client.next_event())["method"], "turn/completed")

    async def test_cancelled_rpc_invalidates_other_waiters_without_resubmit(self) -> None:
        """请求等待取消后受理不明，同连接其他请求及新提交明确失败。"""
        client = await self._start("pending")
        first = asyncio.create_task(client.request("turn/start", {"threadId": "native-thread"}))
        await client.next_event()
        second = asyncio.create_task(client.request("thread/read", {"threadId": "native-thread"}))
        await client.next_event()
        first.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await first
        with self.assertRaises(NativeProtocolError):
            await second
        with self.assertRaises(NativeProtocolError):
            await client.request("turn/start", {"threadId": "native-thread"})
        self.assertEqual(self._methods().count("turn/start"), 1)

    async def test_notification_overflow_invalidates_without_silent_drop(self) -> None:
        """缓冲超限仍交付此前完整通知，随后明确观察不完整且禁止新请求。"""
        client = await self._start("flood", events=4)
        await client.notify("test/flood", {})
        await asyncio.sleep(0.1)
        for index in range(4):
            self.assertEqual(await client.next_event(), {
                "method": "test/progress", "params": {"index": index},
            })
        with self.assertRaisesRegex(NativeProtocolError, "观察已不完整"):
            await client.next_event()
        with self.assertRaises(NativeProtocolError):
            await client.request("thread/read", {})

    async def test_received_terminal_survives_eof_or_invalid_following_message(self) -> None:
        """完整终态不被随后连接故障抹去，交付该事实也不会恢复提交资格。"""
        for mode in ("terminal-eof", "terminal-invalid"):
            with self.subTest(mode=mode):
                client = await self._start(mode)
                self.assertEqual(await client.request("turn/start", {}), {"accepted": True})
                await asyncio.sleep(0.1)
                with self.assertRaises(NativeProtocolError):
                    await client.request("thread/read", {})
                self.assertEqual(await client.next_event(), {
                    "method": "turn/completed", "params": {
                        "threadId": "native-thread",
                        "turn": {"id": "native-turn", "status": "completed"},
                    },
                })
                with self.assertRaises(NativeProtocolError):
                    await client.next_event()
                with self.assertRaises(NativeProtocolError):
                    await client.request("turn/start", {})

    async def test_close_wakes_pending_notification_consumer(self) -> None:
        """关闭唤醒空等消费者，而不是留下长期挂起读取。"""
        client = await self._start("normal")
        waiting = asyncio.create_task(client.next_event())
        await asyncio.sleep(0)
        await client.aclose()
        with self.assertRaises(NativeProtocolError):
            await waiting
        with self.assertRaises(ProcessLookupError):
            os.kill(client.pid, 0)

    async def test_cancelled_close_wait_does_not_cancel_actual_cleanup(self) -> None:
        """关闭调用方取消等待后，自身连接进程仍由唯一关闭任务回收。"""
        client = await self._start("slow-close")
        closing = asyncio.create_task(client.aclose())
        await asyncio.sleep(0.05)
        closing.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await closing
        await client.aclose()
        with self.assertRaises(ProcessLookupError):
            os.kill(client.pid, 0)


if __name__ == "__main__":
    unittest.main()
