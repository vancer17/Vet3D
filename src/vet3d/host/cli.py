# 文件信息：L0-01 一次性非交互演示宿主。
# stdout 只交付演示回包，stderr 记录诊断；不提供 BFF API、人工确认或任务恢复。
"""将命令行输入映射到已装配的应用服务。"""

import argparse
import asyncio
from collections.abc import Sequence
import json
import logging
import sys
from typing import cast

from vet3d.application import DemoRequest, InvalidDemoRequest
from vet3d.bootstrap import (
    InvocationTimeoutError, build_demo_application, configure_logging, invoke_demo,
)


def main(argv: Sequence[str] | None = None) -> int:
    """运行一次明确的演示请求并向调用进程交付结果。

    :param argv: 命令行参数；为空时读取进程参数，不进行交互询问。
    :returns: 正常为零，输入错误为二，超时为一百二十四，取消为一百三十，其余失败为一。
    """
    parser = argparse.ArgumentParser(description="验证 Vet3D 装配骨架，不执行动物建模。")
    parser.add_argument("--text", required=True, help="一至二百五十六个字符的非空白 UTF-8 演示文本")
    arguments = parser.parse_args(argv)
    configure_logging()
    service = build_demo_application()
    request = DemoRequest(text=cast(str, arguments.text))
    try:
        reply = asyncio.run(invoke_demo(service, request))
    except InvalidDemoRequest:
        return 2
    except InvocationTimeoutError:
        return 124
    except (KeyboardInterrupt, asyncio.CancelledError):
        return 130
    except Exception:
        # 调用边界已记录异常；此处只投影退出码，不再次记录堆栈。
        return 1
    try:
        sys.stdout.write(json.dumps({"text": reply.text}, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    except (OSError, UnicodeError):
        logging.getLogger("vet3d").exception("demo_delivery_failed")
        return 1
    return 0
