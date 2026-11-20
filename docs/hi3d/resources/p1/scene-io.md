# Blender 场景导入与网格操作 scene_io.py

## 资源身份与模型可见性

`scene_io.py` 是 Hi3D Agent 1.2.11（Windows x64）随 `.dependency-blender-tools` 交付的 Blender Python 模块。模型可由包的参考入口找到场景导入和对象保留的调用约定。本资源经 Python 导入，随包参考路径未声明独立的 LLM Tool 或模型可见 `description`。 [归档源码](../../upstream/1.2.11/archived-p1/resources/runtime/prebuilt-skills/.dependency-blender-tools/scripts/scene_io.py) · [随包场景 IO 契约](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-blender-tools/references/scene-io.md>)

## 参数、结果与副作用

| 接口 | 行为 |
| --- | --- |
| `import_objects(path, *, reset=False)` | 解析并检查已有文件，按后缀调用 Blender 的 GLB、GLTF、OBJ 或 PLY 导入算子。对 `.blend` 使用 `bpy.data.libraries.load(link=False)` 追加全部对象到场景根集合并保留父子层级。`reset=True` 在导入前执行工厂空场景重置。返回本次新增的场景对象列表。 |
| `retain_meshes(objects, *, remove_others=False, apply_transform=True)` | 接收非空、不重复的当前场景网格集合。先快照所有世界矩阵，再解除父级并写回世界矩阵。可选删除场景内其他对象。默认逐件选择并应用位置、旋转和缩放，返回原对象名到保留对象的映射。 |
| `create_mesh_object(name, vertices, faces, *, collection, material=None, recalculate_normals=False, smooth=False)` | 在指定集合创建网格对象。坐标采用调用方给出的场景单位。可选添加材质、平滑面着色及通过临时 BMesh 重算法线。返回新对象。异常时清理本次对象及网格，并释放临时 BMesh。 |

导入路径缺失抛出 `FileNotFoundError`，未知后缀或不合法的保留对象抛出 `ValueError`。这些预检先于对应的场景修改。算子抛出的异常向上传播，清场或解除父级后可能留下部分修改。场景导入按新增对象集合返回，调用方据此核对导入结果。对象保留可以改变选择、活动对象和对象本身。单位、合并规则及任何写盘步骤由调用方负责。

## 依赖与执行权限

直接导入 Python 标准库和 Blender `bpy`，仅在重算法线分支导入 Blender `bmesh`。所选文件格式使用对应 Blender 导入算子。函数作用于当前 Blender 场景并继承其文件读取权限。经 `exec_command` 启动时在外层核对沙箱和前置 Hook。 [后台 Blender 包装器](../blender-execute.md) · [执行权限与 Hook](../../tools/exec-command.md#权限沙箱与前置-hook)

## 调用示例与核查

**根据归档源码编写的 Python 示例。** 在独立 Blender 的调用方脚本中运行，令归档的 `.dependency-blender-tools/scripts` 可导入。

```python
import bpy
from scene_io import create_mesh_object

triangle = create_mesh_object(
    "review-triangle",
    [(0, 0, 0), (1, 0, 0), (0, 1, 0)],
    [(0, 1, 2)],
    collection=bpy.context.scene.collection,
    recalculate_normals=True,
)
assert len(triangle.data.polygons) == 1
```

已核对三个入口和 `bmesh` 的条件依赖。Blender 4.5.16 LTS 中归档副本成功创建合成三角面并重算法线。同版合成资产测试经 `asset_scene` 验证了 GLB 清场后重新导入。真实 GLTF 外部资源、OBJ 与 PLY 版本兼容、BLEND 追加后的父级及共享资源、形态键和共享网格的变换处理仍按实际入口验证。 [GLB 隔离测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-blender-tools/tests/test_asset_scene.py>) · [P1 路径与摘要](../../upstream/1.2.11/extraction/p1/priority.json)
