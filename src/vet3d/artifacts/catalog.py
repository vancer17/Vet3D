# 文件信息：L1-04 单资产持久登记的消费方契约。
# 作用：复用产物、内容、位置和出处的唯一类型，限定仓储实例的工作区范围。
# 边界：不创建批次或登记意图，不访问文件，不将登记等同于文件可读或业务通过。
"""声明不可变单资产登记边界，由可信服务核对实际文件后调用仓储。"""

from typing import Protocol

from vet3d.identity import ArtifactId, WorkspaceId

from ._checks import ArtifactContractError, _require_type
from .ports import LocatedArtifact
from .provenance import ImportOrigin
from .storage import validate_file_scope
from .validation import validate_import_origin


class ArtifactRegistrationConflict(ArtifactContractError):
    """表示已有产物身份绑定了不同登记字段，不能覆盖或重新认领。"""


def validate_registration(
    record: LocatedArtifact, *, workspace_id: WorkspaceId, origin: ImportOrigin | None = None,
) -> None:
    """核对单资产声明属于固定工作区，并关联实际提供的出处说明。

    本校验没有磁盘副作用；通过仅说明输入关联合法，实际字节须由可信
    消费服务另行观察。未提供出处保持未知，不推导原件或派生件类别。

    :param record: 本次准备登记或读回的唯一身份、内容及位置组合。
    :param workspace_id: 仓储或消费者在装配时固定的工作区身份。
    :param origin: 实际已知的导入出处，可为空，不充当文件读取地址。
    :raises TypeError: 输入不是规定的具体记录或身份类型。
    :raises ArtifactContractError: 记录跨工作区，或出处属于另一产物。
    """
    _require_type(record, LocatedArtifact)
    validate_file_scope(
        record.artifact, workspace_id=workspace_id,
        reference=record.reference, location=record.location,
    )
    if origin is not None:
        validate_import_origin(origin, reference=record.reference)


class ArtifactRepository(Protocol):
    """声明固定工作区内的单资产持久登记，不持有文件观察或批次状态。

    仓储保留不可变登记字段及实际提供的出处。单件事务提交即为登记事实，
    不再保存 registered、ready 或文件存在的镜像字段。
    """

    def get(self, artifact_id: ArtifactId) -> LocatedArtifact | None:
        """读取确切产物的已提交登记，查询失败不得降级为未登记。

        :param artifact_id: 本次要解析的唯一产物身份。
        :returns: 本工作区的登记记录，或确实没有记录时的空值。
        :raises ArtifactContractError: 已知记录属于其他工作区。
        """
        ...

    def register(
        self, record: LocatedArtifact, *, origin: ImportOrigin | None = None,
    ) -> LocatedArtifact:
        """原子登记单个资产，完全相同的重放读回，任何字段变化拒绝覆盖。

        可信服务须在首次登记前核对实际文件；仓储不接收验证布尔值，也不
        声称自己进行了文件观察。出处同样属于原登记字段，未知与已提供的
        说明不能在重放中互相替换。多资产调用允许逐件提交及部分完成。

        :param record: 本次确切的产物身份、内容引用及受管位置。
        :param origin: 此产物实际已知的导入出处，不提供时保持未知。
        :returns: 首次提交的登记，或已有且全部登记字段相同的原记录。
        :raises ArtifactRegistrationConflict: 同一产物身份已有不同登记字段或出处。
        :raises ArtifactContractError: 输入或工作区不满足登记前提。
        """
        ...

    def get_origin(self, artifact_id: ArtifactId) -> ImportOrigin | None:
        """读取已保存的原出处声明，不由无出处推断登记情况或来源类别。

        :param artifact_id: 需要查询出处的确切产物身份。
        :returns: 原出处说明，或没有保存该说明时的空值；登记情况由 get 查询。
        :raises ArtifactContractError: 已知记录属于其他工作区。
        """
        ...
