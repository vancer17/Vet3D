# 文件信息：L1-05 配置与本地基础设施的有限命令入口。
# 作用：由明确配置初始化或重开现有存储，验证实际装配并按顺序关闭。
# 边界：不是常驻 BFF、健康检查、执行沙箱或任务恢复服务。
"""提供 Docker 与独立安装共同使用的非交互装配探针。"""

import argparse
import asyncio
from collections.abc import Sequence
import json
import logging
from pathlib import Path
import signal
import sys
from typing import cast

from vet3d.bootstrap import (
    Settings, configure_logging, initialize_operations, load_settings, open_operations,
)


async def _probe(settings: Settings, *, initialize: bool) -> dict[str, object]:
    """执行有限真实装配，在取消或错误后排空实际资源。

    :param settings: 已通过统一入口解析的冻结环境配置。
    :param initialize: 明确的新存储初始化操作，默认重开既有存储。
    :returns: 仅描述实际装配与诊断交付的摘要。
    """
    factory = initialize_operations if initialize else open_operations
    runtime = await factory(settings)
    try:
        logging.getLogger("vet3d").info("operations_probe_observed")
        # 让已登记的取消在输出成功前被观察；此处不模拟业务任务。
        await asyncio.sleep(0)
    finally:
        cancelled = False
        while True:
            try:
                status = await runtime.aclose()
                break
            except asyncio.CancelledError:
                # 有限宿主不能在仍有诊断线程时退出事件循环；沿原关闭继续等待。
                cancelled = True
        if cancelled:
            raise asyncio.CancelledError
    return {
        "evidence": "local_storage_assembly",
        "operation": "initialize" if initialize else "open",
        "runtime_id": runtime.diagnostics.runtime_id,
        "quality_assessment": "not_run",
        "diagnostics": {
            "dropped_records": status.dropped_records,
            "write_error": status.write_error,
        },
    }


def operations_main(argv: Sequence[str] | None = None) -> int:
    """从显式 YAML 和可选 dotenv 启动一次本地装配。

    :param argv: 命令参数；不提供架构模式、供应商或业务资格开关。
    :returns: 成功零、失败一、SIGINT 一百三十、SIGTERM 一百四十三。
    """
    parser = argparse.ArgumentParser(description="初始化或重开 Vet3D 本地基础设施，完成后退出。")
    parser.add_argument("--config", type=Path, required=True, help="明确的 YAML 配置路径")
    parser.add_argument("--env-file", type=Path, help="可选的应用 dotenv 文件，不自动搜索当前目录")
    parser.add_argument("--initialize", action="store_true", help="显式初始化新存储；重开失败不会自动初始化")
    arguments = parser.parse_args(argv)
    configure_logging()
    received_signal: int | None = None

    async def run() -> dict[str, object]:
        """安装本次宿主的终止信号处理，取消原调用并让清理完成。

        :returns: 有限装配结果，不启动常驻服务。
        """
        loop = asyncio.get_running_loop()
        task = asyncio.current_task()
        assert task is not None

        def stop() -> None:
            """仅第一次 SIGTERM 取消原等待，不以反复取消破坏清理。"""
            nonlocal received_signal
            if received_signal is None:
                received_signal = signal.SIGTERM
                task.cancel()

        loop.add_signal_handler(signal.SIGTERM, stop)
        try:
            settings = load_settings(
                cast(Path, arguments.config), env_file=cast(Path | None, arguments.env_file),
            )
            return await _probe(settings, initialize=cast(bool, arguments.initialize))
        finally:
            loop.remove_signal_handler(signal.SIGTERM)

    try:
        summary = asyncio.run(run())
    except (KeyboardInterrupt, asyncio.CancelledError):
        return 143 if received_signal == signal.SIGTERM else 130
    except Exception as error:
        # 配置异常可能携带输入值，不转储 Settings、YAML 或凭据。
        logging.getLogger("vet3d").error("operations_probe_failed reason=%s", type(error).__name__)
        return 1
    try:
        sys.stdout.write(json.dumps(summary, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    except (OSError, UnicodeError):
        logging.getLogger("vet3d").exception("operations_probe_delivery_failed")
        return 1
    diagnostics = cast(dict[str, object], summary["diagnostics"])
    return 1 if diagnostics["write_error"] is not None or diagnostics["dropped_records"] != 0 else 0
