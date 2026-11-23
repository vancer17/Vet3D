# 文件信息：L1-01 工作区创建用例拥有的同步 I/O 端口。
# 作用：分离注册事务与受管目录操作，由 Bootstrap 显式注入具体适配器。
# 边界：不暴露任意路径读写或执行，也不承担跨线程调度、资源授权和业务验收。
"""定义工作区注册与目录准备的最小替换边界。"""

from typing import Protocol

from vet3d.identity import WorkspaceId

from .records import WorkspaceRecord


class WorkspaceRepository(Protocol):
    """在受信单写入装配内持久保存原始创建意图与首次注册提交。"""

    def get(self, workspace_id: WorkspaceId) -> WorkspaceRecord | None:
        """读取原登记事实，读取故障不能降级为没有记录。

        :param workspace_id: 待读取的工作区身份。
        :returns: 原记录，或确实不存在时的空值。
        """
        ...

    def record_intent(self, workspace_id: WorkspaceId, display_name: str) -> WorkspaceRecord:
        """原子登记或核对原创建字段，不把创建意图当作已提交注册。

        :param workspace_id: 调用者保留的原工作区身份。
        :param display_name: 原样保留的显示名。
        :returns: 新的未提交记录，或已存在且字段相同的原记录。
        :raises WorkspaceConflict: 原身份已经绑定不同的创建字段。
        """
        ...

    def confirm_registration(self, workspace_id: WorkspaceId) -> WorkspaceRecord:
        """首次提交注册时间，已提交记录读回原值，缺少意图时拒绝。

        :param workspace_id: 已经登记原创建意图的身份。
        :returns: 保留原字段与首次提交时间的记录。
        """
        ...


class WorkspaceDirectories(Protocol):
    """只为受信创建用例核对和准备目录，不向执行器授权工作区访问。"""

    def check_absent(self, workspace_id: WorkspaceId) -> None:
        """在首次登记意图前确认目标不存在，任何既有对象均不能认领。

        :param workspace_id: 尚无登记记录的工作区身份。
        """
        ...

    def prepare(self, workspace_id: WorkspaceId) -> None:
        """为未提交意图准备目录，仅允许核对可确认的受管创建残留。

        :param workspace_id: 已登记但尚未提交注册的原身份。
        """
        ...

    def require_existing(self, workspace_id: WorkspaceId) -> None:
        """核对已登记目录仍然可访问，缺失或被替换时不创建空目录。

        :param workspace_id: 已提交注册的原工作区身份。
        """
        ...
