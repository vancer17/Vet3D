# 文件信息：L0-04 报告与验收契约的包内输入检查。
# 作用：约束具体冻结记录的类型、文本及集合，不建立通用策略框架。
# 边界：只检查当前传入值，不查询证据、解析报告或推导业务质量。
"""维护报告和验收声明的基础结构要求。"""


class AssessmentContractError(ValueError):
    """表示报告或验收声明不满足结构、关联或交接要求。"""


def require_type(value: object, expected: type[object]) -> None:
    """拒绝具体契约类型以外的值，不进行隐式转换。

    :param value: 需要核对的传入值。
    :param expected: 此位置唯一接受的具体类型。
    :raises TypeError: 传入值不是所要求的类型。
    """
    if type(value) is not expected:
        raise TypeError(f"此位置必须使用 {expected.__name__}")


def require_text(value: str) -> None:
    """核对必须保留的协议或诊断文字，不解释其业务含义。

    :param value: 不允许为空白的原始文字。
    :raises TypeError: 传入值不是字符串。
    :raises AssessmentContractError: 文字为空白或不能编码为 UTF-8。
    """
    require_type(value, str)
    if not value.strip():
        raise AssessmentContractError("报告与验收文字不能为空白")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise AssessmentContractError("报告与验收文字必须可编码为 UTF-8") from error


def require_text_set(values: frozenset[str], *, nonempty: bool) -> None:
    """检查不可变的章节或检查项集合，保持原始名称。

    :param values: 本次声明的文字集合。
    :param nonempty: 该要求集合是否至少需要一个条目。
    :raises TypeError: 集合或成员类型不符。
    :raises AssessmentContractError: 要求集合为空或成员文字无效。
    """
    require_type(values, frozenset)
    if nonempty and not values:
        raise AssessmentContractError("交接要求必须明确至少一个条目")
    for value in values:
        require_text(value)
