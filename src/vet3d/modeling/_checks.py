# 文件信息：L0-03 建模输入的包内结构检查。
# 作用：统一拒绝错类值、可变集合和不完整文本，不读取外部事实或配置。
# 边界：仅供本包具体契约使用，不提供通用验证框架或业务状态。
"""维护建模值对象的基本输入约束。"""


class ModelingContractError(ValueError):
    """表示建模引用、生成交接、视图准备或空间约定不满足规则。"""


def require_type(value: object, expected: type[object]) -> None:
    """拒绝与具体契约类型不符的输入。

    :param value: 待检查值。
    :param expected: 此位置允许的具体类型。
    :raises TypeError: 输入类型错误。
    """
    if type(value) is not expected:
        raise TypeError(f"此位置必须使用 {expected.__name__}")


def require_set(values: object, expected: type[object]) -> None:
    """核对不可变集合及成员类型，避免冻结对象持有可变引用。

    :param values: 待检查的集合。
    :param expected: 集合成员的具体类型。
    :raises TypeError: 集合或成员类型错误。
    """
    if type(values) is not frozenset:
        raise TypeError("此位置必须使用 frozenset")
    for value in values:
        require_type(value, expected)


def require_text(value: object) -> None:
    """核对建模要求或诊断的文本边界，保留原文且不解释其语义。

    :param value: 待记录的要求或诊断文字。
    :raises TypeError: 输入不是字符串。
    :raises ModelingContractError: 文本空白或无法编码为 UTF-8。
    """
    require_type(value, str)
    assert isinstance(value, str)
    if not value.strip():
        raise ModelingContractError("建模要求或诊断不能是空白文本")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ModelingContractError("建模要求或诊断必须可编码为 UTF-8") from error
