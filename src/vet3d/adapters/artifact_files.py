# 文件信息：L1-02 固定工作区的真实普通文件保存与观察适配器。
# 作用：以已有产物身份定位字节，复制受信暂存原件，计算摘要并无覆盖提交。
# 边界：不登记产物、不推导授权、不解码素材；受管根仍要求同 UID 可信独占管理。
# 恢复：失败保留已提交目标；仅清理本次拥有的临时文件，未知残留不扫描认领。
"""将文件端口接到受管目录和真实描述符，保持字节事实与业务登记独立。"""

import errno
import hashlib
import os
import secrets
import stat
from typing import BinaryIO

from vet3d.artifacts import (
    ArtifactContractError, ArtifactFileStore, ContentFingerprint, FileMissing,
    FileObservation, FilePresent, FileReference, FileUnavailable, WorkspaceFileLocation,
    WorkspaceRelativePath, validate_content_observation, validate_file_scope,
)
from vet3d.identity import ArtifactIdentity, WorkspaceId

from .file_commit import commit_file_no_replace
from .workspace_directories import ManagedWorkspaceRoot, _validate_entry


_DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
_FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
_CHUNK_BYTES = 1024 * 1024


def validate_file_byte_limit(max_file_bytes: int) -> None:
    """统一校验装配注入的字节资源上限，不生成业务资格或状态。

    :param max_file_bytes: 单文件实际 I/O 允许的最大字节数。
    :raises TypeError: 上限不是非布尔整数。
    :raises ValueError: 上限不是正数。
    """
    if type(max_file_bytes) is not int:
        raise TypeError("文件字节上限必须是整数")
    if max_file_bytes <= 0:
        raise ValueError("单文件字节上限必须为正数")


def _validate_regular(info: os.stat_result, *, modes: tuple[int, ...]) -> None:
    """要求当前用户拥有的私有单链接普通文件，拒绝其他文件对象。

    :param info: 来自实际打开描述符的属性。
    :param modes: 当前访问边界允许的精确权限集合。
    :raises PermissionError: 类型、属主、权限或链接数不符合要求。
    """
    if (
        not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) not in modes or info.st_nlink != 1
    ):
        raise PermissionError("文件必须是当前用户所有、私有权限的单链接普通文件")


def _require_unchanged(before: os.stat_result, after: os.stat_result) -> None:
    """核对实际读写期间可观察的文件变化，不宣称恶意并发下的快照保证。

    :param before: 操作前的描述符属性。
    :param after: 操作后的描述符属性。
    :raises OSError: 身份、大小、时间、链接、属主或权限已经改变。
    """
    if (
        before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns,
        before.st_ctime_ns, before.st_nlink, before.st_uid, before.st_mode,
    ) != (
        after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns,
        after.st_ctime_ns, after.st_nlink, after.st_uid, after.st_mode,
    ):
        raise OSError("读取期间文件发生可观察变化")


def _write_all(descriptor: int, data: bytes) -> None:
    """完整写出当前块，避免短写被解释为完整原件。

    :param descriptor: 本次独占创建的暂存文件描述符。
    :param data: 当前复制块。
    :raises OSError: 写入失败或没有取得进展。
    """
    offset = 0
    while offset < len(data):
        written = os.write(descriptor, data[offset:])
        if written == 0:
            raise OSError(errno.EIO, "文件写入未取得进展")
        offset += written


class LocalArtifactFileStore(ArtifactFileStore):
    """在固定工作区内保存和观察文件，由 Bootstrap 核对注册并管理源句柄寿命。

    :param root: 同线程持有写入锁的受管根。
    :param workspace_id: 实例唯一工作区作用域，不接受逐次命令重新定义。
    :param max_file_bytes: 装配注入的单文件实际 I/O 上限，不定义业务验收资格。
    """

    def __init__(self, root: ManagedWorkspaceRoot, workspace_id: WorkspaceId, *, max_file_bytes: int) -> None:
        """绑定具体存储和资源限额，不初始化目录、不访问注册库。

        :param root: 当前存储所有者提供的受管根。
        :param workspace_id: 已由装配核对登记的工作区身份。
        :param max_file_bytes: 正整数形式的字节资源上限。
        :raises TypeError: 工作区或限额类型错误。
        :raises ValueError: 限额不是正数。
        """
        if type(workspace_id) is not WorkspaceId:
            raise TypeError("文件存储需要 WorkspaceId")
        validate_file_byte_limit(max_file_bytes)
        self._root = root
        self._workspace_id = workspace_id
        self._max_file_bytes = max_file_bytes

    def location_for(self, artifact: ArtifactIdentity) -> WorkspaceFileLocation:
        """从原身份纯派生固定位置，不以位置存在冒充持久登记。

        :param artifact: 与本实例工作区一致的产物归属记录。
        :returns: files 下以完整产物 UUID 命名的位置。
        :raises ArtifactContractError: 产物属于其他工作区。
        """
        validate_file_scope(artifact, workspace_id=self._workspace_id)
        return WorkspaceFileLocation(artifact.id, WorkspaceRelativePath(f"files/{artifact.id.value}"))

    def _open_files(self, *, create: bool) -> tuple[int, int] | None:
        """通过根的既有校验取得工作区与文件集合句柄。

        :param create: 保存新文件时才允许建立缺失的 files 集合。
        :returns: 调用方关闭的工作区及 files 描述符；只读时集合不存在返回空值。
        :raises OSError: 工作区不存在、集合不安全或目录同步失败。
        """
        workspace = self._root.directories.open_handle(self._workspace_id)
        files: int | None = None
        try:
            if create:
                try:
                    os.mkdir("files", mode=0o700, dir_fd=workspace)
                except FileExistsError:
                    pass
            try:
                files = os.open("files", _DIRECTORY_FLAGS, dir_fd=workspace)
            except FileNotFoundError:
                if create:
                    raise
                self._verify_workspace(workspace)
                os.close(workspace)
                return None
            _validate_entry(files, workspace, "files", directory=True)
            if create:
                os.fsync(files)
                os.fsync(workspace)
            return workspace, files
        except BaseException:
            if files is not None:
                os.close(files)
            os.close(workspace)
            raise

    def _verify_workspace(self, workspace: int) -> None:
        """再次核对原工作区仍是受管根下的已观察对象。

        :param workspace: 当前实际操作持有的工作区句柄。
        :raises OSError: 根或工作区被替换、缺失或改权。
        """
        current = self._root.directories.open_handle(self._workspace_id)
        try:
            original_info, current_info = os.fstat(workspace), os.fstat(current)
            if (original_info.st_dev, original_info.st_ino) != (current_info.st_dev, current_info.st_ino):
                raise OSError("文件操作所属工作区已被替换")
        finally:
            os.close(current)

    def _verify_layout(self, workspace: int, files: int) -> None:
        """核对本次实际使用的集合仍归属于原工作区。

        :param workspace: 原工作区描述符。
        :param files: files 集合描述符。
        :raises OSError: 任一级受管对象已失效。
        """
        self._verify_workspace(workspace)
        _validate_entry(files, workspace, "files", directory=True)

    def _fingerprint(
        self, descriptor: int, *, target: int | None = None, expected_bytes: int | None = None,
    ) -> ContentFingerprint:
        """从描述符起点有界读取并计算字节事实，可同步复制到本次暂存。

        :param descriptor: 借用的原文件或当前观察文件描述符。
        :param target: 可选的独占暂存输出描述符。
        :param expected_bytes: 保存时由预期引用单向给出的长度，至多额外读取一字节。
        :returns: 实际完整读取的 SHA-256 和长度。
        :raises ArtifactContractError: 源在复制期间增长并超过预期引用长度。
        :raises OSError: 读取、写入或资源上限检查失败。
        """
        digest = hashlib.sha256()
        offset = 0
        limit = self._max_file_bytes if expected_bytes is None else min(self._max_file_bytes, expected_bytes)
        while True:
            chunk = os.pread(descriptor, min(_CHUNK_BYTES, limit + 1 - offset), offset)
            if not chunk:
                break
            offset += len(chunk)
            if expected_bytes is not None and offset > expected_bytes:
                raise ArtifactContractError("读取期间源文件增长并超过预期长度")
            if offset > self._max_file_bytes:
                raise OSError(errno.EFBIG, "文件超过实际 I/O 字节上限")
            digest.update(chunk)
            if target is not None:
                _write_all(target, chunk)
        return ContentFingerprint(digest.hexdigest(), offset)

    def _remove_owned_temporary(self, files: int, name: str, descriptor: int) -> None:
        """仅删除本次独占创建且仍指向原 inode 的暂存名。

        :param files: 暂存所在的集合句柄。
        :param name: 本次技术临时名称。
        :param descriptor: 本次持有的暂存文件句柄。
        :raises OSError: 暂存名被替换或清理同步失败；不删除陌生对象。
        """
        try:
            linked = os.stat(name, dir_fd=files, follow_symlinks=False)
        except FileNotFoundError:
            return
        opened = os.fstat(descriptor)
        if (linked.st_dev, linked.st_ino) != (opened.st_dev, opened.st_ino):
            raise OSError("暂存名称已被替换，保留现场")
        os.unlink(name, dir_fd=files)
        os.fsync(files)

    def store_new(self, artifact: ArtifactIdentity, reference: FileReference, source: BinaryIO) -> FilePresent:
        """复制已打开的原件并无覆盖提交，不消费源句柄所有权或生成登记事实。

        :param artifact: 本工作区的确切产物身份。
        :param reference: 调用方保留的预期原始字节引用。
        :param source: 借用的真实普通文件；期间不得并发修改或关闭。
        :returns: 同步完成后实际取得的文件存在观察。
        :raises ArtifactContractError: 作用域、引用关联或源内容不匹配。
        :raises OSError: 文件不安全、已有目标、资源限制或提交失败；目标可能已提交。
        """
        validate_file_scope(artifact, workspace_id=self._workspace_id, reference=reference)
        location = self.location_for(artifact)
        descriptor = source.fileno()
        before = os.fstat(descriptor)
        _validate_regular(before, modes=(0o600, 0o400))
        if before.st_size > self._max_file_bytes or reference.content.byte_size > self._max_file_bytes:
            raise OSError(errno.EFBIG, "源文件或预期长度超过实际 I/O 字节上限")
        if before.st_size != reference.content.byte_size:
            raise ArtifactContractError("源文件实际长度与预期引用不一致")
        opened = self._open_files(create=True)
        assert opened is not None
        workspace, files = opened
        temporary: int | None = None
        temporary_name = ".incoming-" + secrets.token_hex(16) + ".tmp"
        final_name = str(artifact.id.value)
        try:
            try:
                os.stat(final_name, dir_fd=files, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise FileExistsError(errno.EEXIST, "新文件目标已经存在，不认领或覆盖", final_name)
            temporary = os.open(
                temporary_name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                mode=0o600, dir_fd=files,
            )
            observed = self._fingerprint(descriptor, target=temporary, expected_bytes=reference.content.byte_size)
            _require_unchanged(before, os.fstat(descriptor))
            validate_content_observation(reference, observed=observed)
            _validate_entry(temporary, files, temporary_name, directory=False)
            if os.fstat(temporary).st_size != observed.byte_size:
                raise OSError("暂存文件实际长度与复制结果不一致")
            os.fchmod(temporary, 0o400)
            os.fsync(temporary)
            self._verify_layout(workspace, files)
            commit_file_no_replace(files, temporary_name, files, final_name)
            os.fsync(files)
            linked = os.stat(final_name, dir_fd=files, follow_symlinks=False)
            actual = os.fstat(temporary)
            _validate_regular(actual, modes=(0o400,))
            if (linked.st_dev, linked.st_ino) != (actual.st_dev, actual.st_ino):
                raise OSError("已提交目标被替换，无法确认本次结果")
            self._verify_layout(workspace, files)
            return FilePresent(location, observed)
        except BaseException as cause:
            if temporary is not None:
                try:
                    self._remove_owned_temporary(files, temporary_name, temporary)
                except OSError as cleanup_error:
                    cause.add_note(f"本次暂存清理未确认：{cleanup_error}")
            raise
        finally:
            if temporary is not None:
                os.close(temporary)
            os.close(files)
            os.close(workspace)

    def observe(self, artifact: ArtifactIdentity, location: WorkspaceFileLocation) -> FileObservation:
        """观察规范位置的实际字节，将访问故障与确切缺失分别记录。

        :param artifact: 与实例工作区一致的产物归属。
        :param location: 该身份唯一固定位置，不允许调用方选择其他相对文件。
        :returns: 实际存在、缺失或访问不可用；不比较预期内容。
        :raises ArtifactContractError: 作用域、身份或位置不符合本适配器契约。
        """
        validate_file_scope(artifact, workspace_id=self._workspace_id, location=location)
        if location != self.location_for(artifact):
            raise ArtifactContractError("文件观察只接受该产物的规范存储位置")
        try:
            opened = self._open_files(create=False)
            if opened is None:
                return FileMissing(location)
            workspace, files = opened
            try:
                try:
                    descriptor = os.open(str(artifact.id.value), _FILE_FLAGS, dir_fd=files)
                except FileNotFoundError:
                    self._verify_layout(workspace, files)
                    return FileMissing(location)
                try:
                    before = os.fstat(descriptor)
                    _validate_regular(before, modes=(0o400,))
                    if before.st_size > self._max_file_bytes:
                        raise OSError(errno.EFBIG, "文件超过实际 I/O 字节上限")
                    observed = self._fingerprint(descriptor)
                    _require_unchanged(before, os.fstat(descriptor))
                    linked = os.stat(str(artifact.id.value), dir_fd=files, follow_symlinks=False)
                    if (linked.st_dev, linked.st_ino) != (before.st_dev, before.st_ino):
                        raise OSError("文件观察期间目标位置被替换")
                    self._verify_layout(workspace, files)
                    return FilePresent(location, observed)
                finally:
                    os.close(descriptor)
            finally:
                os.close(files)
                os.close(workspace)
        except OSError as cause:
            return FileUnavailable(location, str(cause))
