# 文件信息：L0-04 报告与验收事实的公共入口。
# 作用：公开具体冻结声明、缺项派生和交接守卫，供后续服务使用。
# 边界：不初始化环境、日志、解析器或模型，不注册供应商和运行端口。
"""公开报告完整性与有范围的验收结果，保持事实及身份各自唯一。"""

from ._checks import AssessmentContractError
from .acceptance import (
    AcceptanceOutcome,
    AcceptanceScope,
    AcceptanceVerdict,
    require_accepted,
    validate_acceptance_outcome,
)
from .reports import (
    ReportAssessment,
    ReportRequirements,
    missing_report_sections,
    require_complete_report,
    validate_attempt_report,
    validate_report_reference,
)

__all__ = [
    "AssessmentContractError",
    "AcceptanceOutcome",
    "AcceptanceScope",
    "AcceptanceVerdict",
    "require_accepted",
    "validate_acceptance_outcome",
    "ReportAssessment",
    "ReportRequirements",
    "missing_report_sections",
    "require_complete_report",
    "validate_attempt_report",
    "validate_report_reference",
]
