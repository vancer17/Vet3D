# 文件信息：L1-02 可信宿主的私有暂存输入打开边界。
# 作用：仅从已配置的暂存根取得一个普通文件的只读句柄，供实际存储操作持有。
# 边界：不接 URL、不解析 ImportOrigin、不接受请求中的绝对路径或递归目录。
"""把可信部署位置与单文件请求分开，不把来源标签当作访问凭证。"""

import io
import os
from pathlib import Path
import stat
from typing import BinaryIO
import unicodedata

from .workspace_directories import _DIRECTORY_FLAGS, _open_parent, _validate_entry


def open_staged_input(root: Path, name: str) -> BinaryIO:
    """从私有暂存根打开已完成接收的普通文件，调用者拥有返回句柄。

    :param root: Bootstrap 配置的受信暂存目录，父路径必须存在且没有链接。
    :param name: 请求中的单个文件名，不作裁剪或路径展开。
    :returns: 从文件起点读取的只读二进制句柄，必须在实际 I/O 终结后关闭。
    :raises TypeError: 根或名称不是规定类型。
    :raises ValueError: 根或名称不能表示本入口支持的位置。
    :raises OSError: 目录或输入不满足类型、所有权、权限及单链接要求。
    """
    if not isinstance(root, Path) or type(name) is not str:
        raise TypeError("暂存输入需要 Path 根和字符串文件名")
    if (
        not name or name in (".", "..") or "/" in name or "\\" in name
        or any(unicodedata.category(character) == "Cc" for character in name)
    ):
        raise ValueError("暂存输入必须是单个文件名")
    name.encode("utf-8")
    if ".." in root.parts:
        raise ValueError("暂存根不能包含上级路径段")
    absolute = Path(os.path.abspath(root))
    if absolute == Path("/"):
        raise ValueError("暂存根不能是文件系统根")
    parent = _open_parent(absolute)
    try:
        directory = os.open(absolute.name, _DIRECTORY_FLAGS, dir_fd=parent)
        try:
            _validate_entry(directory, parent, absolute.name, directory=True)
            descriptor = os.open(
                name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                dir_fd=directory,
            )
            try:
                opened = os.fstat(descriptor)
                linked = os.stat(name, dir_fd=directory, follow_symlinks=False)
                if (
                    not stat.S_ISREG(opened.st_mode) or opened.st_uid != os.getuid()
                    or opened.st_nlink != 1 or stat.S_IMODE(opened.st_mode) not in (0o400, 0o600)
                    or (opened.st_dev, opened.st_ino) != (linked.st_dev, linked.st_ino)
                ):
                    raise PermissionError("暂存输入必须为当前用户私有的普通单链接文件")
                _validate_entry(directory, parent, absolute.name, directory=True)
                return io.FileIO(descriptor, mode="rb", closefd=True)
            except BaseException:
                os.close(descriptor)
                raise
        finally:
            os.close(directory)
    finally:
        os.close(parent)
