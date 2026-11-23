# 文件信息
# 从仓库根目录定位源码并调用统一的只读盘点入口。
"""提供从仓库根目录启动 Hi3D 盘点的命令入口。

入口定位仓库的 src 目录，具体行为由基础设施包统一维护。
"""

import sys
from pathlib import Path


def _run() -> int:
    """加载仓库内的盘点命令并传回执行状态。

    :return: 盘点命令的退出码。
    """
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
    from vet3d.infrastructure.hi3d_inventory import main

    return main()


if __name__ == "__main__":
    raise SystemExit(_run())
