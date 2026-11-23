# 求解本地权重并建立绑定

以 Hi3D Agent 1.2.11（Windows x64）为核查基准。`build_character` 对已标定的连续皮肤域生成骨架与初始权重。Blender 内求解和外部 `weight_graph` 共用同一数值实现；缓存回建读取并校验已有权重。构建完成后从实际工程验收绑定候选，收敛回执、构建回执和形变验收分别记录。 [归档 Skill](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) · [安装包求解约定](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/dense-skinning.md:3>)

## 业务定义

| 项目 | 契约 |
| --- | --- |
| 触发 | 本地新建绑定已完成骨架和区域标定，需要在固定的连续皮肤域求解权重；或已有同一网格、骨序、标定和求解意图下的缓存，需继续构建绑定候选。 |
| 上游与输入 | 已通过回读的准备 `.blend`、与骨架一致的休止空间、实际单位与高度 `H`、已标定 profile、变形骨序与皮肤域、可选逐面标签和独立刚性部件映射。复用时附实际缓存、配套收敛报告和求解设置。 [连续网格准备](build-and-review-local-continuous-skin-mesh.md#验收) · [几何标定交接](calibrate-local-skeleton-and-skinning-scope.md#完成与恢复) |
| 图片角色 | 主图和补充方向图用于核对角色及必保外观。绑定后的正侧面、关节近景和指定姿势来自实际候选，关联文件身份和帧号。求解与回建 CLI 使用工程、配置或数组，图像和视向随验收证据交接。 [视觉取证](../infrastructure/workspace/acquire-model-visual-evidence.md) |
| 输出 | 新绑定 `.blend`、配套 `.manifest.json`、实际骨架和拆件清单、输入和候选身份及验收记录。外部路径另保留权重输入 NPZ、权重缓存 NPZ 和 `.solver.json`。 |
| 完成条件与下游 | 核实数值收敛或所用缓存的收敛证据。重开实际候选，确认预期部件非空、权重组与 Armature 关联有效，休止空间、接缝与约定属性通过本节点检查。附上形变验收覆盖范围，交[骨架与蒙皮候选核验](review-rig-and-skinning-candidate.md)，再按用途进入动作适配、姿势／动作验收或导出。动作及引擎尚待核查时在交接中明确状态。 |

## Skill 绑定

通用工作区入口负责文件定位、源文件保护、命令环境和产物身份。连续域如何求权重、拆件和检查由所选领域 Skill 规定。 [通用工作区规则](../upstream/1.2.11/archived-p0/resources/runtime/templates/AGENTS.md#操作规则) · [归档宿主执行约定](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md#宿主执行模式)

| 入口 | 选用条件与作用 |
| --- | --- |
| [rig-retarget](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) | 选定本地新绑、已有最终工作网格和标定配置时使用。按实际连续皮肤域建图，域内先求权重后拆件。 |
| [高面数蒙皮（安装包参考）](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/dense-skinning.md:3>) | 需要高面数原网格、预估 LU 内存压力大或 Blender 缺少兼容 SciPy 时使用外部求解。只有任务允许时才改用代理，使用代理时单独记录实际求解拓扑。 |
| [绑定与动作验收（归档参考）](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/validation.md) | 候选保存后用于实际重开和分层验收。已有可用绑定或只需局部修复时，按 Skill 对应分支选择操作，再决定是否需要新求解。 |

## LLM Tools

| 独立工具说明 | 本节点的调用时机和条件 | 注册与核查 |
| --- | --- | --- |
| [exec](../tools/exec.md) · [exec_command](../tools/exec-command.md) | 读取工程及报告、计算摘要、启动 Blender 或独立 Python。使用 Code Mode 时通过 `exec` 编排实际本地命令。 | Codex 宿主工具。求解调用是随包 CLI。 |
| [wait](../tools/wait.md) · [write_stdin](../tools/write-stdin.md) | 任务未返回时按已取得的 `cell_id` 或 `session_id` 续取同一执行单元或进程。 | 两种续读身份分别来自 Code Mode 和 Unified Exec。 |
| [view_image](../tools/view-image.md) | 有本次候选生成的截图、姿势近景或对照图时按需查看。用户要求不渲染时按 Skill 使用 Blender 视口和数值证据。 | 图像读取工具，截图或渲染由实际工程生成。 |
| [workflow_report](../tools/workflow-report.md) · [user_interaction](../tools/user-interaction.md) | 已有 Skill 工作流图时上报实际阶段与文件。若能否使用代理、能否更改部件等问题仍影响交付而无法从任务确定，再收集用户选择。 | Runtime 动态工具，分别返回图回执或交互结果。 |

`build_character`、`weight_graph` 和 `validate_blend` 由 `run.py` 作本地子命令分派。可选 P0 资源管理后台进程预算与产物摘要，内置求解和回建实际通过随包物化的 P1 `mesh_snapshot` 取基础局部三角网格。PCG 的可选 `rig` 分支指向 MDF，图回执只记录实际处理。留存样例能核实通用工具可见性和部分调用，本节点专项 CLI 由安装包及隔离试验证实。 [构建契约](../resources/specialized-mesh-scripts.md#build_character-权重输入接口) · [外部求解契约](../resources/specialized-mesh-scripts.md#weight_graph-外部权重求解) · [数值检查契约](../resources/specialized-mesh-scripts.md#validate_blend-已保存工程的数值检查) · [P0 包装与预算](../resources/README.md#专项-blender-命令的执行包装) · [P1 实际取点](../resources/p1/mesh-snapshot.md#随包调用证据) · [命令分派](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/run.py:8>) · [安装包 PCG](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/pcg/architecture.yaml:27>)

## Hi3D 实现

### 决策

统一工作表面必须对应可共同变形的区域。衣层、尾部或相贴肢体的几何相接可能连通图中的扩散路径，先根据实际解剖和附件意图区分连续域，再决定是否需要重新准备。固定最终网格、休止坐标和标定配置；求解长度以该网格坐标为准。候选文件保留原始输入用于回退。 [区域与焊接约定](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/geometry-and-binding.md:11>)

| 路径 | 选用条件与执行效果 |
| --- | --- |
| Blender 内求解 | Blender 有 ABI 兼容的 SciPy，且内存适合工作网格时，用未配置 `weights_npz` 的 profile 执行 `build_character --output`。以 `profile.solver` 配置求解，默认 `direct`，也支持 `cg`。三项长度参数在 profile 中是身高比例，构建器乘以 `H`。 |
| 外部 NumPy／SciPy 求解 | 高面数、LU 填充内存压力或 Blender 缺兼容 SciPy 时，先在 Blender 导出初始权重 NPZ，再在独立 Python 调 `weight_graph`。缺省 `cg`，也支持 `direct`。外部三个长度参数直接用网格单位。取到成功缓存后才进入回建。 |
| 缓存回建 | 有与同一输入和求解意图匹配的缓存时，设置 `weights_npz`，从 profile 目录解析缓存路径。构建器复算初始权重以核对缓存。真值引用进入加载分支，文件缺失或不合格时报错，调用方负责重新求解或显式改用内置路径。 |

[路线选择与单位](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/dense-skinning.md:3>) · [构建器分支](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py:24>) · [环境搭配](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/runtime.md:7>)

### 执行

**根据随包 CLI 重建的 PowerShell 示例。** 以 `H=1.8` 和随包长度比例为例。从包外任务目录运行，用新产物路径。Blender 内路线直接对未配置缓存的原 profile 运行 `build_character --output`，按需添加 `--python-packages <兼容目录>`。

```powershell
$runtime = 'D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime'
$entry = "$runtime/prebuilt-skills/rig-retarget/scripts/run.py"
$blender = 'D:/install/blender/blender.exe'
$launch = @('--background', '--factory-startup', '--disable-autoexec',
            '--python-exit-code', '1', '--python', $entry, '--')

& $blender @launch build_character --input 'prepared.blend' --profile 'profile.json' `
  --export-weight-input 'weight-input.npz'

& "$runtime/.runtime-python/python/python.exe" -B $entry weight_graph `
  --input 'weight-input.npz' --output 'weights.npz' --method cg `
  --radius 0.03492 --fidelity-length 0.02502 --edge-floor 0.00003006

# 核对 weights.solver.json 和实际 NPZ 摘要后，在 profile.cached.json
# 保留原标定配置并添加 "weights_npz": "weights.npz"。
& $blender @launch build_character --input 'prepared.blend' --profile 'profile.cached.json' `
  --output 'bound-candidate.blend'
```

1. **生成初始权重。** `build_character` 检查真值 `calibrated`、单 Mesh 和焊接标记，读取 `character_height_m`，用基础局部顶点和三角索引建立骨架与初始配权。变形骨顺序决定权重列。`--export-weight-input` 写入 `vertices`、`faces`、`initial`、`bone_names`、`mesh_sha256`、`calibration_sha256` 后返回。 [准备检查和导出](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py:174>)
2. **求解自由顶点。** 检查有限顶点、三角索引和初始权重，按三角面的唯一无向边建图；边长至少为 `edge_floor`。每点以初始权重最大的骨为占优骨。近似单骨点先作为锚点，已有混合的行保持自由，跨占优骨边界的测地距离小于 `radius` 时也解除固定。边导通为 `1/L²`，保真项为 `1/fidelity_length²`。`direct` 共用一次稀疏 LU，`cg` 逐列用 Jacobi 预条件和初始权重，均按原线性解核查残差。通过后裁负、归一化并精确恢复固定行。 [数组校验与构图](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/weight_graph.py:43>) · [逐列求解](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/weight_graph.py:110>)
3. **取缓存或外部回执。** 外部 CLI 重算输入网格摘要，核对骨名列数，并传递标定摘要。成功先写 `weights/fixed/bone_names/mesh_sha256/calibration_sha256`，计算实际 NPZ 摘要，再写 `.solver.json` 的 `passed:true`。回建会核对当前网格和标定摘要、骨名顺序、形状、有限性、非负、行和以及缓存声明的固定行。它读取 NPZ，不读取 `.solver.json`，也不重算 `fixed` 掩码。 [外部校验与落盘](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/weight_graph.py:179>) · [回建校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py:24>)
4. **拆件和保存绑定。** 根据面心规则或匹配当前网格摘要和面数的 `labels_npz` 拆件。新部件复制逐面材质、材质槽与面角 UV，共享源顶点复制同一权重。`rigid_parts` 把明确的独立刚性壳体覆盖为单骨 100%。权重按 `1/65536` 分配到归一化组，脚本为新部件添加保体积 Armature 修改器并设置骨架父级，移除当前场景中的原工作表面。已有 shape keys、非变形组、原修改器和对象变换需在任务中另行处理。若 profile 有动作配置，构建器可一并创建 Action/NLA；保存 `.blend` 后才写 `.manifest.json`。 [标签核查](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py:71>) · [拆件和蒙皮实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/blender_core.py:107>) · [工程和报告写入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py:213>)

**根据已核实实现重建的伪代码。** 导出、求解和回建可分开运行。报告的状态来自对应阶段。

```python
def build_binding(prepared_blend, profile, export_weight_input, output_blend):
    mesh, height, rig, initial, bone_names = build_rest_inputs(prepared_blend, profile)
    if export_weight_input:
        return write_input_archive(mesh, initial, bone_names, profile, height)

    if profile.get("weights_npz"):
        weights, fixed, diagnostics = read_and_validate_cache(
            mesh, initial, bone_names, profile, height
        )
    else:
        weights, fixed, diagnostics = solve_weight_graph(
            mesh, initial, normalized_solver_lengths(profile, height)
        )

    labels = resolve_face_labels(mesh, profile, height)
    parts = split_and_bind(mesh, rig, weights, labels, profile.get("rigid_parts", {}))
    sequence_configured_actions(rig, profile)
    pack_and_save_candidate(parts, rig, output_blend)
    write_manifest(output_blend, parts, fixed, diagnostics)
```

### 验收

| 层次 | 放行条件 |
| --- | --- |
| 线性求解 | 每个实际求解列的 `info == 0`，解有限，相对残差 `‖Ax−b‖ / max(‖b‖, tiny)` 不超过 `max(5 × rtol, 1e-9)`。报告记录迭代数、退出码与残差。全锚点路径可没有列，需确认符合该域预期。内置诊断在构建成功的 manifest `solver` 中，外部报告须读实际 `.solver.json`，终端 JSON 无 `passed`。 |
| 权重与缓存 | 外部报告显示 `passed:true`，且输入、缓存文件摘要及设置对应本次工作。实际权重有限、非负、行和符合要求，缓存回建使用绝对容差 `1e-7` 并按声明的固定行做精确比对。回建 manifest 中的外部路径、权重文件摘要和标定摘要用于追溯，逐列诊断由原报告提供。 |
| 实际绑定工程 | 独立重开候选，检查实际存在预期部件及非空有效三角表面，Armature 修改器指向预期骨架，顶点有实际变形组权重，共享点和属性符合需求。确认保留项、休止坐标和实际工作模身份。实测单顶点零面夹具能通过导出、外部求解、回建及 `validate_blend` 的数值门槛，得到 `faces:0`、`parts:[]`，须由实际结构检查拒绝。 |
| 姿势与动作 | 对准备过的三角部件集合按实际 `H` 调 `validate_blend`，输入实际候选、报告路径及包含端点的帧范围。默认集合 `CharacterParts`、骨架 `CharacterRig`；名称与高度以实际候选为准。它检查非有限坐标、变形权重、同休止坐标接缝和显著拉伸，拒绝求值顶点数发生变化的网格。变形组行和容差为 `2e-4`，连续皮肤共点的接缝阈值为 `H × 1e-6`。检查完成且 `pass:false` 时先写报告再非零退出。输入或求值提前抛错时可能没有报告。新非循环动作核对全部整数帧，循环核对完整周期及拼接。动态穿插、足底接触和动作自然度须以实际动作和视图验收。 |

[求解判定](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/weight_graph.py:148>) · [回建与 manifest](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py:24>) · [结构与数值检查](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/validate_blend.py:23>) · [验收 CLI](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/validate_blend.py:160>) · [归档验收标准](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/validation.md)

## 完成与恢复

| 情况 | 恢复和交接条件 |
| --- | --- |
| 执行仍在运行、输出截断或句柄失效 | 用原 `cell_id` 或 `session_id` 续取。句柄失效后核对任务目录、实际文件、日志和摘要，保留已落盘证据。求解器未提供迭代级恢复入口，需重跑时从原有效输入和新输出路径开始。 |
| 外部不收敛或缺少配套报告 | `solve_weights` 抛出 `RuntimeError` 时，外部 CLI 尝试保存 `passed:false` 并抛出，失败路径尚未写权重 NPZ。输入、依赖或写入异常可能没有报告。NPZ 写完而报告写失败时保留该文件为待核对产物。复用原输入只在网格、骨序和标定仍匹配时，重算使用新缓存和新报告路径。 |
| 网格、骨序或标定改变 | 有序基础局部顶点或三角索引、骨序、骨规格、默认骨、初始配权区或 `H` 变化时，重导 NPZ 并重算。拓扑或面序变化需同步更新逐面标签。局部网格摘要只覆盖基础坐标与索引，世界变换、材质与 UV 仍按工作网格的实际保留项核查。 |
| 仅求解参数改变 | 可沿用有效的导出输入，但需按新方法、半径、保真长度、边长下限或容差等重新求解并写新缓存引用。求解参数未进入标定摘要，原缓存可能仍能加载。 |
| 分件、落盘或几何验收失败 | 工程先写、manifest 后写，主输出检查也允许覆盖已有同名 manifest。用新工程和报告路径修订，若只涉及标签、刚性映射或材质，且求解域和种子仍一致，可核对并复用已验收的外部缓存。Blender 内求解无独立落盘的权重缓存。数值通过仍出现跨侧拉扯、裂缝或尖刺时，先复查域、截面、初始配权和实际姿势再分支修订。 |
| 绑定候选可交下游 | 交确切 `.blend` 与文件摘要、manifest、骨架和部件清单、休止空间和保留项、不同阶段的验收覆盖，以及有外部求解时的原输入、缓存及收敛报告引用。姿势／动作只核到哪些范围就交哪些证据。需要游戏 GLB 时另做导出和实际加载器复验。 |

[外部失败与落盘顺序](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/weight_graph.py:190>) · [摘要内容](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/weight_graph.py:12>) · [变形失败诊断](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/dense-skinning.md:38>) · [交付边界](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/validation.md#交付状态)

## Vet3D 迁移与核查范围

### 供应商无关的交接契约

| 记录 | 应表达的业务语义 |
| --- | --- |
| 权重输入身份 | 固定连续求解域、休止空间、最终网格、变形骨序、标定版本及初始权重。标签、材质与刚性覆盖分别归属对应版本。 |
| 求解配置和验收 | 记录方法、参数、单位、运行环境、逐列诊断、固定掩码来源、权重摘要与失败状态。使缓存身份覆盖实际求解设置；求解、回建、结构和动态验收各有状态。 |
| 绑定候选 | 关联合格工程、必交部件、骨架及网格版本、权重与形变证据。明确可继续做动作、还需修订或可直接按用途交付。 |

### 安装包证据、样例与缺口

- **安装原件。** 取 `D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime` 的 Windows x64 1.2.11。`weight_graph.py` SHA-256 为 `60136c85a89991342d512ccbff5d5fe2b827567fb5f746eed0ee6cf9a472018f`，`build_character.py` 为 `95cae0d242467669756f53b15ea28eabb01648d6f3b217fd7ad5cc6a7aa6bf53`，`validate_blend.py` 为 `e4148c625c13ea9048a065b8c514aa2d4106236aeee7866e03e4af147d41535c`。 [安装清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json:2>) · [专项脚本原件与哈希](../resources/specialized-mesh-scripts.md#独立复核)
- **隔离实测。** 随包 Python 3.12.14／NumPy 2.5.3／SciPy 1.18.1 重跑 `test_weight_graph` 五项均通过。200 三角面的合成带状网格验证外部 CG 成功、单迭代失败只写失败报告、缓存回建及单帧重开验收、修改骨尾后过期缓存被拒绝。Blender 4.5.16 LTS 临时接入 ABI 兼容的 SciPy 1.15.3 后跑通内置 LU。另复现零面也能通过数值检查的边界，以及回建绕过外部收敛报告的行为。 [数值回归](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_weight_graph.py:31>) · [安装包端到端夹具](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_pipeline.py:91>)
- **样例覆盖。** 三个留存 GLB 无蒙皮和动画，所查两份会话覆盖通用执行及普通建模修订。专项求解签名、落盘、重开和失败短路来自安装代码和隔离实测。 [留存样例](calibrate-local-skeleton-and-skinning-scope.md#安装包证据样例与缺口)
- **四足及生产待实测。** 包内人形种子仅作工程参考。真实四足需验证上游骨架与配权域、紧邻前后肢和独立软层的串权、耳尾附着、重量过渡及拆件接缝、足端接触与大幅屈伸。生产宿主长任务续接、真实高面数 LU／CG 峰值和目标加载器效果也待验证。
