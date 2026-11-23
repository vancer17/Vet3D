# 文件信息：L0-04 的发布、加载与逐项保存确认记录。
# 作用：记录任务操作已确认的交接事实；执行失败、取消和等待结束归执行包。
# 边界：记录由生产者提供，不发起交接，不证明当前资源仍可用或业务质量合格。
"""定义没有成功布尔值或镜像阶段枚举的具体回执。"""

from dataclasses import dataclass
from typing import final

from vet3d.artifacts import ContentFingerprint, FileReference
from vet3d.identity import ArtifactId, AttemptId, ModelVersionId, ReviewTarget

from ._checks import DeliveryContractError, require_destination, require_target, require_type


@final
@dataclass(frozen=True, slots=True)
class PublicationReceipt:
    """记录发布服务确认的实际返回版本，不自动转移候选验收结论。

    :param attempt_id: 本次发布执行的身份，不是上游生成尝试。
    :param version_id: 已确认发布或复用的实际版本身份。
    """

    attempt_id: AttemptId
    version_id: ModelVersionId

    def __post_init__(self) -> None:
        """核对发布操作与实际版本的身份类别。"""
        require_type(self.attempt_id, AttemptId)
        require_type(self.version_id, ModelVersionId)


@final
@dataclass(frozen=True, slots=True)
class LoadReceipt:
    """记录一次实际加载确认，不表示列表选择或永久视窗就绪。

    :param attempt_id: 本次加载执行的身份，不是视窗或生成作业身份。
    :param target: 实际加载的确切文件集合或版本。
    """

    attempt_id: AttemptId
    target: ReviewTarget

    def __post_init__(self) -> None:
        """核对加载确认的操作身份与目标结构。"""
        require_type(self.attempt_id, AttemptId)
        require_target(self.target)


@final
@dataclass(frozen=True, slots=True)
class SaveTarget:
    """表达本次保存要求，不保存同义的源摘要字段。

    :param reference: 预期交给接收端的确切源内容。
    :param destination: 接收端范围内唯一目标的关联文字，不解析为路径或 URL。
    """

    reference: FileReference
    destination: str

    def __post_init__(self) -> None:
        """检查源引用及不透明目标文字，不证明地址存在。"""
        require_type(self.reference, FileReference)
        require_destination(self.destination)


@final
@dataclass(frozen=True, slots=True)
class SavedFile:
    """记录接收端确认的单项保存内容，允许保留不符合预期的观测。

    :param artifact_id: 此项保存所关联的源产物身份。
    :param destination: 接收端确认的目标关联，原文保留。
    :param observed: 接收端实际确认的字节描述，不冒充源文件的预期描述。
    """

    artifact_id: ArtifactId
    destination: str
    observed: ContentFingerprint

    def __post_init__(self) -> None:
        """核对逐项确认的身份、位置关联和内容结构。"""
        require_type(self.artifact_id, ArtifactId)
        require_destination(self.destination)
        require_type(self.observed, ContentFingerprint)


@final
@dataclass(frozen=True, slots=True)
class SaveReceipt:
    """保留同次保存中已经确认的各项，不预存整体完成状态。

    :param attempt_id: 本次实际保存执行的身份。
    :param saved: 已确认项目；可为空或为部分集合，不能重复占用同一目标。
    """

    attempt_id: AttemptId
    saved: tuple[SavedFile, ...]

    def __post_init__(self) -> None:
        """核对不可变确认集合，防止一个目标同时指向不同保存项。"""
        require_type(self.attempt_id, AttemptId)
        require_type(self.saved, tuple)
        destinations: set[str] = set()
        for item in self.saved:
            require_type(item, SavedFile)
            if item.destination in destinations:
                raise DeliveryContractError("保存回执包含重复目标")
            destinations.add(item.destination)
