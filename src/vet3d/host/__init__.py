# 文件信息：演示、生成契约及 L1-05 基础设施探针的非交互宿主公共入口。
# 作用：公开有限安装命令；导入时不启动事件循环或进行装配。
# 边界：不提供 BFF API、真实模型或持久任务恢复。
"""公开演示和合成契约探针的安装入口。"""

from .cli import main
from .probe import probe_main
from .operations import operations_main
from .agent import agent_main

__all__ = ["main", "probe_main", "operations_main", "agent_main"]
