# 文件信息：L1-05 环境配置与真实存储、诊断的有限装配入口。
# 作用：把冻结配置一次性注入现有端口，统一释放存储及诊断所有者。
# 边界：只按显式调用运行受信环境探针，不执行资源脚本或判断业务资格。
"""为可信宿主装配本地基础设施，不把 Settings 传入业务服务。"""

import asyncio
from contextlib import AsyncExitStack
import logging
from pathlib import Path
import sys
from types import TracebackType

from vet3d.identity import WorkspaceId
from vet3d.operations import DiagnosticStatus, EnvironmentReport
from vet3d.resources import InterpreterRequirement, ResourceReference

from .diagnostics import DiagnosticRuntime, open_diagnostics
from .environment import EnvironmentRuntime
from .resources import ResourceRuntime, initialize_resources, open_resources
from .settings import Settings
from .workspaces import (
    WorkspaceArtifacts, WorkspaceFiles, WorkspaceRuntime, initialize_workspaces, open_workspaces,
)

_LOGGER = logging.getLogger("vet3d")


async def _close_after_failure(owner: WorkspaceRuntime | ResourceRuntime | DiagnosticRuntime) -> None:
    """在部分装配失败时排空同一所有者，再把清理期间的取消交回退出栈。

    :param owner: 本次已成功取得的具体资源，不接收任意形状的关闭对象。
    :raises asyncio.CancelledError: 清理等待曾被取消，但实际关闭已经完成。
    """
    cancelled = False
    while True:
        try:
            await owner.aclose()
            break
        except asyncio.CancelledError:
            cancelled = True
    if cancelled:
        raise asyncio.CancelledError


class OperationsRuntime:
    """持有一次显式装配的真实资源；业务消费者仅取得所需端口。"""

    def __init__(
        self, settings: Settings, workspaces: WorkspaceRuntime,
        resources: ResourceRuntime, diagnostics: DiagnosticRuntime,
    ) -> None:
        """保存已成功打开的资源，禁止把部分初始化包装成可用宿主。

        :param settings: 唯一配置入口返回的冻结部署值。
        :param workspaces: 已打开的工作区与资产宿主。
        :param resources: 已打开的受管资源宿主。
        :param diagnostics: 已持有日志目录的唯一诊断所有者。
        """
        self._settings = settings
        self.workspaces = workspaces
        self.resources = resources
        self.diagnostics = diagnostics
        self._environment = EnvironmentRuntime(settings, resources, runtime_id=diagnostics.runtime_id)
        self._loop = asyncio.get_running_loop()
        self._closing: asyncio.Task[DiagnosticStatus] | None = None

    async def files(self, workspace_id: WorkspaceId) -> WorkspaceFiles:
        """为已授权的可信调用方注入固定输入根与文件预算。

        :param workspace_id: 已有的工作区身份，身份本身不是授权。
        :returns: 与原工作区绑定的文件入口。
        """
        self._check_open()
        return await self.workspaces.files(
            workspace_id, input_root=self._settings.files.input_root,
            max_file_bytes=self._settings.files.max_file_bytes,
        )

    async def artifacts(self, workspace_id: WorkspaceId) -> WorkspaceArtifacts:
        """把同一文件预算注入现有资产访问与单件登记入口。

        :param workspace_id: 可信调用方已获准使用的工作区身份。
        :returns: 可作为 ArtifactAccess 注入业务服务的真实端口。
        """
        self._check_open()
        return await self.workspaces.artifacts(
            workspace_id, max_file_bytes=self._settings.files.max_file_bytes,
        )

    def configured_interpreter(self, requirement: InterpreterRequirement) -> Path | None:
        """按资源声明的环境名称返回配置候选，不推断可执行性。

        :param requirement: L1-03 原资源的解释器要求；版本及依赖留给 L2-01 核对。
        :returns: 精确环境名称的配置位置；未配置时为空，不搜索 PATH 或替换环境。
        """
        self._check_open()
        if type(requirement) is not InterpreterRequirement:
            raise TypeError("解释器定位必须使用原资源的 InterpreterRequirement")
        return next(
            (entry.path for entry in self._settings.interpreters if entry.runtime == requirement.runtime), None,
        )

    async def check_environment(self, reference: ResourceReference) -> EnvironmentReport:
        """检查原资源闭包的运行环境，返回机器可读的局部证据。

        :param reference: 已由可信宿主选择的固定资源身份，不是执行授权。
        :returns: 原运行关联下的新观察，不登记任务、资产或发布事实。
        """
        self._check_open()
        return await self._environment.check(reference)

    def _check_open(self) -> None:
        """拒绝跨事件循环调用及关闭后的新装配，不创建业务状态。"""
        if asyncio.get_running_loop() is not self._loop or self._closing is not None:
            raise RuntimeError("本地装配已开始关闭或调用来自其他事件循环")

    async def _finish_close(self) -> DiagnosticStatus:
        """先结束探针清理，再关闭独立存储与诊断，最后交付实际关闭错误。"""
        errors: list[Exception] = []
        while True:
            try:
                await self._environment.aclose()
                break
            except asyncio.CancelledError:
                continue
            except Exception as error:
                # 探针从未持有业务存储；保留其现场，不遗留无关根锁和诊断线程。
                errors.append(error)
                break
        for owner in (self.workspaces, self.resources):
            while True:
                try:
                    await owner.aclose()
                except asyncio.CancelledError:
                    # 只保护内部清理；重新等待同一所有者的实际关闭，不新建操作。
                    continue
                except Exception as error:
                    errors.append(error)
                break
        _LOGGER.info("operations_stopped")
        while True:
            try:
                status = await self.diagnostics.aclose()
                break
            except asyncio.CancelledError:
                continue
        if errors:
            raise BaseExceptionGroup("本地资源关闭失败；独立存储及诊断已执行关闭", errors)
        return status

    async def aclose(self) -> DiagnosticStatus:
        """停止接收新装配并排空资源；取消等待不释放在途所有者。

        :returns: 诊断实际关闭后的损失及写入故障信息，不是业务验收结果。
        """
        if asyncio.get_running_loop() is not self._loop:
            raise RuntimeError("必须在原事件循环关闭本地装配")
        if self._closing is None:
            self._closing = self._loop.create_task(self._finish_close())
            self._closing.add_done_callback(self._observe_close)
        await asyncio.wait({self._closing})
        return self._closing.result()

    def _observe_close(self, task: asyncio.Task[DiagnosticStatus]) -> None:
        """即使等待者离开也取得内部关闭异常，不重复记录底层已报告的堆栈。

        :param task: 唯一实际关闭任务；后续调用者仍可从同一任务取得结果。
        """
        if not task.cancelled():
            task.exception()

    async def __aenter__(self) -> OperationsRuntime:
        """进入已成功装配的宿主作用域。

        :returns: 当前真实资源所有者。
        """
        self._check_open()
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """离开作用域时按存储、诊断顺序关闭，不接管业务异常。

        :param exc_type: 原异常类型。
        :param exc_value: 原异常实例。
        :param traceback: 原异常堆栈。
        """
        await self.aclose()


async def _assemble(settings: Settings, *, initialize: bool) -> OperationsRuntime:
    """从明确的初始化或重开操作装配资源，不由配置切换内部架构。

    :param settings: 经过唯一入口校验的冻结环境配置。
    :param initialize: 本次操作是否显式初始化新存储；重开失败不回退初始化。
    :returns: 全部成功打开的资源所有者。
    """
    if not isinstance(settings, Settings):
        raise TypeError("装配需要已校验的 Settings")
    async with AsyncExitStack() as cleanup:
        try:
            diagnostics = await open_diagnostics(
                settings.diagnostics.root, limits=settings.diagnostics.limits, stderr=sys.stderr,
            )
        except Exception:
            # 此时还没有诊断所有者，文件适配器的启动失败只能在装配边界记录。
            _LOGGER.exception("operations_diagnostics_start_failed")
            raise
        cleanup.push_async_callback(_close_after_failure, diagnostics)
        _LOGGER.info("operations_starting")
        workspace_factory = initialize_workspaces if initialize else open_workspaces
        workspaces = await workspace_factory(
            settings.workspaces.root, max_file_operations=settings.workspaces.max_file_operations,
        )
        cleanup.push_async_callback(_close_after_failure, workspaces)
        resource_factory = initialize_resources if initialize else open_resources
        resources = await resource_factory(
            settings.resources.root, source_root=settings.resources.source_root,
            limits=settings.resources.limits, max_readers=settings.resources.max_readers,
        )
        cleanup.push_async_callback(_close_after_failure, resources)
        result = OperationsRuntime(settings, workspaces, resources, diagnostics)
        _LOGGER.info("operations_started")
        cleanup.pop_all()
        return result


async def initialize_operations(settings: Settings) -> OperationsRuntime:
    """显式初始化新的工作区与资源存储，失败保留实际现场。

    :param settings: 唯一配置入口输出；配置文件和输入目录不会被重写。
    :returns: 已完成本次装配的宿主；部分初始化失败需分别核对原存储。
    """
    return await _assemble(settings, initialize=True)


async def open_operations(settings: Settings) -> OperationsRuntime:
    """重新打开已存在的两类存储，缺失或损坏时拒绝自动修复。

    :param settings: 当前进程明确加载的配置，不恢复旧进程的任务或句柄。
    :returns: 已重开的存储与新进程诊断所有者。
    """
    return await _assemble(settings, initialize=False)
