# 文件信息：L0-04 执行事实的内部结构检查。
# 边界：只校验具体类型和诊断文本，不分类任意 Python 异常，不创建业务状态。
"""维护执行契约唯一异常和包内基本校验。"""


class ExecutionContractError(ValueError):
    """表示执行事实的引用或已确认观察之间存在契约冲突。"""


def require_type(value: object, expected: type[object]) -> None:
    """核对字段的具体类型，不转换身份或推断观察类别。

    :param value: 待检查字段或记录。
    :param expected: 允许的唯一具体类型。
    :raises TypeError: 输入类型与契约不符。
    """
    if type(value) is not expected:
        raise TypeError(f"此位置必须使用 {expected.__name__}")


def require_reason(reason: str) -> None:
    """保留非空白诊断原文，不从文字内容推导重试或终态。

    :param reason: 调用方实际取得的原因说明。
    :raises TypeError: 原因不是字符串。
    :raises ExecutionContractError: 原因为空白或不可编码为 UTF-8。
    """
    require_type(reason, str)
    if not reason.strip():
        raise ExecutionContractError("原因说明不能是空白文本")
    try:
        reason.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ExecutionContractError("原因说明必须可编码为 UTF-8") from error
