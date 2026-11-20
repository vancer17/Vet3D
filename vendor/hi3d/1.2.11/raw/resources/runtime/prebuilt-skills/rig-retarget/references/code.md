# 绑定与动作原子接口

实现位于本包 scripts/rigging；统一入口为 scripts/run.py，按需导入单个模块。运行依赖见 [运行说明](runtime.md)。CLI 参数以 --help 为准；Blender 操作修改当前进程场景，使用后台进程和新候选路径。新增已有骨架适配接口见 [适配接口](retarget-api.md)。

## 包入口

[rigging/__init__.py](../scripts/rigging/__init__.py) 仅声明本地原子模块包，导入时不启动 Blender 操作或网络。统一 CLI、既有骨架适配、计时和新增回归的完整接口见 [适配接口](retarget-api.md)。

## blend_common

代码：[blend_common.py](../scripts/rigging/blend_common.py)。Blender 场景读写、摘要、动作访问与 inventory；摘要只覆盖明确列出的数据，不是任意驱动/约束审计。

| 函数 | 契约与副作用 |
| --- | --- |
| `curves(action)` | Action → F-Curve 列表；兼容分层 Action/channelbags 与旧接口，只读，不改变曲线。 |
| `linked_actions(obj)` | 对象 → 去重的当前 Action 与 NLA 引用列表；无动画时为空。 |
| `digest(value)` | JSON 可序列化对象 → 排序键的 SHA-256；只做确定性摘要。 |
| `animation_hash()` | 无参数 → 当前动作通道、关键帧/手柄/插值摘要；不包括任意约束与驱动语义。 |
| `geometry_hash()` | 无参数 → 当前对象名、mesh/UV/权重/shape keys/rest 骨架摘要；不证明全部材质/约束/世界变换相同。 |
| `open_input(path, output=None)` | 输入 blend、可选候选输出 → 解析后的输入路径；检查输入与覆盖规则，再禁用内嵌脚本执行加载工程。 |
| `write_json(path, value)` | 路径、JSON 数据 → 无返回值；写 UTF-8 报告并创建父目录，允许调用方更新报告。 |
| `save_candidate(args, report)` | 含 output/report/pack 的选项、报告 → 无返回值；保存并禁用内嵌脚本执行重开候选，向报告补 inventory/文件摘要后写出。 |
| `inventory()` | 无参数 → 当前场景帧范围、fps、相机、文本、rig/NLA、动作及贴图打包状态字典；只读。 |


## blender_core

代码：[blender_core.py](../scripts/rigging/blender_core.py)。已校准骨架、分区初始权重和保留 UV/材质的分件绑定；依赖 Blender/NumPy，求解时才导入 SciPy。

| 函数 | 契约与副作用 |
| --- | --- |
| `mesh_arrays(ob)` | Mesh 对象 → float32 顶点与 int32 三角面数组；只读几何，拒绝非三角拓扑。 |
| `mesh_fingerprint(v, f)` | 顶点、面数组 → 统一 mesh_digest；坐标转小端 float32、索引转小端 int32 后求摘要。 |
| `create_rig(spec, height)` | 按父骨在前排列的骨点配置、身高 → 新 Armature；比例点变成模型坐标，设置 roll/父级/变形与姿态模式。 |
| `region_mask(points, row)` | N×3 点、含 bounds 的规则 → 布尔掩码；包含上下界的纯数组判定。 |
| `initial_weights(v, names, profile, height)` | 顶点、变形骨顺序、profile、身高 → N×B 归一化初始权重；后区域覆盖前区域，沿有序过渡平滑分配。 |
| `localized_solve(v, f, initial, radius, fidelity_length, edge_floor, **options)` | 网格/初始权重/长度参数 → 权重和固定掩码；对 solve_weights 的兼容委托，无第二份求解实现。 |
| `part_labels(v, f, profile, height)` | 顶点、三角面、profile、身高 → 每面标签；按面心应用后规则覆盖前规则，不自动识别语义。 |
| `split_bind(surface, rig, names, weights, labels, rigid_parts)` | 统一表面、rig、骨顺序、权重、标签、刚性部件映射 → 新部件对象列表；复制 UV/材质及共享权重，量化至 1/65536 单纯形并移除原工作表面。 |


## build_character

代码：[build_character.py](../scripts/rigging/build_character.py)。组合已准备网格、校准配置、权重求解/缓存、分件、BVH 动作与候选交付；不自动创建服装代理或识别人体。

| 函数 | 契约与副作用 |
| --- | --- |
| `resolve_weights(v, f, names, initial, profile, height, profile_dir)` | 网格、骨顺序、初始权重、profile、身高、profile 目录 → 权重/锚点/报告；验证缓存对应当前校准，或按当前参数求解。 |
| `resolve_labels(v, f, profile, height, profile_dir)` | 网格、profile、身高、profile 目录 → 标签；可加载带匹配 mesh 摘要的 NPZ，长度须等于面数。 |
| `sequence_actions(rig, profile, profile_dir)` | rig、profile、profile 目录 → scene/track/动作列表/检查帧；先烘焙全部动作再创建 NLA，拒绝与动作重叠的检查帧。 |
| `configure_inspection(rig, parts, height, profile, scene, track, inspection)` | rig、parts、height、profile、scene、track、检查帧 → 已使用骨名集合；配置可检查的骨架显示与工程内说明，不替代业务验收。 |
| `build_character(input_path, profile_path, output_path=None, export_weight_input=None, python_packages=None)` | 准备工程、profile、新 blend 或权重导出路径、可选 ABI 匹配包目录 → manifest；明确选择一个输出模式，校验 calibrated 与 weld 标记后组合原子操作。 |


## cache_bvh

代码：[cache_bvh.py](../scripts/rigging/cache_bvh.py)。使用 Blender BVH 导入器按目标 fps 缓存同一骨架空间下的 rest/pose 矩阵；输出 names/rest/poses/fps。

| 函数 | 契约与副作用 |
| --- | --- |
| `cache_motion(input_path, output_path, fps=30, scale=0.0254, forward='-Z', up='Y')` | BVH、新 NPZ 路径、fps/单位缩放/坐标轴 → 帧数/骨数/fps；导入并逐目标帧求值，文件存在时拒绝覆盖。 |


## io_utils

代码：[io_utils.py](../scripts/rigging/io_utils.py)。标准库文件原子能力；所有哈希读取按 1 MiB 分块，JSON 使用同目录唯一临时文件与原子替换。

| 函数 | 契约与副作用 |
| --- | --- |
| `file_digest(path)` | 路径 → SHA-256 十六进制字符串；只读文件，文件缺失等 I/O 错误向调用者传播。 |
| `atomic_json(path, data)` | 路径、可 JSON 序列化对象 → 无返回值；创建父目录，持久化并替换 JSON，失败清理临时文件。 |


## make_profile

代码：[make_profile.py](../scripts/rigging/make_profile.py)。生成比例人形校准种子；输出 calibrated=false，不承诺自动识别骨点、服装语义或真实骨架。

| 函数 | 契约与副作用 |
| --- | --- |
| `profile()` | 无参数 → 新的未校准人形配置字典；比例骨点、区域、命名、映射与 solver 为待校准种子，无文件副作用。 |


## motion

代码：[motion.py](../scripts/rigging/motion.py)。将同 fps 的 BVH 缓存重定向为目标 Action，并按动作修正整掌轴、根位移与可选落地；不自动脚锁或分指。

| 函数 | 契约与副作用 |
| --- | --- |
| `hand_offset(style, side, index, period)` | 动作风格、左右侧、帧序号、周期 → 掌腕 Quaternion；neutral/run/dance 为原创整掌短句种子，非分指或音乐同步系统。 |
| `ground_height(rig, collection_name='CharacterParts')` | rig、部件集合名 → rig 空间最低求值顶点 Z；忽略非 Mesh 并释放求值网格，不寻找任意世界舞台表面。 |
| `build_action(rig, spec, profile, config_dir)` | rig、动作 spec、profile、缓存目录 → 新 Action；校验 fps/样本/映射，修正 rest/父骨空间、掌腕与根位移，产生关键帧但不建 NLA。 |

`fcurves` 直接复用 `blend_common.curves`，不维护重复 Action 访问逻辑。


## prepare_mesh

代码：[prepare_mesh.py](../scripts/rigging/prepare_mesh.py)。导入一张统一生成表面，统一坐标和身高、焊接面角 UV 接缝、三角化及可选本地 Decimate，另存工作工程。推荐减面改用 [mesh-lod](mesh-lod.md) 的严格自交保护与重烘流程；接收返回 LOD 时省略 `faces`，本地 Decimate 不提供等价保护。本脚本清空当前场景并合并输入全部 Mesh，不自动处理分层衣物语义或已有工程权重转移。

| 函数 | 契约与副作用 |
| --- | --- |
| `normalize_vertices(vertices, height)` | N×3 有限顶点、正身高 → 归一化顶点、原包围盒中心、缩放；纯数组变换，拒绝空或退化输入。 |
| `import_surface(input_path, rotation_degrees)` | GLB 路径、Z 旋转角度 → 合并的 Blender Mesh 对象；替换当前工作场景并应用对象变换。 |
| `weld_surface(surface, distance)` | 活动表面、绝对距离 → 焊后顶点数；Geometry Nodes 合并坐标、保留面角 UV，清理无使用者的临时节点树。 |
| `triangulate_reduce(surface, faces=None)` | 表面、可选正整数面预算 → 实际面数；应用三角化与近似 Decimate，不保证精确等于预算。 |
| `prepare_mesh(input_path, output_path, height=1.8, faces=None, weld_relative=1e-06, rotation_deg=0)` | 输入 GLB、新输出路径及尺度/面数/焊接/旋转参数 → 网格报告；另存 .blend 与 .mesh.json，拒绝覆盖。 |


## test_blender

代码：[test_blender.py](../scripts/rigging/test_blender.py)。合成 GLB 的 UV 焊接、原子求解、掌腕短句与含非 Mesh 的 rig 空间落地回归。


## service_rig

代码：[service_rig.py](../scripts/rigging/service_rig.py)。Blender 本地 auto-rig 交接，CLI 为 `service_rig export / bind / inspect / repair`；请求与规则示例见 [服务绑定与修复](service-rig.md)。不联网、不重写 mdf-call，不自动推断骨名语义或编排动作。

| 函数 | 契约与副作用 |
| --- | --- |
| `surface(obj)` | Mesh 对象 → 基础顶点与 loop-triangulated 三角索引；只读三角化，不改多边形拓扑。 |
| `skin_table(obj, rig)` | Mesh、Armature → 有序变形骨名与 N×B float32 权重；排除非骨骼组，拒绝非法/未绑定/未归一化数据。 |
| `rig_digest(obj, rig)` | 网格空间的静止骨矩阵、层级与变形标记 → SHA-256；用于拒绝过期区域规则。 |
| `write_changed_weights(obj, names, before, after)` | 匹配的骨顺序和两份 N×B 表 → 修改顶点数；只原位更新变化成员，移除变零成员并追加新成员；保留现有成员顺序、其他顶点与非骨骼组；共享 Mesh 先复制所选对象的数据，避免修改其他实例。 |
| `preserved_signature(obj, groups=())` | 对象、保护组名 → 几何/面角 UV/材质槽/shape key 坐标/变换及指定组权重摘要；不声称涵盖任意驱动或材质节点。 |
| `export_body(obj, output, faces=None)` | 单身体、全新 GLB 路径、可选提交代理面预算 → 输出/指纹/面数；临时网格副本导出基础静止表面，结束清理副本，不写源文件。 |
| `bind_result(glb, body, targets, alignment_tolerance)` | 单骨架单蒙皮 GLB、未绑定身体及显式目标、世界单位包围盒容差 → 骨架/参考体/保护项报告；按名最近面插值、归一化骨组并加 Armature，不应用目标其他修改器。 |
| `inspect_skin(obj, rig, frames, height)` | 已绑定对象、当前骨架、实际整数帧、局部单位身高 → 校准身份、拉伸与最差面权重报告；要求可见且启用求值、对应拓扑不变，检查后恢复当前帧。 |

CLI 读取输入 `.blend`，拒绝覆盖输入/输出/报告；`bind` 与 `repair` 保存并打包新候选，随后仍需重开做姿态和可视化验收。输入/规则校验失败时拒绝写候选；保存阶段失败可能留下未验证文件，不能当作完成。进程内中间修改从原输入继续。内存主要为 N×B 权重表，不依赖 SciPy。


## skin_weights

代码：[skin_weights.py](../scripts/rigging/skin_weights.py)。纯 NumPy；`service_rig` 与 `validate_blend` 共用一份拉伸判据。

| 函数 | 契约与副作用 |
| --- | --- |
| `check_weights(weights, vertices=None)` | 权重和可选顶点 → 校验后的数组视图；只读，拒绝负/非有限、维数不匹配和未归一化输入。 |
| `repair_regions(vertices, weights, bone_names, rules)` | 局部静止坐标、N×B 权重、有序骨名、显式 bounds/forbidden_bones 规则 → 新权重和变化报告；移除错误归属、归一化受影响行、统一所选皮肤域完全重合点，不改输入。拒绝未知骨、空区域、清理后无剩余影响。 |
| `stretch_metrics(rest, posed, faces, height)` | 同拓扑静止/姿态顶点、三角索引、同单位身高 → 严重边/面积计数、原始倍率、增长量、最差面索引与指标；纯计算，阈值同时限制倍率和绝对增长。 |


## 服务绑定离线验证

代码：[test_skin_weights.py](../scripts/rigging/test_skin_weights.py)、[test_service_rig.py](../scripts/rigging/test_service_rig.py)。前者验证区域外保持、独立手指混合、共享点、幂等、错误拒绝和尺度等价；后者在 Blender 合成 GLB/工程，验证单体导出、权重回迁、非骨组/UV/修改器保留、异常检测、修复、保存重开、旧验证入口复用、过期规则与隐藏求值拒绝。产物位于显式的新任务目录，不调用服务。

```bash
"$PYTHON" "$SKILL_DIR/scripts/run.py" test_skin_weights
"$BLENDER" --background --factory-startup --python-exit-code 1 \
  --python "$SKILL_DIR/scripts/run.py" -- test_service_rig --work "$RUN_DIR/service-rig-test"
```


## test_pipeline

代码：[test_pipeline.py](../scripts/rigging/test_pipeline.py)。从合成 GLB 与程序生成 BVH 贯通准备→缓存→导出权重→外部求解→绑定/动画→重开验收；不代表真实人物的视觉验收。

| 函数 | 契约与副作用 |
| --- | --- |
| `write_bvh(path, calibration, frames=5, height=1.8)` | 路径、校准配置、帧数、身高 → 无返回值；写入已知层级和根位移的合成 BVH。 |
| `run_pipeline(root)` | 新空目录 → 完整集成报告；生成合成 GLB/BVH 并调用公开原子功能，读回候选验收。 |


## test_weight_graph

代码：[test_weight_graph.py](../scripts/rigging/test_weight_graph.py)。5 项离线权重回归；覆盖 direct/CG、固定锚点、失败拒绝、缓存指纹及 CLI 往返。

| 函数 | 契约与副作用 |
| --- | --- |
| `fixture()` | 无参数 → 已知分界的长条网格及初始双骨权重，供独立数值回归。 |

测试类 `Tests`：`test_cg_matches_direct_and_preserves_anchors`、`test_unconverged_solve_is_rejected`、`test_invalid_weights_and_faces_are_rejected`、`test_isolated_anchor_and_calibration_fingerprint`、`test_cli_success_failure_and_fingerprints`。行为范围见本节概述；临时状态由测试建立并清理。


## validate_blend

代码：[validate_blend.py](../scripts/rigging/validate_blend.py)。对拓扑不变的三角角色部件检查权重、边/面积变形、共享接缝和掌腕角；输出的通过结论仅限数值标准。

| 函数 | 契约与副作用 |
| --- | --- |
| `parse_frames(value)` | 整帧范围表达式 → 排序去重帧列表；start:end 包含两端。 |
| `validate(collection, rig, frames, height, seam_exclude=())` | 部件集合名、rig、帧列表、身高、可选明确刚性壳体排除 → 变形报告；求值并比较原拓扑长度/面积/权重/共享点/掌腕。 |


## weight_graph

代码：[weight_graph.py](../scripts/rigging/weight_graph.py)。纯 NumPy/SciPy screened-harmonic 权重求解与指纹化 NPZ；刚性锚点精确保持，未收敛不导出有效结果。

| 函数 | 契约与副作用 |
| --- | --- |
| `mesh_digest(vertices, faces)` | 顶点、面数组 → 内容摘要；与原始 dtype 无关，固定使用 float32/int32 缓存协议。 |
| `calibration_digest(profile, height)` | profile、身高 → 骨点/默认骨/权重区域/身高摘要；动作配置不影响该校准指纹。 |
| `solve_weights(v, f, initial, radius, fidelity_length, edge_floor, method='direct', rtol=2e-06, maxiter=1500, diagnostics=None)` | N×3 顶点、M×3 三角面、N×B 权重、模型单位长度及求解参数 → 权重与布尔固定掩码；可更新 diagnostics，拒绝非有限输入与未收敛列。 |
| `solve_archive(input_path, output_path, radius, fidelity_length, edge_floor, method='cg', rtol=2e-06, maxiter=1500)` | 输入 NPZ、新输出路径、模型单位 solver 参数 → 报告；校验摘要/骨顺序，保存权重与 .solver.json，失败只留失败诊断。 |

网格读取与临时资源统一复用物化的 [blender-tools 快照](../../.dependency-blender-tools/references/mesh-snapshot.md)。原坐标、精度、三角面前提与领域拒绝条件由此入口保留。
