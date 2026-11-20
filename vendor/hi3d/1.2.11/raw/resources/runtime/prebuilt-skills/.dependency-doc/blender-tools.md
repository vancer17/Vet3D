# Blender 后台工具

输入为明确 Blender 可执行文件、场景和输出路径。工具使用 bpy/mathutils/NumPy；分块缓存检查另需 Pillow。原生依赖检查读取工程及资源哈希；scene_io 负责导入与对象保留，head_io 负责单头选择与额外网格保留；头部检查场景由 [model-preview](../.dependency-model-preview/references/head-preview.md) 维护。渲染入口会打开独立工程或写帧，不修改原始文件。

分块 spec 为 JSON 对象数组，每项含安全 tag 和正整数 frames，来源为 case/<tag>.blend。当前检查 profile 固定 864×768、24fps；执行单块最多两次且仅超时重试。来源哈希变化时旧帧隔离，无匹配检查点的帧必须显式 adopt。单帧工具按显式帧范围写 PNG，失败由 --python-exit-code 1 传播。源模型规范化属于 source-prepare，产品姿态/预览编排属于 model-preview。

[AI 入口](../.dependency-blender-tools/REFERENCE.md)与 [独立安装](../.dependency-package-tools/references/usage.md)定义调用方式。

[后台环境与 Python 依赖](../.dependency-blender-tools/references/code-contract.md#后台环境与-python-依赖) 维护显式可执行文件、后台异常退出与嵌入 Python 的 ABI 边界；所用 Blender API/版本及业务线程数由调用方声明。

## 模块与接口

### scripts/asset_scene.py

[唯一实现](../.dependency-blender-tools/scripts/asset_scene.py) 的 `open_asset(path, *, frame=None)` 接收已有 BLEND/GLB 与可选整数帧，返回载入后的当前场景对象。先验证路径、后缀和帧，再完整打开 BLEND（禁止自动执行内嵌脚本、不加载 UI）或复用 scene_io 清场导入 GLB；最后按需切帧并更新依赖图。仅修改当前隔离后台场景，不保存源文件；实际加载失败可能留下部分场景。它不等于 BLEND 对象追加，运行条件见 [完整资产载入](../.dependency-blender-tools/references/asset-scene.md)。

[tests/test_asset_scene.py](../.dependency-blender-tools/tests/test_asset_scene.py) 在合成工程验证完整场景与原帧恢复、GLB 动作/指定帧、失败前场景保持和原文件不变；从物化包以独立 Blender 进程执行。

### scripts/execute.py

[唯一实现](../.dependency-blender-tools/scripts/execute.py)。 Run an explicitly selected installed package script/module in background Blender.

| 接口 | 参数 | 职责与失败边界 |
| --- | --- | --- |
| `execute` | `*, script=None, module=None, scripts=None, arguments=()` | Add only the explicitly selected package's scripts directory, then run its entry.  The target is trusted package code, not a sandbox. It may mutate this background scene and write its declared outputs. Arguments and exceptions are preserved. |
| `main` | `argv=None` | 按上述模块契约执行；显式输入，错误向调用方传播。 |

### scripts/head_io.py

[唯一实现](../.dependency-blender-tools/scripts/head_io.py)。 单头选择与坐标提取，仅在 Blender 内调用。

| 接口 | 参数 | 职责与失败边界 |
| --- | --- | --- |
| `coordinates` | `obj` | 按上述模块契约执行；显式输入，错误向调用方传播。 |
| `load_source` | `path, object_name=None, keep_objects=()` | 按上述模块契约执行；显式输入，错误向调用方传播。 |

### scripts/native_dependencies.py

[唯一实现](../.dependency-blender-tools/scripts/native_dependencies.py)。 native dependencies local stage adapter.

| 接口 | 参数 | 职责与失败边界 |
| --- | --- | --- |
| `execute` | `arguments` | Execute this explicit local stage. Files/processes/Blender state change only when called; failures propagate. |
| `main` | `argv=None` | 按上述模块契约执行；显式输入，错误向调用方传播。 |

### scripts/render_frame_chunk.py

[唯一实现](../.dependency-blender-tools/scripts/render_frame_chunk.py)。 render frame chunk local stage adapter.

| 接口 | 参数 | 职责与失败边界 |
| --- | --- | --- |
| `execute` | `arguments` | Execute this explicit local stage. Files/processes/Blender state change only when called; failures propagate. |
| `main` | `argv=None` | 按上述模块契约执行；显式输入，错误向调用方传播。 |

### scripts/render_frames.py

[唯一实现](../.dependency-blender-tools/scripts/render_frames.py)。 Explicit-input business stage and thin command-line adapter.

| 接口 | 参数 | 职责与失败边界 |
| --- | --- | --- |
| `render_frames` | `*, scene, output, frames='1,100,120'` | Run this named business stage. Inputs and all output paths are explicit.  Mutates the active Blender scene when applicable; never runs on import. Files are generated only under the explicit destination. See code-contract.md. |
| `main` | `argv=None` | 按上述模块契约执行；显式输入，错误向调用方传播。 |

### scripts/render_video_chunks.py

[唯一实现](../.dependency-blender-tools/scripts/render_video_chunks.py)。 Bounded native-scene frame rendering with source-hash checkpoints and fresh processes.

| 接口 | 参数 | 职责与失败边界 |
| --- | --- | --- |
| `build_parser` | `` | 按上述模块契约执行；显式输入，错误向调用方传播。 |
| `execute` | `a` | Execute this explicit local stage. Files/processes/Blender state change only when called; failures propagate. |
| `main` | `argv=None` | 按上述模块契约执行；显式输入，错误向调用方传播。 |

### 产品 studio 组合入口

产品形体、预览、打印、检查和来源操作由各自原子能力维护，调用方显式导入 `studio_core`、`studio_preview`、`studio_print`、`studio_audit` 和 `studio_source`；单位与副作用见 [组合契约](../.dependency-shape-build/references/composition.md)。Blender 工具不反向导入这些领域实现，物化清单不再提供旧 studio 聚合入口。

## 验收方法

仅在仓库外的独立包和合成输入上运行。校验参数错误、输出保护、正常结果及失败传播；记录工具不通过真实任务补统计，Blender 工具不在未保存的前台工程测试，依赖打包不修改已安装目录。验证记录保存到任务目录，不将一次测试当作全部业务/线上服务的验收。

## 离线测试接口

[tests/test_render_spec.py](../.dependency-blender-tools/tests/test_render_spec.py) 覆盖渲染来源、帧数量与 profile 改变时拒绝旧缓存，以及非法/重复场景标签和帧数校验。测试只使用合成数据；通过物化包的 `python -m unittest discover -s tests -v` 运行。

`render_video_chunks.read_spec(path)` 读取并验证唯一场景标签和正整数帧数；`matching_checkpoint(record, source_hash, frame_count, sources)` 要求来源、渲染源码、帧数、分辨率、帧率和引擎全部一致，防止修改帧规格后混入旧帧。

## scripts/scene_io.py

[唯一实现](../.dependency-blender-tools/scripts/scene_io.py) 提供两项操作，完整运行条件见 [随包契约](../.dependency-blender-tools/references/scene-io.md)。

- `import_objects(path, *, reset=False)`：返回新导入的 Blender 对象列表；支持 GLB/GLTF/OBJ/PLY/BLEND。验证路径后可清空场景，BLEND 保留父层级，不执行单位变换或产品选择。无源文件写入；导入错误传播。
- `retain_meshes(objects, *, remove_others=False, apply_transform=True)`：验证非空唯一网格列表，快照全部世界矩阵后解除父级，可删除其他对象并逐件施加变换，返回原名到对象映射。依赖 bpy，修改当前隔离场景/选择；不修复拓扑或合并网格。

`head_io.load_source` 委托上述操作；保留 Source_High 命名及明确单头选择，keep_objects 可保留原名附加网格，业务头发命名由 head-lowpoly 负责。无头/多头/缺失附加网格抛 ValueError。source-prepare 在导入后独立负责高度/坐标规范化。离线验收覆盖带缩放父级的头与头发、附加对象、未知名称、格式失败和清场策略。

## scripts/mesh_snapshot.py

[实现](../.dependency-blender-tools/scripts/mesh_snapshot.py) 与 [运行契约](../.dependency-blender-tools/references/mesh-snapshot.md) 维护快照的字段、单位、求值及清理边界。

| 接口 | 输入 → 输出及副作用 |
| --- | --- |
| `mesh_source` | obj、必填 evaluated、可选 depsgraph → 上下文 (source, mesh)；只拥有临时转换，异常也释放，原 data 不删除 |
| `mesh_data_snapshot` | mesh、transform/scale、triangulation/precision/fields → 脱离资源的几何及所选 loop UV/材质索引数组；不修改源网格 |
| `mesh_snapshot` | obj、必填 evaluated/space、其余快照参数 → 组合以上两者的字典；非法策略失败 |

[快照测试](../.dependency-blender-tools/tests/test_mesh_snapshot.py) 在隔离后台进程验证空间、单位、索引、形变、属性与失败释放，不需要用户工程。领域阈值和序列化保留在各自调用方。

### scene_io.create_mesh_object

`create_mesh_object(name,vertices,faces,*,collection,material=None,recalculate_normals=False,smooth=False)` 使用 from_pydata 建立独立 Mesh 并仅链接目标集合。输入坐标为场景单位；指定材质/平滑，按需在临时 BMesh 重算法线，不修复、不焊点。返回新对象，不改变已有选择；构造异常清理此次对象/网格并传播。材料与集合须为当前 Blender 数据块；不从全局名称猜测。原子及工作流在独立合成场景比较坐标、绕序、集合、材质与曲线输出。

## scripts/material_nodes.py

[实现](../.dependency-blender-tools/scripts/material_nodes.py) 的 `principled_material(name,color,metallic=0,roughness=.5,inputs=None)` 接收线性 RGB/RGBA，创建材质、diffuse_color、基础 BSDF 和显式附加 socket；返回新材质，失败移除它，参数遵从 Blender socket 规则。三/四通道以外失败，不自动转换 sRGB、不分配对象、不添加特殊产品节点。完整运行边界见 [材质契约](../.dependency-blender-tools/references/material-nodes.md)。验收比较基础/额外节点与原 profile，未知 socket 后不得残留新材质。

## scripts/cycles_device.py

[唯一实现](../.dependency-blender-tools/scripts/cycles_device.py) 与 [随包契约](../.dependency-blender-tools/references/cycles-device.md) 提供 select_cycles_device 和 cycles_device_context。输入场景、CPU/AUTO/明确 GPU 后端及显式 fallback_cpu，输出 backend/devices/fallback/reason；前者配置当前进程，后者成功/失败恢复设备状态，新增枚举设备退出后禁用。未知设备或不允许回退时失败，不设置渲染配方或保存偏好。设备枚举通过不代替 GPU 实际渲染验收。

[设备测试](../.dependency-blender-tools/tests/test_cycles_device.py) 使用模拟设备验证 AUTO 顺序、显式 CPU 回退、未知后端与重新枚举后的成功/中断恢复；它不依赖真实 GPU，实际烘焙和渲染由调用方验证。

### scripts/render_scene.py

[render_scene](../.dependency-blender-tools/scripts/render_scene.py) 的 `render_scene(source, output, frames, *, engine, resolution, fps=None, threads=None, samples=None, device=None, denoise=None, prefix='', animation=False, overwrite=True)` 是已有 BLEND 到明确 PNG 帧列表的通用操作。完整参数、状态副作用、失败恢复和四种适配见 [随包契约](../.dependency-blender-tools/references/render-scene.md)。三个旧工具入口组合此函数；业务只选择画面/帧，不复制渲染器设置与写图循环。

`render_video_chunks.render_sources(scripts)` 对四个实际渲染源码取 SHA-256 字典；matching_checkpoint 同时核对该字典，旧检查点无摘要时隔离旧帧，不能以旧图存在复用。相关回归见 [render spec](../.dependency-blender-tools/tests/test_render_spec.py)；[真实场景测试](../.dependency-blender-tools/tests/test_render_scene.py) 在 Blender 内覆盖 EEVEE/Cycles、命名、fps、失败边界和源工程不变。

## 渲染器兼容

[render_engine.py](../.dependency-blender-tools/scripts/render_engine.py) 的 engine_identifier、set_engine、set_samples 的输入输出及失败边界见 [随包契约](../.dependency-blender-tools/references/render-engine.md)。纯名称选择无 bpy 依赖；set_engine 才操作现有场景，render_scene 在加载文件后调用。分块指纹显式包含模块源码，产品/头部/相框及人物采样通过 manifest 物化；无隐式相邻目录依赖。兼容检查使用模拟枚举与安装的 Blender 最小场景，不等同于所有成品重渲染。

render_sources(scripts, blender=None) 同时纳入渲染器兼容源码和实际调用的 Blender 可执行文件摘要；模型输入不变时换渲染实现或可执行文件会使分块渲染缓存失效。
