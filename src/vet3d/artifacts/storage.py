# 文件信息：L1-02 原始文件保存与真实观察的同步 I/O 契约。
# 作用：固定工作区范围，复用既有产物身份、内容引用、位置和观察事实。
# 边界：不登记产物、不保存导入账本，不以文件写入或观察结果推导业务验收。
"""定义最小文件存储端口及无副作用的工作区关联校验。"""

from typing import BinaryIO, Protocol

from vet3d.identity import ArtifactIdentity, WorkspaceId

from ._checks import ArtifactContractError, _require_type
from .content import FileReference
from .locations import WorkspaceFileLocation
from .observations import FileObservation, FilePresent
from .validation import _require_artifact_id, validate_file_location, validate_file_reference


def validate_file_scope(
    artifact: ArtifactIdentity,
    *,
    workspace_id: WorkspaceId,
    reference: FileReference | None = None,
    location: WorkspaceFileLocation | None = None,
) -> None:
    """核对产物属于固定实例工作区，并校验可选引用的位置关联。

    本函数只验证显式关联，不读取工作区登记、不解析实际路径，也不证明
    调用方拥有该工作区权限；具体适配器另行核对派生位置和真实文件。

    :param artifact: 已由受信调用方提供的产物身份及唯一归属。
    :param workspace_id: 装配时固定的工作区身份，不从请求路径推断。
    :param reference: 可选的确切内容引用，提供时必须属于同一产物。
    :param location: 可选的相对位置，提供时必须属于同一产物。
    :raises TypeError: 任一提供的值不是现有契约的具体类型。
    :raises ArtifactContractError: 产物跨工作区或引用、位置指向其他产物。
    """
    _require_type(artifact, ArtifactIdentity)
    _require_type(workspace_id, WorkspaceId)
    if artifact.workspace_id != workspace_id:
        raise ArtifactContractError("产物不属于文件存储实例的工作区")
    if reference is not None:
        validate_file_reference(reference, artifact=artifact)
    if location is not None:
        _require_type(location, WorkspaceFileLocation)
        if reference is None:
            _require_artifact_id(location.artifact_id, artifact.id)
        else:
            validate_file_location(location, reference=reference)


class ArtifactFileStore(Protocol):
    """在实例固定范围内保存和观察字节，不提供登记查询或任意路径访问。"""

    def location_for(self, artifact: ArtifactIdentity) -> WorkspaceFileLocation:
        """从产物身份派生受管位置，不执行文件 I/O 或登记。

        :param artifact: 属于本实例固定工作区的产物身份。
        :returns: 与该产物绑定的派生相对位置，不证明文件已存在。
        :raises TypeError: 输入不是产物身份记录。
        :raises ArtifactContractError: 产物不属于固定工作区。
        """
        ...

    def store_new(
        self, artifact: ArtifactIdentity, reference: FileReference, source: BinaryIO,
    ) -> FilePresent:
        """复制并核对完整源字节后无覆盖提交，不把文件保存当作产物登记。

        源必须是已打开的可读普通文件；调用期间借用其文件描述符，从文件
        起点读取，不改变调用方游标或关闭源。调用方保留所有权，期间不得
        并发修改源。具体适配器负责限额、真实类型核对及提交后的同步。
        已有最终目标不得覆盖；异常仍可能留下待对账的文件副作用。

        :param artifact: 属于本实例固定工作区的新产物身份。
        :param reference: 绑定该身份的预期完整内容指纹。
        :param source: 调用方持有的已打开普通文件，不以出处标签作为读取入口。
        :returns: 已保存位置及实际取得的匹配指纹，不证明登记、验收或发布。
        :raises TypeError: 关联值或输入对象不符合具体类型要求。
        :raises ArtifactContractError: 作用域、内容关联或实际源内容不匹配。
        :raises OSError: 文件访问、无覆盖提交或同步失败，保留原身份对账。
        """
        ...

    def observe(
        self, artifact: ArtifactIdentity, location: WorkspaceFileLocation,
    ) -> FileObservation:
        """核对固定作用域和派生位置后读取实际文件，不比较预期内容。

        :param artifact: 此位置所属产物及其唯一工作区归属。
        :param location: 需要观察的确切位置，须符合本实例的受管布局。
        :returns: 实际存在指纹、已确认缺失或访问不可用；不声明观察长期有效。
        :raises TypeError: 输入不是现有具体身份或位置类型。
        :raises ArtifactContractError: 作用域、产物或受管位置不匹配。
        """
        ...
