# 文件信息：L0-03 与 L0-05 建模准备、生成端口及空间约定的公共入口。
# 作用：公开唯一业务方向、准备与调用引用、纯校验和重建依赖接口。
# 边界：不导入供应商 SDK，不注册 Tool 或模型能力，不初始化宿主或日志。
"""公开中性的照片准备、单次生成交接和规范空间语义。"""

from ._checks import ModelingContractError
from .directions import ViewDirection
from .generation import (
    CapabilityUnverified, GeneratedArtifact, GenerationPlan, ReconstructionRequest,
    ReconstructionUpdate, SubmissionCompatible,
)
from .ports import ReconstructionPort
from .references import (
    ImageOperationReferences, PreparedView, PreparedViews, ReviewReference, TaskReferences,
)
from .spatial import CameraOrientation, SourceScale, camera_orientation, to_metres
from .validation import (
    validate_operation_references, validate_prepared_views, validate_task_references,
)

__all__ = [
    "ModelingContractError", "ViewDirection", "TaskReferences", "ImageOperationReferences",
    "PreparedView", "ReviewReference", "PreparedViews", "CameraOrientation", "SourceScale",
    "camera_orientation", "to_metres", "validate_task_references",
    "validate_operation_references", "validate_prepared_views", "GenerationPlan",
    "ReconstructionRequest", "GeneratedArtifact", "ReconstructionUpdate", "SubmissionCompatible",
    "CapabilityUnverified", "ReconstructionPort",
]
