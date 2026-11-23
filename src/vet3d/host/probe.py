# 文件信息：L0-05 非交互契约探针命令。
# 作用：输出两种替身装配的读回摘要；stderr 由 Bootstrap 管理诊断。
# 边界：不提供供应商选择开关、BFF API、真实文件生成或业务质量结论。
"""从独立安装包运行一次有限的合成契约验证。"""

import argparse
import asyncio
from collections.abc import Sequence
import json
import logging
import sys

from vet3d.bootstrap import InvocationTimeoutError, configure_logging, run_reconstruction_probe


def probe_main(argv: Sequence[str] | None = None) -> int:
    """运行契约探针并交付明确标注合成证据的 JSON 摘要。

    :param argv: 可选命令参数；本入口只有帮助选项，不进行人工交互。
    :returns: 成功为零，超时一百二十四，取消一百三十，其他失败为一。
    """
    parser = argparse.ArgumentParser(description="运行合成生成契约探针，不生成真实动物模型。")
    parser.parse_args(argv)
    configure_logging()
    try:
        results = asyncio.run(run_reconstruction_probe())
    except InvocationTimeoutError:
        return 124
    except (KeyboardInterrupt, asyncio.CancelledError):
        return 130
    except Exception:
        return 1
    summary = {
        "evidence": "synthetic_contract_probe",
        "quality_assessment": "not_run",
        "runs": [
            {
                "attempt_id": str(result.request.attempt.id.value),
                "prepared_directions": [view.direction.value for view in result.request.prepared.views],
                "selected_directions": [
                    next(view.direction.value for view in result.request.prepared.views if view.artifact_id == artifact_id)
                    for artifact_id in result.request.plan.input_ids
                ],
                "observation": type(result.observation).__name__,
                "output_ids": [str(output.artifact.id.value) for output in result.outputs],
            }
            for result in results
        ],
    }
    try:
        sys.stdout.write(json.dumps(summary, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    except (OSError, UnicodeError):
        logging.getLogger("vet3d").exception("contract_probe_delivery_failed")
        return 1
    return 0
