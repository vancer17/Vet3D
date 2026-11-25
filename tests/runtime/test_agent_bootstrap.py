# 文件信息：阶段 B 的真实身份／配置交接与有界装配测试。
# 作用：用真实 L1 注册和受控环境替身验证拒绝、准入、取消排空及清理失败。
# 边界：替身不证明模型语义、Docker 隔离或进程已停止。
"""验证有限宿主拥有资源的真实边界，不为工具操作建立业务状态。"""

import asyncio
import json
import os
from pathlib import Path
import tempfile
from threading import Event
from typing import cast
import unittest
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from vet3d.adapters import (
    CodexAgentSession, CodexDockerEnvironment, CodexEnvironmentCreationError,
    NativeProtocolError, NativeSessionBinding,
)
from vet3d.bootstrap import AgentRuntime, initialize_operations, load_settings
from vet3d.identity import TaskId, TaskIdentity, WorkspaceId


class AgentBootstrapTests(unittest.IsolatedAsyncioTestCase):
    """核对原任务关系、部署参数和实际创建操作之间的交接。"""

    async def asyncSetUp(self) -> None:
        """创建独立存储与无凭证原生配置，不运行真实模型。"""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name in ("inputs", "sources"):
            (self.root / name).mkdir(mode=0o700)
        self.materials = self.root / "inputs" / "task"
        self.materials.mkdir()
        (self.materials / "reference.txt").write_text("input", encoding="utf-8")
        self.native = self.root / "native.toml"
        self.native.write_text(
            'model="model-under-test"\nmodel_provider="provider-under-test"\n'
            '[model_providers.provider-under-test]\nname="Test"\n'
            'base_url="https://example.invalid"\nwire_api="responses"\nenv_key="TEST_API_KEY"\n',
            encoding="utf-8",
        )
        config = self.root / "config.yaml"
        config.write_text(json.dumps({
            "workspaces": {"root": "workspaces"},
            "files": {"input_root": "inputs", "max_file_bytes": 4096},
            "resources": {"root": "resources", "source_root": "sources", "limits": {
                "max_manifest_bytes": 8192, "max_files": 4, "max_file_bytes": 4096, "max_total_bytes": 8192,
            }},
            "diagnostics": {"root": "logs"},
            "agent": {"codex_package": "codex", "native_config": "native.toml", "control_root": "control",
                      "image_id": "test-only", "max_sessions": 1},
        }), encoding="utf-8")
        environment = patch.dict(os.environ, {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        self.settings = load_settings(config)
        self.operations = await initialize_operations(self.settings)
        self.addAsyncCleanup(self.operations.aclose)
        self.workspace = WorkspaceId(uuid4())
        await self.operations.workspaces.create(workspace_id=self.workspace, display_name="阶段 B 测试")
        self.task = TaskIdentity(TaskId(uuid4()), self.workspace)

    def _owner(self) -> AgentRuntime:
        """装配本测试唯一原生宿主，并登记退出时的实际关闭。

        :returns: 使用真实配置及工作区消费者的宿主。
        """
        owner = AgentRuntime(self.settings, self.operations.workspaces, self.operations.resources)
        self.addAsyncCleanup(owner.aclose)
        return owner

    def _session(self) -> CodexAgentSession:
        """构造只证明身份交接的机械会话。

        :returns: 明确使用原任务关系的替身。
        """
        session = Mock(spec=CodexAgentSession)
        session.binding = NativeSessionBinding(self.task, "original-thread")
        session.aclose = AsyncMock()
        session.turn_timeout_seconds = 37.0
        return cast(CodexAgentSession, session)

    async def test_unknown_workspace_rejected_before_environment_creation(self) -> None:
        """未登记工作区不能靠一个合法 UUID 启动动态执行。"""
        owner = self._owner()
        with patch("vet3d.bootstrap.agent.CodexDockerEnvironment.create") as create:
            with self.assertRaises(ValueError):
                await owner.open_session(TaskIdentity(TaskId(uuid4()), WorkspaceId(uuid4())), self.materials)
            create.assert_not_called()

    async def test_material_scope_and_link_rejected_before_environment(self) -> None:
        """授权输入目录以外以及目录内的链接不能被递归送入环境。"""
        owner = self._owner()
        with patch("vet3d.bootstrap.agent.CodexDockerEnvironment.create") as create:
            with self.assertRaises(ValueError):
                await owner.open_session(self.task, self.root / "sources")
            (self.materials / "link").symlink_to(self.native)
            with self.assertRaises(ValueError):
                await owner.open_session(self.task, self.materials)
            create.assert_not_called()

    async def test_native_config_is_single_source_and_admission_has_no_queue(self) -> None:
        """连接选择来自原生配置；原任务重复和并发超额都不重复创建环境。"""
        owner = self._owner()
        environment = Mock(spec=CodexDockerEnvironment)
        session = self._session()
        with patch("vet3d.bootstrap.agent.CodexDockerEnvironment.create", return_value=environment) as create, patch.object(
            owner, "_connect", new=AsyncMock(),
        ), patch("vet3d.bootstrap.agent.CodexAgentSession.open", new=AsyncMock(return_value=session)) as opened:
            self.assertIs(await owner.open_session(self.task, self.materials), session)
            self.assertEqual(opened.call_args.kwargs["model"], "model-under-test")
            self.assertEqual(opened.call_args.kwargs["provider"], "provider-under-test")
            self.assertEqual(create.call_args.kwargs["model_api_key_env"], "TEST_API_KEY")
            for task in (self.task, TaskIdentity(TaskId(uuid4()), self.workspace)):
                with self.assertRaises(RuntimeError):
                    await owner.open_session(task, self.materials)
            self.assertEqual(create.call_count, 1)
            await owner.close_session(session)
            environment.cleanup.assert_called_once()

    async def test_cancel_during_creation_drains_original_then_cleans(self) -> None:
        """创建中的取消保留原 I/O，拿到真实环境后才清理，不遗失句柄。"""
        owner = self._owner()
        entered, release = Event(), Event()
        environment = Mock(spec=CodexDockerEnvironment)

        def create(**kwargs: object) -> CodexDockerEnvironment:
            """模拟尚未交回句柄的原环境创建。

            :param kwargs: 明确装配参数，不解释凭证或业务目标。
            :returns: 原环境对象。
            """
            entered.set()
            if not release.wait(3):
                raise TimeoutError("测试未释放原创建")
            return cast(CodexDockerEnvironment, environment)

        with patch("vet3d.bootstrap.agent.CodexDockerEnvironment.create", side_effect=create), patch.object(
            owner, "_connect", new=AsyncMock(),
        ), patch("vet3d.bootstrap.agent.CodexAgentSession.open", new=AsyncMock(return_value=self._session())):
            opening = asyncio.create_task(owner.open_session(self.task, self.materials))
            self.assertTrue(await asyncio.to_thread(entered.wait, 2))
            opening.cancel()
            await asyncio.sleep(0)
            environment.cleanup.assert_not_called()
            release.set()
            with self.assertRaises(asyncio.CancelledError):
                await opening
            environment.cleanup.assert_called_once()

    async def test_cleanup_failure_keeps_slot_and_can_retry_original_environment(self) -> None:
        """清理失败不能释放名额；再次关闭只针对原环境。"""
        owner = self._owner()
        environment = Mock(spec=CodexDockerEnvironment)
        environment.cleanup.side_effect = [OSError("not stopped"), None]
        session = self._session()
        with patch("vet3d.bootstrap.agent.CodexDockerEnvironment.create", return_value=environment), patch.object(
            owner, "_connect", new=AsyncMock(),
        ), patch("vet3d.bootstrap.agent.CodexAgentSession.open", new=AsyncMock(return_value=session)):
            await owner.open_session(self.task, self.materials)
            with self.assertRaises(ExceptionGroup):
                await owner.close_session(session)
            with self.assertRaises(RuntimeError):
                await owner.open_session(TaskIdentity(TaskId(uuid4()), self.workspace), self.materials)
            await owner.close_session(session)
            self.assertEqual(environment.cleanup.call_count, 2)

    async def test_failed_binding_keeps_environment_until_cleanup_is_confirmed(self) -> None:
        """环境已创建但线程关联失败时，清理失败仍占有原资源和准入名额。"""
        owner = self._owner()
        environment = Mock(spec=CodexDockerEnvironment)
        environment.cleanup.side_effect = [OSError("still running"), None]
        with patch("vet3d.bootstrap.agent.CodexDockerEnvironment.create", return_value=environment) as create, patch.object(
            owner, "_connect", new=AsyncMock(side_effect=NativeProtocolError("binding failed")),
        ):
            with self.assertRaises(BaseExceptionGroup):
                await owner.open_session(self.task, self.materials)
            with self.assertRaises(RuntimeError):
                await owner.open_session(TaskIdentity(TaskId(uuid4()), self.workspace), self.materials)
            self.assertEqual(create.call_count, 1)
            await owner.aclose()
            self.assertEqual(environment.cleanup.call_count, 2)
            self.assertEqual(list(self.settings.agent.control_root.glob("session-*")) if self.settings.agent else [], [])

    async def test_partial_environment_creation_preserves_original_owner(self) -> None:
        """创建及清理都失败时，从异常取回原环境，不将其丢作无主资源。"""
        owner = self._owner()
        environment = Mock(spec=CodexDockerEnvironment)
        environment.cleanup.side_effect = [OSError("cleanup still unavailable"), None]
        failure = CodexEnvironmentCreationError(
            cast(CodexDockerEnvironment, environment),
            BaseExceptionGroup("partial create", [OSError("create failed"), OSError("cleanup failed")]),
        )
        with patch("vet3d.bootstrap.agent.CodexDockerEnvironment.create", side_effect=failure) as create:
            with self.assertRaises(BaseExceptionGroup):
                await owner.open_session(self.task, self.materials)
            with self.assertRaises(RuntimeError):
                await owner.open_session(self.task, self.materials)
            self.assertEqual(create.call_count, 1)
            await owner.aclose()
            self.assertEqual(environment.cleanup.call_count, 2)

    async def test_cancelled_output_copy_is_drained_before_environment_cleanup(self) -> None:
        """复制等待取消后真实 I/O 继续受管，环境关闭须等它排空。"""
        owner = self._owner()
        environment = Mock(spec=CodexDockerEnvironment)
        session = self._session()
        entered, release = Event(), Event()

        def copy(destination: Path) -> None:
            """模拟尚在读取原容器输出的有界文件操作。

            :param destination: 本测试明确的目标目录。
            """
            entered.set()
            if not release.wait(3):
                raise TimeoutError("测试未释放原复制")
            destination.mkdir()

        environment.copy_outputs.side_effect = copy
        with patch("vet3d.bootstrap.agent.CodexDockerEnvironment.create", return_value=environment), patch.object(
            owner, "_connect", new=AsyncMock(),
        ), patch("vet3d.bootstrap.agent.CodexAgentSession.open", new=AsyncMock(return_value=session)):
            await owner.open_session(self.task, self.materials)
            copying = asyncio.create_task(owner.copy_outputs(session, self.root / "received"))
            self.assertTrue(await asyncio.to_thread(entered.wait, 2))
            copying.cancel()
            closing = asyncio.create_task(owner.close_session(session))
            await asyncio.sleep(0.02)
            environment.cleanup.assert_not_called()
            self.assertFalse(copying.done())
            release.set()
            with self.assertRaises(asyncio.CancelledError):
                await copying
            await closing
            environment.cleanup.assert_called_once()
            self.assertTrue((self.root / "received").is_dir())

    async def test_reconnect_replaces_only_connection_and_preserves_original_scope(self) -> None:
        """受信重连沿原环境、任务及线程，旧对象不能操作替换后的环境。"""
        owner = self._owner()
        environment = Mock(spec=CodexDockerEnvironment)
        original, resumed = self._session(), self._session()
        with patch("vet3d.bootstrap.agent.CodexDockerEnvironment.create", return_value=environment) as create, patch.object(
            owner, "_connect", new=AsyncMock(),
        ) as connect, patch("vet3d.bootstrap.agent.CodexAgentSession.open", new=AsyncMock(return_value=original)), patch(
            "vet3d.bootstrap.agent.CodexAgentSession.resume", new=AsyncMock(return_value=resumed),
        ) as resume:
            await owner.open_session(self.task, self.materials, turn_timeout_seconds=37)
            directory = owner.control_directory(original)
            self.assertIs(await owner.reconnect(original), resumed)
            self.assertIs(resume.call_args.args[1], original.binding)
            self.assertEqual(resume.call_args.kwargs["turn_timeout_seconds"], 37)
            self.assertEqual(resume.call_args.kwargs["environment_id"], "task")
            self.assertEqual(owner.control_directory(resumed), directory)
            with self.assertRaises(ValueError):
                owner.control_directory(original)
            self.assertEqual(create.call_count, 1)
            self.assertEqual(connect.call_count, 2)
            environment.stop_control.assert_called_once()
            await owner.close_session(resumed)

    async def test_failed_reconnect_retains_original_environment_for_close(self) -> None:
        """原线程恢复失败不能重新创建环境或释放其实际清理所有权。"""
        owner = self._owner()
        environment = Mock(spec=CodexDockerEnvironment)
        session = self._session()
        with patch("vet3d.bootstrap.agent.CodexDockerEnvironment.create", return_value=environment) as create, patch.object(
            owner, "_connect", new=AsyncMock(),
        ), patch("vet3d.bootstrap.agent.CodexAgentSession.open", new=AsyncMock(return_value=session)), patch(
            "vet3d.bootstrap.agent.CodexAgentSession.resume", new=AsyncMock(side_effect=NativeProtocolError("wrong thread")),
        ):
            await owner.open_session(self.task, self.materials)
            with self.assertRaises(NativeProtocolError):
                await owner.reconnect(session)
            with self.assertRaises(RuntimeError):
                await owner.open_session(TaskIdentity(TaskId(uuid4()), self.workspace), self.materials)
            await owner.close_session(session)
            self.assertEqual(create.call_count, 1)
            environment.cleanup.assert_called_once()

    async def test_native_close_cancellation_group_does_not_skip_environment_cleanup(self) -> None:
        """原生关闭带取消异常组时，整个任务环境仍必须得到实际清理。"""
        owner = self._owner()
        environment = Mock(spec=CodexDockerEnvironment)
        session = self._session()
        cast(AsyncMock, session.aclose).side_effect = BaseExceptionGroup("native close", [asyncio.CancelledError()])
        with patch("vet3d.bootstrap.agent.CodexDockerEnvironment.create", return_value=environment), patch.object(
            owner, "_connect", new=AsyncMock(),
        ), patch("vet3d.bootstrap.agent.CodexAgentSession.open", new=AsyncMock(return_value=session)):
            await owner.open_session(self.task, self.materials)
            with self.assertRaises(BaseExceptionGroup):
                await owner.close_session(session)
            environment.cleanup.assert_called_once()
            await owner.aclose()

    async def test_same_task_id_cannot_change_workspace_during_active_session(self) -> None:
        """活动任务不能通过替换工作区字段绕过重复准入守卫。"""
        owner = self._owner()
        environment = Mock(spec=CodexDockerEnvironment)
        with patch("vet3d.bootstrap.agent.CodexDockerEnvironment.create", return_value=environment) as create, patch.object(
            owner, "_connect", new=AsyncMock(),
        ), patch("vet3d.bootstrap.agent.CodexAgentSession.open", new=AsyncMock(return_value=self._session())):
            session = await owner.open_session(self.task, self.materials)
            with self.assertRaises(RuntimeError):
                await owner.open_session(TaskIdentity(self.task.id, WorkspaceId(uuid4())), self.materials)
            self.assertEqual(create.call_count, 1)
            await owner.close_session(session)

    async def test_material_replaced_with_link_before_open_is_rejected(self) -> None:
        """初始目录检查后的链接替换不能使实际读取越过授权边界。"""
        owner = self._owner()
        original_open = os.open
        source = self.materials / "reference.txt"

        def replace_then_open(
            path: str | bytes | os.PathLike[str] | os.PathLike[bytes], flags: int,
            mode: int = 0o777, *, dir_fd: int | None = None,
        ) -> int:
            """在实际打开前模拟来源被替换，保留真实 no-follow 调用。

            :param path: 本次真实打开路径。
            :param flags: 原打开标志，不移除边界约束。
            :param mode: 新文件模式。
            :param dir_fd: 原目录描述符。
            :returns: 实际系统文件描述符。
            """
            if path == "reference.txt" and dir_fd is not None:
                source.unlink()
                source.symlink_to(self.native)
            return original_open(path, flags, mode, dir_fd=dir_fd)

        with patch("vet3d.bootstrap.agent.os.open", side_effect=replace_then_open), patch(
            "vet3d.bootstrap.agent.CodexDockerEnvironment.create",
        ) as create:
            with self.assertRaises(ValueError):
                await owner.open_session(self.task, self.materials)
            create.assert_not_called()

    async def test_material_member_limit_includes_directories(self) -> None:
        """大量空目录同样占用交接成员额度，不绕过文件数限制。"""
        owner = self._owner()
        for number in range(128):
            (self.materials / str(number)).mkdir()
        with patch("vet3d.bootstrap.agent.CodexDockerEnvironment.create") as create:
            with self.assertRaisesRegex(ValueError, "128"):
                await owner.open_session(self.task, self.materials)
            create.assert_not_called()

    async def test_native_extensions_and_overlapping_control_root_are_rejected(self) -> None:
        """未授权扩展配置与受管根重叠均在原生执行前拒绝。"""
        self.native.write_text(self.native.read_text(encoding="utf-8") + '\n[mcp_servers.test]\ncommand="no"\n', encoding="utf-8")
        with self.assertRaises(ValueError):
            AgentRuntime(self.settings, self.operations.workspaces, self.operations.resources)
        with self.assertRaises(ValueError):
            load_settings(self.root / "config.yaml", overrides={"agent": {"control_root": "inputs/hidden"}})


if __name__ == "__main__":
    unittest.main()
