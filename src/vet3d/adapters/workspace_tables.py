# 文件信息：L1-01 SQLite 注册库的唯一 SQLAlchemy 表定义。
# 作用：将工作区身份、原始名称及首次注册时间保存为单行登记事实。
# 边界：仅供注册仓储使用；不保存目录状态、权限、执行能力或业务发布资格。
"""声明注册存储结构，时间的 UTC 编解码由仓储边界唯一负责。"""

from sqlalchemy import Text
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
