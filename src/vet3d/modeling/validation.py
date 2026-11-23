# 文件信息：L0-03 的建模引用和入选视图交接校验。
# 作用：核对任务范围、确切文件集合、重建必需方向和重复内容。
# 边界：只检查显式提供的数据，不读取图片、不判断同一个体或真实方向、不声明验收通过。
"""在无模型和宿主依赖时检查建模输入的确定性约束。"""

from vet3d.artifacts import FileReference, validate_file_set
from vet3d.identity import ArtifactId, ArtifactIdentity, TaskIdentity

from ._checks import ModelingContractError, require_type
from .references import ImageOperationReferences, SelectedViews, TaskReferences


def _validate_task(references: TaskReferences, task: TaskIdentity) -> None:
    """核对任务级参考确实属于本次提供的任务。

    :param references: 冻结的主体依据和业务要求。
    :param task: 已解析的任务身份与归属。
    :raises TypeError: 记录类型不符合契约。
    :raises ModelingContractError: 参考引用了其他任务。
    """
    require_type(references, TaskReferences)
    require_type(task, TaskIdentity)
    if references.task_id != task.id:
        raise ModelingContractError("任务参考与提供的任务身份不一致")


def _validate_files(
    expected: frozenset[ArtifactId],
    *,
    task: TaskIdentity,
    files: tuple[FileReference, ...],
    artifacts: tuple[ArtifactIdentity, ...],
) -> dict[ArtifactId, FileReference]:
    """核对本次所需图片引用的精确记录和任务范围。

    :param expected: 从角色引用单向取得的所需产物集合。
    :param task: 已核对的所属任务。
    :param files: 恰好覆盖所需产物的内容引用。
    :param artifacts: 与内容引用对应的身份记录。
    :returns: 当前校验内使用的文件引用索引，不持久保存。
    :raises TypeError: 记录结构类型错误。
    :raises ValueError: 文件集合、工作区或图片字节数不符合约束；保留文件层异常类型。
    """
    validate_file_set(files, artifacts=artifacts)
    index = {reference.artifact_id: reference for reference in files}
    if index.keys() != expected:
        raise ModelingContractError("提供的图片内容引用必须恰好覆盖本次所需身份")
    for artifact in artifacts:
        if artifact.workspace_id != task.workspace_id:
            raise ModelingContractError("图片引用必须属于任务工作区")
    if any(reference.content.byte_size == 0 for reference in files):
        raise ModelingContractError("图片内容描述必须为非零字节，不据此证明可以解码")
    return index


def validate_task_references(
    references: TaskReferences,
    *,
    task: TaskIdentity,
    files: tuple[FileReference, ...],
    artifacts: tuple[ArtifactIdentity, ...],
) -> None:
    """核对主体基准的确切内容引用，不执行主体识别。

    :param references: 任务级基准和要求，不含供应商参数。
    :param task: 已解析的所属任务。
    :param files: 主体基准的唯一内容引用。
    :param artifacts: 与该内容引用对应的身份记录。
    :raises TypeError: 传入结构类型错误。
    :raises ValueError: 任务、引用集合、工作区或图片描述不符合约束。
    """
    _validate_task(references, task)
    _validate_files(
        frozenset({references.subject_reference_id}), task=task, files=files, artifacts=artifacts,
    )


def validate_operation_references(
    operation: ImageOperationReferences,
    *,
    references: TaskReferences,
    task: TaskIdentity,
    files: tuple[FileReference, ...],
    artifacts: tuple[ArtifactIdentity, ...],
) -> None:
    """核对一次图像操作用图，允许主图与任务基准不同。

    :param operation: 操作主图、补充参考和目标方向。
    :param references: 任务拥有的主体基准及冻结要求。
    :param task: 已解析的所属任务。
    :param files: 基准、主图、补充参考并集的确切内容引用。
    :param artifacts: 与内容引用一一对应的身份记录。
    :raises TypeError: 传入结构类型错误。
    :raises ValueError: 任务、引用集合、工作区或图片描述不符合约束。
    """
    require_type(operation, ImageOperationReferences)
    _validate_task(references, task)
    expected = operation.supplementary_ids | frozenset({
        references.subject_reference_id, operation.main_image_id,
    })
    _validate_files(expected, task=task, files=files, artifacts=artifacts)


def validate_selected_views(
    selection: SelectedViews,
    *,
    references: TaskReferences,
    task: TaskIdentity,
    files: tuple[FileReference, ...],
    artifacts: tuple[ArtifactIdentity, ...],
) -> None:
    """核对入选视图的必需覆盖和独立内容，不把参考图静默转为重建图。

    :param selection: 明确区分重建与仅验收用途的入选结果。
    :param references: 任务主体基准、必保要求和必需重建方向。
    :param task: 已解析的所属任务。
    :param files: 基准和全部入选条目的确切内容引用并集。
    :param artifacts: 与内容引用一一对应的身份记录。
    :raises TypeError: 传入结构类型错误。
    :raises ValueError: 引用范围、必需方向、图片描述或重建内容独立性不满足。
    """
    require_type(selection, SelectedViews)
    _validate_task(references, task)
    expected = frozenset({references.subject_reference_id}) | frozenset(
        view.artifact_id for view in selection.reconstruction
    ) | frozenset(reference.artifact_id for reference in selection.review_only)
    index = _validate_files(expected, task=task, files=files, artifacts=artifacts)
    directions = frozenset(view.direction for view in selection.reconstruction)
    if not references.required_directions <= directions:
        raise ModelingContractError("入选重建图缺少必需方向，验收参考不能填补该缺口")
    contents = [index[view.artifact_id].content for view in selection.reconstruction]
    if len(set(contents)) != len(contents):
        raise ModelingContractError("同一确切内容不能通过不同身份重复充当重建方向")
