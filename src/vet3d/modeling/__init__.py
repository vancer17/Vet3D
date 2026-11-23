# 文件信息：L0-03 建模输入及空间约定的公共入口。
# 作用：为后续服务、适配器和测试公开唯一业务方向、引用与纯校验。
# 边界：不导入供应商 SDK，不注册 Tool 或模型能力，不初始化宿主或日志。
"""公开中性的照片引用、入选视图和规范空间语义。"""

from ._checks import ModelingContractError
from .directions import ViewDirection
from .references import (
    ImageOperationReferences, ReconstructionView, ReviewReference, SelectedViews, TaskReferences,
)
from .spatial import CameraOrientation, SourceScale, camera_orientation, to_metres
from .validation import (
    validate_operation_references, validate_selected_views, validate_task_references,
)

__all__ = [
    "ModelingContractError", "ViewDirection", "TaskReferences", "ImageOperationReferences",
    "ReconstructionView", "ReviewReference", "SelectedViews", "CameraOrientation", "SourceScale",
    "camera_orientation", "to_metres", "validate_task_references",
    "validate_operation_references", "validate_selected_views",
]
