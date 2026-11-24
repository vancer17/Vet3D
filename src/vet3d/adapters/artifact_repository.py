# 文件信息：L1-04 已登记单资产的真实 SQLite 仓储。
# 作用：复用工作区数据库生命周期，以短事务保存唯一内容绑定和可选出处。
# 边界：不读取文件、不建立批次或登记意图；实际字节由可信消费服务另行验证。
"""实现固定工作区的资产登记与读回，保留文件事实和元数据事实的区别。"""

from typing import TYPE_CHECKING, final

from sqlalchemy.orm import Session

from vet3d.artifacts import (
    ArtifactContractError, ArtifactRegistrationConflict, ArtifactRepository,
    ContentFingerprint, FileReference, ImportOrigin, LocatedArtifact,
    WorkspaceFileLocation, WorkspaceRelativePath, validate_registration,
)
from vet3d.identity import ArtifactId, ArtifactIdentity, WorkspaceId
from .workspace_tables import ArtifactRow

if TYPE_CHECKING:
    from .workspace_repository import SqliteWorkspaceRepository


def _located_from_row(row: ArtifactRow) -> LocatedArtifact:
    """从唯一持久字段重建既有类型，损坏数据通过现行契约明确失败。

    :param row: 当前短事务中的单资产行。
    :returns: 不含文件可用性声明的定位记录。
    """
    artifact_id = ArtifactId.parse(row.id)
    return LocatedArtifact(
        ArtifactIdentity(artifact_id, WorkspaceId.parse(row.workspace_id)),
        FileReference(artifact_id, ContentFingerprint(row.sha256, row.byte_size)),
        WorkspaceFileLocation(artifact_id, WorkspaceRelativePath(row.relative_path)),
    )


def _origin_from_row(row: ArtifactRow) -> ImportOrigin | None:
    """恢复原出处说明，不用无说明推断原件、派生或登记状态。

    :param row: 当前短事务中的原资产行。
    :returns: 实际保存的出处或明确未提供时的空值。
    """
    return None if row.source_label is None else ImportOrigin(ArtifactId.parse(row.id), row.source_label)


@final
class SqliteArtifactRepository(ArtifactRepository):
    """固定工作区的具体仓储，共享原工作区仓储的线程和生命周期。

    :param owner: 可信装配已经初始化或打开的唯一数据库所有者。
    :param workspace_id: 之后各次操作不能改变的工作区身份。
    """

    def __init__(self, owner: "SqliteWorkspaceRepository", workspace_id: WorkspaceId) -> None:
        """绑定既有所有者，不另外创建 Engine、根锁或数据库文件。

        :param owner: 同线程的原数据库所有者。
        :param workspace_id: 实例固定的工作区身份。
        :raises TypeError: 工作区身份类型错误。
        """
        if type(workspace_id) is not WorkspaceId:
            raise TypeError("资产仓储需要 WorkspaceId")
        self._owner = owner
        self._workspace_id = workspace_id

    def _get_row(self, session: Session, artifact_id: ArtifactId) -> ArtifactRow | None:
        """读取真实主键并核对固定归属，不把跨区记录伪装成未登记。

        :param session: 本次独立短事务。
        :param artifact_id: 本次要取得的原产物身份。
        :returns: 属于实例工作区的行或真正缺行时的空值。
        :raises TypeError: 产物身份类型错误。
        :raises ArtifactContractError: 已知产物属于其他工作区。
        """
        if type(artifact_id) is not ArtifactId:
            raise TypeError("资产查询需要 ArtifactId")
        self._owner._require_registered_workspace(session, self._workspace_id)
        row = session.get(ArtifactRow, str(artifact_id.value))
        if row is not None:
            validate_registration(
                _located_from_row(row), workspace_id=self._workspace_id, origin=_origin_from_row(row),
            )
        return row

    def get(self, artifact_id: ArtifactId) -> LocatedArtifact | None:
        """读取确切资产的已提交登记，数据库错误不降级为缺失。

        :param artifact_id: 唯一产物身份。
        :returns: 原定位记录或确实缺行时的空值，不证明文件存在。
        """
        with self._owner._transaction() as session:
            row = self._get_row(session, artifact_id)
            result = None if row is None else _located_from_row(row)
        return result

    def register(
        self, record: LocatedArtifact, *, origin: ImportOrigin | None = None,
    ) -> LocatedArtifact:
        """原子保存单资产，同身份同全部字段只读回，任何改参均拒绝。

        :param record: 已由可信消费服务核对实际字节的确切登记声明。
        :param origin: 实际已知的原出处；不提供时保持未知。
        :returns: 首次提交的记录或已经提交的同参记录。
        :raises ArtifactRegistrationConflict: 同一身份的内容、位置或出处发生变化。
        :raises ArtifactContractError: 输入或归属不符合当前契约。
        """
        validate_registration(record, workspace_id=self._workspace_id, origin=origin)
        with self._owner._transaction() as session:
            row = self._get_row(session, record.artifact.id)
            if row is None:
                session.add(ArtifactRow(
                    id=str(record.artifact.id.value), workspace_id=str(self._workspace_id.value),
                    relative_path=record.location.relative_path.value,
                    sha256=record.reference.content.sha256, byte_size=record.reference.content.byte_size,
                    source_label=None if origin is None else origin.source_label,
                ))
                result = record
            else:
                result = _located_from_row(row)
                if result != record or _origin_from_row(row) != origin:
                    raise ArtifactRegistrationConflict("同一产物身份不能改变原登记字段或出处")
        return result

    def get_origin(self, artifact_id: ArtifactId) -> ImportOrigin | None:
        """读取原出处声明，不借缺少出处推断登记或原件类别。

        :param artifact_id: 原产物身份。
        :returns: 已存说明，或未存该说明时的空值；登记情况由 get 单独查询。
        """
        with self._owner._transaction() as session:
            row = self._get_row(session, artifact_id)
            origin = None if row is None else _origin_from_row(row)
        return origin
