# 文件信息：L1-03 受管资源安装与固定快照读取的显式装配。
# 作用：将真实文件适配器接入有界异步 I/O，分开安装写入和运行期读取准入。
# 边界：等待取消不停止线程；关闭排空真实操作，不管理会话、脚本执行或资源热切换。
"""为可信部署端与只读消费者提供不同入口，不向业务暴露任意宿主路径。"""

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import logging
import math
import os
from pathlib import Path
from types import TracebackType
from typing import cast

from vet3d.adapters import LocalResourceStore, ResourceLimits
from vet3d.artifacts import ContentFingerprint
from vet3d.resources import (
    ResourceContractError, ResourceDescription, ResourceKey, ResourcePath, ResourceReader,
)

from .invocation import _record_termination


_LOGGER = logging.getLogger("vet3d")


class ResourceBusyError(RuntimeError):
    """表示本实例对应的实际 I/O 名额已占满，本次没有提交或进入等待队列。"""


class ResourceClosedError(RuntimeError):
    """表示资源宿主已关闭、尚未装配完成或被其他事件循环调用。"""


class ResourceTimeoutError(TimeoutError):
    """表示宿主等待期限耗尽，不声明复制已经停止或版本尚未发布。"""


class _ResourceWorker:
    """保存一个实际线程池及其在途调用，名额只由一次装配参数确定。"""

    def __init__(self, limit: int, name: str) -> None:
        """建立资源 I/O 所需的有限工作线程，不接受内部排队。

        :param limit: 本入口同时在途的最大实际操作数。
        :param name: 固定的诊断线程名前缀。
        """
        self.limit = limit
        self.executor = ThreadPoolExecutor(max_workers=limit, thread_name_prefix=name)
        self.pending: set[asyncio.Future[object]] = set()


def _absolute_root(path: Path) -> Path:
    """冻结受信部署位置，保留拒绝上级段的边界。

    :param path: Bootstrap 提供的路径，不来自资源读取请求。
    :returns: 在装配时固定的绝对位置，不解析符号链接。
    :raises TypeError: 不是 Path。
    :raises ValueError: 含上级段或指向文件系统根。
    """
    if not isinstance(path, Path):
        raise TypeError("资源根必须使用 Path")
    if ".." in path.parts:
        raise ValueError("资源根不能含上级路径段")
    absolute = Path(os.path.abspath(path))
    if absolute == Path("/"):
        raise ValueError("资源根不能是文件系统根")
    return absolute


class ResourceRuntime:
    """拥有安装和读取线程生命周期，由公开装配函数初始化后使用。"""

    def __init__(self, root: Path, source_root: Path, limits: ResourceLimits, max_readers: int) -> None:
        """固定部署配置，尚未创建磁盘布局或读取清单。

        :param root: 独立受管资源根。
        :param source_root: 与资源根分开的可信本地资源包来源根。
        :param limits: 唯一的资源 I/O 限额对象。
        :param max_readers: 并行读取准入上限，不定义建模任务并发数。
        :raises ValueError: 根重叠或读取限额无效。
        :raises TypeError: 配置类型错误。
        """
        self._root = _absolute_root(root)
        self._source_root = _absolute_root(source_root)
        if self._root.is_relative_to(self._source_root) or self._source_root.is_relative_to(self._root):
            raise ValueError("资源根与安装来源根必须互不包含")
        if type(limits) is not ResourceLimits:
            raise TypeError("资源限额必须使用 ResourceLimits")
        if type(max_readers) is not int or max_readers <= 0:
            raise ValueError("并行读取数必须为非布尔正整数")
        self._limits = limits
        self._loop = asyncio.get_running_loop()
        self._installer = _ResourceWorker(1, "vet3d-resource-install")
        self._readers = _ResourceWorker(max_readers, "vet3d-resource-read")
        self._store: LocalResourceStore | None = None
        self._closing: asyncio.Task[None] | None = None

    def _check_loop(self) -> None:
        """只允许装配时的事件循环管理本实例和关闭过程。"""
        if asyncio.get_running_loop() is not self._loop:
            raise ResourceClosedError("资源宿主只能由装配时的事件循环使用")

    def _ready_store(self) -> LocalResourceStore:
        """取得已经完成布局核对的存储对象，不代替实际访问检查。

        :returns: 已装配的具体文件适配器。
        :raises ResourceClosedError: 尚未完成初始化。
        """
        if self._store is None:
            raise ResourceClosedError("资源存储尚未完成装配")
        return self._store

    def _initialize(self) -> None:
        """在安装线程显式建立空资源根，不触发任何脚本。"""
        self._store = LocalResourceStore.initialize(self._root, self._limits)

    def _open(self) -> None:
        """在安装线程核对既有布局，不补建缺失目录。"""
        self._store = LocalResourceStore.open(self._root, self._limits)

    def _observe(
        self, worker: _ResourceWorker, event: str, snapshot: str, key: str,
        future: asyncio.Future[object],
    ) -> None:
        """观察实际终态并释放准入，取消等待后仍保留唯一晚期故障诊断。

        :param worker: 持有实际调用的资源入口。
        :param event: 固定操作名。
        :param snapshot: 原清单指纹或启动阶段的 storage。
        :param key: 已知资源键，部署操作为短占位符。
        :param future: 实际线程任务，不交给调用方取消。
        """
        worker.pending.discard(future)
        error = future.exception()
        if error is None:
            _LOGGER.info("resource_%s_completed snapshot=%s resource=%s", event, snapshot, key)
        elif isinstance(error, (ResourceContractError, TypeError, ValueError, KeyError, FileExistsError, FileNotFoundError)):
            _LOGGER.warning(
                "resource_%s_rejected snapshot=%s resource=%s reason=%s", event, snapshot, key, type(error).__name__,
            )
        else:
            _LOGGER.error("resource_%s_failed snapshot=%s resource=%s", event, snapshot, key, exc_info=error)

    async def _invoke[T](
        self, worker: _ResourceWorker, operation: Callable[[], T], *, event: str,
        snapshot: str, key: str = "-", timeout_seconds: float | None = 5.0,
    ) -> T:
        """取得实际名额后提交一次调用，不排队、不重试、不强停线程。

        :param worker: 本次操作所属安装或读取入口。
        :param operation: 在受信线程中执行的完整 I/O 操作。
        :param event: 固定日志事件。
        :param snapshot: 本次请求的原快照诊断关联。
        :param key: 读取的原逻辑键，只用于日志。
        :param timeout_seconds: 正有限等待秒数；None 表示调用方管理等待期限。
        :returns: 实际调用结果。
        :raises ResourceBusyError: 没有实际名额，本次未提交。
        :raises ResourceClosedError: 已关闭或跨事件循环。
        :raises ResourceTimeoutError: 等待超时，实际结果需沿原快照核对。
        :raises asyncio.CancelledError: 取消等待，实际任务继续受宿主管理。
        """
        self._check_loop()
        if self._closing is not None:
            raise ResourceClosedError("资源宿主已经开始关闭")
        if timeout_seconds is not None and (
            isinstance(timeout_seconds, bool) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0
        ):
            raise ValueError("等待期限必须为正有限秒数")
        if len(worker.pending) >= worker.limit:
            raise ResourceBusyError("资源 I/O 名额已满，本次未提交")
        await asyncio.sleep(0)
        if self._closing is not None:
            raise ResourceClosedError("资源宿主已经开始关闭")
        if len(worker.pending) >= worker.limit:
            raise ResourceBusyError("资源 I/O 名额已满，本次未提交")
        _LOGGER.info("resource_%s_started snapshot=%s resource=%s", event, snapshot, key)
        future: asyncio.Future[object] = self._loop.run_in_executor(worker.executor, operation)
        worker.pending.add(future)
        future.add_done_callback(partial(self._observe, worker, event, snapshot, key))
        deadline = asyncio.timeout(timeout_seconds)
        try:
            async with deadline:
                await asyncio.wait({future})
                return cast(T, future.result())
        except asyncio.CancelledError as error:
            _record_termination(error, logging.INFO, "resource_wait_cancelled", snapshot)
            raise
        except TimeoutError:
            if deadline.expired():
                timeout_error = ResourceTimeoutError("等待超时，实际结果须按原资源快照对账")
                _record_termination(timeout_error, logging.INFO, "resource_wait_timed_out", snapshot)
                raise timeout_error from None
            raise

    async def install(
        self, bundle_name: str, expected: ContentFingerprint, *, timeout_seconds: float | None = 5.0,
    ) -> ContentFingerprint:
        """仅供可信部署端安装一个明确资源包，不切换既有读取实例。

        :param bundle_name: 固定来源根下的单段资源包目录名。
        :param expected: 调用前从可信构建结果保留的清单原字节指纹。
        :param timeout_seconds: 仅限制等待，不表示实际复制期限。
        :returns: 完整发布版本的原指纹，不是会话绑定或可执行证明。
        """
        if type(expected) is not ContentFingerprint:
            raise TypeError("安装需要清单 ContentFingerprint")
        return await self._invoke(
            self._installer, partial(self._ready_store().install, self._source_root, bundle_name, expected),
            event="install", snapshot=expected.sha256, timeout_seconds=timeout_seconds,
        )

    async def pin(
        self, snapshot: ContentFingerprint, *, timeout_seconds: float | None = 5.0,
    ) -> PinnedResources:
        """核对确切快照并交付固定版本入口，不选择最新版本或持久绑定会话。

        :param snapshot: 调用方保留的确切资源清单指纹。
        :param timeout_seconds: 本次等待期限。
        :returns: 共享本宿主生命周期的只读资源消费者。
        """
        if type(snapshot) is not ContentFingerprint:
            raise TypeError("固定版本需要 ContentFingerprint")
        reader = await self._invoke(
            self._readers, partial(self._ready_store().pin, snapshot), event="pin",
            snapshot=snapshot.sha256, timeout_seconds=timeout_seconds,
        )
        return PinnedResources(self, snapshot, reader)

    async def _finish_close(self) -> None:
        """排空已提交的实际任务后释放两个线程池，不因关闭等待被取消提前回收。"""
        futures = self._installer.pending | self._readers.pending
        while any(not future.done() for future in futures):
            try:
                await asyncio.wait(futures)
            except asyncio.CancelledError:
                continue
        # 每个异常已经由 _observe 观察；关闭不重报原业务调用失败。
        self._installer.executor.shutdown(wait=True)
        self._readers.executor.shutdown(wait=True)
        self._store = None

    def _observe_close(self, task: asyncio.Task[None]) -> None:
        """保证关闭等待者消失后，仍能观察实际资源回收结果。

        :param task: 本实例唯一关闭任务。
        """
        error = task.exception()
        if error is None:
            _LOGGER.info("resource_storage_closed")
        else:
            _LOGGER.error("resource_storage_close_failed", exc_info=error)

    async def aclose(self) -> None:
        """停止两个入口的新准入，等待实际操作和线程终结。"""
        self._check_loop()
        if self._closing is None:
            self._closing = self._loop.create_task(self._finish_close())
            self._closing.add_done_callback(self._observe_close)
        await asyncio.wait({self._closing})
        self._closing.result()

    async def __aenter__(self) -> ResourceRuntime:
        """进入已装配的宿主上下文。

        :returns: 当前宿主。
        """
        self._check_loop()
        if self._closing is not None:
            raise ResourceClosedError("资源宿主已经开始关闭")
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """退出上下文时排空实际工作。

        :param exc_type: 上下文异常类型。
        :param exc_value: 上下文异常值。
        :param traceback: 原异常堆栈。
        """
        await self.aclose()


class PinnedResources:
    """公开接口只提供固定版本读取；Python 对象自身不是权限隔离边界。"""

    def __init__(self, runtime: ResourceRuntime, snapshot: ContentFingerprint, reader: ResourceReader) -> None:
        """接收显式装配的端口和诊断关联，不重复建立资源清单。

        :param runtime: 实际线程及关闭的资源所有者。
        :param snapshot: 装配要求的原快照，用于返回关联核对及诊断。
        :param reader: 已在实际存储核对该快照的同步读取端口。
        """
        self._runtime = runtime
        self._snapshot = snapshot
        self._reader = reader

    def describe(self, key: ResourceKey) -> ResourceDescription | None:
        """查询冻结清单描述，不承诺此刻磁盘仍可读或脚本已经可执行。

        :param key: 清单中的逻辑资源键。
        :returns: 确切引用和声明；未声明的资源为空。
        """
        if type(key) is not ResourceKey:
            raise TypeError("资源描述需要 ResourceKey")
        description = self._reader.describe(key)
        if description is not None:
            if type(description) is not ResourceDescription:
                raise TypeError("资源端口必须返回 ResourceDescription 或 None")
            if description.reference.snapshot != self._snapshot or description.reference.key != key:
                raise ResourceContractError("资源端口的回包不属于本实例固定快照与原资源键")
        return description

    async def read_file(
        self, key: ResourceKey, path: ResourcePath, *, timeout_seconds: float | None = 5.0,
    ) -> bytes:
        """有界读取该资源声明的文件，由实际适配器重新核对字节。

        :param key: 已固定快照中的资源键。
        :param path: 该资源声明的文件相对位置，不是宿主路径。
        :param timeout_seconds: 本次等待期限。
        :returns: 与清单内容匹配的实际字节，不代表 LLM 已收到或执行成功。
        """
        if type(key) is not ResourceKey or type(path) is not ResourcePath:
            raise TypeError("资源读取需要 ResourceKey 和 ResourcePath")
        description = self.describe(key)
        if description is None or path not in description.definition.files:
            raise ResourceContractError("只能读取原固定快照中该资源直接声明的文件")
        return await self._runtime._invoke(
            self._runtime._readers, partial(self._reader.read_file, key, path), event="read",
            snapshot=self._snapshot.sha256, key=key.value, timeout_seconds=timeout_seconds,
        )


async def initialize_resources(
    root: Path, *, source_root: Path, limits: ResourceLimits, max_readers: int,
) -> ResourceRuntime:
    """显式建立新的受管资源根，失败或取消后排空本次实际操作。

    :param root: 不存在或安全空白的独立资源根。
    :param source_root: 可信资源包的固定来源位置。
    :param limits: 显式资源 I/O 预算。
    :param max_readers: 实际读取并发准入上限。
    :returns: 已装配的资源宿主，不包含已安装资源或会话绑定。
    """
    runtime = ResourceRuntime(root, source_root, limits, max_readers)
    try:
        await runtime._invoke(
            runtime._installer, runtime._initialize, event="initialize", snapshot="storage", timeout_seconds=None,
        )
    except BaseException:
        await runtime.aclose()
        raise
    return runtime


async def open_resources(
    root: Path, *, source_root: Path, limits: ResourceLimits, max_readers: int,
) -> ResourceRuntime:
    """重新打开既有资源布局，不修复缺失目录或认领暂存文件。

    :param root: 已初始化的独立资源根。
    :param source_root: 本进程重新注入的可信来源位置。
    :param limits: 本进程显式资源 I/O 预算。
    :param max_readers: 实际读取并发准入上限。
    :returns: 可以沿原快照核对资源的宿主，不恢复会话状态。
    """
    runtime = ResourceRuntime(root, source_root, limits, max_readers)
    try:
        await runtime._invoke(runtime._installer, runtime._open, event="open", snapshot="storage", timeout_seconds=None)
    except BaseException:
        await runtime.aclose()
        raise
    return runtime
