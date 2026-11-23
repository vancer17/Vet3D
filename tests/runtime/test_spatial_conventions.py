# 文件信息：L0-03 五向空间约定与源单位换算测试。
# 作用：验证动物自身前后左右、顶视图上方以及未知尺度的业务边界。
# 范围：只验证声明和纯计算；不执行姿态识别、几何对齐或真实尺寸标定。
"""检查固定空间约定的可观察含义，不复制可配置的相机参数表。"""

from math import inf, nan
from typing import cast
import unittest

from vet3d.modeling import ModelingContractError, SourceScale, ViewDirection, camera_orientation, to_metres


class SpatialConventionTests(unittest.TestCase):
    """以方向关系和单位转换边界检验供应商无关的空间约定。"""

    def test_five_directions_use_animal_sides_and_a_fixed_top_up(self) -> None:
        """左右是动物自身两侧，前后沿头尾方向，顶视图把头端置于画面上方。"""
        self.assertEqual({direction.value for direction in ViewDirection}, {"front", "back", "left", "right", "top"})
        front = camera_orientation(ViewDirection.FRONT)
        back = camera_orientation(ViewDirection.BACK)
        left = camera_orientation(ViewDirection.LEFT)
        right = camera_orientation(ViewDirection.RIGHT)
        top = camera_orientation(ViewDirection.TOP)
        self.assertEqual(front.viewpoint, (0, 1, 0))
        self.assertEqual(right.viewpoint, (1, 0, 0))
        self.assertEqual(left.viewpoint, tuple(-component for component in right.viewpoint))
        self.assertEqual(back.viewpoint, tuple(-component for component in front.viewpoint))
        self.assertEqual(top.viewpoint, (0, 0, 1))
        for orientation in (front, back, left, right):
            self.assertEqual(orientation.image_up, top.viewpoint)
        self.assertEqual(top.image_up, front.viewpoint)

    def test_derived_camera_axes_are_perpendicular_unit_vectors(self) -> None:
        """所有派生观察方向与画面上方向垂直且归一，不需要重复配置。"""
        for direction in ViewDirection:
            with self.subTest(direction=direction):
                orientation = camera_orientation(direction)
                self.assertEqual(sum(component * component for component in orientation.viewpoint), 1)
                self.assertEqual(sum(component * component for component in orientation.image_up), 1)
                self.assertEqual(
                    sum(view * up for view, up in zip(orientation.viewpoint, orientation.image_up, strict=True)),
                    0,
                )
        with self.assertRaises(TypeError):
            camera_orientation(cast(ViewDirection, "left"))

    def test_known_scale_converts_signed_coordinates_without_calibration_claims(self) -> None:
        """已声明单位可换算有符号坐标；换算不赋予 RGB 输入真实尺寸证据。"""
        millimetres = SourceScale(metres_per_unit=0.001)
        self.assertAlmostEqual(to_metres(-2500, scale=millimetres), -2.5)
        self.assertEqual(to_metres(0, scale=millimetres), 0)
        self.assertEqual(to_metres(3.5, scale=SourceScale(metres_per_unit=1)), 3.5)

    def test_unknown_scale_cannot_be_used_as_metres_even_for_zero(self) -> None:
        """未知尺度保持未知，不能按一米或零坐标特例隐式通过换算。"""
        unknown = SourceScale(metres_per_unit=None)
        for value in (0.0, 1.0, -1.0):
            with self.subTest(value=value):
                with self.assertRaises(ModelingContractError):
                    to_metres(value, scale=unknown)

    def test_invalid_scale_coordinates_and_overflow_are_rejected(self) -> None:
        """拒绝布尔值、非有限尺度或坐标，以及换算后溢出的非有限结果。"""
        for scale in (0.0, -1.0, inf, -inf, nan):
            with self.subTest(scale=scale):
                with self.assertRaises(ModelingContractError):
                    SourceScale(metres_per_unit=scale)
        for invalid_type in (True, "1"):
            with self.subTest(value=invalid_type):
                with self.assertRaises(TypeError):
                    SourceScale(metres_per_unit=cast(float, invalid_type))
                with self.assertRaises(TypeError):
                    to_metres(cast(float, invalid_type), scale=SourceScale(metres_per_unit=1.0))
        for non_finite in (inf, -inf, nan):
            with self.subTest(value=non_finite):
                with self.assertRaises(ModelingContractError):
                    to_metres(non_finite, scale=SourceScale(metres_per_unit=1.0))
        with self.assertRaises(ModelingContractError):
            to_metres(1e308, scale=SourceScale(metres_per_unit=1e308))
