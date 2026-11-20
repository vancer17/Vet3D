# 模型来源检查渲染 source_views.py

## 资源身份与模型可见性

`source_views.py` 是 Hi3D Agent 1.2.11 Windows x64 随包 `.dependency-model-preview` 的 Blender Python 模块，源码映射为 `skills/model-preview/scripts/source_views.py`。随包来源检查说明让模型可发现具体入口、方向和场景约定，实际调用由已选脚本在宿主授权下执行。文件没有独立 LLM Tool 注册或工具 `description`。 [归档源码](../../upstream/1.2.11/archived-p1/resources/runtime/prebuilt-skills/.dependency-model-preview/scripts/source_views.py) · [上游来源检查契约](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-model-preview/references/source-views.md>)

## 参数、结果与副作用

| 参数或输出 | 行为 |
| --- | --- |
| `obj`、`out`、`height_mm` | 调用方给出已摆正的单个对象、已存在的输出目录和模型高度。采用米制场景，目标点为 `(0, 0, height_mm / 2000)`，正交比例为 `max(obj.dimensions) * extent_factor`。 |
| 显式灯光和取景 | `extent_factor`、`light_energy`、`light_size`、`light_distance`、`camera_distance`、`world_name` 均必填。以三个相对方向设置方形面积灯。`replace_world=False` 时沿用已有世界，缺少世界或显式要求替换时新建并设世界颜色。 |
| 渲染与文件 | 在当前场景设 Cycles CPU、12 样本、去噪、2 个固定线程、AgX 和 `600×600`。按 `front`、`back`、`left`、`right`、`top`、`hero` 写出固定 `.png` 后缀。编码沿用场景实际格式。相机分别沿 `-Y`、`+Y`、`-X`、`+X`、`+Z` 和 `(1,-2,1)` 观察目标。函数无显式返回值。 |

模块添加灯光和相机，修改当前场景的渲染选项及世界，并留下最后一个方向的相机姿态和输出路径。输入的类型转换与 Blender 渲染或写入异常向上传播，可能留下部分已渲染文件和场景改动。调用方应提供隔离场景、独立输出目录的绝对路径、明确图像格式及必要的可见对象安排。实测未保存的 Blender 工厂场景会将普通相对路径 `review` 解析为当前盘符根下的 `review`。各方向文件是已有三维对象的本地取证产物。

## 依赖、权限与前置 Hook

模块导入标准库、Blender 的 `bpy` 和 `mathutils`，并从同目录 `preview_scene.py` 导入 `area_light`。六视角路径只调用该灯光接口。另行执行构图帧采样时才加载 `scene_samples.py` 和 NumPy 网格快照。渲染和写盘使用 Blender 进程现有权限，外层命令入口按宿主配置处理审批和 Hook。 [预览场景原子](preview-scene.md) · [Blender 启动包装器](../blender-execute.md) · [命令权限](../../tools/exec-command.md#权限沙箱与前置-hook)

## 调用示例

**Blender Python 示例。** 在隔离 Blender 场景中运行，调用方将归档的 `.dependency-model-preview/scripts` 目录加入模块搜索路径。直接复核归档时，可在导入前设置 `sys.dont_write_bytecode=True`，并在独立工作目录运行。

```python
from pathlib import Path
import bpy
from source_views import render_source_views

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 1))
subject = bpy.context.active_object
bpy.context.scene.render.image_settings.file_format = "PNG"
output = Path("review").resolve()
output.mkdir(exist_ok=True)
render_source_views(
    subject, output, 2000, extent_factor=1.75, light_energy=300,
    light_size=2, light_distance=3, camera_distance=6, world_name="Review",
)
```

## 核查依据与待验证项

Blender 4.5.16 LTS 以归档脚本运行上述绝对路径示例，在独立工作目录生成六张实际 `600×600` PNG，覆盖同目录灯光导入和六个相机分支。带头尾及左右地标的四足模型仍需核对顶视滚转、构图、遮挡和真实模型方向。第三方生成 API 的输入槽映射及生成图像质量由各自契约和实测验证。 [P1 核查记录](../../upstream/1.2.11/extraction/p1/priority.md)
