# 文件信息：L0-05 产物元数据解析与文件观察的最小消费方端口。
# 作用：组合既有归属、内容和位置记录；分开元数据登记与实际文件观察。
# 边界：只声明替换接口，不读取文件、不计算摘要、不装配存储或路径解析器。
"""为消费方提供明确的解析结果及独立观察入口。"""

from dataclasses import dataclass
from typing import Protocol, final

from vet3d.identity import ArtifactId, ArtifactIdentity

from .content import FileReference
from .locations import WorkspaceFileLocation
from .observations import FileObservation
from .validation import validate_file_location, validate_file_reference


@final
@dataclass(frozen=True, slots=True)
class LocatedArtifact:
    """组合已登记产物的归属、内容与位置，不声明该位置的文件存在。

    :param artifact: 产物身份及工作区归属的既有权威记录。
    :param reference: 此产物绑定的确切内容引用。
    :param location: 此产物已登记的工作区相对位置。
    """

    artifact: ArtifactIdentity
    reference: FileReference
    location: WorkspaceFileLocation

    def __post_init__(self) -> None:
        """复用既有纯校验核对三个具体记录的身份关联。

        :raises TypeError: 任一字段不是规定的具体类型。
        :raises ArtifactContractError: 归属、内容引用或位置属于不同产物。
        """
        validate_file_reference(self.reference, artifact=self.artifact)
        validate_file_location(self.location, reference=self.reference)


class ArtifactAccess(Protocol):
    """声明消费方需要的元数据解析及文件观察，不把两项事实合并。"""

    async def resolve(self, artifact_id: ArtifactId) -> LocatedArtifact | None:
        """解析确切产物的登记记录，不根据文件访问结果猜测登记情况。

        返回的记录必须属于所请求的产物。None 只表示该身份尚未登记，
        不表示磁盘文件缺失；解析失败须传播异常，不得转换为未登记。

        :param artifact_id: 本次需要解析的确切产物身份。
        :returns: 属于该身份的登记记录；未登记时返回 None。
        """
        ...

    async def observe(self, location: WorkspaceFileLocation) -> FileObservation:
        """观察给定位置，保留存在、缺失或访问不可用的独立事实。

        观察必须关联所请求的位置；存在时保留实际取得的内容指纹，
        不比较预期内容。消费方另用 require_matching_file 核对交接。

        :param location: 本次需要观察的确切工作区位置。
        :returns: 此位置的文件观察，不证明图片可解码或业务质量合格。
        """
        ...
