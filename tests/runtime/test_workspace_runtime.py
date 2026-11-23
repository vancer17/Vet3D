# 文件信息：L1-01 真实工作区装配的异步生命周期验证。
# 作用：验证无队列准入、等待取消与实际 I/O 分离、根锁及关闭资源的持续归属。
# 证据边界：真实 SQLite/本地目录配合受控阻塞点，不代表执行沙箱或断电恢复。
"""通过公开 Bootstrap 入口验证服务端异步消费者的存储边界。"""

import asyncio
from collections.abc import Callable
import logging
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from uuid import uuid4

from vet3d.adapters import LocalWorkspaceDirectories, ManagedWorkspaceRoot
from vet3d.bootstrap import (
    WorkspaceBusyError, WorkspaceClosedError, WorkspaceRuntime, WorkspaceTimeoutError,
    initialize_workspaces, open_workspaces,
)
from vet3d.identity import WorkspaceId
from vet3d.workspaces import WorkspaceConflict, WorkspaceCreationError, WorkspaceRecord


async def _wait_event(event: threading.Event) -> None:
    """在事件循环中有限等待真实工作线程经过指定边界。

    :param event: 由工作线程设置的测试同步点。
    """
    async with asyncio.timeout(5):
        while not event.is_set():
            await asyncio.sleep(0.001)


def _blocked_prepare(
    entered: threading.Event, release: threading.Event, *, fail: bool = False,
) -> Callable[[LocalWorkspaceDirectories, WorkspaceId], None]:
    """仅在真实目录准备前注入可控暂停，不替换注册库或目录副作用。

    :param entered: 工作线程到达暂停点的通知。
    :param release: 测试允许线程继续的通知。
    :param fail: 放行后是否注入 I/O 故障。
    :returns: 保持真实目录端口签名的测试函数。
    """
    original = LocalWorkspaceDirectories.prepare

    def prepare(directories: LocalWorkspaceDirectories, workspace_id: WorkspaceId) -> None:
        """等待测试放行后执行真实准备或报告指定故障。

        :param directories: 当前真实目录适配器。
        :param workspace_id: 原创建身份。
        """
        entered.set()
        if not release.wait(5):
            raise TimeoutError("测试未释放目录操作")
        if fail:
            raise OSError("受控晚期目录失败")
        original(directories, workspace_id)

    return prepare


async def _read_after_io(runtime: WorkspaceRuntime, workspace_id: WorkspaceId) -> WorkspaceRecord | None:
    """等到原实际工作终结，再通过公开接口对账，不在产品里引入自动重试。

    :param runtime: 持有真实工作线程的宿主。
    :param workspace_id: 原创建身份。
    :returns: 原持久记录。
    """
    async with asyncio.timeout(5):
        while True:
            try:
                return await runtime.read(workspace_id)
            except WorkspaceBusyError:
                await asyncio.sleep(0.001)


class WorkspaceRuntimeTests(unittest.IsolatedAsyncioTestCase):
    """以真实装配验证等待者生命周期不能替代存储生命周期。"""

    async def asyncSetUp(self) -> None:
        """创建本例私有根，并保证关闭发生在临时目录清理之前。"""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self._path = Path(temporary.name) / "managed"
        self._runtime = await initialize_workspaces(self._path)
        self.addAsyncCleanup(self._runtime.aclose)
        self._id = WorkspaceId(uuid4())

    async def test_public_create_query_reopen_and_conflict(self) -> None:
        """公开宿主读回真实提交，重开保留时间且同身份改参不改事实。"""
        self.assertIsNone(await self._runtime.read(self._id))
        record = await self._runtime.create(workspace_id=self._id, display_name="  动物  ")
        self.assertIsNotNone(record.registered_at)
        self.assertEqual(await self._runtime.create(workspace_id=self._id, display_name="  动物  "), record)
        with self.assertLogs("vet3d", level="WARNING"), self.assertRaises(WorkspaceConflict):
            await self._runtime.create(workspace_id=self._id, display_name="动物")
        await self._runtime.aclose()
        async with await open_workspaces(self._path) as reopened:
            self.assertEqual(await reopened.read(self._id), record)
        with self.assertRaises(WorkspaceClosedError):
            await self._runtime.read(self._id)

    async def test_busy_has_no_queue_and_event_loop_remains_available(self) -> None:
        """实际存储阻塞时事件循环可推进，同实例新调用和第二根写入者均拒绝。"""
        entered, release = threading.Event(), threading.Event()
        with patch.object(LocalWorkspaceDirectories, "prepare", _blocked_prepare(entered, release)):
            operation = asyncio.create_task(self._runtime.create(workspace_id=self._id, display_name="动物"))
            try:
                await _wait_event(entered)
                with self.assertRaises(WorkspaceBusyError):
                    await self._runtime.read(self._id)
                other_id = WorkspaceId(uuid4())
                with self.assertRaises(WorkspaceBusyError):
                    await self._runtime.create(workspace_id=other_id, display_name="其他")
                with self.assertLogs("vet3d", level="ERROR"), self.assertRaises(BlockingIOError):
                    await open_workspaces(self._path)
            finally:
                release.set()
            self.assertIsNotNone((await operation).registered_at)
        self.assertIsNone(await self._runtime.read(other_id))

    async def test_cancelled_wait_keeps_actual_operation_and_root_owned(self) -> None:
        """取消调用方不会放开实际写入准入，完成后沿原身份读回一次提交。"""
        entered, release = threading.Event(), threading.Event()
        with patch.object(LocalWorkspaceDirectories, "prepare", _blocked_prepare(entered, release)):
            operation = asyncio.create_task(self._runtime.create(workspace_id=self._id, display_name="动物"))
            try:
                await _wait_event(entered)
                operation.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await operation
                with self.assertRaises(WorkspaceBusyError):
                    await self._runtime.read(self._id)
                with self.assertLogs("vet3d", level="ERROR"), self.assertRaises(BlockingIOError):
                    await open_workspaces(self._path)
            finally:
                release.set()
            record = await _read_after_io(self._runtime, self._id)
        assert record is not None
        self.assertIsNotNone(record.registered_at)
        self.assertEqual(await self._runtime.create(workspace_id=self._id, display_name="动物"), record)

    async def test_timeout_late_failure_is_visible_and_original_intent_can_resume(self) -> None:
        """等待超时后的真实故障仍有一次堆栈诊断，并保留原意图供显式恢复。"""
        entered, release = threading.Event(), threading.Event()
        loop = asyncio.get_running_loop()
        unexpected: list[dict[str, object]] = []

        def capture_error(event_loop: asyncio.AbstractEventLoop, context: dict[str, object]) -> None:
            """记录不应出现的重复晚期异常，而不隐藏被断言的事件。

            :param event_loop: 当前测试事件循环。
            :param context: asyncio 额外诊断上下文。
            """
            unexpected.append(context)

        original_handler = loop.get_exception_handler()
        loop.set_exception_handler(capture_error)
        self.addCleanup(loop.set_exception_handler, original_handler)
        with self.assertLogs("vet3d", level="INFO") as captured:
            with patch.object(LocalWorkspaceDirectories, "prepare", _blocked_prepare(entered, release, fail=True)):
                try:
                    operation = asyncio.create_task(self._runtime.create(
                        workspace_id=self._id, display_name="动物", timeout_seconds=0.05,
                    ))
                    await _wait_event(entered)
                    with self.assertRaises(WorkspaceTimeoutError):
                        await operation
                    with self.assertRaises(WorkspaceBusyError):
                        await self._runtime.read(self._id)
                finally:
                    release.set()
                pending = await _read_after_io(self._runtime, self._id)
        assert pending is not None
        self.assertIsNone(pending.registered_at)
        failures = [record for record in captured.records if record.levelname == "ERROR"]
        self.assertEqual(len(failures), 1)
        self.assertIsNotNone(failures[0].exc_info)
        self.assertIn(str(self._id.value), failures[0].getMessage())
        self.assertEqual(unexpected, [])
        self.assertIsNotNone((await self._runtime.create(workspace_id=self._id, display_name="动物")).registered_at)

    async def test_close_wait_cancellation_does_not_release_root_early(self) -> None:
        """关闭等待被取消后仍由内部任务排空写入，实际终结前不允许重新打开。"""
        entered, release = threading.Event(), threading.Event()
        with patch.object(LocalWorkspaceDirectories, "prepare", _blocked_prepare(entered, release)):
            operation = asyncio.create_task(self._runtime.create(workspace_id=self._id, display_name="动物"))
            try:
                await _wait_event(entered)
                closing = asyncio.create_task(self._runtime.aclose())
                await asyncio.sleep(0)
                closing.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await closing
                with self.assertRaises(WorkspaceClosedError):
                    await self._runtime.read(self._id)
                with self.assertLogs("vet3d", level="ERROR"), self.assertRaises(BlockingIOError):
                    await open_workspaces(self._path)
            finally:
                release.set()
            record = await operation
            await self._runtime.aclose()
        async with await open_workspaces(self._path) as reopened:
            self.assertEqual(await reopened.read(self._id), record)

    async def test_pre_submission_cancellation_and_bad_deadlines_do_not_write(self) -> None:
        """提交前取消以及非法等待期限不建立创建意图。"""
        operation = asyncio.create_task(self._runtime.create(workspace_id=self._id, display_name="动物"))
        operation.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await operation
        for timeout in (0.0, -1.0, float("inf"), float("nan"), True):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                await self._runtime.create(workspace_id=self._id, display_name="动物", timeout_seconds=timeout)
        self.assertIsNone(await self._runtime.read(self._id))

    async def test_metadata_read_does_not_claim_directory_access(self) -> None:
        """已登记目录丢失后元数据仍可读，重复创建明确报错且不补建。"""
        record = await self._runtime.create(workspace_id=self._id, display_name="动物")
        directory = self._path / "workspaces" / str(self._id.value)
        directory.rmdir()
        self.assertEqual(await self._runtime.read(self._id), record)
        with self.assertLogs("vet3d", level="ERROR"), self.assertRaises(WorkspaceCreationError):
            await self._runtime.create(workspace_id=self._id, display_name="动物")
        self.assertFalse(directory.exists())

    async def test_independent_root_can_progress_while_first_root_is_busy(self) -> None:
        """根级注册约束不形成跨根的全局串行锁。"""
        async with await initialize_workspaces(self._path.parent / "second") as other:
            entered, release = threading.Event(), threading.Event()
            with patch.object(LocalWorkspaceDirectories, "prepare", _blocked_prepare(entered, release)):
                operation = asyncio.create_task(self._runtime.create(workspace_id=self._id, display_name="动物"))
                try:
                    await _wait_event(entered)
                    self.assertIsNone(await other.read(self._id))
                finally:
                    release.set()
                await operation

    async def test_cancelled_initialization_drains_and_releases_acquired_root(self) -> None:
        """初始化已取得锁后取消，装配入口排空后释放资源而不删除已建存储。"""
        path = self._path.parent / "startup"
        entered, release = threading.Event(), threading.Event()
        original = ManagedWorkspaceRoot.initialize

        def initialize(root: Path) -> ManagedWorkspaceRoot:
            """在实际根建立后暂停，模拟初始化期间的调用方取消。

            :param root: 独立临时根。
            :returns: 持有真实根锁的对象。
            """
            managed = original(root)
            entered.set()
            if not release.wait(5):
                managed.close()
                raise TimeoutError("测试未释放初始化")
            return managed

        with patch.object(ManagedWorkspaceRoot, "initialize", initialize):
            operation = asyncio.create_task(initialize_workspaces(path))
            try:
                await _wait_event(entered)
                operation.cancel()
                await asyncio.sleep(0)
                self.assertFalse(operation.done())
            finally:
                release.set()
            with self.assertRaises(asyncio.CancelledError):
                await operation
        async with await open_workspaces(path) as reopened:
            self.assertIsNone(await reopened.read(self._id))

    async def test_base_exception_from_actual_work_still_allows_root_cleanup(self) -> None:
        """实际线程报告取消类异常时关闭仍释放根，未提交意图可由新宿主恢复。"""

        def abort(directories: LocalWorkspaceDirectories, workspace_id: WorkspaceId) -> None:
            """在真实意图已提交后模拟底层取消异常。

            :param directories: 已绑定的真实目录端口。
            :param workspace_id: 原创建身份。
            """
            raise asyncio.CancelledError("底层取消夹具")

        with patch.object(LocalWorkspaceDirectories, "prepare", abort):
            with self.assertLogs("vet3d", level="ERROR"), self.assertRaises(asyncio.CancelledError):
                await self._runtime.create(workspace_id=self._id, display_name="动物")
        await self._runtime.aclose()
        async with await open_workspaces(self._path) as reopened:
            self.assertIsNotNone((await reopened.create(workspace_id=self._id, display_name="动物")).registered_at)

    async def test_completion_logging_failure_does_not_rollback_registration(self) -> None:
        """完成日志输出失败交由事件循环报告，原已提交注册仍能读回。"""
        loop = asyncio.get_running_loop()
        errors: list[dict[str, object]] = []

        def capture_error(event_loop: asyncio.AbstractEventLoop, context: dict[str, object]) -> None:
            """收集日志处理失败的可见异常边界。

            :param event_loop: 当前测试事件循环。
            :param context: 实际回调失败上下文。
            """
            errors.append(context)

        logger = logging.getLogger("vet3d")
        original_info = logger.info

        def emit(message: object, *args: object) -> None:
            """只让真实提交后的完成诊断失败。

            :param message: 固定日志格式。
            :param args: 日志关联字段。
            """
            if message == "workspace_%s_completed workspace_id=%s" and args[0] == "create":
                raise OSError("测试日志输出失败")
            original_info(message, *args)

        original_handler = loop.get_exception_handler()
        loop.set_exception_handler(capture_error)
        try:
            with patch.object(logger, "info", emit):
                record = await self._runtime.create(workspace_id=self._id, display_name="动物")
            self.assertEqual(len(errors), 1)
            self.assertIsInstance(errors[0]["exception"], OSError)
            self.assertEqual(await self._runtime.read(self._id), record)
        finally:
            loop.set_exception_handler(original_handler)

    async def test_wait_logging_failure_preserves_cancellation_and_timeout(self) -> None:
        """等待终态日志失败保留原取消或期限异常，实际存储仍按原身份对账。"""
        logger = logging.getLogger("vet3d")
        for cancel in (True, False):
            with self.subTest(cancel=cancel):
                workspace_id = WorkspaceId(uuid4())
                entered, release = threading.Event(), threading.Event()
                with patch.object(LocalWorkspaceDirectories, "prepare", _blocked_prepare(entered, release)):
                    try:
                        with patch.object(logger, "log", side_effect=OSError("测试终态日志失败")):
                            operation = asyncio.create_task(self._runtime.create(
                                workspace_id=workspace_id, display_name="动物",
                                timeout_seconds=None if cancel else 0.05,
                            ))
                            await _wait_event(entered)
                            if cancel:
                                operation.cancel()
                            expected = asyncio.CancelledError if cancel else WorkspaceTimeoutError
                            with self.assertRaises(expected) as failure:
                                await operation
                            self.assertIsInstance(failure.exception.__cause__, OSError)
                        with self.assertRaises(WorkspaceBusyError):
                            await self._runtime.read(workspace_id)
                    finally:
                        release.set()
                    record = await _read_after_io(self._runtime, workspace_id)
                assert record is not None
                self.assertIsNotNone(record.registered_at)
