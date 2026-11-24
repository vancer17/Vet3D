# 文件信息：L1-05 基础设施与 L2-01 环境核对的有限命令入口。
# 作用：从明确配置打开存储，按需核对固定资源环境并排空实际资源。
# 边界：不是常驻 BFF、健康检查、执行沙箱或任务恢复服务。
"""提供 Docker 与独立安装共同使用的非交互装配探针。"""

import argparse
import asyncio
from collections.abc import Sequence
from dataclasses import asdict
import json
import logging
from pathlib import Path
import signal
import sys
from typing import cast

from vet3d.bootstrap import (
    Settings, configure_logging, initialize_operations, load_settings, open_operations,
)
from vet3d.artifacts import ContentFingerprint
from vet3d.operations import EnvironmentReport, ProbeFailure, RequirementStatus
from vet3d.resources import ResourceKey, ResourceReference


def _environment_summary(report: EnvironmentReport) -> dict[str, object]:
    """只向控制台投影原环境记录，输出字段不参与内部决策。

    :param report: 已完成的有限检查，不是任务或业务验收记录。
    :returns: 保留原资源、运行关联及未覆盖范围的 JSON 可编码值。
    """
    return {
        "root": asdict(report.root),
        "runtime_id": report.runtime_id,
        "observed_at": report.observed_at.isoformat(),
        "status": report.status.value,
        "checks": [{
            "resource": asdict(check.resource),
            "status": check.status.value,
            "issues": check.issues,
            "observation": asdict(check.evidence) if check.evidence is not None
            and not isinstance(check.evidence, ProbeFailure) else None,
            "failure": check.evidence.reason if isinstance(check.evidence, ProbeFailure) else None,
        } for check in report.checks],
        "scope": "trusted_fixed_cpu_probes",
        "unverified": ["gpu", "untrusted_execution_isolation", "animal_quality"],
    }


async def _probe(
    settings: Settings, *, initialize: bool, reference: ResourceReference | None = None,
) -> dict[str, object]:
    """执行有限真实装配，在取消或错误后排空实际资源。

    :param settings: 已通过统一入口解析的冻结环境配置。
    :param initialize: 明确的新存储初始化操作，默认重开既有存储。
    :param reference: 显式选定的原资源；为空时仅检查既有基础设施装配。
    :returns: 仅描述实际装配与诊断交付的摘要。
    """
    factory = initialize_operations if initialize else open_operations
    runtime = await factory(settings)
    environment: EnvironmentReport | None = None
    try:
        if reference is not None:
            environment = await runtime.check_environment(reference)
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
    summary: dict[str, object] = {
        "evidence": "local_storage_assembly",
        "operation": "initialize" if initialize else "open",
        "runtime_id": runtime.diagnostics.runtime_id,
        "quality_assessment": "not_run",
        "diagnostics": {
            "dropped_records": status.dropped_records,
            "write_error": status.write_error,
        },
    }
    if environment is not None:
        summary["evidence"] = "resource_environment_observation"
        summary["environment"] = _environment_summary(environment)
    return summary


def operations_main(argv: Sequence[str] | None = None) -> int:
    """从显式 YAML 和可选 dotenv 启动一次本地装配。

    :param argv: 命令参数；不提供架构模式、供应商或业务资格开关。
    :returns: 成功零、失败一、SIGINT 一百三十、SIGTERM 一百四十三。
    """
    parser = argparse.ArgumentParser(description="打开 Vet3D 基础设施并按需核对固定资源环境，完成后退出。")
    parser.add_argument("--config", type=Path, required=True, help="明确的 YAML 配置路径")
    parser.add_argument("--env-file", type=Path, help="可选的应用 dotenv 文件，不自动搜索当前目录")
    parser.add_argument("--initialize", action="store_true", help="显式初始化新存储；重开失败不会自动初始化")
    parser.add_argument("--check-environment", metavar="RESOURCE_KEY", help="核对已安装快照中的资源及依赖要求")
    parser.add_argument("--snapshot-sha256", help="检查所需的确切资源清单摘要")
    parser.add_argument("--snapshot-size", type=int, help="检查所需的确切资源清单字节数")
    arguments = parser.parse_args(argv)
    selected = (arguments.check_environment, arguments.snapshot_sha256, arguments.snapshot_size)
    if any(item is not None for item in selected) and not all(item is not None for item in selected):
        parser.error("环境检查必须同时指定资源键、快照摘要及字节数")
    if arguments.initialize and arguments.check_environment is not None:
        parser.error("环境检查只读取已安装的固定快照，不能与新存储初始化组合")
    reference: ResourceReference | None = None
    if arguments.check_environment is not None:
        try:
            reference = ResourceReference(
                ContentFingerprint(cast(str, arguments.snapshot_sha256), cast(int, arguments.snapshot_size)),
                ResourceKey(cast(str, arguments.check_environment)),
            )
        except (TypeError, ValueError) as error:
            parser.error(str(error))
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
            return await _probe(settings, initialize=cast(bool, arguments.initialize), reference=reference)
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
    if "environment" in summary:
        environment = cast(dict[str, object], summary["environment"])
        if environment["status"] != RequirementStatus.SATISFIED.value:
            return 1
    return 1 if diagnostics["write_error"] is not None or diagnostics["dropped_records"] != 0 else 0
