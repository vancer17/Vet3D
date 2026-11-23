# 文件信息：L0-03 的规范化主体坐标和标量单位换算。
# 作用：统一右手系 +X 动物右侧、+Y 头端、+Z 背侧，以及米制长度表达。
# 边界：只派生方向和转换已知单位的有限标量，不对齐模型、不读取文件或校准动物尺寸。
"""提供唯一五向取证约定和显式未知的源尺度。"""

import math
from dataclasses import dataclass
from typing import assert_never, final

from ._checks import ModelingContractError, require_type
from .directions import ViewDirection


def _finite_number(value: object) -> float:
    """接受有限整数或浮点值，排除布尔值和不可表示的数。

    :param value: 待转换的标量。
    :returns: 有限浮点数，不附加物理尺寸依据。
    :raises TypeError: 输入不是普通整数或浮点数。
    :raises ModelingContractError: 值非有限或转换溢出。
    """
    if type(value) not in (int, float):
        raise TypeError("空间标量必须是整数或浮点数，不能是布尔值")
    assert isinstance(value, (int, float))
    try:
        number = float(value)
    except OverflowError as error:
        raise ModelingContractError("空间标量超出有限浮点范围") from error
    if not math.isfinite(number):
        raise ModelingContractError("空间标量必须有限")
    return number


@final
@dataclass(frozen=True, slots=True)
class SourceScale:
    """记录源单位到米的格式换算依据，不代表物理标定已完成。

    :param metres_per_unit: 每个源坐标单位对应的米数；None 表示未知，不默认补一。
    """

    metres_per_unit: float | None

    def __post_init__(self) -> None:
        """拒绝非正和非有限的已知换算因子，保留未知尺度。"""
        if self.metres_per_unit is not None and _finite_number(self.metres_per_unit) <= 0:
            raise ModelingContractError("已知源尺度必须为正有限数")


def to_metres(value: float, *, scale: SourceScale) -> float:
    """将已知源单位的有限标量换为米，不改写模型或宣称真实尺寸。

    :param value: 有符号的源坐标或长度标量。
    :param scale: 显式提供的源尺度。
    :returns: 有限的米制标量。
    :raises TypeError: 标量或尺度类型错误。
    :raises ModelingContractError: 尺度未知、输入非有限或结果溢出。
    """
    require_type(scale, SourceScale)
    number = _finite_number(value)
    if scale.metres_per_unit is None:
        raise ModelingContractError("源尺度未知，不能声明米制换算结果")
    result = number * float(scale.metres_per_unit)
    if not math.isfinite(result):
        raise ModelingContractError("米制换算结果超出有限浮点范围")
    return result


def _require_axis(axis: tuple[int, int, int]) -> None:
    """核对取证输出使用的不可变有符号单位轴。

    :param axis: 三个整数分量组成的轴。
    :raises TypeError: 容器或分量类型错误。
    :raises ModelingContractError: 分量数量或长度不符合单位轴。
    """
    require_type(axis, tuple)
    if len(axis) != 3:
        raise ModelingContractError("方向轴必须有三个分量")
    for component in axis:
        require_type(component, int)
    if sum(abs(component) for component in axis) != 1:
        raise ModelingContractError("方向必须是有符号的单位坐标轴")


@final
@dataclass(frozen=True, slots=True)
class CameraOrientation:
    """承载由业务方向派生的观察位置方向及画面上方向。

    :param viewpoint: 观察者位于主体哪一侧，不是相机朝向或完整位置。
    :param image_up: 画面上方向，不包含距离、焦距或取景大小。
    """

    viewpoint: tuple[int, int, int]
    image_up: tuple[int, int, int]

    def __post_init__(self) -> None:
        """核对两个正交单位轴，避免把无效姿态交给后续渲染器。"""
        _require_axis(self.viewpoint)
        _require_axis(self.image_up)
        if sum(side * up for side, up in zip(self.viewpoint, self.image_up, strict=True)) != 0:
            raise ModelingContractError("观察方向与画面上方向必须正交")


def camera_orientation(direction: ViewDirection) -> CameraOrientation:
    """按唯一主体坐标约定派生五向观察轴，不推断输入已对齐。

    :param direction: 按动物自身侧别定义的业务方向。
    :returns: 观察者侧向及画面朝上轴；顶视头端朝上。
    :raises TypeError: 输入不是业务方向类型。
    """
    require_type(direction, ViewDirection)
    match direction:
        case ViewDirection.FRONT:
            return CameraOrientation((0, 1, 0), (0, 0, 1))
        case ViewDirection.BACK:
            return CameraOrientation((0, -1, 0), (0, 0, 1))
        case ViewDirection.LEFT:
            return CameraOrientation((-1, 0, 0), (0, 0, 1))
        case ViewDirection.RIGHT:
            return CameraOrientation((1, 0, 0), (0, 0, 1))
        case ViewDirection.TOP:
            return CameraOrientation((0, 0, 1), (0, 1, 0))
    assert_never(direction)
