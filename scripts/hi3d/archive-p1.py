# 文件信息
# 加载基础设施中的归档命令并选用锁定的 P1 批次。
"""提供 Hi3D P1 原件抽离的命令行入口。"""

import sys
from pathlib import Path


def _run() -> int:
    """从 src 布局加载 P1 原件归档命令并执行。

    :return: 归档命令的进程退出码。
    """
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
    from vet3d.infrastructure.hi3d_inventory import archive_main
    return archive_main(level="P1")


if __name__ == "__main__":
    raise SystemExit(_run())
