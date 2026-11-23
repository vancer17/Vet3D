# 文件信息：L0-04 任务内交接契约的公共入口。
# 作用：暴露确认回执与局部守卫，不装配服务，不引入全局交付状态。
"""公开发布、加载和保存事实，独立于质量结论及执行终态。"""

from ._checks import DeliveryContractError
from .receipts import LoadReceipt, PublicationReceipt, SavedFile, SaveReceipt, SaveTarget
from .validation import (
    require_complete_save, require_current_load, validate_publication_receipt, validate_save_receipt,
)

__all__ = [
    "DeliveryContractError", "LoadReceipt", "PublicationReceipt", "SavedFile", "SaveReceipt",
    "SaveTarget", "require_complete_save", "require_current_load",
    "validate_publication_receipt", "validate_save_receipt",
]
