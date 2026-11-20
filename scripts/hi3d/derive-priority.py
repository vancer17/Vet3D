# 文件信息
# 从工作树加载基于发行锁的资源优先级派生命令。
"""提供 Hi3D 资源优先级的离线命令入口。"""

import sys
from pathlib import Path


def _run() -> int:
    """按仓库的 src 布局加载优先级命令并执行。

    :return: 命令退出码。
    """
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
    from vet3d.infrastructure.hi3d_inventory import priority_main
    return priority_main()


if __name__ == "__main__":
    raise SystemExit(_run())
