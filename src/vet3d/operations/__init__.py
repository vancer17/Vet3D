# 文件信息：L1-05 诊断与 L2-01 环境核对包的公共入口。
# 作用：向宿主提供有限诊断、环境观察和需求核对，不执行配置或日志初始化。
# 边界：这些记录只支持排障，不定义业务能力、执行终态和发布资格。
"""公开运维观察的唯一数据类型、真实替换端口和具体核对服务。"""

from .diagnostics import DiagnosticLimits, DiagnosticRead, DiagnosticReader, DiagnosticRecord, DiagnosticStatus
from .environment import (
    EnvironmentCheckService, EnvironmentObservation, EnvironmentProbe, EnvironmentReport,
    ProbeError, ProbeFailure, ProbeLimits, RequirementStatus, ResourceEnvironmentCheck,
    supported_dependencies,
)

__all__ = [
    "DiagnosticLimits", "DiagnosticRead", "DiagnosticReader", "DiagnosticRecord", "DiagnosticStatus",
    "EnvironmentCheckService", "EnvironmentObservation", "EnvironmentProbe", "EnvironmentReport",
    "ProbeError", "ProbeFailure", "ProbeLimits", "RequirementStatus", "ResourceEnvironmentCheck",
    "supported_dependencies",
]
