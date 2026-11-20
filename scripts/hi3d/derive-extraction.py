# 文件信息
# 定位仓库源码并运行发行锁到抽离清单的派生命令。
"""提供从仓库执行 Hi3D 抽离清单派生的入口。"""

import sys
from pathlib import Path


def _run() -> int:
    """运行仓库内的抽离清单命令并传回状态。

    :return: 派生命令的进程退出码。
    """
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
    from vet3d.infrastructure.hi3d_inventory import extraction_main
    return extraction_main()


if __name__ == "__main__":
    raise SystemExit(_run())
