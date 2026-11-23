# 文件信息：L0-03 文件契约的内部校验基础。
# 作用：维护唯一契约异常及局部类型、文本检查，不读取环境或外部文件。
"""复用文件契约的结构校验，不提供另一套公开数据表示。"""


class ArtifactContractError(ValueError):
    """表示文件描述、定位或来源关联不符合本项契约。"""


def _require_type(value: object, expected: type[object]) -> None:
    """核对具体字段类型，避免不同身份或描述被隐式转换。

    :param value: 需要核对的字段或记录。
    :param expected: 本位置允许的唯一具体类型。
    :raises TypeError: 输入类型与契约不同。
    """
    if type(value) is not expected:
        raise TypeError(f"此位置必须使用 {expected.__name__}")


def _require_utf8_text(value: str) -> None:
    """检查非空 UTF-8 文本，不修剪或改写调用方原文。

    :param value: 需要原样保留的文本。
    :raises TypeError: 输入不是字符串。
    :raises ArtifactContractError: 文本为空或无法编码为 UTF-8。
    """
    _require_type(value, str)
    if not value:
        raise ArtifactContractError("文本不能为空")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ArtifactContractError("文本必须能够编码为 UTF-8") from error
