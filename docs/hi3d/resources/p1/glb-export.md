# `glb_export.py`

## 资源身份与模型可见方式

Hi3D Agent 1.2.11（Windows x64）将 `skills/model-preview/scripts/glb_export.py` 物化到 `.dependency-model-preview/scripts/glb_export.py`，随包预览测试从这个平铺位置导入。归档保留此实际消费位置。产品子目录的同名副本具有相同 SHA-256，作为另一物化路径的证据引用。模型可在已选 Skill 的资源契约中发现导出函数，经本地命令启动调用程序。安装包核查范围内未发现此脚本的独立 LLM Tool 注册或模型可见 `description`。 [归档原件](../../upstream/1.2.11/archived-p1/resources/runtime/prebuilt-skills/.dependency-model-preview/scripts/glb_export.py) · [副本路径与版本](../../upstream/1.2.11/extraction/p1/priority.md)

归档与安装副本 SHA-256 均为 `8f92bd1c2c0664febbd8f7c841531c546c4feb34e52e088b39ca40a9529069a4`。下列模块说明是本地源码 docstring，不是注册给 LLM 的 Tool description。

**源码模块说明原文**

```text
Explicit selected-object GLB export with bounded temporary state.
```

## 参数、返回与副作用

`export_glb(path, objects, *, convert_curves=False, unhide=False, exporter=None, **options)` 接收输出路径及当前活动视图层中明确的非空、不重复对象集合，场景须处于 Object mode。返回 `Path(path)`。

| 参数 | 行为 |
| --- | --- |
| `path` | 必填，无默认值。以 `str(path)` 交给导出器，成功后返回 `Path(path)`。封装没有解析为工作区路径、创建父目录、校验扩展名或拒绝已有文件；这些策略属于调用方。 |
| `objects` | 必填，无默认值，先转为列表。要求非空、不重复，并按对象名检查活动视图层中存在；对象类型及其导出语义由调用方与导出器确定。 |
| `convert_curves=False` | 开启时把 `CURVE` 对象的求值网格复制成临时导出对象，保留世界矩阵，结束时释放该对象和 mesh。 |
| `unhide=False` | 开启时临时解除目标对象的 `hide_set`。集合的可见性和活动视图层由调用方预先配置。 |
| `exporter=None` | 默认调用 `bpy.ops.export_scene.gltf`。测试或本地调用方可以传入兼容参数的导出函数。 |
| `**options` | 原样交给导出器，实际可用字段随 Blender 的 glTF 导出器而定。路径、GLB 格式和按选择导出在此函数内固定，重复传 `filepath`、`export_format` 或 `use_selection` 会抛 `ValueError`。 |

实现先保存视图层内所有对象的选择和 `hide_get`、活动对象、帧和子帧。清空选择后选择指定对象或临时曲线网格，设置活动对象，并要求导出器结果含 `FINISHED`。清理在 `finally` 中删除临时对象和网格，恢复记录的状态并更新视图层。恢复范围限于这些记录，没有对任意导出器造成的场景编辑做事务回滚。 [原始展示契约](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-model-preview/references/preview-atoms.md>) · [随包测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-model-preview/tests/test_preview_atoms.py>)

返回路径和 `FINISHED` 不证明文件存在、字节完整、GLB 容器合法、单位正确，或已保留 skin、clip、材质及纹理。函数不生成摘要、JSON 报告或持久任务 ID，也不登记模型版本。导出器可以在抛错或返回非完成状态前写出文件，调用方应检查实际输出；封装不删除、撤回或原子发布该文件。

| 失败位置 | 实际边界 |
| --- | --- |
| 对象列表、模式或固定选项冲突 | 对应门槛抛 `ValueError`，发生在选择／导出前。不适用的 Python 对象还可能触发属性或类型异常。 |
| 临时对象准备或导出器执行 | 异常向上传播，并进入 `finally` 清理；磁盘可能没有文件，也可能已有部分或完整文件。 |
| 导出器返回不含 `FINISHED` | 抛 `RuntimeError("GLB exporter did not finish")`；没有自动验证或回滚已经写出的文件。 |
| 清理或恢复本身失败 | 错误继续传播，可能覆盖原导出错误；不能无条件宣称场景已完整恢复。此为源码异常路径，未逐项注入。 |

## 实现伪代码

**根据已核实源码重建的伪代码。** 返回模型路径；不把文件验收或报告落盘加入封装。

```python
def export_glb(path, objects, convert_curves=False, unhide=False,
               exporter=None, **options):
    objects = require_explicit_unique_objects_in_view_layer(objects)
    require_no_fixed_export_keys(options)
    require_object_mode()
    state = capture_selection_hidden_active_frame_and_subframe()
    temporary = []
    try:
        prepare_explicit_selection(objects, temporary, convert_curves, unhide)
        result = call_exporter(
            exporter, filepath=str(path),
            export_format="GLB", use_selection=True, **options
        )
        require_finished(result)
    finally:
        remove_temporary_objects_and_meshes(temporary)
        restore_recorded_state(state)
    return Path(path)
```

### 实际导出器的条件参数

本机隔离核查使用 Blender 4.5.16 LTS／glTF I/O 4.5.51。下表为该实际导出器的部分 RNA 默认值，不是封装默认值，也不是其他 Blender 版本或目标引擎的固定契约。

| 透传字段 | 本机默认及范围 |
| --- | --- |
| `export_animations`、`export_skins`、`export_morph` | 均为 `True`。是否输出本次所需内容，仍须检查实际对象和产物。 |
| `export_extras` | `False`。显式开启只导出已有属性，不生成物理单位元数据或修正几何尺度。 |
| `export_animation_mode` | `ACTIONS`；本机枚举还含 `ACTIVE_ACTIONS/BROADCAST/NLA_TRACKS/SCENE`。 |
| `export_frame_range`、`export_force_sampling` | 分别为 `False`、`True`。 |
| `export_apply` | `False`。 |
| `export_all_influences`、`export_influence_nb` | 分别为 `False`、`4`。四影响只是当前默认，不是所有目标环境的要求。 |

仅静态身体导出可使用不同入口；`service_rig export` 明确关闭 skins、animations、morph，并清除副本形态键，因此不能替代需要保留这些内容的请求。 [静态身体导出契约](../specialized-mesh-scripts.md#rig-retarget-静态网格导出)

## 依赖、权限与前置 Hook

文件导入标准库 `pathlib` 和 Blender 的 `bpy`。默认导出需要可用的 glTF 导出算子。导出器需要目标路径的写入权限。应在独立 Blender 场景中明确对象、视图层和工作目录。经 LLM 本地命令运行时，宿主工具配置的审批、沙箱和前置检查仍生效。 [本地执行工具](../../tools/exec-command.md)

## 调用示例与核查依据

**根据已核实接口重建的 Blender Python 示例。** 将归档 `.dependency-model-preview/scripts/` 加入 Python 模块搜索路径，并准备含 `PreviewMesh` 的场景和已存在的输出目录。示例中的新路径检查由调用方补充。

```python
from pathlib import Path

import bpy
from glb_export import export_glb

target = bpy.context.view_layer.objects["PreviewMesh"]
output = Path("out/preview.glb")
if output.exists():
    raise ValueError("Use a new output path")
path = export_glb(output, [target], export_animations=False)
print(path)
```

**根据已验证行为重建的带绑定／动作示例。** 场景已存在所选 Mesh 和 Armature，处于 Object mode，父目录和新输出由调用方准备。此例仅用本机已验证的当前活动动作模式；不自动准备单位标记或多个 clip。

```python
body = bpy.context.view_layer.objects["SampleBody"]
rig = bpy.context.view_layer.objects["SampleRig"]
path = export_glb(
    Path("out/sample-motion.glb"), [body, rig], unhide=True,
    export_animations=True, export_skins=True, export_morph=True,
    export_extras=True, export_animation_mode="ACTIVE_ACTIONS",
    export_frame_range=True, export_force_sampling=True,
)
```

用归档平铺模块在 Blender 4.5.16 LTS 导出合成立方体，已检查 GLB 文件标识和活动对象恢复。另复跑 5 项随包预览测试，其中导出用例检查显式对象列表、隐对象和静态曲线转换、动画开关，以及导出异常后临时对象、选择、活动状态和帧的恢复。 [P1 精确文件表](../../upstream/1.2.11/extraction/p1/priority.md) · [随包测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-model-preview/tests/test_preview_atoms.py>)

### 合成导出与独立回读证据

前序隔离探针使用未改写的本函数和上述本机导出器，不修改安装包、原工程或用户样例，不调用云端。源为七骨、三帧、单三角的小型工程，明确选 `Body/Target`；以下结果只覆盖这份夹具。

| 检查 | 已观察结果及范围 |
| --- | --- |
| 文件及状态 | 源工程摘要未变，选择／活动／隐藏／frame/subframe 恢复。输出 SHA-256 为 `c31796d06e9e81a4f53f7f2e9c3a99012ee9d61b2b77d46a69c54337f4926a5f`。 |
| 结构及对象 | 有1个skin、7个joints和绑定矩阵，含 `JOINTS_0/WEIGHTS_0`。未选的 `HeldProp` 没有导出。 |
| 实际新进程导入 | 核实身体与骨架关联；按 `pose_bone.custom_shape` 引用排除导入器辅助Mesh。30fps下10–12帧世界坐标最大差约 `1.19e-7`，权重和约 `1.0000000149`。导入Armature为线性蒙皮，不证明任意源保体积效果等价。 |
| clip与采样 | 源 `MappedMotion` 输出为 `Animation`；21个通道优化为2或3键。时间以秒写入，约0.333333–0.4。相同GLB导入24fps场景后Action范围约8–9.6帧，不能假设名称、帧号和每通道键数原样保留。 |
| 未覆盖属性 | 夹具没有材质，输出materials为空；节点extras没有物理单位标记。`export_extras=True` 不会补出该标记。 |
| 输入结构限制 | 本机导出日志提示Armature父级关系警告；该夹具随后回读通过，不能扩大成任意实例／父级结构可靠。 |

临时探针文件为[导出记录](<C:/Users/11408/AppData/Local/Temp/hi3d-delivery-export-i3gii0cn/export-result.json>)、[结构记录](<C:/Users/11408/AppData/Local/Temp/hi3d-delivery-export-i3gii0cn/glb-structure.json>)、[独立导入记录](<C:/Users/11408/AppData/Local/Temp/hi3d-delivery-export-i3gii0cn/import-result.json>)和[24fps导入记录](<C:/Users/11408/AppData/Local/Temp/hi3d-delivery-export-i3gii0cn/import24-result.json>)。临时目录可能被清理，固定源码、导出器版本和中性示例用于长期复核；产物摘要只标识该次运行。

### 非1 fps_base 的本机边界

额外探针设置 `render.fps=30, fps_base=1.25`，有效fps为24。10／11／12帧按有效fps应为约0.416667／0.458333／0.5秒，当前导出器实际写0.266667／0.293333／0.32秒。有效fps本身为整数，此例验证的是 `fps_base!=1`，不是直接测试29.97等分数有效fps。[实际时间记录](<C:/Users/11408/AppData/Local/Temp/hi3d-delivery-export-i3gii0cn/fractional-time-result.json>)

本机源码 [keyframes.py:13](<D:/install/blender/4.5/scripts/addons_core/io_scene_gltf2/blender/exp/animation/keyframes.py:13>) 和 [armature/sampler.py:108](<D:/install/blender/4.5/scripts/addons_core/io_scene_gltf2/blender/exp/animation/sampled/armature/sampler.py:108>) 使用 `frame/(fps*fps_base)`。外部导出器入口 [io_scene_gltf2/__init__.py](<D:/install/blender/4.5/scripts/addons_core/io_scene_gltf2/__init__.py>) SHA-256 为 `ec64056ad551a5b54801aacd48e7f60fb769a653f97b1e1ade2d146a341898a4`。这属于当前实际外部依赖，不是Hi3D云端算法，也不能泛化到其他Blender版本。

**待实测。** 真实高模、四足骨语义、多软层、材质／纹理、单位完整交付、多clip／NLA与长动作循环、复杂形态键／驱动／修改器及目标加载器；不同导出器版本的参数和时间；输出覆盖、部分文件及清理异常的逐项故障注入。已有三个静态GLB与留存会话不覆盖这些分支，不能替代实际产物回读或画质／动作验收。
