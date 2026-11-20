---
name: shape-build
description: "依据明确轮廓、截面和尺寸构建可组合的放样、回转、管道与板壳网格原语。"
---

# 参数化形体构建

依据明确轮廓、截面和尺寸构建可组合的放样、回转、管道与板壳网格原语。

## 输入与完成结果

- 输入：明确的轮廓/截面/尺寸/材质和目标 Blender 场景。
- 输出：planar_core.py 提供毫米制轮廓/放样/板壳；product_core.py 提供米制回转/管道；frame_core / box_core / studio_core 保留各自几何 profile。

## 调用与边界

Blender、NumPy；不推断完整产品设计。毫米与米接口分别调用，布尔及数值清理会改变指定对象，按函数语义记录；预览、打印、审查和来源处理按组合契约调用各自能力。

源码入口与安装依赖见 [package.json](package.json)；调用脚本前按 [独立打包约定](../.dependency-package-tools/references/usage.md) 准备完整包。函数和资源导航见 [代码契约](references/code-contract.md)。

复用纯几何时使用 `*_core`；领域接口的职责去向和 profile 差异见 [组合边界](references/composition.md)。

圆角轮廓、轴向拉伸/圆柱及可编辑曲线管道见 [基础原语](references/primitives.md)，纯坐标核心不加载 Blender，场景适配显式指定集合和单位。

<!-- managed-by: sparc3d-runtime -->
