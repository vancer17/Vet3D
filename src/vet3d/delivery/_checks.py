# 文件信息：L0-04 任务内交接回执的局部结构检查。
# 作用：约束具体不可变类型和接收端关联文字，不访问宿主或外部资源。
"""提供交接包内部的输入检查与所属异常。"""

from vet3d.identity import ArtifactSetTarget, ModelVersionTarget


class DeliveryContractError(ValueError):
    """表示交接声明与提供的操作、对象或完整性要求不匹配。"""


def require_type(value: object, expected: type[object]) -> None:
    """拒绝不同概念的类型和隐式转换。

    :param value: 待核对对象。
    :param expected: 唯一允许的具体类型。
    :raises TypeError: 类型不匹配。
    """
    if type(value) is not expected:
        raise TypeError(f"此位置必须使用 {expected.__name__}")


def require_destination(value: str) -> None:
    """核对接收端提供的不可解析目标文字，不将其作为读取地址。

    :param value: 接收端范围内可区分目标的关联文字。
    :raises TypeError: 输入不是字符串。
    :raises DeliveryContractError: 文字为空白或不能编码为 UTF-8。
    """
    require_type(value, str)
    if not value.strip():
        raise DeliveryContractError("保存目标关联不能为空白")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise DeliveryContractError("保存目标关联必须可编码为 UTF-8") from error


def require_target(value: object) -> None:
    """核对可加载的确切对象，复用已有目标联合。

    :param value: 文件集合或确切版本目标。
    :raises TypeError: 输入不是允许的具体目标类型。
    """
    if type(value) not in (ArtifactSetTarget, ModelVersionTarget):
        raise TypeError("加载目标必须是文件集合或确切模型版本")
