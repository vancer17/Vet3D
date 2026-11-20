# Cycles 单通道纹理烘焙 texture_bake.py

## 资源身份与模型可见性

`texture_bake.py` 是 Hi3D Agent 1.2.11（Windows x64）随 `.dependency-texture-bake` 交付的 Blender Python 模块。模型可沿包文档发现单通道本地烘焙契约，由调用脚本准备网格、材质、参数及输出路径后导入。随包参考路径未声明独立的 LLM Tool 或模型可见 `description`。 [归档源码](../../upstream/1.2.11/archived-p1/resources/runtime/prebuilt-skills/.dependency-texture-bake/scripts/texture_bake.py) · [随包烘焙契约](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-texture-bake/references/contract.md>)

## 参数、结果与副作用

| 参数或接口 | 行为 |
| --- | --- |
| `sources`、`target` | 当前场景中可选的源网格集合和目标网格。要求 Object Mode、至少一件源网格、目标不在源集合内、目标有活动 UV 图、材质槽有效且启用节点。源、目标材质须隔离。 |
| `path`、`name`、`size`、`kind`、`colorspace` | 必填。PNG 路径、图像名、正整数边长、`DIFFUSE` 或 `EMIT` 或 `NORMAL`，以及 Blender 图像色彩空间。烘焙为正方形，法线约定为切线空间 OpenGL +Y。 |
| `cage`、`ray`、`margin`、`use_clear` | 必填。前两项为场景单位中的非负有限距离，`margin` 为非负整数像素，`use_clear` 传给 Blender 的清除设置。 |
| `fill=None`、`normal_16=False`、`overwrite=False` | 可选。初始生成色、Raw RGB 16 位 PNG 输出以及允许覆盖已有路径的显式标志。 |
| `device="CPU"`、`fallback_cpu=False` | 可选。交给同目录设备模块，默认 CPU。GPU 回退需显式允许。 |

`bake_image(sources, target, ...)` 以 selected-to-active 烘焙单次通道，写出 PNG 并打包到临时创建的 Blender `Image`，返回 `(image, report)`。报告含 `device`、`cage`、`ray`、`margin`、`use_clear`、`path`、`kind`、`resolution`、`colorspace`、`seconds` 与 `normal_convention`。DIFFUSE 仅取颜色分量，EMIT 依赖调用方准备发射着色。`bake_context` 管理选中对象、活动对象、可见性、渲染引擎、Cycles 与 bake 状态。`save_png(image, path, *, normal_16=False, pack=True)` 单独写 PNG 并恢复场景色彩与图像输出设置。

不合要求的烘焙输入抛出 `ValueError`，默认拒绝覆盖并抛出 `FileExistsError`，算子未返回 `FINISHED` 时抛出 `RuntimeError`。失败分支清理本次图像和临时纹理节点。函数恢复目标的活动节点及节点选中状态。成功结果保留 PNG 和内存图像，材质贴图的正式绑定及跨通道交付由调用方负责。写盘后失败时，已产生的磁盘文件由调用方检查。

## 依赖与执行权限

实际依赖同目录 `cycles_device.py`、Blender `bpy` 和 Cycles。调用方应使用可抛弃的独立场景并为指定输出路径提供进程可写权限。脚本会创建缺失的父目录。外层通过 `exec_command` 启动时，命令按当前轮权限和前置 Hook 处理。 [Cycles 设备模块](cycles-device.md) · [后台 Blender 包装器](../blender-execute.md) · [执行权限与 Hook](../../tools/exec-command.md#权限沙箱与前置-hook)

## 调用示例与核查

**根据归档源码编写的 Python 示例。** 在专用后台 Blender 运行，令归档的 `.dependency-texture-bake/scripts` 可导入。本例生成合成平面并将 PNG 写入临时目录。

```python
from pathlib import Path
from tempfile import TemporaryDirectory

import bpy
from texture_bake import bake_image

planes = []
for label, height in [("target-fixture", 0.0), ("source-fixture", 0.01)]:
    bpy.ops.mesh.primitive_plane_add(size=2, location=(0, 0, height))
    plane = bpy.context.object
    material = bpy.data.materials.new(label)
    material.use_nodes = True
    material.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (
        0.5, 0.15, 0.1, 1.0
    )
    plane.data.materials.append(material)
    planes.append(plane)
target, source = planes

with TemporaryDirectory() as directory:
    path = Path(directory) / "fixture.png"
    image, report = bake_image(
        [source], target, path=path, name="fixture", size=16,
        kind="DIFFUSE", colorspace="sRGB", cage=0.02,
        ray=0.1, margin=1, use_clear=True,
    )
    assert path.is_file() and list(image.size) == [16, 16]
    print(report["device"])
```

已在 Blender 4.5.16 LTS 运行归档副本的合成平面 DIFFUSE 示例，确认生成 16×16 PNG 并收到 CPU 报告。随包合成平面夹具还验证了 EMIT、NORMAL、像素、16 位 PNG、目标 UV 和正常及异常退出后的状态。真实犬猫模型的 cage 与 ray、遮挡、UV 接缝、GPU 结果及正式贴图绑定仍待实际验收。 [随包隔离测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-texture-bake/tests/test_device_context.py>) · [P1 路径与摘要](../../upstream/1.2.11/extraction/p1/priority.json)
