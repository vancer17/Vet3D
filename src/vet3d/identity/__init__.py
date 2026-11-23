# 文件信息：L0-02 身份与关联包的公共入口。
# 作用：集中暴露唯一身份类型、关系对象及纯校验函数，供跨包消费者使用。
# 边界：导入不装配宿主、不读取环境或存储，不注册 Tool、状态或模型能力。
"""公开稳定业务身份及局部关联契约。"""

from .identifiers import (
    AcceptanceId, ArtifactId, AttemptId, EvidenceId, JobId, ModelFamilyId,
    ModelVersionId, SessionId, TaskId, TurnId, WorkspaceId,
)
from .relations import (
    AcceptanceIdentity, ArtifactIdentity, ArtifactSetTarget, AttemptIdentity,
    AttemptOutput, Derivation, EvidenceIdentity, IdentityRelationError,
    JobIdentity, ModelFamilyIdentity, ModelVersionIdentity, ModelVersionTarget,
    ReviewTarget, SessionIdentity, TaskIdentity, TurnIdentity,
)
from .validation import (
    validate_acceptance, validate_artifact_target, validate_attempt,
    validate_attempt_output, validate_derivation, validate_job,
    validate_model_version, validate_session, validate_turn, validate_version_target,
)

__all__ = [
    "AcceptanceId", "ArtifactId", "AttemptId", "EvidenceId", "JobId",
    "ModelFamilyId", "ModelVersionId", "SessionId", "TaskId", "TurnId", "WorkspaceId",
    "AcceptanceIdentity", "ArtifactIdentity", "ArtifactSetTarget", "AttemptIdentity",
    "AttemptOutput", "Derivation", "EvidenceIdentity", "IdentityRelationError",
    "JobIdentity", "ModelFamilyIdentity", "ModelVersionIdentity", "ModelVersionTarget",
    "ReviewTarget", "SessionIdentity", "TaskIdentity", "TurnIdentity",
    "validate_acceptance", "validate_artifact_target", "validate_attempt",
    "validate_attempt_output", "validate_derivation", "validate_job",
    "validate_model_version", "validate_session", "validate_turn", "validate_version_target",
]
