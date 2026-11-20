# 网格快照 mesh_snapshot.py

## 资源身份与模型可见性

`mesh_snapshot.py` 是 Hi3D Agent 1.2.11 Windows x64 随包的 Blender Python 模块，源码映射为 `tools/blender-tools/scripts/mesh_snapshot.py`。P1 选取预览包 `.dependency-model-preview/scripts/mesh_snapshot.py` 的实际副本，供同目录的姿态采样导入。模型可从 Blender 工具参考文档发现该模块，并在宿主允许的本地命令内调用。文件没有独立 LLM Tool 注册或模型可见工具 `description`。 [归档源码](../../upstream/1.2.11/archived-p1/resources/runtime/prebuilt-skills/.dependency-model-preview/scripts/mesh_snapshot.py) · [接口证据](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-blender-tools/references/mesh-snapshot.md>)

## 参数、结果与副作用

| 接口 | 参数及结果 |
| --- | --- |
| `mesh_source(obj, *, evaluated, depsgraph=None)` | 产生 `(source, mesh)` 上下文。原始 `MESH` 分支借用 `source.data`，求值网格和 `CURVE`、`SURFACE`、`FONT`、`META` 转换使用 `to_mesh()`，在 `finally` 中回收临时转换。求值分支可传依赖图，缺省使用当前 Blender 上下文。借用对象的可用范围是上下文。 |
| `mesh_snapshot(obj, *, evaluated, space, scale=1.0, triangulation='loop', precision='float64', fields=(), depsgraph=None)` | 显式选择原始或求值对象和 `local` 或 `world` 坐标。世界分支应用源对象 `matrix_world`。`scale` 为正有限输出倍率，由调用方指定单位。 |
| `mesh_data_snapshot(mesh, *, transform=None, ...)` | 对已有 mesh 作独立复制，可显式传入顶点变换。`loop` 使用 Blender loop triangles，`require_triangles` 先要求全三角面，`bmesh` 在临时 BMesh 上三角化并释放。精度仅接受 `float32` 或 `float64`。 |
| 返回数据 | `vertices` 为 `N×3` 浮点数组，`triangles` 为 `M×3 int32`。`bounds` 为最小与最大坐标，空网格取 `None`。请求 `loops` 时返回 `triangle_loops`，请求 `uv` 同时返回逐 loop UV 与对应索引，请求 `materials` 返回材料槽名称和逐三角材质编号。 |

未知坐标空间、非法倍率、未知精度或属性、不可转换对象以及在 `bmesh` 模式请求属性会抛出 `ValueError`。快照为脱离场景的数据，可继续用于比较。源 mesh 分支会计算 Blender 的三角面缓存。调用方选择实际帧和依赖图，并负责几何有限性、材质节点及图片的进一步验收。

## 随包调用证据

`rig-retarget/scripts/rigging/mesh_snapshot.py` 与 P1 归档的预览包副本 SHA-256 同为 `2a073c84a13a945bd83effd3d6c15f5bb4ad218d2a9cb0c3025e36149d32d8f2`。`build_character` 通过 `blender_core.mesh_arrays()` 实际调用物化副本，固定 `evaluated=False`、`space="local"`、`triangulation="require_triangles"`、`precision="float32"`，取基础顶点和实际三角索引。构建入口据此计算初始权重，导出权重输入时使用同一组数组生成网格指纹。这个调用以局部坐标为准，回读校验世界尺寸、父级和面角属性时应单独选择相应参数。 [发行映射](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/package.json:3>) · [构建与权重输入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py:186>) · [实际采样](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/blender_core.py:9>) · [P1 收据](../../upstream/1.2.11/archived-p1/archive.lock.json)

## 依赖、权限与前置 Hook

模块导入 Python 标准库和 NumPy。对象提取时加载 Blender 的 `bpy`，`bmesh` 仅在显式选择该三角化模式时加载。函数直接读取现有 Blender 场景对象并管理临时转换，文件写入由上层决定。场景操作继承当前 Blender 进程权限。用本地命令启动 Blender 时，由该命令入口执行适用的权限和 Hook。 [Blender 启动包装器](../blender-execute.md) · [命令权限](../../tools/exec-command.md#权限沙箱与前置-hook)

## 调用示例

**Blender Python 示例。** 在 Blender 后台进程中运行，调用方将归档的 `.dependency-model-preview/scripts` 目录加入模块搜索路径，并选好活动网格对象。

```python
import bpy
from mesh_snapshot import mesh_snapshot

snapshot = mesh_snapshot(
    bpy.context.active_object,
    evaluated=True,
    space="world",
    fields=("uv", "materials"),
)
print(snapshot["vertices"].shape, snapshot["triangles"].shape)
```

## 核查依据与待验证项

归档平级模块通过同目录姿态采样闭包验证，以上求值网格示例已用合成立方体运行。Blender 工具包中同源码、同 SHA-256 的副本有 3 项隔离测试证据，覆盖 shape key、骨骼变形、UV、材质槽及失败清理。真实四足模型的形态键组合、毛发表现、贴图语义和逐帧变形仍需实测。 [测试来源](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-blender-tools/tests/test_mesh_snapshot.py>) · [P1 核查记录](../../upstream/1.2.11/extraction/p1/priority.md)
