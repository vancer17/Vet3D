# 文件信息：L1-05 运维诊断包的公共入口。
# 作用：向宿主提供有限诊断读取契约与部署预算，不执行配置或日志初始化。
# 边界：这些记录只支持排障，不定义业务能力、执行终态和发布资格。
"""公开运维诊断的唯一数据类型与读取端口。"""

from .diagnostics import DiagnosticLimits, DiagnosticRead, DiagnosticReader, DiagnosticRecord, DiagnosticStatus

__all__ = ["DiagnosticLimits", "DiagnosticRead", "DiagnosticReader", "DiagnosticRecord", "DiagnosticStatus"]
