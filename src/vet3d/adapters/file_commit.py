# 文件信息：L1-02 Debian 单文件无覆盖提交的最小系统调用边界。
# 作用：使用 Linux renameat2 的 RENAME_NOREPLACE，拒绝原目标已存在的提交。
# 边界：不选择目录、不检查业务归属、不提供覆盖降级或跨文件系统复制。
"""封装明确采用的 Linux 无覆盖重命名，不建立多平台兼容层。"""

import ctypes
import errno
import os


_RENAME_NOREPLACE = 1  # Linux ABI：目标已经存在时拒绝重命名。


def commit_file_no_replace(source_directory: int, source_name: str, target_directory: int, target_name: str) -> None:
    """在受信目录句柄间提交单个文件名，原子拒绝已有目标。

    :param source_directory: 暂存文件所在目录的描述符。
    :param source_name: 暂存文件的单段名称。
    :param target_directory: 最终文件所在目录的描述符。
    :param target_name: 最终文件的单段名称。
    :raises ValueError: 名称包含路径或空名称。
    :raises OSError: libc、内核或文件系统不支持，或提交失败；无覆盖降级。
    """
    for name in (source_name, target_name):
        if not name or name in (".", "..") or "/" in name or "\x00" in name:
            raise ValueError("单文件提交仅接受单段名称")
    library = ctypes.CDLL(None, use_errno=True)
    try:
        rename = library.renameat2
    except AttributeError as cause:
        raise OSError(errno.ENOSYS, "当前 libc 不提供 renameat2") from cause
    rename.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    rename.restype = ctypes.c_int
    result = rename(
        source_directory, os.fsencode(source_name), target_directory, os.fsencode(target_name), _RENAME_NOREPLACE
    )
    if result != 0:
        code = ctypes.get_errno()
        raise OSError(code, f"无覆盖文件提交失败：{os.strerror(code)}", target_name)
