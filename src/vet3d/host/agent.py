# 文件信息：L2-02 阶段 B 的有限非交互宿主。
# 作用：从统一配置打开已有工作区，提交目标、消费原生进度并可传递一次独立追加要求。
# 边界：不是 BFF 服务；退出零仅表示原生轮次 completed，不表示建模目标、资产或业务验收通过。
"""显式运行有限原生会话，不在默认产品启动或测试中调用模型。"""

import argparse
import asyncio
from collections.abc import Sequence
from functools import partial
import json
import logging
import math
from pathlib import Path
import signal
import sys
from uuid import UUID

from vet3d.adapters import CodexAgentSession, NativeMessage
from vet3d.bootstrap import AgentRuntime, configure_logging, load_settings, open_operations
from vet3d.identity import TaskId, TaskIdentity, WorkspaceId


def _goal(path: Path) -> str:
    """读取可信调用方明确提供的有限目标，不解析或生成修复指令。

    :param path: UTF-8 目标文件。
    :returns: 原始非空目标文本。
    :raises ValueError: 目标为空或超过 64 KiB。
    """
    with path.open("rb") as stream:
        data = stream.read(65537)
    if len(data) > 65536:
        raise ValueError("目标必须是非空且不超过 64 KiB 的文本")
    text = data.decode("utf-8")
    if not text.strip():
        raise ValueError("目标必须是非空且不超过 64 KiB 的文本")
    return text


def _positive_seconds(value: str) -> float:
    """在任何装配副作用前拒绝无效的命令行期限。

    :param value: 命令行的秒数字符串。
    :returns: 有限正数秒。
    :raises argparse.ArgumentTypeError: 输入不是有限正数。
    """
    try:
        seconds = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("轮次期限必须为有限正数") from error
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError("轮次期限必须为有限正数")
    return seconds


async def _progress(event: NativeMessage) -> None:
    """显示有限原生进度，不改变运行时内部的模型反馈。

    :param event: 会话交回的原生通知；完整内容仍由运行时管理。
    """
    method = event.get("method")
    if method not in {"turn/started", "turn/completed", "item/started", "item/completed"}:
        return
    params = event.get("params")
    item = params.get("item") if isinstance(params, dict) else None
    logging.getLogger("vet3d").info(
        "native_progress method=%s thread=%s turn=%s item_type=%s",
        method, params.get("threadId") if isinstance(params, dict) else None,
        params.get("turnId") if isinstance(params, dict) else None,
        item.get("type") if isinstance(item, dict) else None,
    )


def agent_main(argv: Sequence[str] | None = None) -> int:
    """运行可信宿主明确指定的一至两轮原生任务，完成后关闭环境。

    :param argv: 显式部署、原身份和任务目标参数；不接收任意原生 RPC。
    :returns: 原生 completed 为零，失败为一，参数错误为二，取消为 130／143。
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--workspace-id", type=UUID, required=True)
    parser.add_argument("--task-id", type=UUID, required=True)
    parser.add_argument("--materials", type=Path, required=True)
    parser.add_argument("--goal-file", type=Path, required=True)
    parser.add_argument("--continue-file", type=Path)
    parser.add_argument("--skill-name")
    parser.add_argument("--skill-path")
    parser.add_argument("--turn-timeout-seconds", type=_positive_seconds, default=600)
    parser.add_argument("--output-directory", type=Path)
    arguments = parser.parse_args(argv)
    if (arguments.skill_name is None) != (arguments.skill_path is None):
        parser.error("选用 Skill 必须同时提供名称及任务环境内路径")
    configure_logging()
    interrupted: int | None = None

    async def run() -> NativeMessage:
        """装配原会话并保持信号清理，不依赖逐命令审批。

        :returns: 仅描述技术轮次的有限结果。
        """
        loop = asyncio.get_running_loop()
        current = asyncio.current_task()
        assert current is not None
        session: CodexAgentSession | None = None
        stopping: asyncio.Task[None] | None = None

        async def cancel_session() -> None:
            """把宿主信号交给原轮次，失败时由已有退出路径回收环境。"""
            assert session is not None
            try:
                await session.cancel()
            except Exception:
                logging.getLogger("vet3d").exception("native_host_cancel_unconfirmed")
                current.cancel()

        def stop(signum: int) -> None:
            """只响应第一次停止信号，避免重复信号打断实际清理。

            :param signum: SIGTERM 或 SIGINT 的原信号编号。
            """
            nonlocal interrupted, stopping
            if interrupted is None:
                interrupted = signum
                if session is None:
                    current.cancel()
                else:
                    stopping = asyncio.create_task(cancel_session())

        for signum in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(signum, partial(stop, signum))
        try:
            settings = load_settings(arguments.config, env_file=arguments.env_file)
            initial = _goal(arguments.goal_file)
            continuation = _goal(arguments.continue_file) if arguments.continue_file is not None else None
            task = TaskIdentity(TaskId(arguments.task_id), WorkspaceId(arguments.workspace_id))
            async with await open_operations(settings) as operations:
                async with AgentRuntime(settings, operations.workspaces, operations.resources) as owner:
                    session = await owner.open_session(
                        task, arguments.materials.absolute(), turn_timeout_seconds=arguments.turn_timeout_seconds,
                    )
                    terminal = await session.run(
                        initial, on_event=_progress,
                        skill_name=arguments.skill_name, skill_path=arguments.skill_path,
                    )
                    if interrupted is None and continuation is not None and terminal.get("status") == "completed":
                        terminal = await session.run(continuation, on_event=_progress)
                    if arguments.output_directory is not None:
                        await owner.copy_outputs(session, arguments.output_directory)
                    return {
                        "task_id": str(task.id.value), "workspace_id": str(task.workspace_id.value),
                        "thread_id": session.binding.thread_id, "turn": terminal,
                        "quality_assessment": "not_run", "formal_assets_registered": False,
                    }
        finally:
            for signum in (signal.SIGTERM, signal.SIGINT):
                loop.remove_signal_handler(signum)
            if stopping is not None:
                await asyncio.shield(stopping)

    try:
        result = asyncio.run(run())
    except (KeyboardInterrupt, asyncio.CancelledError):
        return 143 if interrupted == signal.SIGTERM else 130
    except ValueError as error:
        # 配置错误可能包含原始输入，只记录异常类别，不转储凭证或整个配置。
        logging.getLogger("vet3d").error("native_host_invalid_input reason=%s", type(error).__name__)
        return 2
    except (Exception, BaseExceptionGroup):
        logging.getLogger("vet3d").exception("native_host_failed")
        return 1
    try:
        sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    except (OSError, UnicodeError):
        logging.getLogger("vet3d").exception("native_host_result_delivery_failed")
        return 1
    terminal = result["turn"]
    if interrupted is not None:
        return 143 if interrupted == signal.SIGTERM else 130
    return 0 if isinstance(terminal, dict) and terminal.get("status") == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(agent_main())
