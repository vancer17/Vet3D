# 文件信息：L0-03 的任务、单次操作与入选视图引用。
# 作用：分开维护主体基准、操作主图、重建视图及仅验收参考，复用产物身份。
# 边界：不存副本摘要、不绑定供应商、不判定图片内容或质量，不构造 BFF Command。
"""以具体冻结结构维护不同作用域的建模输入。"""

from dataclasses import dataclass
from typing import final

from vet3d.identity import ArtifactId, TaskId

from ._checks import ModelingContractError, require_set, require_text, require_type
from .directions import ViewDirection


@final
@dataclass(frozen=True, slots=True)
class TaskReferences:
    """固定任务级主体依据和业务要求，操作不重复声明这些事实。

    :param task_id: 所属业务任务。
    :param subject_reference_id: 主体基准的确切产物身份。
    :param preserve_features: 明确的必保要求原文，可为空，不表示质量已经确认。
    :param required_directions: 必须参与重建的方向，由业务要求提供，不由部署配置决定。
    """

    task_id: TaskId
    subject_reference_id: ArtifactId
    preserve_features: tuple[str, ...]
    required_directions: frozenset[ViewDirection]

    def __post_init__(self) -> None:
        """核对任务级输入，不推断要求是否充分或可被模型满足。"""
        require_type(self.task_id, TaskId)
        require_type(self.subject_reference_id, ArtifactId)
        require_type(self.preserve_features, tuple)
        for feature in self.preserve_features:
            require_text(feature)
        require_set(self.required_directions, ViewDirection)
        if not self.required_directions:
            raise ModelingContractError("静态照片重建必须明确至少一个必需方向")


@final
@dataclass(frozen=True, slots=True)
class ImageOperationReferences:
    """表达一次图像操作的引用，不改变任务级主体基准。

    :param main_image_id: 此次操作从哪份确切图片出发。
    :param supplementary_ids: 本次补充参考，不重复列出操作主图。
    :param target_direction: 本次希望产出的明确方向，不是输入图的观察方向。
    """

    main_image_id: ArtifactId
    supplementary_ids: frozenset[ArtifactId]
    target_direction: ViewDirection

    def __post_init__(self) -> None:
        """核对操作引用结构，避免主图在补充集合中重复声明。"""
        require_type(self.main_image_id, ArtifactId)
        require_set(self.supplementary_ids, ArtifactId)
        require_type(self.target_direction, ViewDirection)
        if self.main_image_id in self.supplementary_ids:
            raise ModelingContractError("操作主图不能再次列为同次补充参考")


@final
@dataclass(frozen=True, slots=True)
class ReconstructionView:
    """绑定一张入选重建图片与明确的业务方向。

    :param artifact_id: 此次参与重建的确切产物。
    :param direction: 已声明的观察方向；本项不证明像素与声明相符。
    """

    artifact_id: ArtifactId
    direction: ViewDirection

    def __post_init__(self) -> None:
        """核对重建图身份和必需方向，拒绝未知或裸字符串方向。"""
        require_type(self.artifact_id, ArtifactId)
        require_type(self.direction, ViewDirection)


@final
@dataclass(frozen=True, slots=True)
class ReviewReference:
    """保留仅供验收的参考，其方向未定也不丢弃引用。

    :param artifact_id: 此次仅用于验收的确切产物。
    :param direction: 已知方向；None 表示尚未确定，不是可提交的第六方向。
    """

    artifact_id: ArtifactId
    direction: ViewDirection | None = None

    def __post_init__(self) -> None:
        """核对验收参考结构，不把可选方向解释为重建覆盖。"""
        require_type(self.artifact_id, ArtifactId)
        if self.direction is not None:
            require_type(self.direction, ViewDirection)


@final
@dataclass(frozen=True, slots=True)
class SelectedViews:
    """表达一次入选结果，候选池与供应商槽位不属于本结构。

    :param reconstruction: 每方向至多一张的入选重建图。
    :param review_only: 仅用于验收的参考，不计入重建方向覆盖。
    """

    reconstruction: tuple[ReconstructionView, ...]
    review_only: tuple[ReviewReference, ...]

    def __post_init__(self) -> None:
        """拒绝重复条目和重复重建方向，不维护可漂移的数量字段。"""
        require_type(self.reconstruction, tuple)
        require_type(self.review_only, tuple)
        ids: set[ArtifactId] = set()
        directions: set[ViewDirection] = set()
        for view in self.reconstruction:
            require_type(view, ReconstructionView)
            if view.artifact_id in ids or view.direction in directions:
                raise ModelingContractError("重建视图不得重复产物或方向")
            ids.add(view.artifact_id)
            directions.add(view.direction)
        for reference in self.review_only:
            require_type(reference, ReviewReference)
            if reference.artifact_id in ids:
                raise ModelingContractError("同次入选产物不能重复列入仅验收参考")
            ids.add(reference.artifact_id)
