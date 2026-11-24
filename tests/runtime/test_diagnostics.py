# 文件信息：L1-05 真实诊断文件与读取契约的高价值测试。
# 作用：核对身份过滤、字节预算、轮转、故障可见性及取消后的真实资源所有权。
# 边界：故障替身只检查机械协议；这些测试不证明执行隔离或业务恢复。
"""通过私有临时目录与有限故障注入验证运维诊断。"""

import asyncio
from dataclasses import replace
import io
import json
import logging
import os
from pathlib import Path
import tempfile
from threading import Event
import unittest
from unittest.mock import patch
from uuid import uuid4

from vet3d.adapters import LocalDiagnosticFiles
from vet3d.bootstrap import (
    DiagnosticBusyError, DiagnosticClosedError, configure_logging,
    is_diagnostics_active, open_diagnostics,
)
from vet3d.identity import TaskId, TaskIdentity, WorkspaceId
from vet3d.operations import DiagnosticLimits


class _ForbiddenRendering:
    """代表禁止被诊断格式化器展开的大对象。"""

    def __str__(self) -> str:
        """若生产者线程尝试对象转储，立即暴露测试失败。

        :raises AssertionError: 任意调用均不应发生。
        """
        raise AssertionError("不允许任意对象格式化")

    def __repr__(self) -> str:
        """阻止用 repr 绕过禁止对象转储的边界。

        :raises AssertionError: 任意调用均不应发生。
        """
        raise AssertionError("不允许任意对象表示")


class _BrokenOutput(io.StringIO):
    """模拟容器标准错误通道不可写，与文件存储故障分开验证。"""

    def write(self, text: str) -> int:
        """让镜像输出失败，不影响调用方已完成的业务动作。

        :param text: 后台线程准备输出的有界文本。
        :raises OSError: 模拟输出通道关闭。
        """
        raise OSError("镜像输出已关闭")


async def _wait_for(event: Event) -> None:
    """有限等待故障夹具进入真实线程，避免阻塞测试事件循环。

    :param event: 由实际线程设置的门闩。
    :raises TimeoutError: 测试夹具未在预算内到达目标边界。
    """
    async with asyncio.timeout(3):
        while not event.is_set():
            await asyncio.sleep(0.001)


class DiagnosticTests(unittest.IsolatedAsyncioTestCase):
    """验证有界真实文件诊断与独立业务事实的交接。"""

    def setUp(self) -> None:
        """建立当前用户拥有的临时父目录及互不相同的业务身份。"""
        self.temporary = tempfile.TemporaryDirectory(prefix="vet3d-diagnostics-")
        self.root = Path(self.temporary.name) / "diagnostics"
        self.workspace = WorkspaceId(uuid4())
        self.other_workspace = WorkspaceId(uuid4())
        self.task = TaskIdentity(TaskId(uuid4()), self.workspace)
        self.logger = logging.getLogger("vet3d")
        self.extra = {"workspace_id": str(self.workspace.value), "task_id": str(self.task.id.value)}

    def tearDown(self) -> None:
        """只清理本用例临时文件，不触及其他工作区或产品资产。"""
        self.temporary.cleanup()

    async def test_filters_use_both_authoritative_ids(self) -> None:
        """任务读取同时核对工作区；消息文本中的身份不会成为查询关联。"""
        runtime = await open_diagnostics(self.root, stderr=None)
        async with runtime:
            self.logger.info("same task", extra=self.extra)
            self.logger.info("other workspace", extra={
                "workspace_id": str(self.other_workspace.value), "task_id": str(self.task.id.value),
            })
            self.logger.info("workspace_id=%s task_id=%s", self.workspace.value, self.task.id.value)
            task_result = await runtime.read_task(self.task)
            self.assertEqual([record.message for record in task_result.records], ["same task"])
            self.assertEqual(len((await runtime.read_workspace(self.other_workspace)).records), 1)
            self.assertEqual(task_result.status.dropped_records, 0)
            self.assertIsNone(task_result.status.write_error)

    async def test_recent_query_has_explicit_truncation(self) -> None:
        """有限查询只返回最近匹配记录并明确说明更早匹配被截断。"""
        runtime = await open_diagnostics(self.root, stderr=None)
        async with runtime:
            for index in range(5):
                self.logger.info("event %s", index, extra=self.extra)
            result = await runtime.read_task(self.task, limit=2)
            self.assertEqual([record.message for record in result.records], ["event 3", "event 4"])
            self.assertTrue(result.truncated)
            with self.assertRaises(ValueError):
                await runtime.read_task(self.task, limit=True)
            with self.assertRaises(ValueError):
                await runtime.read_task(self.task, limit=1001)

    async def test_valid_json_and_byte_rotation_budgets(self) -> None:
        """多字节消息始终保留合法 JSON，每个文件与归档总量有固定上限。"""
        limits = DiagnosticLimits(max_record_bytes=1024, max_file_bytes=2048, archive_count=2)
        runtime = await open_diagnostics(self.root, limits=limits, stderr=None)
        async with runtime:
            for index in range(20):
                self.logger.info("动物 " + "甲🐈" * 4000 + "%s", index, extra=self.extra)
            await runtime.read_workspace(self.workspace)
        files = tuple(self.root.glob("events.jsonl*"))
        self.assertEqual(len(files), 3)
        self.assertLessEqual(sum(path.stat().st_size for path in files), 3 * limits.max_file_bytes)
        for path in files:
            self.assertLessEqual(path.stat().st_size, limits.max_file_bytes)
            for line in path.read_bytes().splitlines(keepends=True):
                self.assertLessEqual(len(line), limits.max_record_bytes)
                self.assertIsInstance(json.loads(line), dict)

    async def test_restart_retains_old_runtime_and_reports_partial_tail(self) -> None:
        """重新装配读取已写记录，旧损坏尾行不会与新行拼接或伪装完整。"""
        first = await open_diagnostics(self.root, stderr=None)
        self.logger.info("before restart", extra=self.extra)
        await first.aclose()
        with (self.root / "events.jsonl").open("ab") as stream:
            stream.write(b'{"partial":')
        second = await open_diagnostics(self.root, stderr=None)
        async with second:
            self.logger.info("after restart", extra=self.extra)
            result = await second.read_task(self.task)
            self.assertEqual([record.message for record in result.records], ["before restart", "after restart"])
            self.assertEqual(result.malformed_records, 1)
            self.assertEqual([record.runtime_id for record in result.records], [first.runtime_id, second.runtime_id])
            self.assertNotEqual(first.runtime_id, second.runtime_id)

    async def test_invalid_scope_is_not_silently_made_unscoped(self) -> None:
        """格式错误的结构化身份产生明确诊断损失，不被文本猜测修复。"""
        runtime = await open_diagnostics(self.root, stderr=None)
        async with runtime:
            self.logger.info("bad identity", extra={"workspace_id": "not-uuid"})
            self.logger.info("missing workspace", extra={"task_id": str(self.task.id.value)})
            result = await runtime.read_task(self.task)
            self.assertEqual(result.records, ())
            self.assertEqual(result.status.dropped_records, 2)
            self.assertIn("diagnostic_encoding_failed", result.status.write_error or "")

    async def test_arbitrary_objects_and_widths_do_not_execute_formatting(self) -> None:
        """日志对象不会执行自定义字符串方法，超大占位宽度不分配对应内存。"""
        runtime = await open_diagnostics(self.root, stderr=None)
        async with runtime:
            self.logger.info("object=%s width=%1000000000s", _ForbiddenRendering(), "x", extra=self.extra)
            result = await runtime.read_task(self.task)
            self.assertIn("[_ForbiddenRendering]", result.records[0].message)
            self.assertLess(len(result.records[0].message), 1024)

    async def test_exception_keeps_bounded_context_and_stack(self) -> None:
        """异常保留类型、原因和调用帧，而不序列化局部变量或全部对象。"""
        runtime = await open_diagnostics(self.root, stderr=None)
        async with runtime:
            try:
                raise RuntimeError("实际失败原因")
            except RuntimeError:
                self.logger.exception("processing failed", extra=self.extra)
            result = await runtime.read_task(self.task)
            self.assertIn("RuntimeError: 实际失败原因", result.records[0].message)
            self.assertIn("test_exception_keeps_bounded_context_and_stack", result.records[0].message)

    async def test_broken_file_does_not_raise_into_business_logging(self) -> None:
        """写盘失败不会中断业务线程；读取和关闭都能看到诊断故障。"""
        runtime = await open_diagnostics(self.root, stderr=None)
        with patch.object(LocalDiagnosticFiles, "append", side_effect=OSError("disk full")):
            self.logger.info("operation already committed", extra=self.extra)
            result = await runtime.read_task(self.task)
            self.assertEqual(result.records, ())
            self.assertEqual(result.status.dropped_records, 1)
            self.assertIn("diagnostic_write_failed", result.status.write_error or "")
        status = await runtime.aclose()
        self.assertEqual(status, result.status)

    async def test_broken_stderr_does_not_erase_saved_record(self) -> None:
        """镜像输出失败与文件保存事实分离，不丢弃已经保存的诊断。"""
        runtime = await open_diagnostics(self.root, stderr=_BrokenOutput())
        async with runtime:
            self.logger.info("saved", extra=self.extra)
            result = await runtime.read_task(self.task)
            self.assertEqual(len(result.records), 1)
            self.assertEqual(result.status.dropped_records, 0)
            self.assertIn("diagnostic_stderr_failed", result.status.write_error or "")

    async def test_queue_overflow_is_bounded_visible_and_nonblocking(self) -> None:
        """实际写入阻塞时队列不膨胀，日志返回且查询准入明确失败。"""
        entered, release = Event(), Event()
        original = LocalDiagnosticFiles.append

        def blocked(files: LocalDiagnosticFiles, data: bytes) -> None:
            """暂停真实写入，用于验证生产者和事件循环仍能推进。

            :param files: 本次真实文件适配器。
            :param data: 已有界的待写记录。
            """
            entered.set()
            if not release.wait(5):
                raise TimeoutError("测试未释放实际写入")
            original(files, data)

        runtime = await open_diagnostics(self.root, limits=DiagnosticLimits(queue_capacity=1), stderr=None)
        try:
            with patch.object(LocalDiagnosticFiles, "append", blocked):
                self.logger.info("writing", extra=self.extra)
                await _wait_for(entered)
                self.logger.info("queued", extra=self.extra)
                self.logger.info("dropped", extra=self.extra)
                self.assertEqual(runtime.status().dropped_records, 1)
                with self.assertRaises(DiagnosticBusyError):
                    await runtime.read_task(self.task)
                release.set()
                await runtime.aclose()
        finally:
            release.set()
            await runtime.aclose()
        reopened = await open_diagnostics(self.root, stderr=None)
        async with reopened:
            self.assertEqual([entry.message for entry in (await reopened.read_task(self.task)).records], ["writing", "queued"])

    async def test_cancelled_close_retains_lock_until_actual_io_finishes(self) -> None:
        """取消关闭等待不会放弃仍在写入的线程或提前转移根的所有权。"""
        entered, release = Event(), Event()
        original = LocalDiagnosticFiles.append

        def blocked(files: LocalDiagnosticFiles, data: bytes) -> None:
            """保留真实写入，使取消边界可以观察。

            :param files: 原目录所有者。
            :param data: 原待写记录。
            """
            entered.set()
            if not release.wait(5):
                raise TimeoutError("测试未释放实际写入")
            original(files, data)

        runtime = await open_diagnostics(self.root, stderr=None)
        try:
            with patch.object(LocalDiagnosticFiles, "append", blocked):
                self.logger.info("pending", extra=self.extra)
                await _wait_for(entered)
                closing = asyncio.create_task(runtime.aclose())
                await asyncio.sleep(0)
                closing.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await closing
                self.assertTrue(is_diagnostics_active())
                with self.assertRaises(RuntimeError):
                    configure_logging()
                with self.assertRaises(BlockingIOError):
                    LocalDiagnosticFiles(self.root, DiagnosticLimits())
                with self.assertRaises(DiagnosticClosedError):
                    await runtime.read_task(self.task)
                release.set()
                await runtime.aclose()
                self.assertFalse(is_diagnostics_active())
        finally:
            release.set()
            await runtime.aclose()

    async def test_active_handler_ownership_and_previous_configuration_restore(self) -> None:
        """活动期间拒绝重复日志初始化，真正关闭后恢复原处理器。"""
        previous = list(self.logger.handlers)
        runtime = await open_diagnostics(self.root, stderr=None)
        async with runtime:
            with self.assertRaises(RuntimeError):
                configure_logging()
            with self.assertRaises(RuntimeError):
                await open_diagnostics(Path(self.temporary.name) / "other", stderr=None)
        self.assertEqual(self.logger.handlers, previous)

    async def test_cancelled_read_does_not_break_following_requests(self) -> None:
        """取消查询等待后，实际有界读取仍可结束且不破坏后续消费者。"""
        runtime = await open_diagnostics(self.root, stderr=None)
        async with runtime:
            self.logger.info("retained", extra=self.extra)
            reading = asyncio.create_task(runtime.read_task(self.task))
            await asyncio.sleep(0)
            reading.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await reading
            self.assertEqual(len((await runtime.read_task(self.task)).records), 1)

    async def test_missing_active_file_is_explicit_read_failure(self) -> None:
        """活动日志丢失不能被解释为工作区没有事件。"""
        runtime = await open_diagnostics(self.root, stderr=None)
        async with runtime:
            (self.root / "events.jsonl").unlink()
            with self.assertRaises(FileNotFoundError):
                await runtime.read_task(self.task)

    async def test_replaced_active_file_is_not_an_empty_success(self) -> None:
        """原活动文件被同权限空文件替换时仍拒绝查询，不能仅按名字接收。"""
        runtime = await open_diagnostics(self.root, stderr=None)
        async with runtime:
            active = self.root / "events.jsonl"
            active.rename(self.root / "removed")
            descriptor = os.open(active, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(descriptor)
            with self.assertRaises(OSError):
                await runtime.read_task(self.task)

    async def test_close_failure_is_observable_after_lock_release(self) -> None:
        """真实句柄已释放后的关闭故障仍交付给 Operations，不伪装完整输出。"""
        original = LocalDiagnosticFiles.close

        def failed(files: LocalDiagnosticFiles) -> None:
            """完成真实释放后注入同步失败，检查关闭观察和所有权移交。

            :param files: 原文件所有者。
            :raises OSError: 模拟最后同步阶段的已观察故障。
            """
            original(files)
            raise OSError("sync failure")

        runtime = await open_diagnostics(self.root, stderr=None)
        with patch.object(LocalDiagnosticFiles, "close", failed):
            status = await runtime.aclose()
        self.assertIn("diagnostic_close_failed", status.write_error or "")
        reopened = await open_diagnostics(self.root, stderr=None)
        await reopened.aclose()

    async def test_root_symlink_and_loose_permissions_are_rejected(self) -> None:
        """目录隔离依赖明确的受管路径，不自动修复权限或跟随链接。"""
        self.root.mkdir(mode=0o755)
        with self.assertRaises(PermissionError):
            await open_diagnostics(self.root, stderr=None)
        self.root.rmdir()
        self.root.symlink_to(Path(self.temporary.name), target_is_directory=True)
        with self.assertRaises(OSError):
            await open_diagnostics(self.root, stderr=None)

    async def test_unknown_content_and_changed_budget_are_not_cleaned(self) -> None:
        """不明文件和预算缩小引起的冲突明确拒绝，不删除原诊断。"""
        runtime = await open_diagnostics(self.root, stderr=None)
        self.logger.info("长消息" * 1000, extra=self.extra)
        await runtime.aclose()
        original = (self.root / "events.jsonl").read_bytes()
        with self.assertRaises(ValueError):
            await open_diagnostics(self.root, limits=DiagnosticLimits(max_record_bytes=1024, max_file_bytes=1024), stderr=None)
        self.assertEqual((self.root / "events.jsonl").read_bytes(), original)
        (self.root / "unknown").write_text("keep", encoding="utf-8")
        with self.assertRaises(ValueError):
            await open_diagnostics(self.root, stderr=None)
        self.assertEqual((self.root / "unknown").read_text(encoding="utf-8"), "keep")

    async def test_existing_control_and_log_hardlinks_are_rejected(self) -> None:
        """控制锁及日志不能通过额外硬链接暴露到另一个名字。"""
        runtime = await open_diagnostics(self.root, stderr=None)
        await runtime.aclose()
        os.link(self.root / "writer.lock", Path(self.temporary.name) / "linked-lock")
        with self.assertRaises(PermissionError):
            await open_diagnostics(self.root, stderr=None)

    def test_limits_reject_boolean_and_inconsistent_sizes(self) -> None:
        """唯一预算拒绝布尔整数和无法容纳单条记录的文件大小。"""
        with self.assertRaises(TypeError):
            replace(DiagnosticLimits(), queue_capacity=True)
        with self.assertRaises(ValueError):
            DiagnosticLimits(max_record_bytes=1024, max_file_bytes=1023)
