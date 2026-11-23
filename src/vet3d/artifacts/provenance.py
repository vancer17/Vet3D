# 文件信息：L0-03 的导入出处说明。
# 边界：仅记录实际已知说明；派生和执行产出关系继续由 L0-02 的既有类型维护。
"""关联产物与导入出处，不把说明转换为可读取地址。"""

from dataclasses import dataclass
from typing import final

from vet3d.identity import ArtifactId

from ._checks import _require_type, _require_utf8_text


@final
@dataclass(frozen=True, slots=True)
class ImportOrigin:
    """保存调用方实际已知的导入出处，不保证来源真实或完整。

    标签只保留原文；存在出处记录不等于文件可读取或内容已经通过校验。

    :param artifact_id: 该说明所属的产物身份。
    :param source_label: 非空 UTF-8 出处说明，不作为文件定位入口。
    """

    artifact_id: ArtifactId
    source_label: str

    def __post_init__(self) -> None:
        """核对出处关联及文本，不解析或访问说明中可能出现的位置。

        :raises TypeError: 身份或标签类型错误。
        :raises ArtifactContractError: 出处说明为空或无法编码为 UTF-8。
        """
        _require_type(self.artifact_id, ArtifactId)
        _require_utf8_text(self.source_label)
