# Hi3D 1.2.11 P1 资源归档

本批保留 15 个原件的安装包相对路径及原始字节。归档收据记录每个文件的大小和 SHA-256，并绑定 P1 精确文件表、P0 发布清单和同一发行锁。43 项证据按相对路径和安装包链接引用。 [归档收据](../../upstream/1.2.11/archived-p1/archive.lock.json) · [P1 精确文件表](../../upstream/1.2.11/extraction/p1/priority.md) · [43 项证据与验证缺口](evidence.md)

## 原件与独立说明

| 资源 | 用途 |
| --- | --- |
| [`image_sheet.py`](image-sheet.md) | 由调用方指定照片、顺序与标签，输出联系表和格位映射。 |
| [`asset_scene.py`](asset-scene.md) | 在 Blender 中重开 GLB 或 BLEND，获取对应场景对象。 |
| [`scene_io.py`](scene-io.md) | 导入、保留和构造显式场景对象。 |
| [`glb_export.py`](glb-export.md) | 从显式对象集合导出 GLB，并恢复记录的状态；返回路径不验证文件、skin／clip或质量。实际导出选项由当前导出器决定。 |
| [`source_views.py`](source-views.md) | 在归一化场景中渲染前、后、左、右、顶和展示视图。 |
| [`preview_scene.py`](preview-scene.md) | 相机、构图、投影和灯光支持。 |
| [`scene_samples.py`](scene-samples.md) | 对明确帧及子帧取样，恢复调用前时间位置。 |
| [`mesh_snapshot.py`](mesh-snapshot.md) | 获取原始或求值网格、三角面及可选属性。 |
| [`glb_bounds.py`](glb-bounds.md) | 用受支持的静态 POSITION 与节点变换计算范围；非空场景、最终世界范围有限性和实际蒙皮另验。批次报告覆盖行为见独立页。 |
| [`glb_clips.py`](glb-clips.md) | 读取 GLB 容器，并可显式合并同时播放且无冲突的动画通道；不拼接时间线或验收动作语义。GLB与报告分步写入。 |
| [`material_nodes.py`](material-nodes.md) | 用线性颜色和节点参数创建基础 Principled 材质。 |
| [`texture_bake.py`](texture-bake.md) | 对已对齐的网格执行指定通道的本地纹理烘焙。 |
| [`cycles_device.py`](cycles-device.md) | 选择 Cycles 设备，并在上下文退出时恢复偏好和场景状态。 |
| [`rigging/__init__.py`](rigging-package.md) | 保留数值蒙皮模块的原有包入口。 |
| [`rigging/skin_weights.py`](skin-weights.md) | 校验权重、按明确规则返回局部修复数组及统计，筛查同拓扑姿态的拉伸；共享位置平均及失败边界见[独立函数契约](skin-weights.md#repair_regions-局部数组修复)。 |

## 依赖闭包与使用范围

7 条文件依赖或包结构关系均在归档内。调用方传入的图片和模型、独立 Blender、Pillow、NumPy 及 Blender 组件作为外部前提记录。需要后台脚本包装器时沿用已归档的 P0 `execute.py`。 [P1 依赖与外部前提](../../upstream/1.2.11/extraction/p1/priority.json) · [P0 Blender 启动包装器](../blender-execute.md)

| 归档入口 | 已核对路径关系 |
| --- | --- |
| `asset_scene.py` | 同目录 `scene_io.py`。 |
| `glb_bounds.py` | 同目录 `glb_clips.py`。 |
| `source_views.py` | 同目录 `preview_scene.py`，六方向渲染调用面积灯入口。 |
| `preview_scene.py` | `check_framing` 按需加载同目录 `scene_samples.py`。 |
| `scene_samples.py` | 同目录 `mesh_snapshot.py`。 |
| `rigging/skin_weights.py` | 保留同目录 `__init__.py` 供原包路径导入。 |
| `texture_bake.py` | 同目录 `cycles_device.py`。 |

归档副本已在 Windows 临时目录隔离验证。Blender 4.5.16 LTS 使用归档的 GLB 导出与重开、网格及子帧取样和六方向渲染入口，CPU 烘焙夹具覆盖 `DIFFUSE`、`EMIT`、`NORMAL`、16 位法线 PNG 及状态恢复。随包 Python 的 Pillow 与 NumPy 环境验证了拼版像素和源图摘要、GLB 容器及包围盒、蒙皮包导入、权重校验和拉伸筛查。各示例使用合成输入，复核范围在各资源页中说明。

真实动物模型的顶视旋转、皮毛材质和四足形变仍需以目标样本验收。线上服务的顶视支持、受理与画质依后续选型验证。安装包中的人形绑骨和供应商脚本保留在证据索引中。 [证据与验证缺口](evidence.md)

## 专项发行中的调用证据

`head-lowpoly/scripts/` 下以下七个模块的 SHA-256 与 P1 收据对应原件相同。按实际导入与调用可核对它们的用途。 [P1 归档收据](../../upstream/1.2.11/archived-p1/archive.lock.json)

| 同字节资源 | 实际调用与条件 |
| --- | --- |
| `scene_io.py` | `head_io.py` 通过 `import_objects` 和 `retain_meshes` 导入并保留受选对象。`head_preview.py` 用 `create_mesh_object` 构造预览网格。 [导入入口](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/head_io.py:7>) · [预览入口](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/head_preview.py:6>) · [场景 IO 说明](scene-io.md) |
| `preview_scene.py`、`material_nodes.py` | `head_preview.py` 对应的预览阶段使用 `area_light` 和 `principled_material` 构造灯光和材质。 [预览导入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/head_preview.py:6>) · [预览场景](preview-scene.md) · [材质节点](material-nodes.md) |
| `texture_bake.py`、`cycles_device.py` | 本地烘焙时，`bake.py` 调用 `bake_image`，共享烘焙模块使用 `cycles_device_context` 管理设备状态。 [烘焙调用](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/bake.py:103>) · [设备调用](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/texture_bake.py:39>) · [纹理烘焙](texture-bake.md) · [设备环境](cycles-device.md) |
| `glb_clips.py` | `deliver.py` 用 `read_glb` 回读交付容器。 [容器回读](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/deliver.py:5>) · [GLB 资源](glb-clips.md) |
| `image_sheet.py` | `package_review.py` 用 `write_sheet` 整理交付报告中的拼图。 [报告拼图](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/package_review.py:7>) · [拼图资源](image-sheet.md) |

### rig-retarget 的导入与调用

发行包把 `skin_weights.py` 和 `mesh_snapshot.py` 物化进 `rig-retarget/scripts/rigging/`。本轮核对两个文件与 P1 收据对应原件的 SHA-256。专项包有自己的 `rigging/__init__.py`，其摘要与 P1 中的同名文件不同。 [发行映射](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/package.json:3>) · [P1 原件收据](../../upstream/1.2.11/archived-p1/archive.lock.json) · [包初始化说明](rigging-package.md)

| 资源 | 实际调用与条件 |
| --- | --- |
| `skin_weights.py` | `service_rig.py` 顶层导入 `check_weights`、`repair_regions` 和 `stretch_metrics`。绑定、检查和修订分支调用这些函数。`export` 分支加载该模块，执行基础网格检查、导出及摘要写入。`rig_adapter inspect/calibrate` 经 `service_rig` 间接导入该模块，隔离追踪中未执行其权重函数。`validate_blend` 则直接调用其 `stretch_metrics`，从基础网格读取三角索引，并通过 depsgraph 采样各帧顶点。 [实际拉伸调用](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/validate_blend.py:95>) · [验收脚本契约](../specialized-mesh-scripts.md#validate_blend-已保存工程的数值检查) · [专项导入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:7>) · [导出函数](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:127>) · [适配器导入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:11>) · [蒙皮资源](skin-weights.md) · [单身体检查](../specialized-mesh-scripts.md#service_rig-inspect-单身体蒙皮检查) · [权重回迁](../specialized-mesh-scripts.md#service_rig-bind-服务权重回迁) |
| `mesh_snapshot.py` | `build_character` 实际调用 `blender_core.mesh_arrays()`，通过专项物化副本读取基础网格的局部坐标。参数为 `evaluated=False`、`space="local"`、`triangulation="require_triangles"`、`precision="float32"`，输出用于初始权重及网格指纹。`prepare_mesh` 自行读写基础顶点，`service_rig export` 使用自身 `surface()`。 [构建调用](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py:186>) · [快照入参](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/blender_core.py:9>) · [准备取点](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/prepare_mesh.py:109>) · [导出取面](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:15>) · [快照接口](mesh-snapshot.md) |
| `glb_export.py` | 通用对象集合导出入口。`service_rig export` 将临时副本直接交给 Blender glTF 算子。 [共用导出说明](glb-export.md) · [实际算子调用](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:155>) |

Blender 4.5.16 LTS 隔离复核覆盖两种文件。把已导入的权重和形变函数替换为触发即报错的桩后，`export_body()` 仍可生成合成 GLB，另行重开后世界坐标和三角数符合预期。独立进程重开另一个准备后的合成 `.blend`，通过归档 `asset_scene` 和 `mesh_snapshot` 读得 4 顶点、2 三角面、6 处面角 UV 和两种材质，世界 Z 范围约为 `[0, 1.8]`。默认 `prepare_mesh` 的 `rigging` 模块加载记录仅含包初始化和 `rigging.prepare_mesh`。真实模型的区域归属、保形、贴图完整性和变形质量仍需按实际资产验收。 [静态导出回归](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_service_rig.py:14>) · [准备与落盘](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/prepare_mesh.py:109>) · [P0 启动与计时](../README.md#专项-blender-命令的执行包装)

`rig_adapter inspect/calibrate` 使用同包 `blend_common.open_input()` 打开 BLEND。隔离追踪确认两者均不依赖 P1 `asset_scene` 或 `mesh_snapshot` 执行。`service_rig inspect` 则由自身 `surface()` 与依赖图读取基础和求值网格，直接调用 `skin_weights` 的数值函数。调用方可另选本页的场景与网格资源读取实际文件。 [包内载入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/blend_common.py:108>) · [适配器工具契约](../specialized-mesh-scripts.md#rig_adapter-已有骨架检查与调整)

`service_rig repair` 使用 `surface()` 和 `skin_table()` 读取基础网格及当前变形权重，匹配规则指纹后调用 P1 `repair_regions`；该函数只返回新数组和统计，Blender 写回、保护比较、工程保存及 JSON 报告由专项脚本完成。写回函数 `write_changed_weights` 位于未列入 P1 收据的 `service_rig.py`；`io_utils.py`、`weight_graph.py` 也未归档为 P1。`inspect/repair` 不会自动执行 P1 场景／网格回读，也没有新的同名 LLM Tool 注册。 [数组修复](skin-weights.md#repair_regions-局部数组修复) · [本地修订 CLI](../specialized-mesh-scripts.md#service_rig-repair-局部权重修订) · [写回与保护函数](../specialized-mesh-scripts.md#service_rig-权重写回与保护函数)

`rig_adapter cache` 同样通过 `blend_common.open_input()` 重开 BLEND，直接用 depsgraph 求值所选 Armature 的全部骨骼。其采样循环自行保存并恢复当前帧及子帧，没有调用 P1 `asset_scene`、`scene_samples` 或 `mesh_snapshot`。`rig_adapter` 顶层通过 `service_rig` 间接加载 `skin_weights`、`weight_graph` 等模块，但缓存分支不调用权重检查、区域修复、拉伸测量或权重求解；`weight_graph` 的 SciPy 导入位于 `solve_weights()` 函数内，因此纯缓存不要求执行 SciPy 求解。`cache_bvh` 则直接调用 Blender BVH 导入算子并读取姿态矩阵。这些是安装源码的调用关系，与另选共享资源进行取证分别记录。 [求值循环](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:198>) · [缓存分支](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:300>) · [间接导入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:9>) · [条件性 SciPy 导入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/weight_graph.py:39>) · [BVH 缓存契约](../specialized-mesh-scripts.md#cache_bvh-bvh-兼容缓存)

缓存使用的 `io_utils.py`、`retarget_math.py` 由 Skin Weights 和 Motion Retarget 资源物化，P0／P1 收据均未收录。专项说明记录其参数、矩阵门禁、摘要与落盘边界。Blender 4.5.16 LTS 的留存合成探针验证了子帧恢复、非整数源帧率、显式源帧率、NLA-only 求值，以及静态骨架仍能生成合法格式缓存；这些结果不表示报告包含动作语义或变形质量验收。真实 BVH／FBX／GLB／VMD 导入链、复杂控制器、长动作中断和四足动作质量仍待实测。三个留存 GLB 与历史会话不覆盖这些分支。 [共享函数与安装摘要](../specialized-mesh-scripts.md#动作缓存的分派与共享函数) · [缓存结果与验证范围](../specialized-mesh-scripts.md#rig_adapter-cache-求值动作缓存) · [留存探针结果](<C:/Users/11408/AppData/Local/Temp/hi3d-source-cache-54af2857c76e480c9f387c7d719edbc5/probe-results.json>) · [发行映射](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/package.json:3>)

`rig_adapter calibrate/retarget` 的实际载入与保护来自 `blend_common` 和 `service_rig.preserved_signature`；`retarget` 另调用专项 `retarget_math.retarget_samples` 计算旋转及根位移，再由 `bake_action` 写目标 Action。`retarget_math.py`、`blend_common.py`、`io_utils.py` 及专项 `rig_timing.py` 不是已归档 P0／P1 文件。经导入链加载 P1 `skin_weights` 不表示这些分支自动执行 `check_weights`、`repair_regions` 或 `stretch_metrics`，也不会自动采用本页的场景／网格回读。几何／权重保护、映射计算、实际形变数值检查分别取证，`pose_qa_pending:true` 保留姿势待验状态。 [映射 CLI](../specialized-mesh-scripts.md#rig_adapter-retarget-动作映射与烘焙) · [函数及副作用](../specialized-mesh-scripts.md#retarget_math-与-action-烘焙函数) · [实际分支](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:340>)

原比例骨架的 `motion.build_action` 使用 Blender、NumPy、mathutils 和同包 `blend_common.curves`；`sequence_actions` 在 builder 内组织 Action／NLA。动画包 `stage_ops clip` 则通过显式 `--rig-skill` 加载 `blend_common` 的场景与文件函数。这些入口均为本地脚本或函数，不能列为 P1 已归档原件或动态 LLM Tool；它们不会因导入共享原语而自动完成 P1 网格、接缝或拉伸验收。条件性的对象导出和已有 GLB 动画片段处理可另选本批 `glb_export`、`glb_clips`，两者不进行跨骨架重定向。 [旧动作与 NLA](../specialized-mesh-scripts.md#motionbuild_action-与-nla-编排) · [裁剪参数及落盘](../specialized-mesh-scripts.md#stage_ops-clip-已烘焙动作裁剪) · [GLB 导出](glb-export.md) · [既有片段处理](glb-clips.md)

### 通用取证的适用范围

| 检查目标 | 可选资源与证据边界 |
| --- | --- |
| 场景、尺寸与网格属性 | `asset_scene` 可重开实际 `.blend` 并禁用内嵌脚本，也可通过 `scene_io` 导入 GLB。`mesh_snapshot` 按调用方选择的局部或世界空间和求值状态返回三角数组及可选面角 UV、材质编号。核对父级与尺度时可分别采样基础局部坐标和实际世界坐标。验收原生四边面及保护链时另从实际编辑工程或 OBJ 读取面环。 [场景载入](asset-scene.md) · [场景 IO](scene-io.md) · [网格快照](mesh-snapshot.md) |
| 拓扑与相交 | 调用方可另选专项 `mesh_measure` 核对实际连通、边界、非流形和退化，选用 `collision` 检查严格三角穿越。`geometry_compare` 需要同索引拓扑。焊接或减面已改变索引时，应另建立表面对照。这些检查脚本属于随包抽离候选。 [网格测量与比较](../specialized-mesh-scripts.md#mesh-audit-网格测量函数) · [严格穿越源码](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/collision.py:26>) · [抽离清单](../../upstream/1.2.11/extraction/extraction.json) |
| GLB 静态包围盒 | `glb_bounds.inspect()` 使用 `glb_clips.read_glb()` 解析 GLB 容器，对支持的内嵌浮点位置和默认场景节点变换计算尺寸，并列出动画名与外部资源 URI。批处理 CLI 另要求文件小于 25 MiB 且无外部资源 URI。`.blend` 对象与坐标由场景载入和快照接口读取。 [GLB 包围盒](glb-bounds.md) · [容器读取](glb-clips.md) |
| 对照图与展示文件 | `source_views` 和 `preview_scene` 生成或辅助布置方向明确的视图。前后保形比较应锁定同一尺度和相机，避免独立自动取景掩盖尺度差。需交付选定对象的 GLB 时可用 `glb_export`。 [来源视图](source-views.md) · [预览场景](preview-scene.md) · [GLB 导出](glb-export.md) |
| 动作形变 | 需要动作验收时，调用方可选 `scene_samples` 读取指定帧、`mesh_snapshot` 抽取求值网格，或用 `skin_weights` 核对权重及同一最终拓扑的静止和姿态网格。这些不是 `rig_adapter cache/calibrate/retarget` 自动执行的检查，缓存报告也不含形变通过结论。重建前后的不同拓扑需另外建立对应。真实四足形变、接缝及目标加载器表现仍待实测。 [场景取样](scene-samples.md) · [蒙皮权重](skin-weights.md) · [求值缓存](../specialized-mesh-scripts.md#rig_adapter-cache-求值动作缓存) |

## 复核或重建归档

从仓库根目录执行。命令核对发行锁、抽离清单及已发布 P0 和 P1 清单，逐件读取安装包计算摘要，然后验证整个归档的文件集合。已有归档通过核查时原样复用。 [命令入口](../../../../scripts/hi3d/archive-p1.py)

输出目录须与版本下的 `inventory/` 和 `extraction/` 互不包含。示例使用两者的同级目录。

运行示例时将产物写入独立临时目录。普通 Python 可用 `-B`，Blender 内嵌 Python 可在导入前设置 `sys.dont_write_bytecode = True`，避免在归档目录生成字节码缓存。

```powershell
$release = 'docs/hi3d/upstream/1.2.11'
python -B scripts/hi3d/archive-p1.py `
    --release-dir $release `
    --resources-root 'D:/install/Hi3DAgent.__hi3d-transaction/resources' `
    --output-dir "$release/archived-p1"
```
