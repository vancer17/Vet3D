# 文件信息：L1-01 工作区和 L1-04 单资产注册库的唯一 SQLAlchemy 表定义。
# 作用：保存工作区注册及不可变单资产内容绑定，行提交即为资产登记事实。
# 边界：仅供仓储使用；不保存文件存在、批次状态、执行能力或业务发布资格。
"""声明注册存储结构，时间的 UTC 编解码由仓储边界唯一负责。"""

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class WorkspaceTableBase(DeclarativeBase):
    """持有当前注册库唯一权威元数据，不承担历史 Schema 迁移。"""


class WorkspaceRow(WorkspaceTableBase):
    """存储创建意图及首次注册提交，空时间仅表示意图尚未提交。"""

    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(
        Text, primary_key=True, doc="原 WorkspaceId 的规范 UUID4 文本；创建幂等键。"
    )
    display_name: Mapped[str] = mapped_column(
        Text, nullable=False, doc="未经裁剪或路径解释的原始工作区显示名。"
    )
    registered_at: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="首次注册提交的带 UTC 时区 ISO 时间；空值为未提交意图。"
    )


class ArtifactRow(WorkspaceTableBase):
    """保存单个产物的唯一归属、内容、位置及实际提供的出处。"""

    __tablename__ = "artifacts"
    __table_args__ = (
        UniqueConstraint("workspace_id", "relative_path"),
        CheckConstraint("byte_size >= 0"),
    )

    id: Mapped[str] = mapped_column(
        Text, primary_key=True, doc="原 ArtifactId 的规范 UUID4 文本；首次登记的唯一键。"
    )
    workspace_id: Mapped[str] = mapped_column(
        Text, ForeignKey("workspaces.id"), nullable=False, doc="产物唯一所属的已注册工作区身份。"
    )
    relative_path: Mapped[str] = mapped_column(
        Text, nullable=False, doc="该产物在所属工作区的规范相对位置，不保存宿主绝对路径。"
    )
    sha256: Mapped[str] = mapped_column(
        Text, nullable=False, doc="FileReference 所绑定原始字节的完整 SHA-256。"
    )
    byte_size: Mapped[int] = mapped_column(
        Integer, nullable=False, doc="同一 ContentFingerprint 的非负原始字节长度。"
    )
    source_label: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="实际提供的 ImportOrigin 原文；空值只表示未提供出处。"
    )
