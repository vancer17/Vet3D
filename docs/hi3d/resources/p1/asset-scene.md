# 完整资产载入 asset_scene.py

## 资源身份与模型可见性

`asset_scene.py` 是 Hi3D Agent 1.2.11（Windows x64）随 `.dependency-blender-tools` 交付的 Blender Python 模块。随包参考文件用「完整资产载入」介绍它，调用方在后台 Blender 脚本中导入 `open_asset`。源码提供模块和函数文档字符串，随包参考路径未声明独立的 LLM Tool 或模型可见 `description`。 [归档源码](../../upstream/1.2.11/archived-p1/resources/runtime/prebuilt-skills/.dependency-blender-tools/scripts/asset_scene.py) · [随包参考入口](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-blender-tools/REFERENCE.md>) · [完整资产载入契约](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-blender-tools/references/asset-scene.md>)

## 参数、结果与副作用

| 接口 | 行为 |
| --- | --- |
| `open_asset(path, *, frame=None)` | `path` 必填。先解析路径，再验证给定文件存在且后缀为 `.blend` 或 `.glb`。`frame` 省略或为 `None` 时沿用载入后的帧，显式值接受 Python 整数并拒绝布尔值。 |
| BLEND | 调用 `bpy.ops.wm.open_mainfile(filepath=..., load_ui=False, use_scripts=False)`，载入完整工程并禁用内嵌脚本自动执行。 |
| GLB | 调用同目录 `scene_io.import_objects(path, reset=True)`，先重置场景，再导入模型。 |
| 返回 | 显式指定帧时调用 `scene.frame_set(frame)`。随后更新视图层并返回当前场景的 Blender 对象列表。 |

路径缺失抛出 `FileNotFoundError`，后缀或帧类型不符抛出 `ValueError`。这些检查发生在替换场景之前。Blender 算子错误向调用方传播，失败时可能已经替换或部分修改场景。载入只读取源文件，状态变更发生在进程中的场景。 [归档场景导入接口](scene-io.md)

## 依赖与执行权限

模块直接依赖同目录 `scene_io.py` 和 Blender 的 `bpy`。由受控的后台进程持有场景。路径解析后以进程权限读取文件，BLEND 的脚本禁用选项只约束该载入分支。由 Agent 经 `exec_command` 启动时，沙箱和前置 Hook 由外层命令入口处理。 [后台 Blender 包装器](../blender-execute.md) · [执行权限与 Hook](../../tools/exec-command.md#权限沙箱与前置-hook)

## 调用示例与核查

**根据归档源码编写的 Python 示例。** 在独立 Blender 进程运行，令归档的 `.dependency-blender-tools/scripts` 可导入，准备临时工作目录中的 `example.glb`。

```python
from pathlib import Path

from asset_scene import open_asset

objects = open_asset(Path("example.glb"), frame=0)
print([item.name for item in objects])
```

已在 Blender 4.5.16 LTS 直接运行归档副本的合成 GLB 调用。随包夹具还验证了 BLEND 工程标记及保存帧、GLB 导入帧与动画数据存在、预检拒绝时保持原场景，以及两个源文件的 SHA-256 保持。真实工程的外链、四足蒙皮和动作回读、破损模型导入后留下的状态待按目标样本核对。 [随包测试入口](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-blender-tools/tests/test_asset_scene.py>) · [P1 路径与摘要](../../upstream/1.2.11/extraction/p1/priority.json)
