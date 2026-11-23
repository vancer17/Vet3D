# 网格与动画处理专项脚本

## 资源身份与归档范围

以 Hi3D Agent 1.2.11（Windows x64）的安装事务备份为核查基准。下文的随包原件位于 `resources/runtime/prebuilt-skills/`。`SKILL.md`、PCG 与参考文件提供选用条件及接口约定。Python 命令和函数由本地调用方执行，可通过工作区的命令工具启动。公开 MDF 请求由 Runtime 注册的 `mdf_api` 处理，`retopology` 是该工具的能力枚举。 [版本快照](../upstream/1.2.11/README.md) · [MDF Tool](../tools/mdf-api.md#参数与结果) · [本地命令 Tool](../tools/exec-command.md)

本页列出的专项脚本已进入安装包抽离候选清单。P0、P1 收据均无这些专项原件，P2 延期表也未单独登记这些路径。归档 Skill、PCG 和参考文件用于固定发行证据。相关的运行、缓存和资产回读能力可复用已归档的共享原件。 [候选清单](../upstream/1.2.11/extraction/extraction.json) · [优先级记录](../upstream/1.2.11/extraction/priority.json) · [P0 资源](README.md) · [P1 资源](p1/README.md)

## 命令与函数

### `hi3d-quad-judge.py`

`python hi3d-quad-judge.py <predict|verdict|route|align> <input.json> <output.json>` 读取调用方已准备的测量数据，创建新的 JSON 报告并向标准输出写摘要。输出文件须尚未存在。工具通过报告字段表达判断，`rollback_refine`、`keep_previous` 等动作可以随退出码 `0` 返回。捕获到 `KeyError` 或 `ValueError` 时退出 `2`。 [CLI 入口](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/quad-flow-plus/scripts/hi3d-quad-judge.py:228>)

| 模式 | 输入与返回 |
| --- | --- |
| `predict` | 用 `epsilon` 和 `regions` 估算保形减密。每个区须有 `id`、`faces`。`kind` 默认 `gray`，也可为 `yellow` 或 `red`。灰、黄区还需 `area`，可传 `max_curvature`、`boundary_segments`、`learned_floor`，黄区可传 `max_span`。红区保留当前面数。返回 `regions`、`totals` 中的 `aggressive`、`recommended`、`conservative`。 [预测函数](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/quad-flow-plus/scripts/hi3d-quad-judge.py:48>) |
| `verdict` | 传 `epsilon`、可选 `limits`，每区传 `id`、`level` 和 `metrics`。指标字段为 `forward_error`、`backward_error`、`min_angle`、`max_aspect`、`max_normal_degrees`、`max_uv_stretch`、`closed_loops`、`nonquad`、`nonmanifold`。`probe` 默认为 `false`，启用时须传 `faces`。级别依 `8,6,4,3,2,1` 回退。返回 `action`、`next_level`、`failures`、`learned_floor`。探针通过时下限取实测面数，其余为 `null`。 [验收函数](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/quad-flow-plus/scripts/hi3d-quad-judge.py:64>) |
| `route` | 传候选 `primitive`、至少三视图的 `primitive_silhouette_iou`、`cavity_status`、含 `method/scope/record` 的 `cavity_evidence`。`decomposition_needed` 可选，默认为 `false`，`limits.min_primitive_iou` 默认 `0.95`。返回 `primitive_align`、`v5_baseline`、`inspect_components` 或 `inspect_geometry`。 [路由函数](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/quad-flow-plus/scripts/hi3d-quad-judge.py:145>) |
| `align` | 传 `iteration`、`faces`、`v5_faces`、`gray_yellow_max`、至少三个值的 `silhouette_iou`、`silhouette_max_error`、`bad_red`、`bad_gray_yellow`、`epsilon`、`metrics`、`local_attempts`、`stalled`、`fallback_validated`。可传 `next_faces`、`limits.min_silhouette_iou`（默认 `0.99`）和 `quality_limits`。返回 `action` 与 `failures`，表达接受、细分、修复、回退或继续取证。 [对齐判定](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/quad-flow-plus/scripts/hi3d-quad-judge.py:185>) |

实际取样、拟合、建模和写网格由调用方完成。`route` 使用传入的轮廓和内腔证据；`verdict` 使用传入的实测指标。 [专项 Skill](../upstream/1.2.11/prebuilt-skills/quad-flow-plus/SKILL.md)

### `hi3d-chain-budget.py`

`python hi3d-chain-budget.py <plan|verify-chains> <input.json> <output.json>` 要求输入、输出解析后都在当前工作区内，输出使用不存在的 `hi3d-` 文件名。结构或路径错误退出 `2`。验证失败时仍写报告并退出 `1`。预算计算可在 `count_bounds_feasible: false` 时正常退出 `0`。 [CLI 和路径边界](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/quad-flow-plus/scripts/hi3d-chain-budget.py:133>)

- `plan` 读取 `baseline_quads`、`target_quads` 或 `remaining_ratio` 二选一、`core_closed`，以及可选 `preserved_quads`、`protected_core_vertices`、`core_euler_characteristic`。输出计划三角基片数、`K + 3T` 所得原生四边面数、三角化预览面数、必要下限和可行性。闭合核心考虑偶数基片数，欧拉下限仅用于给出欧拉特征的闭合核心。该报告的 `geometry_quality_verified` 为 `false`。 [计划函数](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/quad-flow-plus/scripts/hi3d-chain-budget.py:24>)
- `verify-chains` 接收实际 `vertices`、多边形 `faces`、有序 `chains` 及可选 `marker_tolerance`，默认 `1e-6`，使用调用方坐标单位。每条链给唯一 `id`、布尔 `closed`、有序顶点索引，按需给 `required`（默认 `true`）和 `reference_markers`（`vertex`、`position`）。从实际面环提取无向边，逐链返回 `missing_edges`、`maximum_marker_displacement`、`chain_valid`，并在至少有一条必保链且全部通过时返回 `all_required_chains_valid: true`。没有标记时位移为 `null`，`full_surface_quality_verified` 固定为 `false`。 [验证函数](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/quad-flow-plus/scripts/hi3d-chain-budget.py:77>)

**合成调用示例。** 在临时工作区创建 `rim.json`，内容如下。

```json
{
  "vertices": [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
  "faces": [[0, 1, 2, 3]],
  "chains": [{"id": "rim", "closed": true, "vertices": [0, 1, 2, 3]}]
}
```

从该目录调用随包 Windows Python。

```powershell
$package = 'D:/install/Hi3DAgent.__hi3d-transaction/resources'
$python = "$package/runtime/.runtime-python/python/python.exe"
$script = "$package/runtime/prebuilt-skills/quad-flow-plus/scripts/hi3d-chain-budget.py"
& $python -B $script verify-chains rim.json hi3d-rim-report.json
```

外环返回退出码 `0`。在新输入中将链顶点改为 `[0,2,3]`，使用新的报告路径再运行，返回退出码 `1` 与 `missing_edges: [[0,2]]`。两份报告均将全表面质量保留为未验证。 [边链测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/quad-flow-plus/scripts/hi3d-test-chain-budget.py>)

### `hi3d-quad-template.py`

NumPy 函数 `build_template(grid_points, normal)` 用于闭合四边过渡，只接收包括 `(0,0)` 至 `(4,4)` 全部键的 `5×5` 点阵和非零有限法向。输入点均须为有限三维坐标，初始网格步长须非零。生成成功时返回 `coordinates`、`quads`、`topology`，把 16 个 quad 改为 1 个中心 quad 加 14 个过渡 quad，保持外边并核对两条边界环。输入错误抛出 `ValueError`，模板构造失败返回 `None`。本地投射、原网格替换、属性转移和误差测量由 Blender 调用方另行完成。 [函数实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/closed-quad-transition/scripts/hi3d-quad-template.py:121>) · [模板验证](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/closed-quad-transition/scripts/hi3d-quad-template.py:85>) · [闭合过渡 Skill](../upstream/1.2.11/prebuilt-skills/closed-quad-transition/SKILL.md)

### `head-lowpoly` 的交接与回读

该人头专项由 `python run.py <config.json> [--check] [--fresh]` 调用。必填配置为内嵌资源的高模 GLB `source`、与原件摘要匹配的眼口区域配置 `face_config`、包外任务目录 `output`、实际 `blender`。`retopology_backend` 允许 `runtime` 或 `instant_meshes`，Runtime 路线取回原任务记录，`instant_meshes` 路线要求外部程序路径。存在 `.runtime-profile.json` 时默认走 `runtime`，否则默认走 `instant_meshes`。`--check` 仅校验配置，通过后输出 `CONFIG_READY`。实例运行按输入、配置、脚本及输出摘要决定阶段复用。`--fresh` 重建本地阶段记录；远端恢复仍以原作业账本为准。 [入口与预检](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/run.py:34>) · [复用条件](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/run.py:224>) · [完整配置](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/references/inputs.md:18>)

| 入口 | 职责与检查 |
| --- | --- |
| `mdf_handoff.prepare_handoff(config)`、`resolve_result(config)` | 从 `working_surface.glb`、`remesh_face_goal` 和稳定作业路径生成 `retopology-request.json`。包内组包为 `action: invoke`、`capability: retopology`、`file`、`params: {face: remesh_face_goal, face_type: quads, topology_method: standard}`、`jobPath`、`outputDir`。账本与下载目录分开，默认分别为 `mdf-retopology.json` 和 `mdf-retopology/`。恢复时复核请求参数、源摘要参与计算的指纹、输出目录、HTTP 200、整数业务码 0 及 `SUCCEEDED`，再校验该目录中的 `model_obj` ZIP 路径和摘要。校验通过返回 ZIP 路径。等待服务结果或下载时，上层 CLI 返回 `waiting_retopology` 与退出码 `3`。 [交接实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/mdf_handoff.py:20>) · [退出状态](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/run.py:295>) |
| `mdf_handoff.unpack_geometry(archive, target)` | ZIP 内须有唯一、非空且不超过 512 MiB 的 OBJ。调用前由 `resolve_result` 复核原产物摘要。解包按读取字节数再次限制上限，仅把 `v/vt/vn/f/o/g/s` 行写入显式目标并返回目标路径。 [ZIP 处理](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/mdf_handoff.py:58>) |
| Blender `retopology.py -- working`、`import`、`facial` | 各动作追加同一个 `resolved_config.json`。`working` 从 `source.blend` 生成工作副本，以 `working_surface.glb` 或 `working_surface.obj` 导出，并生成 `working_surface_report.json`。`import` 按输入 GLB 的 Y-up 约定回读 OBJ，要求单网格、有限顶点、原生非退化四边面，包围盒偏差超过源最长跨度 10% 时拒绝。输出 `source_quads.obj` 和 `retopology_import_report.json`。`facial` 按两个眼区和一个口区配置重建指定闭环，输出 `Lowpoly_Unbaked.blend`、`lowpoly_patch_data.npz` 和 `lowpoly_report.json`。 [工作网格](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/retopology.py:21>) · [实际 OBJ 验证](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/retopology.py:72>) · [眼口处理](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/retopology.py:318>) |

人头包实际导入 P0 同字节副本的 `run_process`、`digest` 与 `artifacts_match`。本地烘焙依赖 P1 `texture_bake.py`、`cycles_device.py`，完整高模保留为独立烘焙源。 [进程资源](process-run.md) · [断点资源](checkpoints.md) · [纹理烘焙](p1/texture-bake.md) · [人头 Skill](../upstream/1.2.11/prebuilt-skills/head-lowpoly/SKILL.md) · [人头接口参考](../upstream/1.2.11/prebuilt-skills/head-lowpoly/references/retopology-api.md)

### `rig-retarget` 静态网格导出

`rig-retarget/scripts/run.py` 将 `service_rig export` 分派到 `rigging.service_rig.main`。这是由 Blender 执行的本地子命令。必填 `--input`（源 `.blend`）、`--body`（确切对象名）、`--output`（新 `.glb`）及 `--report`（新 JSON，与输出路径不同）。可选 `--faces` 是至少 `4` 的整数，省略时保留基础网格。缺失对象、空 Mesh、非有限基础坐标、非法预算或已有输出会使执行失败。`--python-exit-code 1` 可让 Blender 以退出码 `1` 报告未处理的 Python 异常。 [CLI 分派](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/run.py:31>) · [参数与路径校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:372>)

**实现伪代码。** 临时副本沿用源对象在已打开场景中的 `matrix_world`。所需的休止帧和静态求值结果由输入准备方确定。

```python
body = open_blend_and_find_mesh(input_path, object_name)
with selected_base_mesh_copy(body, matrix_world=body.matrix_world) as copy:
    clear_shape_keys(copy)
    source_triangles = surface(copy).triangle_count
    if faces is not None and source_triangles > faces:
        apply_decimate(copy, ratio=faces / source_triangles)
    export_selected_glb(output, animations=False, skins=False, morph=False)
    result = {
        "mesh": str(output), "sha256": file_digest(output),
        "triangles": surface(copy).triangle_count,
        "source_object": body.name, "base_mesh_only": True,
    }
result["input_sha256"] = file_digest(input_path)
atomic_json(report, result)
```

`surface()` 使用 Blender 和 NumPy 读取有限基础顶点与 loop triangles。文件由 Blender glTF 导出算子写出。`io_utils.file_digest` 按 1 MiB 分块取 SHA-256，`atomic_json` 经同目录临时文件写入、`fsync`、替换报告。GLB 先落盘，报告随后写入。脚本清理临时对象、恢复选择，原工程不保存改动。减面预算为目标值，报告保留实测三角数。 [基础网格读取](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:15>) · [副本导出](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:127>) · [摘要与原子写入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/io_utils.py:10>)

顶层导入同包 `weight_graph`、`skin_weights` 和 `validate_blend`，其中权重、动作检查和修订函数用于其他子命令。默认导出无需 SciPy。`skin_weights.py` 是与 P1 原件同字节的导入依赖，`mesh_snapshot.py` 由同包另一分支调用。随包示例直接启动 `run.py`，也可由 P0 `execute.py` 包装。若在子命令前传全局 `--timing-log`，入口使用本包 `rigging/timing.py` 追加阶段 JSONL，可用 `--task-id` 和 `--attempt` 标记。 [顶层依赖](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:7>) · [可选计时](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/run.py:38>) · [P1 物化证据](p1/README.md#专项发行中的调用证据) · [P0 启动包装](blender-execute.md)

**根据随包 CLI 重建的调用示例。** 从已有 `sample.blend` 选取 `SampleMesh`，输出到当前目录的新路径。需要减面时另传 `--faces`。

```powershell
$skills = 'D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills'
& 'D:/install/blender/blender.exe' --background --factory-startup `
  --disable-autoexec --python-exit-code 1 `
  --python "$skills/rig-retarget/scripts/run.py" -- service_rig export `
  --input 'sample.blend' --body 'SampleMesh' `
  --output 'sample-static.glb' --report 'sample-export.json'
```

`run.py`、`service_rig.py`、`io_utils.py` 和专项计时脚本均可在安装包中定位，P0／P1 收据未收录这些专项路径。 [包物化映射](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/package.json:3>) · [抽离候选](../upstream/1.2.11/extraction/extraction.json) · [绑定 Skill](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md)

### service_rig inspect 单身体蒙皮检查

`service_rig` 是由 Blender Python 运行的本地 CLI。`scripts/run.py` 按显式子命令导入 `rigging.service_rig`。模块文档字符串同时供 `argparse` 生成本地帮助，下方逐字保留该字符串。入口可由宿主本地执行工具启动。 [模块与导入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:1>) · [命令分派](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/run.py:31>) · [本地执行工具](../tools/exec-command.md)

```text
Local Blender handoff for auto-rig: export, bind, inspect and repair. No network.
```

| 参数 | 条件及默认值 |
| --- | --- |
| `inspect` | 选定读取单个身体及其蒙皮求值的操作。 |
| `--input <BLEND>`、`--body <对象名>`、`--report <JSON>` | 必填，均无默认值。身体按实际对象名查找。入口检查报告尚不存在且与输入路径不同。 |
| `--rig <对象名>` | 可省略，省略时取 `body.find_armature()`。提供时要求该对象为 Armature，且等于身体当前关联的 Armature。 |
| `--frames <帧列表>` | 该操作必填。逗号分隔整数或含首尾的闭区间，如 `1:12,20`，排序去重后须非空；不接受小数帧。 |
| `--height <数值>` | 该操作必填，采用身体网格局部坐标的同单位高度，进入拉伸函数后校验有限且大于零。 |

共用 parser 还接受 `--output`，但 `inspect` 不保存该路径；若提供，仍参与输出与报告不得同址的校验。`--faces`、`--rigged-glb`、`--targets`、`--alignment-tolerance`、`--rules` 在此操作不读取。参数可以解析不代表该操作使用它。 [条件分派与路径门槛](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:388>)

输入工程由 `open_mainfile` 载入，当前对象处于编辑模式时切换到对象模式。该命令没有为载入算子显式设置 `use_scripts=False`，下面启动示例由 Blender `--disable-autoexec` 约束自动执行。`inspect_skin` 保存原整数帧，并在正常或异常离开逐帧循环时恢复，但没有保存并恢复原 subframe。它要求身体、骨架和指向该骨架的 Armature 修改器在每个指定帧参与视口求值，基础表面非空且坐标有限，逐点变形权重有效。求值网格须与基础顶点形状及三角索引逐项对应，改变拓扑时要求建立相应基准。 [参数和载入顺序](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:372>) · [逐帧检查](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:288>)

| 函数或字段 | 输入、结果和边界 |
| --- | --- |
| `surface(obj)` | 输入非空 Mesh。读取有限基础顶点为 `float32 N×3`，计算 Blender loop triangles 后返回 `int32 M×3` 索引。计算三角缓存改变进程中的网格缓存状态。 [实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:15>) |
| `skin_table(obj, rig)` | 按骨架中 `use_deform` 的实际骨名顺序建立密集 `N×B` 权重表，只纳入同名顶点组，再交 `check_weights` 校验。返回骨名列表和权重数组。实际网格与骨架关联由 CLI 和求值分支另查。 [读取](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:30>) |
| `check_weights`、`stretch_metrics` | P1 同字节数值函数。前者校验非空浮点权重矩阵、有限非负、行和绝对容差 `2e-4`。后者检查同拓扑静止／姿态表面的拉伸和双面积增长。调用方提供骨语义、实际单位与高度。 [P1 函数契约](p1/skin-weights.md#参数返回与副作用) |
| `mesh_sha256`、`bone_names`、`rig_sha256` | 报告保存基础网格指纹、变形骨名顺序，以及以身体局部坐标表达的绑定矩阵、骨名、父骨名与 `use_deform` 摘要。`rig_adapter` 的同名骨架摘要只使用骨名、父索引和骨架局部休止矩阵，使用时记录实际生产者。 [绑定摘要](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:44>) · [骨架摘要](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:44>) |
| `bone_heads`、`coordinate_space`、`max_weight_sum_error` | 身体局部休止坐标中的实际骨头位置、坐标空间说明及变形权重的最大行和误差。 |
| `frames` | 各帧拉伸／面积计数、倍率、绝对增长及 `worst`。每帧详细最坏清单至多 20 面，包含实际面号、顶点索引、静止坐标和权重；清单不能替代全部异常计数。 |
| `pass`、`motion_observed` | `pass` 要求所有被检查帧没有显著拉伸和大面积增长。`motion_observed` 检查至少一帧相对基础休止网格的最大坐标偏差大于 `H×1e-6`。动作存在、跨帧变化、解剖匹配及动态接触由实际工程另行核对。 |

正常检查通过后，CLI 增加 `input_sha256` 并用 `atomic_json` 写报告，成功时主要输出位于该报告。`pass:false` 时先写完整报告再抛 `RuntimeError`，使用 `--python-exit-code 1` 可取得失败退出码。对象或输入缺失、无实际 Armature 关系、关闭求值、非法帧或权重、拓扑对应失效等前提错误可能在写报告前终止。该 CLI 在报告写入前计算输入文件摘要，调用方需要验证读前与读后的文件身份时另取两次摘要。入口拒绝已有报告，随后原子写入采用临时文件替换目标。并发执行需要调用方分配独立路径。 [报告写入与失败顺序](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:411>) · [原子 JSON](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/io_utils.py:19>)

**根据随包 CLI 重建的 PowerShell 示例。** 指定已有真实绑定的工程、身体和骨架，用新报告路径。`1.8` 和帧段为通用示例值，实际调用传本角色的网格单位及已有测试范围。

```powershell
$rigSkill = 'D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget'
& 'D:/install/blender/blender.exe' --background --factory-startup --disable-autoexec `
  --python-exit-code 1 --python "$rigSkill/scripts/run.py" -- service_rig inspect `
  --input 'sample-bound.blend' --body 'SampleBody' --rig 'SampleRig' `
  --frames '1:12' --height 1.8 --report 'sample-skin-report.json'
```

**根据已核实实现重建的伪代码。** 前提异常直接终止，完成数值检查后的失败写出可诊断报告。

```python
require_new_report_path(report_path, input_path)
open_blend(input_path)
body = find_object(body_name)
rig = find_supplied_or_body_armature(body, rig_name)
require_body_armature_matches(body, rig)
frames = parse_sorted_unique_frames(frame_spec)
report = inspect_skin(body, rig, frames, height)
report["input_sha256"] = file_digest(input_path)
atomic_json(report_path, report)
if not report["pass"]:
    raise RuntimeError("Skin deformation failed; inspect report before repair")
```

Blender 4.5.16 LTS 的合成夹具复现了零影响顶点被拒绝、真实修改器关联缺失被拒绝、恒定静止结果 `pass:true / motion_observed:false`，以及恒定非休止姿势的两个字段均为 `true`。报告需与实际非空身体、帧范围及跨帧观察关联。完整真实四足动作、接缝、碰撞与目标加载器回读仍待实测。 [随包回归夹具](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_service_rig.py:14>) · [验收范围](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/validation.md#数值与视觉)

### service_rig bind 服务权重回迁

`service_rig bind` 从静止的服务 GLB 导入骨架和蒙皮身体，通过最近面插值向显式未绑定目标写入权重。CLI 与上节共享 `--input`、`--body`、`--report` 和新路径检查，另要求新的 `.blend` 输出。该操作会编辑当前场景并保存候选。 [操作实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:180>)

| 参数 | 条件及默认值 |
| --- | --- |
| `--input <BLEND>`、`--body <对象名>`、`--report <JSON>`、`--output <BLEND>` | 必填，均无默认值。报告和输出须尚未存在、彼此不同，并与输入路径区分。输出扩展名必须为 `.blend`，扩展名检查发生在回迁函数之后。 |
| `--rigged-glb <GLB>` | 必填。按调用方给出的路径交 Blender glTF 导入器，路径及源字节身份由调用方对账。 |
| `--targets <对象名...>` | 必填，实际对象列表须唯一、非空并包含 `--body`，每个目标是非空且尚未绑定的 Mesh。 |
| `--alignment-tolerance <数值>` | 必填，无默认值。必须有限且大于零，使用基础顶点乘世界变换后的坐标单位。 |

导入结果须有一个 Armature，关联该 Armature 的服务 Mesh 须恰有一个。可同时存在额外未蒙皮 Mesh。Armature 上有活动 Action 或 NLA Track 时拒绝，服务身体权重按 `skin_table` 校验。目标现有顶点组与服务变形骨名冲突时拒绝。对齐门槛比较服务身体和 `--body` 的世界基础顶点 AABB 最大极值差，其他目标的部位关系、衣层及语义需要独立确认。 [输入与对齐门槛](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:180>) · [服务交接参考](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/service-rig.md:37>)

通过输入检查后，脚本移除导入参考体上的非变形组，为每个目标添加服务骨名组，使用 Blender Data Transfer 的 `POLYINTERP_NEAREST`、按名称和世界变换传递权重。仅应用临时传递修改器，随后添加保体积 Armature 并归一化，重新校验权重及保护签名。多用户目标 Mesh 先复制数据。导入参考网格隐藏，新工程打包贴图后另存，再算输出摘要并写报告。保护签名覆盖基础顶点、面角 UV、面材质分配、材质槽名称、形态键坐标、世界变换和指定原顶点组。实际材质节点、其他修改器和动作效果按实际文件核对。 [回迁与保护](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:230>) · [保护签名](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:90>)

完整报告包含 `rig`、`reference_body`、`bones`、`bounds_max_delta`、`targets`（对象及 `preserved`）、`service_glb_sha256`、`pose_qa_pending:true`、`output_sha256` 和 `input_sha256`。工程先保存，报告随后原子写入。后段失败时可留工程而缺报告，调用方核对实际文件和摘要再恢复。新候选路径避免重复应用到已绑定目标。载入、导入或回迁中失败时当前进程场景可能已经改变，独立进程可从原工程重新开始。 [结果字段](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:277>) · [保存及报告](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:443>)

**根据随包 CLI 重建的 PowerShell 示例。** `sample-high.blend` 包含未绑定的 `SampleBody`，`sample-service.glb` 是已检查的静止服务蒙皮。`0.001` 使用两者世界坐标单位，调用方按当前资产确认该值。

```powershell
$rigSkill = 'D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget'
& 'D:/install/blender/blender.exe' --background --factory-startup --disable-autoexec `
  --python-exit-code 1 --python "$rigSkill/scripts/run.py" -- service_rig bind `
  --input 'sample-high.blend' --body 'SampleBody' --rigged-glb 'sample-service.glb' `
  --targets 'SampleBody' --alignment-tolerance 0.001 `
  --output 'sample-bound-candidate.blend' --report 'sample-bind-report.json'
```

**根据已核实实现重建的伪代码。** 候选保存和报告写入分步完成。

```python
require_distinct_new_output_and_report(input_path, output_path, report_path)
open_blend(input_path)
body, targets = find_named_targets(body_name, target_names)
result = bind_result(service_glb, body, targets, alignment_tolerance)
require_blend_extension(output_path)
pack_images_and_save(output_path)
result["output_sha256"] = file_digest(output_path)
result["input_sha256"] = file_digest(input_path)
atomic_json(report_path, result)
```

随包 `test_service_rig` 在本机 Blender 4.5.16 LTS 的合成工程中通过了导出、回迁、修复和重开检查。补充隔离例子将左右权重对调且保持每点归一化，回迁成功且保留错误对应，报告 `pose_qa_pending:true`。身体位移超过对齐容差、零影响顶点和带动作的服务骨架分别被相应门槛拒绝。生产自动绑定、真实高模的解剖对应、复杂软层及四足姿势质量仍待实测。直接依赖为 Blender、NumPy 和同包 `io_utils`、`weight_graph`、`skin_weights`、`validate_blend`。P0 包装／预算和可选 P1 场景回读由调用方选用。 [合成测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_service_rig.py:14>) · [P0 执行包装](README.md#专项-blender-命令的执行包装) · [P1 权重原件](p1/skin-weights.md) · [可选场景载入](p1/asset-scene.md)

### service_rig repair 局部权重修订

`rig-retarget/scripts/run.py -- service_rig repair` 是 Blender 本地 CLI，由 `run.py` 导入 `rigging.service_rig.main()`，不是动态 LLM Tool。核查版本为 Windows x64 1.2.11；模块说明及 argparse description 原文见本页[单身体检查](#service_rig-inspect-单身体蒙皮检查)，它不是模型工具 description。直接执行依赖 Blender、NumPy 和同包模块；导入 `weight_graph.mesh_digest` 不执行图求解，也不因此要求运行 SciPy。 [分派](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/run.py:26>) · [本地模块与导入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:1>) · [宿主执行工具](../tools/exec-command.md)

| 参数 | 实际范围及默认值 |
| --- | --- |
| `--input <BLEND>`、`--body <对象名>`、`--report <JSON>` | 必填，无默认值。按确切身体名读取。报告须尚不存在且与输入路径不同。 |
| `--output <BLEND>` | 此操作必需，无默认值，须尚不存在且与报告不同。后缀须为 `.blend`，但后缀检查发生在权重写回和保护比较之后。 |
| `--rules <JSON>` | 此操作必需，无默认值。读取规则 JSON；内容身份和区域契约见下文。 |
| `--rig <对象名>` | 可省略，取 `body.find_armature()`；指定时须是 Armature 且等于身体当前实际关联骨架。 |
| 共用 parser 的其他参数 | `--frames`、`--height`、`--faces`、`--targets`、`--rigged-glb`、`--alignment-tolerance` 在 repair 中不读取。接受参数不代表执行相应检查或处理。 |

入口先检查路径，再打开输入工程并切 Object 模式。载入没有显式传 `use_scripts=False`，示例以 Blender `--disable-autoexec` 限制自动执行。它要求非空 Mesh 表面和有限基础坐标，按实际 `use_deform` 骨名建立密集权重表。输入权重必须已非空、有限、非负且归一，行和绝对容差 `2e-4`；该入口不自动填补零权重或修好非法输入。repair 不执行 inspect 的可见性、逐帧求值或动作检查。 [入口和修订分支](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:372>)

规则顶层读取 `mesh_sha256`、`bone_names`、`rig_sha256` 和 `regions`。前三项分别与当前基础 float32 顶点／int32 三角索引摘要、有序变形骨名、身体局部绑定矩阵及层级摘要精确匹配。它们不绑定原权重、Action、工程文件字节或身体对象名；相同网格和骨架下换过权重的文件仍可能接受旧规则。规则来源和实际输入版本由调用方另行对账。

`regions` 非空，每条规则必须恰含 `bounds`、`forbidden_bones`。坐标盒为有限 `2×3`、min≤max，含边界，使用身体基础网格局部休止坐标；禁用名单非空、唯一且是当前有序变形骨名。规则数组计算在权重副本中进行：按顺序移除区域内禁用影响、归一剩余行，最后对全部选区并集内精确同坐标行平均。不识别骨语义、连通壳体或衣层，也不做邻域平滑、top-k 或几何修改。 [规则门槛](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:425>) · [P1 数组契约](p1/skin-weights.md#repair_regions-局部数组修复)

**根据随包契约重建的中性规则示例。** 摘要必须替换为实际检查结果，完整骨序、坐标和禁用骨由实际资产决定；占位值不能直接通过校验。

```json
{
  "mesh_sha256": "<实际基础网格摘要>",
  "rig_sha256": "<实际身体局部绑定矩阵摘要>",
  "bone_names": ["sample_base", "sample_other"],
  "regions": [
    {
      "bounds": [[-0.2, -0.1, -0.1], [0.2, 0.1, 0.1]],
      "forbidden_bones": ["sample_other"]
    }
  ]
}
```

全部数组计算成功后才写回变化行；共享 Mesh 有变化时先复制所选数据。保护签名只纳入指定非变形骨组等数据，不禁止本轮变形权重的预期变化。保护比较通过后，标记 `pose_qa_pending:true`，再检查后缀、打包并保存新工程，计算输出和输入摘要，最后原子写报告。函数没有事务回滚，也不自动重开验收。 [写回与保护函数](#service_rig-权重写回与保护函数) · [保存顺序](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:443>)

| 完整报告字段 | 含义及限制 |
| --- | --- |
| `changed_vertices` | 完整前后权重数组不同的行数，包含共享位置平均造成的变化。 |
| `rules[].vertices`、`affected`、`max_removed_weight` | 每条命中数、实际删除了正禁用影响的行数、最大移除量。重叠规则按当前结果依次计数，不是去重总改动数。 |
| `shared_position_duplicates` | 所有选区并集内精确重复位置的重复顶点计数，不等于连通或语义接缝数。 |
| `pose_qa_pending` | 固定 `true`，不是质量通过标记。 |
| `output_sha256`、`input_sha256` | 保存后与末尾读取的文件摘要；输入只有末尾一次读取，不是前后防篡改检查。 |

报告没有 `pass`、完整规则、目标／骨架名、网格／骨架指纹或修后逐帧结果。CLI 不额外打印同份结构化报告到 stdout。规则命中但没有变化也能保存新工程；禁用影响已为零时，共享位置平均仍可能改变行，所以 `affected:0` 不保证 `changed_vertices:0`。

| 失败位置 | 内存、文件及恢复边界 |
| --- | --- |
| 输入、身份、规则或数组校验 | JSON 缺字段或类型不适用也可能触发原生异常。数组副本尚未写 Blender；不会进入候选保存。空区域、未知骨或移除后总影响≤`1e-12` 会拒绝，不猜替代骨。 |
| 写回／保护比较 | 当前场景可能已经局部修改，没有自动回滚；从可信输入重新打开，用新路径重做。 |
| 后缀、打包、保存、摘要 | 后缀检查晚于写回。失败后先核对是否已有可重开的候选，不以非零退出推定没有文件。 |
| 工程已存、报告失败 | 保留已有工程和诊断，按实际摘要、规则及检查补证；需要重做时采用新输出与报告。 |
| 原子报告及并发 | 入口拒绝已有报告，但末尾 `atomic_json` 本身会替换目标；没有独占锁或工程／报告事务，入口预检后的并发文件可能被替换。 |
| 业务子命令已完成、可选计时追加失败 | 只有显式使用 `run.py --timing-log` 时发生此层写入；追加在 `finally`，失败可令外层非零，工程和报告可能已经完整。若业务本身先失败，日志写入异常还可能遮盖原异常。先按实际产物与原诊断核对，计时状态不替代修复或质量结果。 |

`--timing-log`、`--task-id`、`--attempt` 是 `run.py` 的全局参数，须置于 `service_rig` 前，默认任务标记为 `local`、尝试标记为 `1`。专项计时只追加 JSONL，没有资产路径隔离、字节指纹或恢复账本；它不是 P0 通用计时。调用方须选独立日志路径。 [分派与默认值](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/run.py:38>) · [追加及异常传播](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/timing.py:11>) · [共享分派契约](#动作缓存的分派与共享函数)

**根据已核实实现重建的伪代码。** 省略上下文切换，保留主要门槛和真实落盘顺序。

```python
require_new_output_and_report(input_path, output_path, report_path)
open_blend(input_path)
body, rig = resolve_body_and_matching_armature(body_name, rig_name)
rules = read_json(rules_path)
vertices, faces = surface(body)
names, before = skin_table(body, rig)
require_rule_fingerprints_match(rules, body, rig, vertices, faces, names)
protected = non_deform_group_names(body, names)
signature = preserved_signature(body, protected)
after, result = repair_regions(vertices, before, names, rules["regions"])
write_changed_weights(body, names, before, after)
require(preserved_signature(body, protected) == signature)
result["pose_qa_pending"] = True
require_blend_extension(output_path)
pack_and_save_blend(output_path)
result["output_sha256"] = file_digest(output_path)
result["input_sha256"] = file_digest(input_path)
atomic_json(report_path, result)
```

**根据随包 CLI 重建的中性 PowerShell 请求。** 输入包含实际 `SampleBody` 及其 `SampleRig`，规则已经按本文件身份核对；该示例只调用修订，不隐含动作验收。

```powershell
$rigSkill = 'D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget'
& 'D:/install/blender/blender.exe' --background --factory-startup --disable-autoexec `
  --python-exit-code 1 --python "$rigSkill/scripts/run.py" -- service_rig repair `
  --input 'sample-bound.blend' --body 'SampleBody' --rig 'SampleRig' `
  --rules 'sample-rules.json' `
  --output 'sample-repaired.blend' --report 'sample-repair-result.json'
```

本地命令没有持久业务任务 ID，仍运行时沿宿主执行句柄续取；句柄失效后核对进程、日志和产物。可以对最新可信的已绑定候选继续 repair，但需重新核实规则来源和检查范围，不能把新启动当原进程续跑。 [.blend 文件结果](../tools/exec-command.md#本地脚本的文件结果) · [进程续读](../tools/write-stdin.md)

Blender 4.5.16 LTS 的随包 `test_service_rig` 合成回归已覆盖错误跨侧影响、修复、保存重开、两帧复验、非骨组保护和共享 Mesh sibling 不变，stale 骨架指纹被拒绝。纯数值五项测试与额外共享位置探针见 P1 页。生产资产、真实四足、多层软部件、复杂驱动／修改器、高模内存和目标加载器表现仍待实测；repair 的写回中断、保护失败、保存／报告故障、可选计时追加故障及并发未逐项注入，相关边界来自源码，不能算成 bind 故障探针的覆盖。 [随包夹具](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_service_rig.py:115>) · [P1 测试和探针](p1/skin-weights.md#调用示例与核查依据)

### service_rig 权重写回与保护函数

以下是同包 Python 函数，不是独立 LLM Tool。通过函数直接复用时，只能依赖它自身的检查，不能把 CLI 的对象／指纹门槛算进函数契约。 [安装实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:61>)

| 函数 | 参数、返回与失败／副作用 |
| --- | --- |
| `write_changed_weights(obj, names, before, after)` | 校验前后权重及维度，要求匹配对象顶点数和列数，返回变化行数。自身不验证 `names` 唯一、实际骨序或 Armature 归属。实际变化非零且 Mesh 多用户时先复制数据，删除变为零的成员，`REPLACE` 更新变化正权重，保留其余成员顺序；中途异常无回滚，不保存文件。 |
| `preserved_signature(obj, groups=())` | 返回 `data_sha256`、材质槽名称和世界矩阵。哈希覆盖基础 float32 坐标、角点拓扑、面材质分配、UV 层名／坐标、形态键名／坐标、指定组成员及权重。指定组缺失可抛错，`surface` 校验基础坐标；UV／形态键主要是哈希，不是普遍有限性验收。 |
| `rig_digest(obj, rig)` | 摘要覆盖全部骨名、父名、`use_deform` 和身体局部空间绑定矩阵；不含权重或动作。对象空间不能求逆等异常直接传播。不能与 `rig_adapter` 的同名摘要算法互换。 |
| `mesh_digest(vertices, faces)` | 对转换为小端 float32 顶点和 int32 面的字节求 SHA-256；没有自行验证对应的真实 Blender 对象或权重版本。 |
| `file_digest(path)` | 以 1 MiB 块读文件并返回 SHA-256，I/O 异常传播；单次调用不比较执行前后版本。 |
| `atomic_json(path, data)` | 建父目录，在同目录唯一临时文件写 UTF-8 JSON，flush／fsync 后 `replace`；finally 清临时文件。没有“目标须新建”的内部门槛、独占锁或多文件事务，已有目标可被替换；不清除已保存工程。 |

[绑定摘要](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:44>) · [写回和签名](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:61>) · [网格摘要](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/weight_graph.py:12>) · [文件原语](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/io_utils.py:10>)

保护签名只记录指定组的实际顶点成员和权重，没有单独保护空顶点组目录。形态键只纳入名称与坐标，不包括 value、slider 或驱动。材质节点／纹理字节、法线、全部修改器、父级和 Action/NLA／驱动也未完整覆盖，不能把签名通过叫作任意属性都保留。写回尽量不重建原成员顺序，以避免改变双四元数累计的符号选择；不同平台、复杂姿势和导出后效果仍需对实际求值复验。`io_utils.py`、`weight_graph.py`、`run.py` 与专项计时原件均未进入 P0／P1 收据；P1 `skin_weights.py` 则有独立归档。 [签名实际成员](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:90>) · [发行映射](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/package.json:3>) · [P1 原件](p1/skin-weights.md) · [专项共享函数](#动作缓存的分派与共享函数)

### `prepare_mesh` 网格准备

`rig-retarget/scripts/run.py -- prepare_mesh` 是 Blender 本地命令入口。`run.py` 导入 `rigging.prepare_mesh` 并调用 `main()`。直接依赖为 Blender `bpy`、`mathutils.Matrix`、NumPy 和标准库。准备分支独立于 P0 启动包装和 P1 网格快照，也无需 SciPy。可选计时由 `run.py` 处理，独立于准备分支的参数。 [命令分派](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/run.py:31>) · [脚本导入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/prepare_mesh.py:3>) · [P0 包装与计时](README.md#专项-blender-命令的执行包装)

| 参数 | 类型及条件 |
| --- | --- |
| `--input`、`--output` | 必填。输入为可被 Blender glTF 导入器读取的文件，输出为新的工作 `.blend`。同名 `.mesh.json` 也须是新路径，两个输出均不得覆盖输入。 |
| `--height`、`--weld-relative` | 有限正数，默认分别为 `1.8` 和 `1e-6`。焊接距离为两者乘积。 |
| `--rotation-deg` | 有限数值，默认 `0`。对网格数据施加绕 Z 轴的旋转。 |
| `--faces` | 可选正整数。省略时执行焊接和三角化。给出时仅在三角面数超预算后应用近似 Decimate。 |

入口清理当前工作场景并导入网格，合并场景中的全部 Mesh。应用对象变换后对基础顶点按 XY 包围盒中心及最低 Z 归一化。距离焊接使用 Geometry Nodes，随后三角化和可选减面。脚本要求输入有有限且非空的顶点数据及足够的 Z 跨度。几何处理范围由输入文件决定。父级可能保留，准备后应以实际工程、基础坐标和世界变换为准。 [参数与结果](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/prepare_mesh.py:89>) · [合并与焊接](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/prepare_mesh.py:32>)

**实现伪代码。** 焊接距离在归一化之后应用。报告字段记录准备过程和工作面数。

```python
surface = import_and_join_meshes(input_path, z_rotation)
center, scale = normalize_base_coordinates(surface, height)
distance = height * weld_relative
before = count_vertices(surface)
welded = weld_by_distance(surface, distance)
actual_faces = triangulate_and_optionally_reduce(surface, faces)
write_preparation_properties(surface, height, weld_relative)
pack_assets_and_save_blend(output_path)
write_mesh_json(output_path, before, welded, actual_faces, distance, center, scale)
```

`.mesh.json` 由 `--output` 路径替换后缀得到。CLI 将同一报告对象序列化到标准输出。文件与工程分步落盘，工程先保存，随后直接用 `write_text` 写报告。`welded_before_weights` 表示经过准备分支。合成夹具验证了该标记和正常进程退出可与 `working_faces: 0` 同时出现。已有工程或报告路径会被拒绝，调用方可保留诊断并改用新候选路径。 [保存与报告源码](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/prepare_mesh.py:109>)

**根据随包 CLI 重建的调用示例。** 在任务目录准备 `sample.glb` 并使用新的输出路径。

```powershell
$rig = 'D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget'
& 'D:/install/blender/blender.exe' --background --factory-startup `
  --disable-autoexec --python-exit-code 1 --python "$rig/scripts/run.py" `
  -- prepare_mesh --input 'sample.glb' --output 'sample-prepared.blend'
```

**合成夹具的实际报告。** Blender 4.5.16 LTS 中，两个具有重合顶点位置及独立面角 UV 的三角面经过准备和重开后，得到以下报告字段和值。

```json
{
  "vertices_before_weld": 6,
  "vertices_after_weld": 4,
  "working_vertices": 4,
  "working_faces": 2,
  "height_m": 1.8,
  "weld_distance_m": 0.0000018,
  "normalization_center": [0.5, 0.0, 0.0],
  "normalization_scale": 1.8
}
```

**根据已核实接口编写的回读示例。** 在独立 Blender 进程中将 `asset_scene.py`、其同目录的 `scene_io.py` 和 `mesh_snapshot.py` 所在目录加入模块搜索路径。下面以实际保存的 `.blend` 和配套报告为输入，核对单网格、非空三角数组和计数。报告高度来自请求参数，需要世界空间取证时另用 `space="world"` 采样。

```python
import json
from pathlib import Path

from asset_scene import open_asset
from mesh_snapshot import mesh_snapshot

prepared = Path("sample-prepared.blend")
report = json.loads(prepared.with_suffix(".mesh.json").read_text(encoding="utf-8"))
mesh, = [obj for obj in open_asset(prepared) if obj.type == "MESH"]
snapshot = mesh_snapshot(
    mesh, evaluated=False, space="local", triangulation="require_triangles",
    fields=("uv", "materials"),
)
vertex_count = len(snapshot["vertices"])
triangle_count = len(snapshot["triangles"])
if triangle_count == 0:
    raise ValueError("The saved mesh has no triangle faces")
if (vertex_count, triangle_count) != (report["working_vertices"], report["working_faces"]):
    raise ValueError("Mesh counts differ from the preparation report")
```

同一夹具把 `--weld-relative` 改为 `2` 时，随包命令仍正常退出，重开工程得到 1 个顶点和 0 面，保留焊接标记。读取实际基础网格可识别这一结果。连通性、退化、自交、UV 内容和实际尺度可继续按用途选择独立测量。 [场景载入与副作用](p1/asset-scene.md#参数结果与副作用) · [快照返回结构](p1/mesh-snapshot.md#参数结果与副作用) · [测量接口](#mesh-audit-网格测量函数)

### `make_profile` 人形比例种子

`scripts/run.py make_profile` 使用标准库 Python。必填 `--output <JSON>`，无其他子命令参数。脚本拒绝已有路径，再创建父目录并直接写 JSON。参数解析失败会报错，已有目标路径抛出 `ValueError`；成功时标准输出为提示语，完整结果在写出的文件。这个入口仅在需要人形比例模板时使用。 [命令分派](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/run.py:31>) · [CLI 与写入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/make_profile.py:128>)

种子包含 `calibrated: false`、`fps: 30`、15 根骨、`weight_regions`、`part_rules`、`motion_map`、`solver` 等。根骨不参与变形，默认配权骨为 `BODY_RIGID`，默认部件为 `Body`。骨点、范围和过渡带使用归一化身高的比例，`rigid_parts`、`animations` 和 `provenance` 初始为空。种子生成时无网格输入。调用方完成实际几何核对后填写骨点、滚转、区域和部件，并记录布尔 `calibrated: true`。 [种子结构](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/make_profile.py:8>) · [配置字段与默认值](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/make_profile.py:111>) · [Skill 标定要求](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/geometry-and-binding.md:17>)

**根据随包 CLI 重建的 PowerShell 示例。** 从包外任务目录运行。其余示例沿用 `$blender` 和 `$launch`。

```powershell
$skill = 'D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget'
$blender = 'D:/install/blender/blender.exe'
$launch = @('--background', '--factory-startup', '--disable-autoexec',
            '--python-exit-code', '1', '--python', "$skill/scripts/run.py", '--')
python "$skill/scripts/run.py" make_profile --output 'sample-seed.json'
```

### `build_character` 权重输入接口

`scripts/run.py build_character` 由 Blender Python 执行。必填 `--input <BLEND>`、`--profile <JSON>`，并在 `--export-weight-input <NPZ>` 或 `--output <BLEND>` 中任选一个。`--python-packages <目录>` 可选，提供时追加到 `sys.path`。导出权重输入与读取现成缓存均可在没有 SciPy 的情况下执行。实时求解会在建图前导入 SciPy，全锚点输入也经过该导入。 [CLI 参数](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py:244>) · [依赖约定](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/runtime.md:7>)

入口要求新主输出路径，按真值检查 `profile.calibrated`，并要求场景恰有一个 Mesh、具备真值 `welded_before_weights`，`character_height_m` 可读为浮点数。`blender_core.mesh_arrays()` 实际调用物化 P1 `mesh_snapshot`，使用基础局部 `float32` 顶点与实际三角面。按父骨在前的顺序创建骨架，骨段小于身高的 `1e-5` 时拒绝。初始权重先分给默认骨，后命中区域覆盖前者，多骨区域仅在命中顶点时检查过渡数量、中心顺序和正半宽。隔离复核中，字符串 `"false"` 通过真值检查，零面网格也能导出 `faces.shape == (0, 3)`。实际关节位置、区域覆盖和非空表面需另外检查。 [入口校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py:174>) · [建骨与初始配权](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/blender_core.py:9>) · [P1 快照](p1/mesh-snapshot.md#随包调用证据)

| 模式 | 输出和落盘 |
| --- | --- |
| `--export-weight-input` | 直接写压缩 NPZ，包含 `vertices`、`faces`、`initial`、`bone_names`、`mesh_sha256`、`calibration_sha256`。标准输出先写 `WEIGHT_INPUT_EXPORTED` 和路径，再写含 `weight_input` 的 JSON。此分支在读取 `weights_npz` 或 `labels_npz`、求解、分件和保存工程之前返回。 |
| `--output` | 读取有效的 `weights_npz` 或执行求解，再解析逐面标签、分件及刚性覆盖，按 `animations` 配置烘焙动作。打包并保存工程后，以 `with_suffix(".manifest.json")` 派生报告路径。报告和终端 JSON 包含网格摘要、部件、骨架名、面数、加权骨及锚点计数、动作、检查帧、fps、来源与求解记录。该分支自身不重开工程。 |

[导出与完整构建](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py:199>) · [写出顺序](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py:224>) · [CLI 标准输出](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py:260>)

完整构建的路径检查只覆盖主输出。合成复核确认同名 manifest 可被覆盖，报告路径被目录占用时，命令在工程落盘后报错。调用方可为工程和报告同时预留新路径，分别核对退出状态、文件和报告；只落盘部分结果时保留诊断，复验后再决定是否用新路径重跑。实时求解失败会在保存前退出，构建器没有独立的 `.solver.json`；实时求解诊断随成功构建的 manifest 写出。 [主输出校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py:174>) · [本地文件结果](../tools/exec-command.md#本地脚本的文件结果)

未配置 `weights_npz` 时，内置求解默认 `direct`、`rtol=2e-6`、`maxiter=1500`。`radius`、`fidelity_length` 和 `edge_floor` 默认分别为 `0.0194`、`0.0139`、`0.0000167`，调用求解器前乘以角色身高。逐面标签默认用 `default_part`（缺省为 `Body`）与 `part_rules` 计算；若给出 `labels_npz`，脚本检查网格摘要及 `labels` 长度后采用该标签。`rigid_parts` 将指定标签的拆件覆盖为对应变形骨 100% 权重。 [内置求解和标签](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py:54>) · [默认标签与刚性覆盖](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/blender_core.py:99>)

真值 `weights_npz` 从 profile 目录解析。缓存需匹配网格摘要、变形骨名顺序 及标定摘要；权重形状须等于初始权重，`fixed` 须为逐顶点的布尔数组。校验有限、非负、行和绝对容差 `1e-7`，并精确比对掩码声明的固定行。此分支不重算掩码，也不读取 `.solver.json`。缺失或过期缓存报错，不会回退到实时求解。回建 manifest 的 `solver` 给出缓存路径、实际权重文件摘要和标定摘要，收敛证据由外部报告保留。

网格摘要覆盖有序基础局部坐标与三角索引；标定摘要覆盖骨规格、默认骨、初始配权区及身高。网格或标定变化后重导输入并重算。求解参数单独追溯，变更时需重算并更新缓存路径。 [缓存校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py:24>) · [摘要范围](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/weight_graph.py:12>) · [外部求解与回执](#weight_graph-外部权重求解)

**根据随包 CLI 重建的 PowerShell 示例。** 两条命令展示可独立选择的输出模式。`sample-profile.json` 已对 `sample-prepared.blend` 标定，完整构建使用兼容 SciPy 环境或有效缓存。

```powershell
& $blender @launch build_character --input 'sample-prepared.blend' `
  --profile 'sample-profile.json' --export-weight-input 'sample-weight-input.npz'

& $blender @launch build_character --input 'sample-prepared.blend' `
  --profile 'sample-profile.json' --output 'sample-build.blend'
```

**根据已核实源码重建的实现伪代码。** 两种模式共享建骨和初始配权，完整构建才处理求解、分件及配套报告。

```python
destination = require_exactly_one_new_path(output, export_weight_input)
profile = read_json(profile_path)
require_truthy(profile.get("calibrated"))
mesh = open_single_weld_marked_mesh(input_path)
height, vertices, faces = read_base_local_triangles(mesh)
rig = create_rig(profile["bones"], height)
names = deform_bone_names(rig)
initial = initial_weights(vertices, names, profile, height)
if export_weight_input:
    write_weight_input(destination, vertices, faces, initial, names, profile, height)
else:
    weights = resolve_weights(vertices, faces, names, initial, profile, height)
    labels = resolve_labels(vertices, faces, profile, height)
    pack_and_save(split_bind_and_configure(mesh, rig, weights, labels, profile), destination)
    write_manifest(destination.with_suffix(".manifest.json"))
```

构建器的 `.manifest.json` 保存工作网格的 `mesh_sha256`、`parts`、`rig`、`faces`、`weighted_bones`、`rigid_anchor_vertices`、`actions`、`inspection_frame`、`fps`、`provenance` 和 `solver`。`mesh_sha256` 对应拆件前的工作数组，候选工程字节身份需另外计算文件摘要。该分支保存后直接写 manifest，实际重开及姿势检查由调用方执行。 [manifest 原文](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py:224>) · [数值检查](#validate_blend-已保存工程的数值检查)

### `weight_graph` 外部权重求解

`scripts/run.py weight_graph` 由具备 NumPy／SciPy 的独立 Python 执行。它与 Blender 内实时求解共用 `solve_weights()`；外部入口读取已导出的数组并写缓存及回执。包内独立 Python 位于 `resources/runtime/.runtime-python/python/python.exe`，可直接运行该入口。 [归档运行环境](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/runtime.md:7>) · [命令分派](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/run.py:31>) · [外部 CLI](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/weight_graph.py:243>)

`solve_weights` 和 CLI 均没有区域列表、`free_mask`、`fixed_mask` 或 `forbidden_bones` 输入。锚点由 `initial.max(1) >= 1-1e-10` 自动决定，再按占优骨交界和测地半径释放；输出 `fixed` 是计算结果，不是任意调用方掩码。它不读取 repair 规则，也不保证指定区域外不变或某区域禁骨硬零。由算法可推知，自由点的零影响可从相邻非零列重新引入，真正局部约束需要外层额外设计和复验。 [参数](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/weight_graph.py:26>) · [锚点生成](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/weight_graph.py:79>)

| 参数 | 契约 |
| --- | --- |
| `--input <NPZ>`、`--output <NPZ>` | 必填。读取 `vertices`、`faces`、`initial`、`bone_names`、`mesh_sha256`、`calibration_sha256`，禁用 pickle。输出权重 NPZ 及通过 `with_suffix(".solver.json")` 派生的报告。**两条输出路径均须是新路径**。 |
| `--radius`、`--fidelity-length`、`--edge-floor` | 必填，均用网格坐标单位。半径须有限且非负，保真长度与边长下限须有限且大于零。 |
| `--method`、`--rtol`、`--maxiter` | 可选。默认 `cg`、`2e-6`、`1500`。方法可选 `direct` 或 `cg`，相对容差须有限正数，迭代上限为正整数。 |

外部入口重算网格摘要，检查骨名数组为一维字符串且列数匹配，将输入的标定摘要带到输出。实际骨名顺序与标定是否对应 Blender 工程，在缓存回建时校验。求解器校验有限且非空的顶点、三角索引范围以及有限非负的初始权重，初始权重行和绝对容差为 `1e-8`。未被测地邻域解锁的单骨锚点保持固定，混合点及边界邻域内解除固定的点按骨列求解。`direct` 共用稀疏 LU，`cg` 使用 Jacobi 预条件。`info` 非零、解非有限或相对残差超过 `max(5 × rtol, 1e-9)` 即拒绝，随后才裁负、归一化和恢复固定行。无需解自由点时，报告 `columns` 可以为空。三角面数组允许为空，实际有效表面由调用方单独核对。 [输入与构图](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/weight_graph.py:43>) · [收敛与后处理](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/weight_graph.py:110>) · [外部回执校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/weight_graph.py:190>)

| 情况 | 文件和终端结果 |
| --- | --- |
| 成功 | 先写压缩 NPZ，键为 `weights`、`fixed`、`bone_names`、`mesh_sha256`、`calibration_sha256`。然后计算 `weights_sha256`，写报告 `passed:true`。报告还含输入摘要、求解参数、顶点／边／自由点／锚点数及逐列 `iterations`、`info`、`relative_residual`。标准输出为返回的诊断 JSON，`passed` 仅写入报告。 |
| 求解出现 `RuntimeError` | 尝试写 `passed:false` 及已收集的诊断后重抛，此时尚未写权重 NPZ。 |
| 前置检查、依赖或写入异常 | 有任一同名输出即拒绝并保留旧文件。参数、摘要、数组或依赖错误可能没有新报告。缓存已写出但报告写失败会留下待核对 NPZ。重跑使用新输出与新报告路径，可继续使用仍有效的输入。 |

[文件写入顺序与错误处理](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/weight_graph.py:206>) · [终端输出](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/weight_graph.py:254>) · [缓存回建](#build_character-权重输入接口)

**根据随包 CLI 重建的 PowerShell 示例。** 沿用前文 `$skill`。以下长度为示例网格单位，输入须已有正确的摘要和列顺序。

```powershell
$solver = "$skill/../../.runtime-python/python/python.exe"
& $solver -B "$skill/scripts/run.py" weight_graph `
  --input 'sample-weight-input.npz' --output 'sample-weights.npz' `
  --radius 0.10 --fidelity-length 0.05 --edge-floor 1e-6 --method cg
```

**根据源码重建的实现伪代码。** 宿主进程状态与落盘的诊断分开读取，重试从有效输入开始。

```python
report_path = output_path.with_suffix(".solver.json")
require_both_paths_new(output_path, report_path)
vertices, faces, initial, bone_names, identity = read_verified_input(input_path)
diagnostics = input_digests(input_path, identity)
try:
    weights, fixed = solve_weights(vertices, faces, initial, solver_config, diagnostics)
except RuntimeError:
    write_json(report_path, dict(diagnostics, passed=False))
    raise
write_weight_cache(output_path, weights, fixed, bone_names, identity)
diagnostics["weights_sha256"] = file_sha256(output_path)
write_json(report_path, dict(diagnostics, passed=True))
print_json(diagnostics)
```

### `validate_blend` 已保存工程的数值检查

`scripts/run.py validate_blend` 由 Blender Python 执行，另行打开实际候选。脚本通过 `bpy` 直接读取基础网格与各帧求值顶点，并调用同包物化的 P1 `skin_weights.stretch_metrics`。 [读取与逐帧调用](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/validate_blend.py:23>) · [发行映射](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/package.json:7>) · [P1 权重与拉伸](p1/skin-weights.md)

| 参数 | 契约 |
| --- | --- |
| `--input <BLEND>`、`--report <JSON>` | 必填。输入为已保存工程，报告是指定的普通文件路径。为防止覆盖源工程或误读旧回执，使用与输入不同的新报告路径。 |
| `--frames <帧列表>` | 必填，逗号分隔帧及闭区间，如 `1:12,20`，排序去重后须非空。报告覆盖实际选取的帧。 |
| `--collection`、`--rig`、`--height` | 默认 `CharacterParts`、`CharacterRig`、`1.8`。按实际集合、骨架及与网格坐标同单位的高度指定。 |
| `--seam-exclude` | 可选对象名列表，默认空。只影响接缝计数；有 `intentional_rigid_shell` 的对象也会排除在接缝检查外，仍参与实际权重与拉伸检查。 |

[帧解析和接缝范围](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/validate_blend.py:12>) · [参数与报告写入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/validate_blend.py:180>)

遍历指定集合的直接 Mesh。目标变形骨的同名组须有有限非负权重，组和绝对容差为 `2e-4`。接缝比较的是相同基础局部坐标的顶点在各帧的几何位置，峰值须不超过 `H × 1e-6`。边长异常要求倍率大于 3 且增长超过 `H/120`，双面积异常要求倍率大于 8 且增长超过 `H²/81000`。非三角输入或求值顶点数发生变化时会提前抛错。脚本使用基础索引计算，仍需按实际工程核对索引对应、Armature 连接和 UV。实测空集合、仅含同名有效权重组但无 Armature 修改器的工程均可得到 `pass:true`，子集合的网格也不会自动纳入。 [权重与接缝范围](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/validate_blend.py:23>) · [求值和接缝](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/validate_blend.py:95>) · [拉伸双阈值](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/skin_weights.py:93>)

此命令在进程中载入工程并逐帧求值，结束时当前帧停在最后采样，未保存该场景改动。报告未包含输入文件摘要或被检查对象的摘要，调用方按实际工程补充字节身份与检查清单。 完整报告含 `pass`、检查帧数、无效权重／非有限帧／拉伸计数、接缝峰值、阈值、`per_frame` 及 `worst`。特定人形掌腕骨齐全时还会记录腕角统计。终端 JSON 省略 `per_frame` 和 `worst`。检查完成才直接写文件，`pass:false` 时先写报告再抛错；输入或求值提前失败时，旧报告可能原样保留。**报告写入可覆盖已有文件，路径也未与输入工程隔离。** 将 `--report` 设为输入路径会用 JSON 覆盖工程，已在一次性合成夹具复现。报告只覆盖所选集合和帧，实际绑定、形态及属性的验收另行核对。 [通过条件与报告字段](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/validate_blend.py:139>) · [文件写入与报错顺序](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/validate_blend.py:197>) · [宿主读取文件结果](../tools/exec-command.md#本地脚本的文件结果)

**根据随包 CLI 重建的 PowerShell 示例。** 沿用前文 `$blender` 和 `$launch`。指定实际工程中的集合和骨架，并使用新报告路径。示例帧只覆盖指定区间。

```powershell
& $blender @launch validate_blend --input 'sample-build.blend' `
  --report 'sample-validation.json' --collection 'CharacterParts' `
  --rig 'CharacterRig' --frames '1:12' --height 1.8
```

**根据源码重建的实现伪代码。** 提前异常会在写报告前终止；数值检查完成后可留下可诊断的失败报告。

```python
frames = parse_sorted_unique_frames(frame_spec)
require_nonempty(frames)
open_saved_blend(input_path)
report = scan_direct_mesh_members(collection, rig, frames, height, seam_exclude)
write_json(report_path, report)
print_json_summary(report, omit=("per_frame", "worst"))
if not report["pass"]:
    raise RuntimeError("Deformation acceptance failed; inspect report")
```

### `rig_adapter` 已有骨架检查与调整

`rig_adapter` 是随包本地 CLI，入口文档字符串同时用于 `argparse --help`，不是注册给 LLM 的 Tool description。模型通过本地执行工具启动 Blender 后运行该命令。以下逐字保留脚本说明原文；本节仅说明 `inspect/calibrate`，其他操作各有独立小节，不能把下列伪代码当作完整分派器。 [脚本入口](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:1>) · [求值缓存](#rig_adapter-cache-求值动作缓存) · [映射与烘焙](#rig_adapter-retarget-动作映射与烘焙) · [本地执行工具](../tools/exec-command.md)

```text
Inspect/calibrate an existing rig, cache evaluated motion, and bake a mapped action.
```

`scripts/run.py rig_adapter` 由 Blender Python 执行。`inspect` 和 `calibrate` 都要求 `--input <BLEND>`、`--rig <Armature 对象名>`、`--report <JSON>`。`calibrate` 另需 `--spec <JSON>` 和 `--output <BLEND>`，`--replace-animation` 默认关闭。工程和报告输出路径解析为绝对路径，须是互不相同的新路径，并与输入区分。载入使用同包 `blend_common.open_input()`，显式禁用内嵌脚本。 [路径与分派](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:273>) · [CLI 参数](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:389>) · [载入实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/blend_common.py:108>)

| 操作 | 校验与完整报告 |
| --- | --- |
| `inspect` | 按对象名查指定 Armature。报告 `input_sha256`、`rig_sha256`、`rig`、`names`、`parents`、`rest`、`heads`、`tails`、`world_matrix` 和 `inventory`。可检查随后会被调整门禁拒绝的骨架。 |
| `calibrate` | 需要布尔 `calibrated: true`、匹配的 `rig_sha256` 及非空 `bones` 映射。每项按实际骨名给 `tail` 或 `tail_at`，并给 `roll_axis`。两者同时给出时优先采用 `tail_at`。尾点和轴须有限，尾段长度与叉积长度都不得小于 `1e-8`。在休止空间修改后，以绝对容差 `1e-7` 检查关节头。报告增加前后骨架摘要、编辑骨清单、关节头和资产保护标记、候选摘要、重开清单和 `pose_qa_pending: true`。 |

[检查字段](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:281>) · [调整校验和报告字段](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:142>)

`inspect` 的三个参数均无默认值，`--rig` 按精确对象名选择 `ARMATURE`。`inventory` 包含场景帧段、有效 fps、相机、各骨架的活动 Action 和 NLA strips、全部 Action 及文件图像打包状态。该分支生成结构盘点，身体与骨架关联、顶点权重和实际形变由调用方另行检查。后续编辑的兼容性检查由 `validate_target()` 执行。 [场景清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/blend_common.py:141>) · [检查分支](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:295>)

`calibrate` 的完整报告字段为 `input_sha256/rig_sha256/rig`、`before_rig_sha256/after_rig_sha256/joint_heads_preserved/edited_bones`、`saved_inventory/file_sha256/output/protected_assets_preserved/pose_qa_pending`。`input_sha256` 指目标输入工程字节，顶层 `rig_sha256` 仍是输入骨架；要引用校准后 rest，应采用 `after_rig_sha256` 或重开后的检查结果。报告不自动复制 axes 配置，也不保存其文件摘要。`operation` 只在 stdout 摘要中，不在完整报告内。 [结果构造](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:188>) · [通用报告与 stdout](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:281>)

校准 JSON 没有完整字段白名单。`calibrated` 严格要求 `is True`；尾点／骨名引用和类型错误还可能直接产生 `KeyError`、`ValueError` 或 Blender 异常，没有统一错误枚举。`new_path()` 只解析路径、拒绝已存在或指定冲突并创建父目录，不检查工作区根、`hi3d-` 前缀或 `.blend/.json` 后缀；工作区与写根约束由宿主或调用方另外落实。新路径预检没有并发独占锁，不能当作报告原子写入保证。 [字段读取](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:142>) · [路径函数](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:273>)

输入缺失、指定骨架不存在或对象类型错误、报告路径已存在或与输入相同、源文件最终摘要发生变化，以及载入或写盘异常均会失败。路径预检会先创建新报告的父目录，随后输入检查失败时目录仍可能保留。报告以普通 JSON 写入，失败后核对实际文件、退出码和 JSON 可读性。以独立进程和新报告路径重取证时沿用所选源文件与对象。显式提供 `run.py --timing-log` 时，同包 `rigging/timing.py` 可另记该命令耗时。 [路径顺序](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:273>) · [摘要与写入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:383>) · [JSON 写盘](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/blend_common.py:122>) · [可选计时](README.md#专项-blender-命令的执行包装)

调整要求普通 FK 继承和刚体对象变换，拒绝父对象、目标对象或 Pose 约束、驱动、共享 Armature 数据及动画化的 Armature 数据。目标已有活动 Action 或 NLA 时默认拒绝。显式传 `--replace-animation` 时清除所选对象的动画引用，链接动作中含对象通道时仍会拒绝。`build_character` 将新骨骼的 `inherit_scale` 设为 `NONE`，该适配器要求 `FULL`，直接串接会报错。 [目标约束](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:105>) · [新骨架设置](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/blender_core.py:41>)

`rig_sha256` 覆盖骨名、父级和休止矩阵，实测沿原方向延长骨尾时可能保持一致。调整分支在同一场景时间核对受保护几何、UV、形态键、材质槽及逐面分配、顶点组、图像内容和附件的局部关系。它打包保存工程、禁用内嵌脚本重开、再次核查资产并确认源文件摘要后才写 UTF-8 报告。后段失败时可能留下候选工程。标准输出摘要含 `operation`、`report`、`output`、`pose_qa_pending`；`inspect` 的后两项为 `null`。姿势和实际形变仍需验收。 [骨架和资产摘要](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:44>) · [落盘、报告和标准输出](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:373>)

**根据随包 CLI 重建的 PowerShell 示例。** `sample-fk.blend` 包含满足调整条件的 `SampleRig`。检查后按现场报告的 `rig_sha256`、实际骨名及已复核的骨尾和滚转轴写入 `sample-axes.json`，并填布尔标记。下列 JSON 中的骨名和方向仅示范形状，摘要替换为现场值。

```json
{
  "calibrated": true,
  "rig_sha256": "<sample-rig.json 中的实际摘要>",
  "bones": {
    "upper_arm.L": {"tail_at": "forearm.L", "roll_axis": [0, 0, 1]}
  }
}
```

```powershell
$blender = 'D:/install/blender/blender.exe'
$rigSkill = 'D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget'
$launch = @('--background', '--factory-startup', '--disable-autoexec',
            '--python-exit-code', '1', '--python', "$rigSkill/scripts/run.py", '--')

& $blender @launch rig_adapter inspect --input 'sample-fk.blend' `
  --rig 'SampleRig' --report 'sample-rig.json'

& $blender @launch rig_adapter calibrate --input 'sample-fk.blend' `
  --rig 'SampleRig' --spec 'sample-axes.json' `
  --output 'sample-axis-candidate.blend' --report 'sample-axis-report.json'
```

**根据已核实源码重建的实现伪代码，仅覆盖 `inspect/calibrate`。** 检查只写报告，调整在保存前后核对保护项。

```python
paths = require_distinct_new_outputs(input_path, output_path, report_path)
rig, source_sha, rest = open_source_and_inspect(paths.input, rig_name)
report = source_report(rig, source_sha, rest)
if operation == "inspect":
    report.update(read_inspection_inventory(rig, rest))
elif operation == "calibrate":
    protected, frame = snapshot_protected_assets_and_frame()
    validate_target(rig, replace_animation)
    edits = validate_calibration_spec(spec, rest)
    apply_tail_and_roll(rig, edits, replace_animation)
    require_heads_preserved(rig, rest)
    require_assets_preserved(protected, frame)
    save_pack_and_reopen(paths.output)
    require_assets_preserved(protected, frame)
    report.update(saved_candidate_report(paths.output, pose_qa_pending=True))
require_source_sha(paths.input, source_sha)
write_json(paths.report, report)
```

`build_character` 实际调用 P1 `mesh_snapshot`。`rig_adapter` 使用同包 `blend_common`、`retarget_math` 和 `service_rig`，间接导入 P1 `skin_weights`。隔离追踪中的 `inspect/calibrate` 未执行其检验、修订或拉伸函数。P0 启动、预算和计时及可选的 P1 回读各有独立入口。 [P0 启动包装](README.md#专项-blender-命令的执行包装) · [P1 导入与调用](p1/README.md#rig-retarget-的导入与调用) · [发行映射](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/package.json:3>)

Blender 4.5.16 LTS 使用随包 `run.py` 隔离执行 `inspect`，有对象约束、无网格和无动作的单骨工程也可生成盘点，原文件摘要一致。指定不存在的骨架时，配合 `--python-exit-code 1` 以退出码 1 失败且没有新报告。合成测试覆盖对象选择与报告边界。真实绑定工程的可用性、四足姿态和完整动作质量按实际资产另验。 [命令执行及报告](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:389>)

### rig_adapter retarget 动作映射与烘焙

**身份和说明原文。** `run.py rig_adapter retarget` 由 Blender Python 调用同一 `rig_adapter.main/execute`，共享上节逐字保留的 argparse 模块说明，不注册新的 LLM Tool、MDF 能力或名为 `bake_action` 的独立命令。它接收现有目标工程和 v1 动作缓存，计算角色映射并在同一执行中烘焙、另存候选。核查版本为 Windows x64 Hi3D Agent 1.2.11。 [CLI 定义](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:389>) · [本地命令分派](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/run.py:31>)

`rig-retarget` Skill 指导实际骨语义、配置准备和保留项，脚本按显式输入执行。详细执行与数学接口参考尚未纳入当前仓库原文快照，以下引用实际安装包；它们是领域指导或本地接口，不是额外动态工具。 [归档 Skill](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) · [安装包适配参考](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/existing-rig.md>) · [安装包接口参考](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/retarget-api.md>)

| CLI 参数 | 必填、默认值与实际范围 |
| --- | --- |
| `--input`、`--rig` | 必填，无默认值。现有 BLEND 与精确 Armature 对象名；使用 `open_mainfile(use_scripts=False)` 载入。 |
| `--output`、`--report` | 必填，无默认值。须为互不冲突的新路径，与输入分离，预检创建父目录。没有工作区根或后缀门禁，建议明确使用 `.blend` 和 `.json`。 |
| `--spec`、`--cache` | 必填，无默认值。分别读取映射 JSON 和 NPZ；CLI 不自动归档配置。 |
| `--action` | 必填，无默认值。新 Action 名不能已存在于全部 `bpy.data.actions` 中。 |
| `--frame-start` | 可选整数，默认 `0`。输出为连续整数帧 `start … start+F-1`。 |
| `--replace-animation` | 默认 false。显式允许替换所选 rig 的动画引用；不放宽其他目标兼容性门槛。 |
| fps、源帧范围等 | 本操作没有 `--fps/--source-fps/--start/--end`；取缓存中的 fps，处理缓存内全部姿态。重采样属于缓存生产者。 |

`validate_target()` 要求目标世界变换符合刚体容差、无父对象／对象约束／驱动、无 Pose 约束、正常 FK 继承、单用户 Armature 数据且数据本体无动画。活动 Action／NLA 默认拒绝；允许替换时仍拒绝所关联 Action 的对象通道。它不负责证明实际身体蒙皮有效。 [兼容性门槛](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:105>)

| 映射 JSON | 已核实条件与语义 |
| --- | --- |
| `calibrated` | 严格布尔 `true`，表示调用方完成实际核验，不是宿主审批标志。 |
| `rig_sha256`、`cache_sha256` | 分别匹配当前目标 rest 指纹和缓存实际字节。缓存以 `allow_pickle=False` 读取，schema 必须为 `rig-retarget-cache-v1`。 |
| `mapping` | 非空，键为目标骨名，每项 `source` 引用真实源骨；`mode` 默认 `global`，支持 `local`，local 源骨必须有父骨。 |
| `source_to_target` | 可选，默认单位阵；单个刚体 4×4，先左乘源 rest 和所有源 pose，不携带比例缩放。 |
| `alignment_wxyz` | 每项可选，有限非零 wxyz，读取后归一化，优先于端点计算。 |
| `source_end/target_end` | 两者同时存在才按关节头方向计算对齐；只有一个且未给显式四元数时采用单位旋转，不保证报错。 |
| `root` | 必需。含真实无父骨目标 `target`、源 `source`、两条关节数相同且至少两关节的比例链；比例链不要求直接父子。`offset` 默认零，`in_place` 默认 false。 |
| `limbs` | 可选，默认空。每项源／目标须各为直接相连的三关节链，提供有限非零 fallback `pole`。 |
| `sole_points/floor_z/preserve_flight` | 只有实际配置鞋底点时使用。点和地面需有限；`preserve_flight` 默认 true，按目标空间 Z 做补偿。 |

配置没有完整 JSON Schema 或未知键白名单。`in_place` 和 `preserve_flight` 由 Python 真值读取，应传实际布尔值；字符串 `"false"` 会作为真值。未知键可能被忽略，缺字段／错误引用可能抛原生异常。消费者检查矩阵、数组维度和层级，但不统一重验 `sample_frames/source_fps/source_world_at_first_sample` 及缓存内部所有来源摘要，也不按源帧号重新取样。 [消费校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:340>) · [计算输入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/retarget_math.py:99>)

**根据随包接口重建的中性映射示例。** 假定源和目标已核验为相同轴向，列出的骨名与直接链真实存在，`root` 确为目标无父骨。示例摘要为占位，不能直接执行；字段值与覆盖范围由实际资产确定。

```json
{
  "calibrated": true,
  "rig_sha256": "<实际目标 rest 摘要>",
  "cache_sha256": "<实际缓存文件摘要>",
  "source_to_target": [[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]],
  "mapping": {
    "root": {"source": "SourceRoot"},
    "upper": {"source": "SourceUpper", "source_end": "SourceLower", "target_end": "lower"},
    "lower": {"source": "SourceLower"},
    "tip": {"source": "SourceTip", "mode": "local", "alignment_wxyz": [1,0,0,0]}
  },
  "root": {
    "target": "root", "source": "SourceRoot",
    "source_chain": ["SourceUpper", "SourceLower", "SourceTip"],
    "target_chain": ["upper", "lower", "tip"],
    "offset": [0,0,0], "in_place": false
  },
  "limbs": [{
    "source_chain": ["SourceUpper", "SourceLower", "SourceTip"],
    "target_chain": ["upper", "lower", "tip"],
    "pole": [0,-1,0]
  }]
}
```

**根据随包 CLI 重建的 PowerShell 示例。** 输入、缓存和配置已准备，候选与报告均为新路径。是否允许替换已有动画由调用方明确，示例不默认开启。

```powershell
$blender = 'D:/install/blender/blender.exe'
$rigSkill = 'D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget'
& $blender --background --factory-startup --disable-autoexec --python-exit-code 1 `
  --python "$rigSkill/scripts/run.py" -- rig_adapter retarget `
  --input 'sample-target.blend' --rig 'SampleRig' `
  --cache 'sample-motion.npz' --spec 'sample-mapping.json' `
  --action 'SampleMotion' --frame-start 1 `
  --output 'sample-animated.blend' --report 'sample-retarget.json'
```

**根据已核实源码重建的执行伪代码。** fps 设置发生在 Action 创建之后，保存与报告分步完成。

```python
output = new_path(output_path, forbidden=(input_path, report_path))
report_path = new_path(report_path, forbidden=(input_path,))
source = open_input(input_path)
rig, info = select_and_read_target(rig_name)
report = initial_target_report(source, rig, info)
spec = read_json(spec_path)
protected, original_time = snapshot_assets_and_time()
validate_target(rig, replace_animation)
require(spec["rig_sha256"] == skeleton_digest(info))
cache = load_npz(cache_path, allow_pickle=False)
require(cache["schema"] == "rig-retarget-cache-v1")
require(spec["cache_sha256"] == file_digest(cache_path))
quats, locations, details = retarget_samples(cache, info, spec)
bake_action(rig, info["names"], quats, locations,
            details["root"], frame_start, action_name)
set_frame_range_and_fps(cache["fps"], frame_start, len(quats))
report.update(details)
report.update(output_time_and_cache_identity())
require_preserved(protected, original_time)
pack_and_save(output)
reopen_without_embedded_scripts(output)
require_preserved(protected, original_time)
report.update(saved_candidate_fields(output), pose_qa_pending=True)
require(file_digest(source) == report["input_sha256"])
write_json(report_path, report)
```

| 返回位置 | 结构及验证范围 |
| --- | --- |
| 完整 JSON 报告 | `input_sha256/rig_sha256/rig`；`scale/max_limb_reach_error/frames/root`；`fps/frame_range/cache_sha256`；`saved_inventory/file_sha256/output/protected_assets_preserved/pose_qa_pending`。 |
| 身份含义 | `input_sha256` 是本次目标工程，`rig_sha256` 是目标输入 rest，源动作身份来自实际缓存及其上游记录。`file_sha256` 是候选文件字节。 |
| stdout 摘要 | `operation:"retarget"`、CLI 传入的 `report`、解析后的 `output`、`pose_qa_pending:true`。完整报告没有 `operation`。成功 `main()` 返回 0。 |
| 未保存的内容 | 不自动复制配置，不保存完整 mapping／坐标变换／limbs、spec 路径或 spec 字节摘要；调用方另行归档。Action 名没有独立顶层报告字段，实际动作清单见 `saved_inventory`。 |
| 质量边界 | 无统一动作质量 `pass`；`pose_qa_pending:true` 表示待验。部分映射可输出，IK 误差非零也没有业务失败阈值，结构保护不等于动画质量。 |

[结果与 stdout](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:362>) · [数学返回](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/retarget_math.py:308>)

| 失败阶段 | 可能留下的状态及恢复边界 |
| --- | --- |
| 预检／载入／配置 | 可有已创建父目录；通常尚无候选或报告。错误可能来自 JSON、NumPy、mathutils 或 Blender，没有统一结构化错误回包。 |
| 计算／烘焙／时间设置 | 当前进程可能已清目标动画引用、重置姿态或创建部分 Action。坏 fps 可在烘焙后才失败；没有场景事务回滚。 |
| 保存／重开／保护／摘要 | 工程可能已落盘，后段复验仍可失败；不能仅凭文件存在判断本次成功。 |
| 报告写入 | 入口拒绝旧报告，但底层 `write_json` 为普通覆盖写入，没有原子替换或并发锁，可能留下不完整 JSON。预检后并发创建的同路径文件也可能被覆盖。 |
| 原进程仍运行或回执不明 | 用执行层原句柄续读；失效后核对进程、日志和文件。CLI 没有持久作业账本、提交查询、断点烘焙或自动补写报告接口。 |
| 重新执行 | 从原有效输入使用新输出／报告路径和可用 Action 名；先保留并核对已落盘工程，不能把重启当同一执行的续接。 |

调用方可用 Blender `--python-exit-code 1` 获得未处理脚本异常的失败信号，仍需核对报告及实际产物。专项计时在主操作之后还可能失败，日志路径须与输入、缓存、输出和报告分离。 [通用进程结果](../tools/exec-command.md#本地脚本的文件结果) · [计时副作用](#动作缓存的分派与共享函数)

该 CLI 没有 `dryRun/query/resume` 或自动候选复用参数，也没有“试烘／最终烘焙”两套命令；重复启动是新执行，不会按配置指纹找回旧 Action。缓存报告中的源摘要不在此回源核验，spec 也不回写或冻结。报告更新时会再次读取缓存摘要，但没有将该末尾值与最初校验值作最终一致性断言，不能把文件路径和报告摘要解释为执行期间的文件锁。实际配置和来源身份由调用方另行保留。 [完整执行与摘要位置](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:340>)

### retarget_math 与 Action 烘焙函数

`retarget_math.py` 是物化的 Motion Retarget 资源实现，不在已归档 P0／P1 文件清单中。其模块说明原文如下；这是本地 Python 模块说明，不是 LLM Tool description。

```text
Rest-aware rotations and fixed-length limb solving; no Blender scene mutation.
```

| 函数 | 参数、返回和实际调用条件 |
| --- | --- |
| `retarget_samples(source, target, spec)` | source 为骨名／父索引／rest／poses 数组，target 为目标骨架数组；spec 需严格 `calibrated:true`、非空 mapping、root 和可选 limbs。校验唯一骨名、父前子后、非空姿态与矩阵／维度。返回 `(F×B×4 float32 quaternions, F×3 float32 root_locations, diagnostics)`，诊断含 `scale/max_limb_reach_error/frames/root`。不修改输入数组或 Blender 场景。 |
| `hierarchy(names, parents)` | 要求骨名唯一、父索引数量匹配、整数且 `-1 <= parent < current_index`。只核结构，不判断解剖。 |
| `unit_quaternion(value)` | 有限、非零 wxyz 长度 4；归一化返回 mathutils Quaternion。 |
| `chain_scale(source_rest, target_rest, source_chain, target_chain)` | 两条同关节数、至少两关节的头点链，返回目标／源长度比；总长退化拒绝，缺失链骨可抛 `KeyError`，不校验直接父子关系。 |
| `two_bone_ik(hip, goal, length_a, length_b, pole)` | 同空间有限点及 pole、有限正链长；目标与 hip 距离小于 `1e-10` 或 pole 在目标轴法平面的投影长度小于 `1e-8` 时拒绝。返回膝、限制到可达区间的踝和目标误差；不伸长骨段，不含脚锁／碰撞。 |
| `forward_heads(names, parents, rest, desired, root, root_position)` | 根据有序骨名、父级、rest 矩阵、期望绝对旋转及指定根位置，返回骨名到头点的字典。其他无父骨保持各自 rest 位置；无场景写入。 |
| `bake_action(rig, names, quaternions, locations, root, frame_start, name)` | 内部 Blender helper，返回实际 Action 对象，不返回通用 JSON；没有独立 `run.py bake_action` 命令或动态工具。假定数组已由计算阶段准备，并非完整输入／权重／语义验收器。 |

[计算接口源码](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/retarget_math.py:24>) · [内部烘焙函数](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:229>) · [Motion Retarget 资源入口](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-motion-retarget/REFERENCE.md>)

`retarget_samples` 自身不检查 schema、文件路径或文件摘要，也不读取 fps；这些校验或设置属于外层 CLI，其数学 spec 无须携带用于外层对账的哈希字段。直接调用函数时仍须由调用方核对数据身份和来源，不能把 CLI 参数表当作函数完整签名。

**源码函数说明原文。** `bake_action` 的文档字符串如下；其中的版本措辞按原文保留，实际门槛见下文的 slots 能力检测。

```text
Bulk-create one Blender 5.x Action with continuous quaternion signs.
```

计算先以 `source_to_target` 统一源 rest 和 pose 的空间。global 取源全局相对 rest 的变化；local 提取源父子关节增量，转换到目标局部轴后叠加目标父姿态。最后转成目标 pose bone 的局部 basis。未映射骨随父保持中性；相邻输出四元数点积为负时取反以保持符号连续。

**根据实际计算重建的公式。** `Rs/Ps` 为已统一空间的源 rest／pose 旋转，`Rt` 为目标 rest，`Dt` 为目标期望旋转，`A` 将目标中性方向对齐到已变换的源中性方向。

```text
global: Dt = Ps × inverse(Rs) × A × Rt
local:
    Ls = inverse(Rs_parent) × Rs
    Pl = inverse(Ps_parent) × Ps
    delta = inverse(Ls) × Pl
    C = inverse(Rt) × inverse(A) × Rs
    neutral = Dt_parent × inverse(Rt_parent) × Rt
    Dt = neutral × C × delta × inverse(C)
local basis:
    q = inverse(Rt) × (Rt_parent × inverse(Dt_parent)) × Dt
    根骨省略父项。
```

根平移来自源根当前头点相对 rest 的位移，按链长比例缩放，不自动首帧归零；`in_place` 清目标空间 XY、保留 Z，offset 同步作用于根和 IK 目标。配置 limbs 才执行固定链长 IK；鞋点分支不是接触状态求解。IK 改变父骨后，local 和未映射子骨重新继承局部关系，global 保留请求的绝对朝向。 [旋转与根运动](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/retarget_math.py:190>)

`bake_action` 首先拒绝已存在 Action 名，检测 `Action.slots` 能力而非严格版本号；随后清所选 rig 的动画引用、切 POSE，设 quaternion／location／scale 初值，创建 layered Action、OBJECT slot 和通道。全部目标骨写 quaternion 四通道，根写 location 三通道，线性插值；不创建 NLA。旧 Action 数据块不主动删除，未选对象引用不因这段逻辑清除。失败可能留下已改内存或部分 Action，该 helper 不提供回滚或完整独立输入验收。

**根据源码重建的 helper 伪代码。** 名称、矩阵和数组的上游校验由调用方负责；helper 返回 Blender 对象，不写 JSON 或工程文件，也不重复计算四元数连续性。

```python
def bake_action(rig, names, quaternions, locations, root, frame_start, name):
    require(name not in all_action_names())
    require_action_slots_capability()
    frames = arange(frame_start, frame_start + len(quaternions))
    rig.animation_data_clear()
    reset_all_pose_bones(rig, mode="QUATERNION", location=0, scale=1)
    action, slot, channelbag = create_layered_action(name, rig)
    assign_action_and_slot(rig, action, slot)
    for bone_index, bone_name in enumerate(names):
        for component in range(4):
            write_linear_channel(channelbag, bone_name, "rotation_quaternion",
                                 component, frames,
                                 quaternions[:, bone_index, component])
    for component in range(3):
        write_linear_channel(channelbag, root, "location", component,
                             frames, locations[:, component])
    return action
```

副作用范围是所选 rig 的动画引用和全部 Pose 骨初值，不是仅改映射字典中列出的骨。当前实现通过 `retarget_samples` 为全部目标骨产生输出；单独调用 helper 时，不能以存在 Action 或某些曲线推断数组完整、绑定有效或动作通过。 [实际 helper](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:229>)

保护由 `protected_assets/require_preserved` 完成，覆盖场景非空 Mesh 的基础几何、面分配、UV、shape key、材质槽、全部顶点组及成员顺序／权重，以及全部图像的适用内容摘要。生成图读像素、打包图读字节、文件图读外部文件；不支持的非 VIEWER 图像类型拒绝。附件比较局部变换、父级逆矩阵及挂接关系，允许随新动作移动。比较在原帧／subframe 进行并恢复预览时间，不是完整材质节点、修改器、驱动或全部对象属性保护。该过程没有自动执行 `check_weights/repair_regions/stretch_metrics`。 [保护函数](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:54>)

**留存执行证据与待实测。** 未改写的随包 `test_retarget` 在 Blender 4.5.16 LTS 通过 16 项合成断言，覆盖 rest 对齐、局部手指、根比例、源对象运动／IK、固定链长、断链／缩放拒绝、权重顺序和保存重开；实际能力检测允许该测试环境，不等于所有版本兼容。 [回归源码](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_retarget.py:107>) · [留存 16 项结果](<C:/Users/11408/AppData/Local/Temp/hi3d-retarget-audit-722b3e5c5b2a434ebd672a9dcb8a3090/checks.json>)

额外隔离探针直接调用原 `retarget_samples`，确认字符串 `"false"` 与布尔 true 的 in-place 结果相同；单根映射仍输出七骨三帧；单端点和未知顶层键可被接受；数值 `calibrated:1` 被拒绝。这只证明数学函数的所构造分支，不是完整 CLI 或真实动作通过。本次文档修订读取既有结果，没有重跑这些试验。 [探针脚本](<C:/Users/11408/AppData/Local/Temp/hi3d-axis-tool-probe-4ffb42fe782e4624af28edfcca7cd850/probe.py>) · [探针结果](<C:/Users/11408/AppData/Local/Temp/hi3d-axis-tool-probe-4ffb42fe782e4624af28edfcca7cd850/results.json>)

新路径竞争、部分工程／报告写入、坏 fps 的晚期失败及计时同址破坏等为源码边界，尚未逐一故障注入。生产宿主、复杂控制 rig／材质／修改器、真实四足、完整关节覆盖、鞋底／衣层接触和目标引擎仍待实测。三个留存静态 GLB 和会话不覆盖这些专项命令，不代表工具或分支全集。

### motion.build_action 与 NLA 编排

**身份与说明原文。** Hi3D Agent 1.2.11 的 `rig-retarget/scripts/rigging/motion.py` 提供旧比例骨架的动作函数；`build_character.py` 在构建过程中调用它并组织 NLA。这些是本地 Python 接口，没有同名 LLM Tool、MDF 能力枚举或独立 `run.py motion.build_action/sequence_actions` 子命令。以下逐字保留 `motion.py` 模块说明；它不是 LLM Tool description。

```text
BVH cache retargeting and palm-axis correction for every action.
```

| 函数 | 输入、调用条件与返回 |
| --- | --- |
| `build_action(rig, spec, profile, config_dir)` | 输入实际比例骨架、动作 spec、profile 和缓存基目录；读取旧 NPZ，修改 rig、场景时间和 Action，返回 Blender `Action`。不独立保存工程或返回 JSON。 |
| `hand_offset(style, side, index, period)` | 返回整掌短句 Quaternion；支持 run／dance 的实际分支，其他 style 走基础短句，未作枚举拒绝；只有 `side=="L"` 走左侧符号，其他值走右侧。不是独立手指或音乐同步接口。 |
| `ground_height(rig, collection_name="CharacterParts")` | 对集合 `all_objects` 中 Mesh 求值，转换到 rig 空间，返回最低 Z；缺集合或无有限聚合最低点时失败。临时求值网格在 finally 释放。不是逐对象全部坐标有限性的完整验收器。 |
| `sequence_actions(rig, profile, profile_dir)` | 位于 `build_character.py`；先生成所有动作，再创建 NLA，返回 `(scene, track, actions, inspection)`，其中 actions 是 `(spec, Action)` 对列表。无独立报告或 CLI。 |

[动作函数源码](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/motion.py:11>) · [NLA 函数源码](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py:84>) · [旧缓存契约](#cache_bvh-bvh-兼容缓存)

| 配置 | 必填、默认值和实际条件 |
| --- | --- |
| `spec.cache/name/samples` | 必填；缓存路径相对 config_dir，绝对路径按 Path 语义处理；samples 为零基 `[start,end)`，要求 `0 <= start < end <= F`。旧缓存读取 `names/rest/poses/fps`，以 `allow_pickle=False` 加载。 |
| `profile.motion_map` | 必填，目标骨名到源骨名的映射。检查映射值存在于源骨名，但没有通用角色识别、完整目标映射或全数组 schema 门禁。 |
| `profile.fps` | 默认 30，缓存及 profile 均转 int 后比较。不同整数值拒绝，不是小数采样率的精确一致性验证。 |
| `profile.body_bone/root_bone` | 默认 `BODY_RIGID/root`。比例依赖固定 `thigh.L/shin.L/foot.L` 目标语义与对应源映射；源腿头点总长小于 `1e-6` 时拒绝。 |
| 源脚基线 | 优先使用同时存在的 `LeftToeBase/RightToeBase`；不足两侧时读取 `motion_map["foot.L"]/["foot.R"]`。该基线读取在落地开关判断之外，即使 ground=false 也需满足实际源骨引用。 |
| `spec.in_place/loop` | loop 缺省按 false；in_place 缺省沿用 loop 的真值。未做完整布尔 schema 校验。 |
| `spec.ground` | 非循环默认 true、循环默认 `"source_flight"`；false 关闭修高。真实最低点在 rig 空间计算，不搜索世界舞台。 |
| `spec.hand_style`、`profile.rotation_factors` | 风格默认 neutral；rotation_factors 默认空，按给定目标骨限制旋转。字段和骨名错误可能直接抛异常。 |
| `spec.loop_blend_frames` | 默认 4，转 int 后与样本数三分之一取较小值。用于尾窗混合和追加闭合键，没有统一完整参数白名单。 |
| `profile.parts_collection` | 默认 CharacterParts，仅落地修高时传给 ground_height。 |
| `profile.animations` | sequence_actions 缺省空列表。每项还须给 `timeline_start`；repeat 默认 1，转 float 后交 Blender strip 属性。 |
| `profile.inspection_frame` | 默认最大 strip 结束帧向上取整后加 10；落在任一 strip 含端点范围内时失败。 |

[缓存及配置校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/motion.py:89>) · [循环与曲线](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/motion.py:209>)

旧旋转按源 pose 相对 rest 的变化转换到目标局部 basis；未映射骨随父保持中性。函数不主动设置各 Pose 骨的 rotation_mode，Quaternion 模式等兼容前提由比例 builder 或调用方准备。根 XY 相对所选首样本，身体 Z 相对所选段的中位高度，再按实际网格进行可选落地修正；与通用 retarget 的 rest 位移语义不同。循环向首样本混合尾窗，追加首键，全部曲线为 LINEAR；尾窗分量混合后没有独立的四元数归一验收。它不保证脚锁、接点速度或动作自然度。

**根据已核实源码重建的实现伪代码。** helper 无独立文件事务；先完成全部 Action，再建 NLA 是函数内部实际顺序。

```python
def sequence_actions(rig, profile, profile_dir):
    actions = [(spec, build_action(rig, spec, profile, profile_dir))
               for spec in profile.get("animations", [])]
    rig.animation_data_create()
    rig.animation_data.action = None
    track = new_nla_track(rig, "CharacterPerformance")
    end_frame = 1
    for spec, action in actions:
        strip = add_strip(track, spec["name"], int(spec["timeline_start"]), action)
        strip.repeat = float(spec.get("repeat", 1))
        strip.extrapolation = "NOTHING"
        strip.blend_type = "REPLACE"
        end_frame = max(end_frame, ceil(strip.frame_end))
        add_marker(spec["name"], int(strip.frame_start))
    inspection = int(profile.get("inspection_frame", end_frame + 10))
    require(all(not (s.frame_start <= inspection <= s.frame_end)
                for s in track.strips))
    set_scene_range_and_frame(1, max(end_frame, inspection), inspection)
    return scene, track, actions, inspection
```

**根据函数契约重建的中性调用示例。** 在 Blender Python 中调用；rig、源缓存与映射需预先准备且实际兼容。`samples=[0,24]` 表示 24 个样本；示例不是通用服务骨架映射表。sequence_actions 自己创建动作，不能先单独 build_action 后再调用它并称作复用。

```python
from rigging.build_character import sequence_actions

profile = {
    "fps": 30,
    "motion_map": verified_motion_map,
    "body_bone": "BODY_RIGID",
    "root_bone": "root",
    "animations": [{
        "name": "SampleClip", "cache": "sample-legacy.npz",
        "samples": [0, 24], "timeline_start": 1,
        "loop": False, "ground": False
    }]
}
scene, track, actions, inspection = sequence_actions(rig, profile, task_dir)
```

build_action 没有通用适配器的全局同名 Action 拒绝，Blender 可自动改名；也不执行 validate_target、保护快照或完整蒙皮 QA。它不是安全替换任意已有 rig 动作的适配器，既有 NLA、特殊继承、约束和数据仍由调用方核对。函数中断可留部分 Action、姿态及场景变更，无回滚。

sequence_actions 即使 animations 为空也能创建 track 并设置检查帧；检查帧冲突发生在动作和 strips 已创建之后。两个 helper 自身无 JSON 报告，完整 builder 才先保存工程、再以候选旁 `.manifest.json` 直接写报告，已有同名 manifest 可被覆盖，后段失败可有工程无报告。此写入边界不能套用 rig_adapter 的新报告预检。 [构建及 manifest](#build_character-权重输入接口) · [报告写入](#绑定脚本的文件与报告写入)

**证据与待实测。** 原件固定摘要见本页独立复核。已有 test_blender 的整掌／落地合成检查与 test_retarget 的通用适配测试，不能视为本旧路线的全部循环、NLA 或故障分支覆盖。真实 BVH 导入器、来源动作、完整循环、复杂旧动作栈、多层衣物、四足及引擎结果待实测；本次文档修订未新增这些运行结论。 [随包小型测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_blender.py>) · [旧路线参考原件](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/motion-and-hands.md>)

### stage_ops clip 已烘焙动作裁剪

**工具身份与说明原文。** Hi3D Agent 1.2.11 的动画包本地 CLI，由 `hi3d-model-gpt-animation/scripts/run.py --rig-skill <独立绑定包> stage_ops clip` 分派至 `character/stage_ops.py`。没有同名动态 LLM Tool，也不是 MDF 能力。它与 inspect 共用以下模块说明原文，不是 LLM Tool description。

```text
Inspect, clip, orient, or edit text in a local Blender scene. Run via Blender --python.
```

| 参数 | 必填、默认和使用条件 |
| --- | --- |
| `--rig-skill` | 上层分派器要求显式提供，目录须有 `scripts/rigging/blend_common.py`。 |
| `--input/--output` | 必填。读取现有 BLEND；输出必须新路径且与输入不同，打开时禁用内嵌脚本。无统一工作区根或扩展名门槛。 |
| `--rigs` | 必填且至少一项，精确 Armature 对象名，拒绝重复选择。 |
| `--source-start/--source-end` | 必填整数、含首尾，要求 end 大于 start，至少两帧；样本数 `N=end-start+1`。 |
| `--start` | 可选整数，默认 0，输出末帧为 start+N-1，检查场景允许范围。保持现有 fps，不重采样到新 fps。 |
| `--report` | 可选，默认候选旁 `.report.json`。普通覆盖写入，没有与输入／输出或已有文件隔离的门槛。 |
| `--pack` | 默认关闭，提供才在保存前打包资源。 |
| `--stage-actions` | 可选 Action 名列表，默认空。仅重采样显式选择的 Action，不能与所选 rig 动作重叠；除 fake user 外有多个用户时拒绝。 |
| `--stage-source-start/--stage-source-end` | 可选浮点，省略分别采用源首末整数帧；stage-actions 非空时要求实际末端大于起点，按 N 个均匀样本取 F-Curve 值。没有统一有限值和完整语义预检。 |
| `--rebase-markers` | 默认关闭。开启才删除源区间外 marker，并平移区间内 marker。 |

[显式分派依赖](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d-model-gpt-animation/scripts/run.py:27>) · [参数与分派](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d-model-gpt-animation/scripts/character/stage_ops.py:285>) · [新候选载入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/blend_common.py:108>)

该操作只复制受支持的本地 pose transform。拒绝所选 rig 的对象／Pose 约束及对象驱动；关联 Action 的每条通道必须以 `pose.bones[` 开头，且以 `.location/.rotation_quaternion/.rotation_euler/.rotation_axis_angle/.scale` 之一结尾，任一不满足即拒绝。IK、对象运动和属性驱动先由专门适配器显式烘焙。它没有套用 rig_adapter 的完整目标门禁，也没有调用 orient／text 分支的 geometry_hash／animation_hash 保护。

执行时先在原 Action／NLA 状态下采样全部所选 rig 的 `matrix_basis`，再清动画引用，避免先改一人再污染另一人的取样。旧 Action 仅在剩余用户数等于 fake user 数时删除。每人新 Action 写 location／quaternion／scale 的整数帧 LINEAR 键，四元数符号连续；然后创建 Selected clip NLA track。新名由 Blender 处理，不具备通用 bake_action 的同名拒绝。 [裁剪及旧 Action 处理](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d-model-gpt-animation/scripts/character/stage_ops.py:145>)

可选 stage Action 先保存曲线取样值，后移除其 F-Curve modifiers、旧键及手柄信息，写入新整数帧线性键。它可以处理被明确选定的舞台属性，但不是完整依赖图的视觉烘焙。场景及预览时间轴全局改变；未选动作保留，不表示全场景只剩一段。已有 Bezier 子帧行为、物理、接触和连续时间动作质量仍需实际检查。

**根据源码重建的核心伪代码。** 所有快照先于任何所选 rig 的动画清理；修改与报告没有事务回滚。

```python
open_input(input_path, output_path)  # checks new output; use_scripts=False
rigs = require_unique_named_rigs(rig_names)
require_supported_pose_transform_channels(rigs)
stage_actions = require_explicit_unshared_stage_actions(stage_names, rigs)
frames = inclusive_integer_range(source_start, source_end)
require_at_least_two_frames_and_valid_destination(frames, output_start)
snapshots = sample_all_selected_rigs_before_mutation(rigs, frames)
stage_values = sample_stage_fcurves(stage_actions, stage_interval, len(frames))
clear_selected_animation_and_remove_only_orphaned_old_actions(rigs)
actions = write_linear_pose_actions(rigs, snapshots, output_start)
create_selected_clip_nla(rigs, actions, output_start)
rewrite_selected_stage_curves(stage_values, output_start)
set_scene_and_preview_range(output_start, len(frames))
if rebase_markers:
    rebase_selected_interval_markers()
report = clip_report()
save_candidate_and_reopen(output_path, pack=pack)
report.update(saved_inventory=inventory(), file_sha256=file_digest(output_path))
write_json(report_path or sidecar_path(output_path), report)
```

| 结果或失败阶段 | 输出与恢复边界 |
| --- | --- |
| 完整 JSON | `operation:"clip"`、`source_frames_inclusive/output_frames_inclusive/samples/rigs/stage_actions/unselected_animation`；保存 helper 再加 `saved_inventory/file_sha256`。不含源文件或映射摘要、几何保护或动作质量 pass。 |
| stdout | `{"operation":"clip","complete":true}`，在保存重开及报告写入后打印；不表示内容验收通过。 |
| 前提或采样失败 | 可更换当前场景和帧，尚未完成新动作；没有结构化失败 JSON，旧报告可能原样保留。 |
| 修改中途失败 | 可有已清引用、已删除的无用户 Action、新曲线或部分 strips，未保存的内存不构成候选；从原工程重新打开。 |
| 保存后失败 | 工程可能已存在，重开／inventory／摘要／报告阶段仍可失败；核实际文件，不直接重复同址写入。 |
| 报告覆盖 | write_json 普通写入可覆盖既有报告，默认 sidecar 也可能已存在。报告还可与输入或输出同址；计算候选摘要之后写 JSON 可覆盖工程。这是源码可见边界，本次未对 clip 做同址故障注入。 |
| 恢复 | 先核原进程及实际文件。需要重做时用原有效工程、新输出和独立新报告；没有持续任务 ID、断点裁剪或自动补报告。 |

[完整返回与 stdout](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d-model-gpt-animation/scripts/character/stage_ops.py:274>) · [保存与普通报告](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/blend_common.py:122>)

**根据已核实 CLI 重建的中性 PowerShell 示例。** 在包外任务目录使用已准备的烘焙工程；调用方先选择新的独立候选和报告路径。示例仅裁剪所选 rig，不添加 stage Action 或 marker 变更。

```powershell
$skills = 'D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills'
$sourceBlend = (Resolve-Path -LiteralPath 'inputs/sample-baked.blend').Path
$candidate = [System.IO.Path]::GetFullPath('exports/sample-clipped.blend')
$report = [System.IO.Path]::GetFullPath('exports/sample-clip.json')
if ((Test-Path -LiteralPath $candidate) -or (Test-Path -LiteralPath $report) -or
    ($candidate -eq $sourceBlend) -or ($report -eq $sourceBlend) -or ($report -eq $candidate)) {
    throw 'Choose separate new output and report paths'
}
& 'D:/install/blender/blender.exe' --background --factory-startup --disable-autoexec `
  --python-exit-code 1 --python "$skills/hi3d-model-gpt-animation/scripts/run.py" -- `
  --rig-skill "$skills/rig-retarget" stage_ops clip `
  --input $sourceBlend --rigs 'SampleRig' --source-start 1 --source-end 24 --start 0 `
  --output $candidate --report $report
```

**证据与待实测。** 原件和共享保存 helper 摘要见本页独立复核；参数、返回和写入边界来自安装源码。既有 stage_ops inspect 的报告覆盖试验不能代替 clip 实测，test_retarget 也没有覆盖 clip 的全部分支。本次未执行新裁剪，真实多角色 NLA、共享 Action、stage 曲线、报告同址／中断、子帧变化、四足和目标引擎表现待验证。三个留存 GLB 与两份会话不覆盖这些专项操作。

### rig_adapter cache 求值动作缓存

**身份与调用条件。** 此操作属于 Hi3D Agent 1.2.11 的 `rig-retarget/scripts/rigging/rig_adapter.py` 本地 CLI，由 `scripts/run.py rig_adapter cache` 分派，经 Blender Python 执行；不是动态 LLM Tool，也不是 MDF 能力枚举。它与上节共享同一段 CLI 说明原文。输入必须是已准备好的 BLEND 和确切 Armature 对象名，活动 Action、NLA、IK、约束及对象运动由该工程的当前配置决定。CLI 没有 `--action`、`--clip`、`--take` 或 `cache --replace-animation`，也不负责从 FBX／GLB／VMD 自动选择导入器或动作。 [说明原文](#rig_adapter-已有骨架检查与调整) · [CLI 参数](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:389>) · [领域 Skill](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) · [已有骨架参考，安装原件](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/existing-rig.md:35>)

| 参数 | 必填、默认及实际边界 |
| --- | --- |
| `--input` | 必填，现有 BLEND 文件。`open_input()` 检查文件存在并以 `use_scripts=False` 打开，替换当前进程场景；此操作不另存源工程。 |
| `--rig` | 必填，按精确对象名选 `ARMATURE`，不自动猜测骨架。采样开始前要求对象可见且 `pose_position == "POSE"`；不是逐帧重新检查可见性。 |
| `--output` | 必填，解析后的新输出路径，不能与输入或报告相同。建议显式使用 `.npz`；实现向已打开的二进制文件流写入，不自动追加扩展名。 |
| `--report` | 必填，新 JSON 路径，不能与输入相同；主输出与报告必须不同。预检会创建父目录。 |
| `--start`、`--end` | 必填浮点源帧号，可含子帧。拒绝 `end < start`；相等时可生成一个样本。未统一检查所有数值参数的有限性，NaN／Inf 可能在后续帧数或矩阵计算中报错。 |
| `--fps` | 必填浮点输出采样率。在有限数值域拒绝非正值；非有限值未统一预检，见上行。没有统一帧数或内存预算上限。 |
| `--source-fps` | 可选浮点，默认 `None`。省略时用场景 `fps / fps_base`。实现使用 truthy-or，`0` 被当作省略，负值被拒绝；覆盖值只决定时间换算，不改变源场景 fps。 |

[输入载入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/blend_common.py:108>) · [路径校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:273>) · [采样前提](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:198>) · [帧数与 fps](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:300>)

**采样与坐标语义。** 输出均匀采样源帧时间，步长为 `source_fps / fps`，帧数为 `floor((end-start) × fps/source_fps + 1e-8) + 1`。末端不在网格上时不会强行追加 `end`，因此报告 `source_frames` 是实际首末采样帧。调用方需另存原请求范围、动作身份以及实际场景 fps；指定覆盖值时，NPZ 中的 `source_fps` 已被覆盖值替换。 [实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:303>)

逐样本调用 `scene.frame_set(floor(frame), subframe=...)`，通过 depsgraph 的 `rig.evaluated_get()` 读骨姿态。取第一采样时刻的骨架对象世界矩阵 `A` 为固定锚点，保存 `A⁻¹ × W(frame) × P_bone(frame)`。这样移去初始对象世界放置，同时保留其后的相对对象运动；不是每帧消除对象运动，也不自动把根骨首姿态归零。`rest` 仍为骨架局部休止矩阵。所有 `rig.data.bones` 都进入缓存，包括控制骨和非变形骨。`finally` 恢复调用前的帧与子帧。源 IK／NLA 可以被求值，不沿用目标 FK 编辑的 `validate_target()` 门禁。 [骨数组](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:31>) · [固定空间求值](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:198>)

**根据已核实源码重建的实现伪代码。** 顺序保留了输出预检、求值、NPZ 写入、源文件复核与报告落盘之间的边界。

```python
output = new_path(args.output, forbidden=[args.input, args.report])
report_path = new_path(args.report, forbidden=[args.input])
source = open_input(args.input)  # use_scripts=False
rig = selected_rig(args.rig)
report = {"input_sha256": file_digest(source),
          "rig_sha256": skeleton_digest(skeleton(rig)), "rig": rig.name}
if args.end < args.start or min(args.fps, args.source_fps or 1) <= 0:
    raise ValueError("Valid fps and nonempty frame range required")
source_fps = args.source_fps or scene.render.fps / scene.render.fps_base
count = floor((args.end - args.start) * args.fps / source_fps + 1e-8) + 1
frames = args.start + arange(count) * source_fps / args.fps
data = cache_rig(rig, frames.tolist())  # restores original frame/subframe
data.update(schema="rig-retarget-cache-v1", source_fps=source_fps,
            fps=args.fps, input_sha256=report["input_sha256"],
            rig_sha256=report["rig_sha256"])
with output.open("xb") as stream:
    savez_compressed(stream, **data)
report.update(output=str(output), frames=count,
              source_frames=[frames[0], frames[-1]], source_fps=source_fps,
              fps=args.fps, cache_sha256=file_digest(output))
if file_digest(source) != report["input_sha256"]:
    raise ValueError("Source file changed")
write_json(report_path, report)  # plain UTF-8 write, not atomic_json()
```

[组包、写入与报告](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:281>) · [JSON 写入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/blend_common.py:122>)

| 返回载体 | 完整字段与含义 |
| --- | --- |
| 压缩 NPZ | `schema="rig-retarget-cache-v1"`、`names`（B 个骨名）、`parents`（B 个父索引，根为 `-1`）、`rest`（B×4×4）、`heads`／`tails`（B×3）、`poses`（F×B×4×4）、`sample_frames`（F 个源帧号）、`source_world_at_first_sample`（4×4 锚点）、`source_fps`、`fps`、`input_sha256`、`rig_sha256`。 |
| JSON 报告 | `input_sha256`、`rig_sha256`、`rig`、`output`（解析后的输出路径）、`frames`、`source_frames`（实际首末帧）、`source_fps`、`fps`、`cache_sha256`。不含动作语义、运动幅度、`pass` 或姿态验收结果。 |
| 标准输出摘要 | `operation:"cache"`、`report`（CLI 传入的报告路径）、`output`（解析后的路径）、`pose_qa_pending:null`。`null` 是该分支未设置此字段，不代表姿态已通过。成功 `main()` 返回 `0`；未处理异常配合 Blender `--python-exit-code 1` 可作为失败退出。 |

`rig_sha256` 只覆盖有序骨名、父索引和休止矩阵，不覆盖权重、`use_deform`、骨尾、Action／NLA 或外部依赖。`input_sha256` 绑定工程文件字节，不能替代未打包图像、链接库或插件版本身份。生产者没有强制“存在有效动作”或“姿态随时间变化”；静态骨架也能写出结构正确的缓存。采样会检查锚点和最终组合姿态为有限刚体矩阵，但没有独立验证每个控制器中间变换或完整层级契约。 [摘要定义](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:44>) · [标准输出](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:413>) · [矩阵函数](#动作缓存的分派与共享函数)

`rig_adapter retarget` 的消费者以 `allow_pickle=False` 读取 NPZ，要求 v1 schema，并核对映射中的 `cache_sha256` 与实际文件摘要。其数学函数另查唯一骨名、父子顺序、数组形状、非空姿态及刚体矩阵。消费者不会全面复核全部溯源元数据或按 `sample_frames` 再采样；不可把“能加载”当成动作身份与质量验收。 [缓存消费](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:344>) · [结构检查](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/retarget_math.py:105>)

| 情形 | 文件、报告及恢复边界 |
| --- | --- |
| 输入、对象、参数或采样失败 | 可能只留已建父目录，没有 NPZ 或报告；异常不另写结构化失败 JSON。采样在内存收集所有姿态，没有逐帧断点或追加续写。`finally` 恢复场景时间，但进程被强制终止时不保证执行。 |
| NPZ 写入失败 | `"xb"` 拒绝已有主输出，保护旧文件；压缩写入不是事务，可留下部分 NPZ，没有成功报告。 |
| NPZ 完成后失败 | 后续缓存摘要、源文件复核或报告写入失败，可留下完整 NPZ 和缺失／部分报告。生产者不重新打开验证 NPZ；文件存在或缺报告都不能单独说明成功／未执行。 |
| 报告覆盖 | 正常入口拒绝已存在报告；实际 `write_json()` 是普通写入，非独占、非原子。预检与写入之间有并发窗口，不能声称并发覆盖受保护。 |
| 原进程仍运行或状态不明 | 使用原 `cell_id`／`session_id` 续查各自宿主句柄；句柄不是缓存任务 ID。丢失句柄时先核对实际进程、日志、NPZ 可读性与摘要和报告身份，不盲目重发同址写入。 |
| 需重做 | 保留旧候选，以新的输出和报告路径重跑。源动作配置、约束、对象运动、休止骨架、帧率解释、范围或输出采样率变化后重新核对并生成。没有本脚本内置的提交账本、跨进程恢复或自动报告补写。 |

[原句柄续查](../tools/README.md#结果续接标识) · [文件操作顺序](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:273>)

**根据已核实 CLI 重建的中性 PowerShell 示例，非本次实际调用。** 输入工程已准备好名为 `SourceRig` 的骨架及所需动作配置。所有输出使用新路径。

```powershell
$blender = 'D:/install/blender/blender.exe'
$run = 'D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/run.py'
& $blender --background --factory-startup --disable-autoexec `
  --python-exit-code 1 --python $run -- `
  rig_adapter cache --input 'sample-source.blend' --rig 'SourceRig' `
  --start 0 --end 48 --fps 30 `
  --output 'sample-motion.npz' --report 'sample-motion-report.json'
```

### cache_bvh BVH 兼容缓存

**身份与实际说明原文。** `scripts/run.py cache_bvh` 分派本地 `rigging.cache_bvh.main()`，由 Blender Python 执行。以下是模块文档字符串，原样用作 argparse description；不是 LLM Tool description。实际调用要求该 Blender 环境已提供兼容的 `bpy.ops.import_anim.bvh`，不能从随包命令存在推定导入器已经可用。 [入口与说明](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/cache_bvh.py:1>)

```text
Import BVH through Blender and cache evaluated rest/pose matrices at target fps.
```

| 参数 | 必填、默认及边界 |
| --- | --- |
| `--input`、`--output` | 必填 Path。直接检查传入输出路径是否存在；输入读取和格式错误由 Blender 导入器报告。建议使用明确的新 `.npz` 路径。 |
| `--fps` | 可选整数，默认 `30`。直接赋给 `scene.render.fps`，没有同步重置 `fps_base`，最终时间解释还取决于场景和导入器。 |
| `--scale` | 可选浮点，默认 `0.0254`，传为 `global_scale`。 |
| `--forward`、`--up` | 可选字符串，默认 `"-Z"`、`"Y"`，传为 `axis_forward`、`axis_up`。脚本没有独立枚举、有限性或组合合法性校验。 |

`cache_motion(input_path, output_path, fps=30, scale=0.0254, forward="-Z", up="Y")` 设置 fps 后以 `use_fps_scale=True`、`update_scene_duration=True` 导入 BVH，采用导入后当前对象及其活动 Action，把 Action 帧范围两端转为整数，逐整数帧含末端采样 `rig.pose.bones[].matrix`。输出只有 `names`（B 个骨名）、`rest`（B×4×4）、`poses`（F×B×4×4）、`fps`（标量）；函数返回且 CLI 打印 `{"frames": F, "bones": B, "fps": fps}` 摘要，没有 JSON 报告路径。它没有 v1 schema、父索引、源帧列表、固定世界锚点、文件或骨架摘要；不能通过补一个 schema 字段冒充新缓存格式。 [核心函数](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/cache_bvh.py:10>) · [CLI](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/cache_bvh.py:42>)

**根据已核实源码重建的实现伪代码。**

```python
if Path(output).exists():
    raise ValueError("Choose a new cache output path")
scene.render.fps = fps
import_bvh(input, global_scale=scale, use_fps_scale=True,
           update_scene_duration=True, axis_forward=forward, axis_up=up)
rig = context.object
start, end = map(int, rig.animation_data.action.frame_range)
poses = []
for frame in range(start, end + 1):
    scene.frame_set(frame)
    poses.append(read_current_pose_matrices(rig))
Path(output).parent.mkdir(parents=True, exist_ok=True)
savez_compressed(output, names=bone_names(rig), rest=rest_matrices(rig),
                 poses=poses, fps=fps)
print({"frames": len(poses), "bones": len(rig.data.bones), "fps": fps})
```

此入口修改进程内场景，不清空原场景、不恢复调用前帧或 fps、不保存 BLEND。也不做通用刚体矩阵、动作有效性或运动幅度判定。`np.savez_compressed(Path)` 为普通写入：传入无 `.npz` 扩展名的路径时 NumPy 可自动追加后缀，前面的存在性检查因而可能没有检查实际写入目标；并发也没有独占锁。压缩中断可留部分文件，失败不生成专门错误报告，旧摘要或日志不能代表新尝试。重做应使用新的明确 `.npz` 路径及独立尝试日志。`main()` 成功返回 `None`，配合 `run.py` 属于正常成功，与 `rig_adapter.main()` 返回 `0` 的方式不同。 [写入与摘要](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/cache_bvh.py:31>) · [通用分派](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/run.py:38>)

旧消费者 `motion.build_action()` 按 `allow_pickle=False` 加载 `names/rest/poses/fps`，要求缓存 fps 与 profile fps 相等、所选零基右开 `samples=[start,end)` 有效，以及映射引用的源骨存在。它与 v1 的完整层级及固定空间契约不同。 [兼容消费者](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/motion.py:89>)

**根据已核实 CLI 重建的中性 PowerShell 示例，未实测 BVH 导入。** 下列依赖实际可用的 BVH 导入器。

```powershell
$blender = 'D:/install/blender/blender.exe'
$run = 'D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/run.py'
& $blender --background --factory-startup --disable-autoexec `
  --python-exit-code 1 --python $run -- cache_bvh `
  --input 'sample-motion.bvh' --output 'sample-bvh-cache.npz' `
  --fps 30 --scale 0.0254 --forward='-Z' --up Y
```

### 动作缓存的分派与共享函数

`run.py` 的 `COMMANDS` 登记的是本地命令名称，`dispatch()` 导入 `rigging.<command>.main(argv)`；不是 Runtime 动态工具注册。`arguments()` 从 Blender 的 `--` 后读取脚本参数。可选 `--timing-log`、`--task-id`（默认 `"local"`）、`--attempt`（默认 `"1"`）必须位于命令名称之前，字符串身份没有自动去重或任务锁。未传计时参数就直接分派。 [命令清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/run.py:8>) · [解析与分派](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/run.py:26>)

| 依赖及条件 | 参数、结果与失败边界 |
| --- | --- |
| `io_utils.file_digest(path)`，v1 文件追溯实际调用 | 分块读取文件，每块 1 MiB，返回 SHA-256 十六进制字符串。打开或读取错误直接抛出；不锁文件，也不追踪工程外部依赖。本分支未使用同模块的 `atomic_json()`。 [函数](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/io_utils.py:10>) |
| `retarget_math.rigid_matrices(values, label)`，v1 锚点及组合姿态实际调用 | 转为 `float64`，要求尾维 `4×4`、全有限、仿射末行、旋转正交及行列式近 `1`。末行绝对容差 `2e-5`，正交与行列式绝对容差 `2e-4`，`np.allclose` 另沿用默认相对容差。成功返回数组，错误 `ValueError` 包含 label；无场景写入。拒绝尺度、剪切和反射，不自动修正。 [函数](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/retarget_math.py:8>) |
| `blend_common.open_input() / write_json()`，v1 实际调用 | 前者读取 BLEND 并禁用内嵌脚本；后者 `mkdir` 后以 UTF-8 `write_text(json.dumps(...))` 写报告，允许底层覆盖且不具备原子替换。外层 `new_path()` 的旧报告拒绝与底层写入方式分别记录。 [函数](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/blend_common.py:108>) |
| `timing.record_stage(path, task, stage, attempt="1")`，仅显式计时时 | 退出上下文时追加一行 JSONL，字段 `task_id/stage/attempt/status/start/end/seconds`。正常为 `complete`，捕获 `BaseException` 为 `failed_or_interrupted` 并重抛；`stage` 是 `rig_adapter` 或 `cache_bvh`，不自动细分 cache。硬终止可能没有日志；finally 中日志写入再失败可掩盖原异常，也可在主产物及报告已完成后令命令失败。不校验产物摘要、不提供断点恢复。 [计时函数](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/timing.py:11>) |

`io_utils` 与 `retarget_math` 按专项发行映射物化，P0／P1 收据均未归档；分别来自 Skin Weights 与 Motion Retarget 资源。专项 `timing.py` 是 Run Tools 的 `profiles/rig_timing.py` 副本，摘要不同于 P0 通用计时原件。P0 启动包装、进程预算、断点检查可由外层另选，`run.py` 不会自动套用。 [发行映射](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/package.json:3>) · [P0 包装与计时](README.md#专项-blender-命令的执行包装) · [P1 导入边界](p1/README.md#rig-retarget-的导入与调用)

计时日志使用 `open("a")` 追加，未校验其路径与输入、NPZ 或报告隔离。调用方应为日志选用与这些文件不同的路径；这是调用建议，原脚本没有此门禁。同址时 `finally` 的晚期追加可能破坏源文件、NPZ 或报告，包括主操作已经完成后的追加；该边界由源码核实，尚未故障注入实测。 [计时写入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/timing.py:22>)

`rig_adapter` 顶层导入 `service_rig.preserved_signature`，进而加载权重相关模块；cache 实际不调用该保护函数、`retarget_samples`、权重校验／修复或拉伸函数。SciPy 在权重求解函数内部才加载，纯缓存不因此要求 SciPy。P1 `asset_scene/mesh_snapshot/scene_samples` 可被调用方另选用于检查实际资产，不是这两个缓存函数的必经依赖。`rig-retarget` Skill 和 Motion Retarget `REFERENCE.md` 提供准备、语义及接口约定；后者是资源指导，不是新的 LLM Tool。 [顶层导入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:11>) · [权重求解时导入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/weight_graph.py:39>) · [Motion Retarget 参考，安装原件](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-motion-retarget/REFERENCE.md>)

**已验证与待实测。** 留存 Blender 4.5.16 LTS 隔离证据中的随包 `test_retarget` 共 16 项通过，涵盖源对象运动、源 IK 求值、重定向及保护等不同范围，不能统称 16 项缓存测试。额外合成探针复现：帧／子帧恢复；分数源 fps 时按均匀网格省略不可达末端；`source_fps=60` 覆盖；NLA-only 与等效活动 Action 的姿态一致；无 Action／NLA 的静态缓存仍被接受。探针文件存在且字段已核对，本次文档修订未重跑这些实测。 [随包回归源码](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_retarget.py:57>) · [留存回归结果](<C:/Users/11408/AppData/Local/Temp/hi3d-source-cache-54af2857c76e480c9f387c7d719edbc5/checks.json>) · [留存探针结果](<C:/Users/11408/AppData/Local/Temp/hi3d-source-cache-54af2857c76e480c9f387c7d719edbc5/probe-results.json>) · [探针脚本](<C:/Users/11408/AppData/Local/Temp/hi3d-source-cache-54af2857c76e480c9f387c7d719edbc5/probe.py>)

`cache_bvh` 的实际导入、FBX／GLB／VMD 及 MMD 插件、复杂 NLA／动画约束切换、外部资源变化、长动作内存和中断、并发及部分文件故障、生产宿主跨进程恢复、其他 Blender 版本与真实四足步态／触地均待实测。上述失败落盘边界以源码顺序为证，不宣称已经逐一故障注入。所查三个静态 GLB 与两份留存会话未覆盖这些缓存命令，不能据此缩减工具或分支清单。

### `stage_ops inspect` 场景与朝向盘点

`hi3d-model-gpt-animation/scripts/run.py` 通过显式 `--rig-skill` 查找并导入独立绑定包的共享原语，再分派到 `character/stage_ops.py`。该入口属于 Blender 本地脚本，以下为传给本地参数解析器的说明原文。 [显式依赖分派](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d-model-gpt-animation/scripts/run.py:27>) · [脚本说明](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d-model-gpt-animation/scripts/character/stage_ops.py:1>)

```text
Inspect, clip, orient, or edit text in a local Blender scene. Run via Blender --python.
```

| 参数或输出 | 合同 |
| --- | --- |
| `--input`、`--report` | 必填，无默认值。读取现有 BLEND，将完整报告写到给定 JSON 路径。 |
| `--rig-skill` | 由上层分派器接收。执行时须指向含 `scripts/rigging/blend_common.py` 的实际独立包。 |
| `--rigs` | 可选。省略时只返回场景 inventory；提供时须有一个或多个精确 Armature 对象名，拒绝重复选择。 |
| `--frames` | 可选整数列表。计算朝向时省略则使用场景 `frame_start`，帧顺序和重复值原样保留，取样会改变进程内当前帧。 |
| `--head-bone`、`--forward` | 分别默认 `head` 和 `(0, -1, 0)`，仅计算朝向时使用。前向平方长度小于 `1e-12` 时拒绝。 |
| 完整报告 | inventory 字段及可选的 `headings[骨架名]`，每项含 `frame` 与归一化的 `world_forward`。朝向由指定骨骼相对休止姿态的旋转和骨架世界变换计算。 |
| 标准输出 | `{"operation":"inspect","complete":true}`。文件摘要、绑定权重与动作质量由调用方独立核对。 |

[检查实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d-model-gpt-animation/scripts/character/stage_ops.py:33>) · [CLI 参数和写入顺序](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d-model-gpt-animation/scripts/character/stage_ops.py:285>)

CLI 提供 `--rigs` 或 `--frames` 时要求至少一个值。未选骨架时，帧、头骨和前向参数不参与检查。前向仅按长度阈值预检，非有限数值需由调用方核对。

缺独立依赖包、输入打不开、所选 Armature 或头骨不存在、重复选择、零前向向量以及 I/O 错误会失败。`open_input()` 禁用工程内嵌脚本，盘点会替换进程场景并按需改变帧。JSON 写入可覆盖已有报告，且 `inspect` 没有检查报告与输入路径的重叠。示例由调用方先预留独立的新报告路径，输入内容摘要也由调用方记录。 [输入读取](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/blend_common.py:108>) · [报告写盘](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/blend_common.py:122>)

朝向计算在报告写入之前完成，计算中途失败可留下上次的报告。恢复时按本次退出状态、输入身份和实际文件核对报告来源，使用新报告路径重新执行所需盘点。源文件与骨架摘要由调用方另存。

**根据已核实 CLI 编写的中性 PowerShell 示例。** 先检查报告路径，再启动独立后台 Blender，省略骨架选择时仅盘点场景。输出路径预检由调用方实施。

```powershell
$blender = 'D:/install/blender/blender.exe'
$skills = 'D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills'
$inputBlend = (Resolve-Path -LiteralPath 'inputs/sample-scene.blend').Path
$reportPath = [System.IO.Path]::GetFullPath('exports/hi3d-sample-scene.json')
if ((Test-Path -LiteralPath $reportPath) -or ($reportPath -eq $inputBlend)) {
    throw 'Choose a separate new report path'
}
& $blender --background --factory-startup --python-exit-code 1 `
  --python "$skills/hi3d-model-gpt-animation/scripts/run.py" -- `
  --rig-skill "$skills/rig-retarget" stage_ops inspect `
  --input $inputBlend --report $reportPath
```

**根据随包实现重建的伪代码。** 打开和写入按照实际脚本顺序表示，路径保护在调用方完成。

```python
import json

require_explicit_rig_package(rig_skill)
open_input(input_path)
report = inventory()
if rig_names:
    require_nonzero_forward(forward)
    report["headings"] = inspect_selected_headings(
        rig_names, frames or [scene.frame_start], head_bone, forward
    )
write_json(report_path, report)
print(json.dumps({"operation": "inspect", "complete": True}))
```

Blender 4.5.16 LTS 以原版分派器和单骨夹具隔离复现了已有报告覆盖，以及报告路径等于输入时将一次性 BLEND 副本写成 JSON、终端仍返回 `complete:true`。指定独立报告时原工程 SHA-256 一致。测试文件均在临时目录。真实多角色依赖、朝向和运行中断需在实际工程复核。脚本直接复用 `blend_common`，需要独立载入或网格取样时由调用方另选 P1 模块。 [共享场景清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/blend_common.py:141>) · [P1 场景载入](p1/asset-scene.md) · [P1 网格快照](p1/mesh-snapshot.md)

### `mesh-audit` 网格测量函数

| 函数 | 参数与结果 |
| --- | --- |
| `measure_mesh(mesh, *, transform=None, unit_mm=1.0, weld=None, area_epsilon=0.0, area_inclusive=False)` | 分析临时 BMesh，`weld=None` 保留实际拓扑。返回顶点、面、三角、连通分量、边界、非流形、绕向、退化、坐标有限性、包围盒和有符号体积。非流形计数包含边界边，两者一起解释。退化面积阈值使用输入坐标单位的平方，焊接阈值使用输入坐标单位，`unit_mm` 缩放毫米尺寸和体积字段。 [网格测量源码](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/mesh_measure.py:6>) |
| `scene_measure.measure_objects(objects, *, unit_mm, precision='float64', empty='error', topology_objects=())` | 汇总对象基础网格的世界空间范围。仅对显式列入 `topology_objects` 的对象测量局部拓扑和体积，需至少一个非空 Mesh。 [场景测量源码](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/scene_measure.py:27>) |
| `triangle_arrays.measure_indexed(coords, triangles, *, area_threshold=1e-12, exact_weld=False)` | 独立 NumPy 诊断。统计基础局部数组、边使用和退化。`exact_weld=True` 单独报告按相同位置合并后的诊断数值，保留原数组。 [数组诊断源码](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/triangle_arrays.py:33>) |
| `collision.crossing_pairs(vertices, triangles)` | 使用 Blender `mathutils` 的 BVH 筛选并检测严格三角穿越，返回面索引对。共顶点、共面、切触及闭体包含须另行检查。 [严格穿越源码](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/collision.py:26>) |
| `compare_geometry(rest, current, faces)` | 接收同一拓扑、同一空间的对应 `N×3` 有限顶点数组及共同的三角面或四边面索引。比较严格表面交叉与退化，返回新增交叉、位置和 `geometry_passed`。跨拓扑保形需另行取样，切触、共面、共顶点和闭体包含另有检查。 [比较源码](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/geometry_compare.py:18>) |
| `surface_tree(points, triangles, *, epsilon=0)`、`pair_counts(trees, pairs)` | 从非空三角面建立 BVH，计数调用方给出的命名表面对的重叠。容差使用输入坐标单位。计数提供表面诊断，闭体包含及接触用途另行判断。 [表面对源码](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/surface_pairs.py:11>) |

这些测量函数由调用方独立执行，其路径在抽离候选中，P0／P1 文件收据未收录。可先使用 P1 `asset_scene` 重开实际 `.blend`，结合 `mesh_snapshot` 读取基础局部和世界空间。方向取证可另用 `source_views` 和 `preview_scene`，前后对照应保持同一尺度与相机。若只查 GLB，可用 P1 包围盒接口。原生多边形连接由实际可编辑工程或原生 OBJ 回读。 [场景载入](p1/asset-scene.md) · [网格快照](p1/mesh-snapshot.md) · [方向取证](p1/source-views.md) · [世界包围盒](p1/glb-bounds.md) · [抽离候选](../upstream/1.2.11/extraction/extraction.json)

### `audit_models.py` 独立 GLB 回读

核查版本为 Windows x64 1.2.11。该文件由 Blender Python 执行，是专项本地脚本；安装包核查范围内没有同名 LLM Tool 注册或模型可见 description。`audit_models.py` 和同包 `frame_runtime.py` 在抽离候选中，未纳入 P0／P1 原件收据。它实际使用同目录物化的 P1 `glb_clips.read_glb`，直接依赖 Blender `bpy`、NumPy、`mathutils` 和标准库。 [实际入口](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/audit_models.py:1>) · [抽离清单](../upstream/1.2.11/extraction/extraction.json) · [P1 容器函数](p1/glb-clips.md)

**源码模块说明原文。** 这是模块 docstring，不是 LLM Tool description；该 CLI 的 `ArgumentParser` 也没有把它设为 description。

```text
Explicit-input business stage and thin command-line adapter.
```

| 参数／入口 | 实际契约 |
| --- | --- |
| `--input <路径>` | CLI 必填，无默认值。单文件分支要求 `is_file()` 且后缀精确为小写 `.glb`；其他情况按目录枚举直接子级 `*.glb`，不递归。没有输入列表或 URL 参数。 |
| `--output <JSON路径>` | CLI 必填，无默认值。解析后不得位于本 Skill 包内；不是“须新建”检查，没有后缀或工作区根门槛。父目录在报告写入前创建。 |
| `audit(*, input, output)` | 两项均为必填关键字参数，使用相同路径处理。完整数据写报告，函数没有显式结构化返回值。 |
| `frame_runtime.validate_paths(options)` | 归一化 Namespace 中声明的路径，要求输入存在、输出在包外；只修改 Namespace，不创建文件或重置场景。不核输入／输出同址、新路径或内容摘要。 |

不要把同文件 `resolve_file_request()` 的输入文件／写根保护计入此入口：`audit` 调用的是 `validate_paths`。该脚本自身也没有 `hi3d-` 前缀门禁，宿主权限与调用方的路径规则分别生效。 [路径函数](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/frame_runtime.py:10>) · [独立写根函数](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/frame_runtime.py:44>)

每个文件先完整读取字节，用 `read_glb` 解析容器，再 `read_factory_settings(use_empty=True)` 重置场景并实际导入。脚本收集全部导入 Mesh，静态范围用基础网格世界顶点，按米乘1000输出毫米。JSON中有动画时，从1到所有 Action 最大结束帧四舍五入所得整数逐帧采样对象包围盒角点，不逐 clip 切换，也不是完整求值蒙皮验证。 [导入与采样](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/audit_models.py:23>)

| `models[]` 字段 | 内容与覆盖 |
| --- | --- |
| `file/sha256/bytes/MiB` | 文件名、实际输入字节 SHA-256和大小；并非输出报告本身摘要。 |
| `animated/animation_count` | 来自原 GLB JSON 的动画列表，不能证明非空 Action 或实际跨帧运动。 |
| `meshes/triangles` | 所有导入 Mesh及多边形按 `len(vertices)-2` 计数的三角数。没有自动排除骨骼 `custom_shape` 显示对象。 |
| `dimensions_mm/min_mm/max_mm` | 静态世界顶点及条件动画包围盒的汇总范围。没有逐一核对预期身体、skin或尺度元数据。 |
| `bounds_method/sampled_frames` | 脚本自述的取样方法及静态1帧／动画结束帧数；不是“已覆盖所有clip、全部变形或连续时间”的证明。 |

完整报告为 `{"models":[...]}`，没有 `pass`、skin／权重合格判定或目标引擎结论。stdout打印 `MODEL_AUDIT_COMPLETE` 和文件大小摘要，不是同份JSON报告。没有产物事务或持续任务ID。 [报告字段及写入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/audit_models.py:44>)

| 失败位置 | 内存与文件边界 |
| --- | --- |
| 路径、枚举、容器／导入 | 缺输入、无匹配GLB或解析异常向上传播，未提交新汇总。导入已重置／改变场景；没有场景回滚。 |
| 数组和取样 | 无Mesh、空顶点或不适用数据可能触发 NumPy／Blender 原生异常；没有统一的可交付身体门槛。批次中途失败不提交先前条目的新报告。 |
| 报告写入 | 所有文件处理完才普通 `write_text` 覆盖报告，没有原子替换或并发锁。前提失败可留旧报告；写入中断可能留部分JSON。 |
| 输入／输出同址 | 没有同址保护。若输入GLB在包外且可写，导入完成后报告可用JSON覆盖原GLB。此为源码边界，未做该破坏性故障注入。 |
| 回执不明 | 按实际输入摘要、报告完整性及本轮枚举对账。文件存在或stdout提示不构成质量通过，旧报告不能当本轮结果。 |

**根据已核实实现重建的伪代码。** 报告只在批次完成后写入，检查没有业务质量 `pass`。

```python
def audit_models(input_path, report_path):
    options = normalize_existing_input_and_package_external_output(
        input_path, report_path
    )
    paths = select_lowercase_glb_file_or_direct_children(options.input)
    require_nonempty(paths)
    rows = []
    for path in paths:
        data = path.read_bytes()
        document, chunks = read_glb(data)
        reset_blender_and_import(path)
        meshes = all_imported_mesh_objects()
        bounds = base_world_vertex_bounds(meshes)
        if document.get("animations"):
            bounds = include_integer_frame_object_boxes(meshes, bounds)
        rows.append(file_statistics_and_bounds(path, data, document, meshes, bounds))
    write_json_overwriting(options.output, {"models": rows})
    print_completion_summary(rows)
```

**根据实际 CLI 重建的中性 PowerShell 请求。** 调用方预先保证报告为独立的新路径。下面约束不属于脚本自带的新路径门禁。

```powershell
$audit = 'D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/audit_models.py'
$report = 'reports/hi3d-sample-audit.json'
if (Test-Path -LiteralPath $report) { throw 'Use a new report path' }
& 'D:/install/blender/blender.exe' --background --factory-startup --disable-autoexec `
  --python-exit-code 1 --python-expr 'import sys; sys.dont_write_bytecode=True' `
  --python $audit -- --input 'exports/hi3d-sample.glb' --output $report
```

前序合成立方体回读验证了导入、静态范围、计数和输入摘要。七骨三帧的独立导入探针另证明显示辅助Mesh可被生成，但该探针不是调用此脚本完成的完整动画验收。真实四足、全clip／长动作、复杂依赖、辅助体过滤、输出同址／部分报告等故障仍需专项实测；本页不把静态门槛当作新增故障实测。若只需受支持的静态尺寸，可选 P1 `glb_bounds.inspect`；逐对象数组可选 `asset_scene/mesh_snapshot`，它们都不是此脚本自动追加的质量检查。 [P1 尺寸](p1/glb-bounds.md) · [场景载入](p1/asset-scene.md) · [网格快照](p1/mesh-snapshot.md)

### 绑定脚本的文件与报告写入

| 入口 | 路径、字节身份与失败产物 |
| --- | --- |
| `rig_adapter inspect` | 新报告路径，普通 UTF-8 JSON 写入。读取前后核对源文件 SHA-256，前提失败可留下已建父目录，写入中断需核对报告可读性。 [路径及写盘](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:273>) |
| `rig_adapter calibrate / retarget` | 输入与主输出／报告分离，预检拒绝已存在的候选和报告；没有后缀／工作区门禁或并发锁。候选先保存、重开复验，再普通覆盖写报告；后段失败可留下工程、无报告或半份 JSON。报告中的 `input_sha256` 是目标工程，配置需另行归档。 [校准返回](#rig_adapter-已有骨架检查与调整) · [重定向返回与失败](#rig_adapter-retarget-动作映射与烘焙) |
| `rig_adapter cache` | 预检拒绝已有 NPZ 和报告；NPZ 用 `xb` 独占创建但非原子压缩写入。写出后才算缓存摘要、复核源文件并普通写报告；可留下部分 NPZ、完整 NPZ 无报告或部分报告。报告预检不是并发锁。[参数、文件与恢复](#rig_adapter-cache-求值动作缓存) |
| `cache_bvh` | 无独立报告，普通压缩写 NPZ，只打印帧数、骨数和 fps。检查传入输出是否存在，但缺少 `.npz` 后缀时可能自动追加后缀，实际目标的已有文件保护因此不完整。 [兼容格式与失败](#cache_bvh-bvh-兼容缓存) |
| `service_rig inspect` | 入口拒绝已有报告，再用同目录临时文件原子替换目标。结束前计算一次 `input_sha256`。检查得到 `pass:false` 时先写报告再失败，输入及求值前提抛错时可无报告。 [CLI 与报告](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:372>) |
| `service_rig bind / repair` | 入口要求新候选、新报告且与规定路径分离，但不是并发锁。工程先保存，再算输出／末尾输入摘要，最后原子替换报告；后段失败可留工程而无报告。写回／保护失败可留内存修改，无自动回滚；repair 的回执无 `pass`，零变化也可另存。 [回迁契约](#service_rig-bind-服务权重回迁) · [修订契约](#service_rig-repair-局部权重修订) |
| `io_utils.atomic_json` | helper 自身不拒绝已有目标，以同目录临时文件刷新／fsync 后替换，可能覆盖并发者文件；finally 只清临时文件，不撤销已保存工程。CLI 的新路径预检与函数替换语义分别核对。 [辅助函数](#service_rig-权重写回与保护函数) |
| 可选专项 `record_stage` | `run.py --timing-log` 启用时在 `finally` 追加记录，无输入／输出／报告同址门槛。工程和报告完成后追加失败仍可令命令非零，也可能遮盖业务原异常；不提供多文件事务或回滚。[分派与计时](#动作缓存的分派与共享函数) · [原件](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/timing.py:11>) |
| `weight_graph` | 两输出先做新路径预检，普通写压缩 NPZ 后才算摘要和普通写报告；预检不是独占锁。仅求解 `RuntimeError` 分支尝试写 `passed:false`，其他前提／I/O 失败可能无报告，后段也可能留下完整缓存。 [求解输出与失败](#weight_graph-外部权重求解) |
| `validate_blend` | 普通 JSON 覆盖式写入，报告路径可与输入相同。提前失败可能留下旧报告。检查完成再写完整报告并输出摘要，`pass:false` 随后失败。调用方记录实际输入摘要与非空检查对象。 [报告顺序](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/validate_blend.py:197>) |
| `build_character` | 要求新的主输出工程，配套 manifest 以替换扩展名的路径直接写入，已有同名 manifest 可被覆盖。工程先保存，报告失败时可留工程。文件、工作网格和候选摘要分别对账。 [构建与落盘](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py:174>) |
| `motion.build_action / sequence_actions` | 仅生成／组织当前场景中的 Action 和 NLA，自身没有工程或 JSON 落盘。中途失败可能留下部分动作，文件边界属于实际调用方；完整 builder 的 manifest 写入不能视为这些 helper 的独立回执。 [旧动作与编排](#motionbuild_action-与-nla-编排) |
| `stage_ops clip` | 主候选新路径，先保存重开、记摘要后普通写报告；默认 sidecar 可覆盖既有文件，显式报告也未与输入／输出隔离。故障可能留下已保存工程、旧报告或部分 JSON；同址报告可在摘要计算后覆盖工程。此为源码边界，clip 同址尚未实测。 [裁剪与报告](#stage_ops-clip-已烘焙动作裁剪) |

## 外部后端

尺度环带和面颈校准的 Skill 提供输入、保护区域和验收约定。面颈校准包由调用方在 Blender 中实施造型，Skill 中明示包内无可执行造型脚本。 [尺度环带 Skill](../upstream/1.2.11/prebuilt-skills/scale-aware-quad-rings/SKILL.md) · [面颈校准 Skill](../upstream/1.2.11/prebuilt-skills/lowpoly-quad-face-neck/SKILL.md)

外部扩展、可执行文件和 Blender 环境按实际安装发现。四边通 Plus 的参考文件记录三个可选入口及原四边通分支。 [后端与输入说明](../upstream/1.2.11/prebuilt-skills/quad-flow-plus/references/hi3d-initial-remesh.md)

| 后端 | 包内可复核的接口 |
| --- | --- |
| QRemeshify | 在已配置扩展的 Blender 中选中工作副本，处于对象模式，通过 `bpy.ops.qremeshify.remesh()` 调用。参考列出 `quadwild_props`、`quadpatches_props`。须回读实际的新非空网格、面型和坐标。 |
| AutoRemesher | 外部 CLI 使用三角 OBJ，参数为 `--input`、`--output`、`--report`、`--target-quads`。目标面数为近似值。回读 OBJ 并按源工程安排属性转移。 |
| Instant Meshes 2026 | 通过已装扩展的 `bpy.ops.mesh.instant_retopo_execute()` 和 `retopo_props` 传入实际引导。兼容的 `pyretopo` 可直接使用，CLI 分支以 `--contour` 接收轮廓 OBJ。CLI 分支的 `mirror_x` 未传入后端，需要对称时复核实际引导与结果。 |

人头独立包的 `instant_meshes` 配置使用原 CLI 的 `-d -r 4 -p 4 -f <goal> -S 2 -o <output> <input>`。四边通 Plus 的 2026 插件与该 CLI 各有接口。可回读的候选、真实面数、边界和保护结构通过检查后才具备后续复用依据。 [人头 CLI 调用](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/run.py:117>) · [外部后端实际调用](../upstream/1.2.11/prebuilt-skills/quad-flow-plus/references/hi3d-initial-remesh.md#三项插件的实际调用)

## 独立复核

以下校验值来自本机 Windows x64 1.2.11 安装事务备份。可从包内对应路径以 `Get-FileHash -Algorithm SHA256` 复算。 [安装包清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) · [锁定发行库存](../upstream/1.2.11/inventory/inventory.jsonl)

| 安装原件 | SHA-256 |
| --- | --- |
| [`hi3d-quad-judge.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/quad-flow-plus/scripts/hi3d-quad-judge.py>) | `26a18ceefc1fd3fc65befe9de3a8df474fffb3de59ff52e1467b77bc1a17d618` |
| [`hi3d-chain-budget.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/quad-flow-plus/scripts/hi3d-chain-budget.py>) | `d89fd57f97c9c39da9dcc7eccb64951d3699f1981f29f9685cf9a07462ad5002` |
| [`hi3d-quad-template.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/closed-quad-transition/scripts/hi3d-quad-template.py>) | `80473c02a954413338316ca8ccc39195974346ab88324b3a4601d29a93a3d358` |
| [`mdf_handoff.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/mdf_handoff.py>) | `2aae4fb218f2b77b579c1b82bb641d95d6d8c148e46de91ec94c62d2ee028d7d` |
| [`retopology.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/retopology.py>) | `3b3db4a8cb1305b32b10a88bae31da701fdc89e2d0f917709bdd06a568d1357d` |
| [人头 `run.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/run.py>) | `2ea63e65e7f9add4b14a761fc0693ddf0e363f1bff6b563077c0c5ccbb0ffb94` |
| [`mesh_measure.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/mesh_measure.py>) | `d403a16539b55efeec50bed5a12c03adfd89d7602d6d317b069c87f333b93de5` |
| [绑定 `run.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/run.py>) | `ad7b270350d617baefd9d18ae8044db902b153502374cbecb61afaabdb4f7f6d` |
| [`service_rig.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py>) | `b1090def180cd66ce35bb0c2f1ec4b2343df93ab039fc6fad7958bd989ffcd76` |
| [P1 `skin_weights.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/skin_weights.py>) | `07668c30ed37172c5b0babf053eefc206a3fcc6077ff3ba901aee9b68a1c11e4` |
| [服务本地回归 `test_service_rig.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_service_rig.py>) | `04283a9af7ba9c83a2c36c3d7a9fbe3dc13c819b90b6573b6020318128e33b07` |
| [数值回归 `test_skin_weights.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_skin_weights.py>) | `919210871da0e7f9d774de90176f6b20bcefd0f2f010ae7c15f1501076356e9f` |
| [`prepare_mesh.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/prepare_mesh.py>) | `492728e7f666ae876113fb6ce994afb3ee82a4745145b165fbe31c587cb42da5` |
| [`make_profile.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/make_profile.py>) | `49703be6c0c9c52b95e2733bda275714e9353e2f3c2462c8f7e653f62f3aa035` |
| [`build_character.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py>) | `95cae0d242467669756f53b15ea28eabb01648d6f3b217fd7ad5cc6a7aa6bf53` |
| [`weight_graph.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/weight_graph.py>) | `60136c85a89991342d512ccbff5d5fe2b827567fb5f746eed0ee6cf9a472018f` |
| [`validate_blend.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/validate_blend.py>) | `e4148c625c13ea9048a065b8c514aa2d4106236aeee7866e03e4af147d41535c` |
| [`blender_core.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/blender_core.py>) | `3dd41ea41b64d6297ca88ad7231526a6ff404d88a4cda1011f84c3b56e19a1cc` |
| [`rig_adapter.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py>) | `7f4bc80f4f268b4ff4b58764355fd5b7387e6e0ed9840186563f3f93cd9f04d7` |
| [`cache_bvh.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/cache_bvh.py>) | `824c40407a96b38eabf2763487ffe446571e6093a8a6496bc07127c265cf6d16` |
| [`retarget_math.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/retarget_math.py>) | `fe49ac3a4ec82f487fcbf28476b241f88889ba6ba40fe14dc21015b29cd1142b` |
| [兼容消费 `motion.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/motion.py>) | `ba8e6dd9abcd6508c4972ffc37d535cbb26663e4170658938b461199a8bc54cf` |
| [场景盘点 `stage_ops.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d-model-gpt-animation/scripts/character/stage_ops.py>) | `ccfe82eec7d0136223f7626ef54c13fa9c7fc0a22d0cb898ce17052db43058ad` |
| [动画分派 `run.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d-model-gpt-animation/scripts/run.py>) | `2744d2ddfbe5daab86d433faa1a0999080b0afc97bb3e03c612e8e72a2d011f3` |
| [共享 `blend_common.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/blend_common.py>) | `54b0d588c8bfda7cd3640e6c0227a9a88e093b0a287885c5811282444909b9dd` |
| [绑定 `io_utils.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/io_utils.py>) | `ead12b0548776102ed0432cd6ce21f71bfb66040c5cb8f682f75ebcdde2c3ef7` |
| [绑定 `timing.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/timing.py>) | `b95c0ea266ef797d196aadbc63d0c2c744498d6fb72fd9f12b8c3e90c26c1233` |
| [映射回归 `test_retarget.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_retarget.py>) | `839640d8936e91eb186cc663984e00752488c7175b33ed35ef2ffb50345b964c` |
| [旧动作 `motion.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/motion.py>) | `ba8e6dd9abcd6508c4972ffc37d535cbb26663e4170658938b461199a8bc54cf` |
| [NLA 与构建 `build_character.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py>) | `95cae0d242467669756f53b15ea28eabb01648d6f3b217fd7ad5cc6a7aa6bf53` |
| [动画包分派 `run.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d-model-gpt-animation/scripts/run.py>) | `2744d2ddfbe5daab86d433faa1a0999080b0afc97bb3e03c612e8e72a2d011f3` |
| [场景与裁剪 `stage_ops.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d-model-gpt-animation/scripts/character/stage_ops.py>) | `ccfe82eec7d0136223f7626ef54c13fa9c7fc0a22d0cb898ce17052db43058ad` |
| [`audit_models.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/audit_models.py>) | `250d2fe24c7a63e8d1874d2515555262f2d0e7bcd029577a28bbd6db83f285fa` |
| [审计 `frame_runtime.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/frame_runtime.py>) | `bd20f4e414f96cf6a90ba6ab79d165204e4654fa4b18b96edab6f503595a1a36` |
| [`geometry_compare.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/geometry_compare.py>) | `f9806e385016cd968a339c27e55b3776a04d4ddcf551fd3a85303f0a7d23e93d` |
| [`collision.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/collision.py>) | `66f72f29f9dfd3e58813d5ffc017a3c713040b15c5efa94ea6a11991e8e0ee72` |
| [`scene_measure.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/scene_measure.py>) | `c95cbe415033de5e8fc2853c1215da1583994ec5ed1383770967db1311d9aa9a` |
| [`triangle_arrays.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/triangle_arrays.py>) | `84a6aaa3572d82bab18fe4bb3ad815f4c0acca1c164726dc4998fad17130e86f` |
| [`surface_pairs.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/surface_pairs.py>) | `f3816a038cf85fb7391d45bd000b2e77aa1605024e71758f57f182c193d41284` |

- **已离线复核。** 从临时目录用随包 Python 重跑四边通判定 39 项、边链与预算 13 项、闭合模板 8 项和人头交接 10 项，均通过。覆盖本地输入校验、判定输出、合成边链及替身账本中的成功回包和 OBJ 读取。 [判定测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/quad-flow-plus/scripts/hi3d-test-quad-judge.py>) · [边链测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/quad-flow-plus/scripts/hi3d-test-chain-budget.py>) · [模板测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/closed-quad-transition/scripts/hi3d-test-quad-template.py>) · [人头交接测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/test_mdf_handoff.py>)
- **静态导出与回读。** Blender 4.5.16 LTS 的随包 `test_service_rig` 合成回归通过。独立夹具复现了基础和减面导出、直接启动与 P0 包装启动输出字节一致、可选计时追加 JSONL，以及 P1 权重模块加载而权重函数未执行。可选 `audit_models.py` 从合成立方体回读得到一个网格、12 个三角面、实际世界范围和摘要。真实网格减面后的局部保形、复杂贴图保留以及四足绑定和形变表现需用目标资产验证。 [Blender 回归入口](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_service_rig.py:14>) · [审计源码](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/audit_models.py:25>)
- **网格准备与权重交接。** Blender 4.5.16 LTS 合成夹具中，`prepare_mesh` 直接与 P0 包装启动输出相同报告，显式计时写入完成记录。回读合成焊接工程确认了三角、面角 UV 和材料。隔离验证覆盖外部 CG 求解、缓存回建和过期校准被拒绝。随包权重图测试 5 项通过。留存三个静态 GLB 与两份会话覆盖普通网格修订和通用工具调用，所查记录没有显示这组专项命令执行。生产工具调度、高面数资源消耗和真实四足资产的域隔离、保形及动态接触仍待实测。 [焊缝测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_blender.py:22>) · [权重图测试原件](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_weight_graph.py>) · [留存工作区](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40>)
- **求解与数值验收复核。** 200 三角面的合成网格覆盖外部 CG、结构匹配的缓存回建和已保存工程重开。Blender 4.5.16 LTS 使用临时兼容 SciPy 目录跑通内置 LU。随包独立 Python 重跑 `test_weight_graph` 五项通过，并复现不收敛只写失败报告、输入校验失败无新文件。`validate_blend` 隔离试验覆盖帧排序去重、接缝排除范围、旧报告覆盖、输入同址覆盖和提前异常保留旧报告。空集合和无 Armature 修改器的合规同名权重组均可通过数值判定。 [求解回归](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_weight_graph.py:31>) · [完整候选夹具](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_pipeline.py:91>) · [验收原件](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/validate_blend.py:180>)
- **骨架 CLI 隔离复核。** Blender 4.5.16 LTS 合成夹具复现种子拒绝覆盖、初始权重导出、缓存回建、已有骨架的严格布尔和休止摘要检查，以及保护校验后的工程重开。实测完整构建覆盖已有 manifest，写报告失败时留下工程。已有骨架检查可读 `inherit_scale="NONE"` 的对象，调整分支拒绝该继承方式；针对普通 FK 的 `tail_at` 编辑保留了关节头、权重和 UV，同向延长骨尾时摘要可保持一致。随包 `test_retarget` 隔离回归通过。 [随包测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_retarget.py:209>) · [配套报告写入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py:224>) · [已有骨架检查和落盘](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:281>)
- **骨架 CLI 待实测。** 随包运行说明列 Blender 5.x 作为已有骨架适配环境，已跑的隔离分支使用 4.5.16 LTS。生产宿主调度和长任务恢复、大型网格 LU／CG 峰值、复杂资产保护、真实四足的肢体串权、拆件接缝、独立软层和足端动态接触待实测。 [随包运行环境](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/runtime.md:7>)
- **待实测。** 外部后端参考只记录 macOS arm64 和 Blender 5.1.1 的安装冒烟。Windows 上的实际扩展及 CLI、生产 MDF 原生 OBJ、引导在真实网格上的贴合度，以及属性和变形保留均待实测。报表中的计数、边链通过和摘要核验各自只覆盖所测范围。 [外部后端实测范围](../upstream/1.2.11/prebuilt-skills/quad-flow-plus/references/hi3d-initial-remesh.md#本次已实测范围)
