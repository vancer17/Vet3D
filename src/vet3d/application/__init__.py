# 文件信息：L0-01 演示与 L0-05 最小生成用例的公共入口。
# 统一导出具体服务和消费方仓储端口；不装配适配器、环境或 BFF。
"""公开可独立测试的应用服务及其记录契约。"""

from .demo import (
    DemoPort,
    DemoReply,
    DemoRequest,
    DemoService,
    InvalidDemoReply,
    InvalidDemoRequest,
)
from .reconstruction import ReconstructionRecordingError, ReconstructionService
from .reconstruction_records import (
    ReconstructionConflict, ReconstructionEvent, ReconstructionRecord,
    ReconstructionRepository, apply_reconstruction_event,
)

__all__ = [
    "DemoPort", "DemoReply", "DemoRequest", "DemoService",
    "InvalidDemoReply", "InvalidDemoRequest",
    "ReconstructionConflict", "ReconstructionEvent", "ReconstructionRecord",
    "ReconstructionRecordingError", "ReconstructionRepository", "ReconstructionService",
    "apply_reconstruction_event",
]
