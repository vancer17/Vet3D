# 文件信息
# 统一暴露发行盘点、抽离和优先级清单、原件归档的命令入口。
"""公开 Hi3D 安装资源盘点包的命令入口。"""

from .cli import main
from .archive import archive_main
from .extraction import extraction_main
from .priority import priority_main

__all__ = ["archive_main", "extraction_main", "main", "priority_main"]
