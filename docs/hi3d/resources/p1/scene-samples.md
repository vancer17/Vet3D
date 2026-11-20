# 姿态与世界坐标网格采样 scene_samples.py

## 资源身份与模型可见性

`scene_samples.py` 是 Hi3D Agent 1.2.11 Windows x64 随包的 Blender Python 模块，源码映射为 `skills/motion-check/scripts/scene_samples.py`。P1 保留预览包 `.dependency-model-preview/scripts/scene_samples.py` 的实际副本，以支持同目录预览接口的按帧取样。模型可通过随包姿态采样说明及调用模块发现它，经授权的脚本入口使用。文件没有独立 LLM Tool 注册或工具 `description`。 [归档源码](../../upstream/1.2.11/archived-p1/resources/runtime/prebuilt-skills/.dependency-model-preview/scripts/scene_samples.py) · [姿态采样契约](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-motion-check/references/scene-samples.md>)

## 参数、结果与副作用

| 接口 | 参数及结果 |
| --- | --- |
| `sample_frames(scene, frames, inspect)` | `scene` 必须为当前活动场景。将非空有限帧序列按输入顺序处理，可采样负帧及小数帧。每帧用 `floor(frame)` 取整数部分，更新视图层后调用 `inspect(frame)`，返回各次回调结果。 |
| `world_mesh(obj, *, evaluated=True)` | 用同目录网格快照取得世界坐标和三角形。返回 `(points, faces, bounds)`，点为 Blender `Vector`，三角面为索引元组，包围盒为两组坐标列表。求值分支包含当前姿态和修改器结果。 |

非活动场景、空帧序列、非有限帧及空或非有限碰撞网格会抛出 `ValueError`。采样通过 `finally` 恢复原帧和子帧，再更新视图层。回调异常向上传播，其额外场景操作由调用方管理。采样期间应保留活动场景和被检查对象。返回几何用于离散诊断，离散样本之间的运动需要另行检查。

## 依赖、权限与前置 Hook

模块导入 Blender 的 `bpy` 和 `mathutils.Vector`，在包导入时从 `.mesh_snapshot` 解析依赖，平级导入时使用 `mesh_snapshot`。该依赖进一步使用 NumPy。函数调整当前场景帧并读取对象几何，调用方负责回调的文件访问。经本地命令执行时，权限与前置 Hook 由外层命令入口处理。 [网格快照](mesh-snapshot.md) · [命令权限](../../tools/exec-command.md#权限沙箱与前置-hook)

## 调用示例

**Blender Python 示例。** 调用方将归档的 `.dependency-model-preview/scripts` 目录加入模块搜索路径，当前场景已有活动网格。

```python
import bpy
from scene_samples import sample_frames, world_mesh

scene = bpy.context.scene
subject = bpy.context.active_object

def inspect(frame):
    points, faces, bounds = world_mesh(subject, evaluated=True)
    return frame, len(points), len(faces), bounds

print(sample_frames(scene, [1, 1.5, 2], inspect))
```

## 核查依据与待验证项

隔离测试验证了合成对象的整数及小数帧取样、原帧与子帧恢复、世界网格读出，以及平级与包模块名都解析到相应同目录快照。以上示例在归档模块上执行后恢复到原帧 `4`、子帧 `0.125`。产品目录的同字节副本只作投放证据。真实动物含骨骼、形状键和复杂修改器时的实际变形、连续性和采样成本仍待核验。 [产品子目录证据](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-model-preview/scripts/product/scene_samples.py>) · [P1 核查记录](../../upstream/1.2.11/extraction/p1/priority.md)
