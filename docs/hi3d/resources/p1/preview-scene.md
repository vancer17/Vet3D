# 预览场景原子 preview_scene.py

## 资源身份与模型可见性

`preview_scene.py` 是 Hi3D Agent 1.2.11 Windows x64 随包 `.dependency-model-preview` 的 Blender Python 模块，源码映射为 `skills/model-preview/scripts/preview_scene.py`。随包参考文档给出自定义正交相机、投影和面积灯接口，模型可在读取到该引用后经宿主允许的本地执行入口使用。文件没有独立 LLM Tool 注册或工具 `description`。P1 归档选用平级脚本，产品子目录的同字节副本保留为证据。 [归档源码](../../upstream/1.2.11/archived-p1/resources/runtime/prebuilt-skills/.dependency-model-preview/scripts/preview_scene.py) · [预览原子接口](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-model-preview/references/preview-atoms.md>)

## 参数、结果与副作用

| 函数 | 参数及结果 |
| --- | --- |
| `bounds_points(objects, *, evaluated, require_mesh=False)` | 返回显式对象包围盒角点的世界坐标，`evaluated` 选择是否取求值对象。传入空对象列表，或设置 `require_mesh=True` 时遇到非网格或空网格会失败。 |
| `position_camera(camera, center, direction, scale, roll=0)` | 以 `center` 加相对位置向量 `direction` 放置相机，使用角度制 `roll` 设置旋转，再设 `ortho_scale`。直接修改传入的相机。 |
| `fit_orthographic_camera(camera, objects, resolution, *, evaluated, margin=1.15)` | 使用显式有效分辨率和倍率留边。根据 `sensor_fit`、横竖画幅及相机空间角点平移相机并调整比例。接受正交相机、正宽高、有限且至少为 `1` 的倍率。 |
| `projected_bounds(scene, camera, objects, *, evaluated, check_depth=False, require_mesh=False)` | 返回 `min_x`、`max_x`、`min_y`、`max_y`、`all_in_front`。启用 `check_depth` 会拒绝近远裁切区间之外或恰落在边界的角点。 |
| `fit_projected_orthographic_camera(scene, camera, objects, *, evaluated, margin=.05)` | 接受独立、无约束及动画的静态正交相机和非空网格，留边比例为 `[0, .45)`。结合 Blender 投影、镜头偏移和像素宽高比调整比例及平面位置，返回最终投影边界。留边失败会抛出 `RuntimeError`，此前的相机改动保留。 |
| `check_framing(scene, camera, objects, frames, *, evaluated, margin=.01)` | 在显式帧上检查角点严格位于留边范围和相机前方，以 `all_bounds_in_frame` 和 `samples` 返回结果。采样中的帧与子帧由同目录辅助模块恢复。 |
| `area_light(name, location, target, energy, size, color, *, collection, shape='DISK')` | 创建面积灯数据和对象，加入指定集合并瞄准目标，返回灯光对象。 |

无效输入、退化投影以及深度约束失败会抛出 `ValueError`。相机拟合和灯光添加会改变现有场景状态。投影与构图检查使用包围盒角点，遮挡和形变仍由调用方结合实际渲染评估。

## 依赖、权限与前置 Hook

模块直接导入 `bpy`、`mathutils` 和 `bpy_extras.object_utils`。调用 `check_framing()` 时才加载同目录 `scene_samples.py`，进而加载依赖 NumPy 的 `mesh_snapshot.py`。相机、集合及可用 Blender 上下文由调用方提供。本模块在当前进程内修改场景，适用的权限审批与 Hook 由外层命令入口处理。 [姿态采样](scene-samples.md) · [命令权限](../../tools/exec-command.md#权限沙箱与前置-hook)

## 调用示例

**Blender Python 示例。** 调用方将归档的 `.dependency-model-preview/scripts` 目录加入模块搜索路径，当前场景已有正交相机及活动网格。

```python
import bpy
from preview_scene import fit_projected_orthographic_camera

scene = bpy.context.scene
subject = bpy.context.active_object
limits = fit_projected_orthographic_camera(
    scene, scene.camera, [subject], evaluated=True, margin=0.1
)
print(limits)
```

## 核查依据与待验证项

已核对归档副本、静态接口及条件导入。隔离验证覆盖平级脚本和包命名空间的构图采样，以上正交拟合示例已用合成立方体运行。六视图渲染使用本模块的 `area_light()`。产品包的同字节副本在自身目录解析 `scene_samples.py`。真实四足姿态的评估包围盒、裁切与可见性仍需验证。 [产品子目录证据](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-model-preview/scripts/product/preview_scene.py>) · [P1 核查记录](../../upstream/1.2.11/extraction/p1/priority.md)
