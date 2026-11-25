# 文件信息：Vet3D 选型实验的具体消费者入口。
# 作用：公开阶段 A 可复跑实验所需的材料和协议组件。
# 边界：不是产品 Agent 端口；实验结果不能替代业务验收或生产选型。
"""提供范围受限的原生 Agent 接入实验组件。"""

from vet3d.adapters import CodexDockerEnvironment
from .native_agent_resources import TaskMaterials, prepare_task_materials
from vet3d.adapters import (
    AppServerStdioClient, JsonValue, NativeMessage, NativeProtocolError,
    NativeResponseError, NativeSessionBinding, validate_model_selection,
)
from .native_agent_run import TurnObservation, run_native_turn

__all__ = [
    "CodexDockerEnvironment", "AppServerStdioClient", "JsonValue", "NativeMessage", "NativeProtocolError",
    "NativeResponseError", "NativeSessionBinding", "TaskMaterials", "prepare_task_materials",
    "TurnObservation", "run_native_turn", "validate_model_selection",
]
