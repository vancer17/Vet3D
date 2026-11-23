# 标定本地骨架与蒙皮范围

以 Hi3D Agent 1.2.11（Windows x64）为核查基准。新建骨架时，执行者在最终工作网格上标定骨点、骨轴与初始配权，再交 `build_character`。已有骨架确需调整轴向时，`rig_adapter calibrate` 按现场骨架摘要核对并修订骨尾与滚转。两条路线的配置、完成条件和下游各有独立契约。 [归档 Skill](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) · [新骨架配置](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/geometry-and-binding.md:17>) · [已有骨架轴向调整](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/existing-rig.md:5>)

## 业务定义

| 项目 | 契约 |
| --- | --- |
| 触发 | 已选本地新绑定且连续皮肤网格准备完成，或已有绑定经检查确认需要修正骨尾与轴向。可直接复用的已有绑定按用途交动作适配或交付。 [上游路线](confirm-rigging-purpose-pose-and-route.md#决策) |
| 新建输入 | 已验收的 `prepared.blend` 与准备报告、源及工作网格身份、休止空间、单位和前向、可共同求解的连续皮肤域、独立软层和刚性部件清单。 [网格准备](build-and-review-local-continuous-skin-mesh.md#验收) · [上游分域](define-body-and-accessory-binding-domains.md) |
| 已有骨架输入 | 原绑定工程、目标 Armature 对象名、实际骨架检查报告、须保留的网格和权重，以及是否要重烘目标动作。已有动作且本次须保留时，先复核是否可沿原休止骨架适配。 |
| 图片角色 | 主图和补充方向图可核对角色、左右和必保外观。以工作工程的正面、侧面、关节截面及局部坐标确定骨点与区域。主图、补图、目标视向和保留项随取证记录交接，两条本地 CLI 都用工程或配置文件作输入。 [视觉取证](../infrastructure/workspace/acquire-model-visual-evidence.md) |
| 输出与完成条件 | 新建路线交几何核对通过的标定 JSON、对应网格、域、部件与证据，按下游需要附初始权重 NPZ。调整路线交重开通过的候选 BLEND、原／新骨架摘要和调整报告，并记录姿势验收状态。 |
| 下游 | 新建路线交 [求解本地权重并建立绑定](solve-local-skin-weights-and-bind.md)，完成图权重求解和分件后，再按任务验收形变。已有骨架路线按新休止空间更新映射并进入动作重烘或姿势核对。源文件、原权重及原动作身份随任务保留。 |

## Skill 绑定

通用桌面入口负责工作区定位、文件身份、原件保护与宿主执行约定。骨点定位、配权区、已有骨架调整和动作保护按所选领域 Skill 执行。 [归档工作区规则](../upstream/1.2.11/archived-p0/resources/runtime/templates/AGENTS.md#操作规则) · [归档宿主执行约定](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md#宿主执行模式)

| 入口 | 选用条件与作用 |
| --- | --- |
| [rig-retarget](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) | 本地新绑、已有骨架动作适配或局部修复时选用。新绑按实际角色标定骨架、范围及接触点，已有骨架先检查再决定是否修改。 |
| [几何与绑定（安装包参考）](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/geometry-and-binding.md:17>) · [高面数蒙皮（安装包参考）](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/dense-skinning.md:3>) | 新建本地配置时读骨点、滚转、区域和分件规则。高面数、稀疏求解内存压力或 Blender 缺兼容 SciPy 时，进一步采用外部求解交接。 |
| [已有骨架与序列适配（安装包参考）](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/existing-rig.md:5>) · [绑定与动作验收（归档参考）](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/validation.md) | 确定复用现有骨架时读检查、轴向调整和映射契约。已有骨架修改及后续新绑定或动作候选均按实际交付范围验收。 |

## LLM Tools

| 独立工具说明 | 本节点的用途和调用条件 | 注册与核查 |
| --- | --- | --- |
| [exec](../tools/exec.md) · [exec_command](../tools/exec-command.md) | 读固定工程与报告，运行 Python 种子生成、Blender 后台检查和构建。 | Code Mode 和本地进程入口。专项动作由随包 Python CLI 派发。 |
| [wait](../tools/wait.md) · [write_stdin](../tools/write-stdin.md) | 收到执行单元或本地进程句柄且仍在运行时，分别用原 `cell_id` 或 `session_id` 续取。 | 分别对应 Code Mode 和 Unified Exec。 |
| [view_image](../tools/view-image.md) | 已从确切工程制备正侧视图或局部截面时按需读图。用户要求不渲染时采用 Blender 视口与数值检查。 | 图像读取入口；视图和截面由实际工程生成。 |
| [workflow_report](../tools/workflow-report.md) · [user_interaction](../tools/user-interaction.md) | 使用已安装 Skill 的工作流图时上报已有阶段与实际文件。任务用途、保留既有动作等关键要求无法从输入确定时才澄清。 | Runtime 动态工具。标定标记由执行者记录检查结论。 |

`make_profile`、`build_character` 和 `rig_adapter` 是 `scripts/run.py` 的本地子命令，`inspect`／`calibrate` 属于 `rig_adapter` 自身操作。`weight_graph` 在下游求解时才运行。随包 PCG 的 `rig` 是可选 `mdf-call` 分支，`retarget` 描述已有／服务骨架的动作适配。本节点的本地步骤来自 Skill 与脚本。所查会话有通用工具调用，专项调用的证据来自安装原件和隔离试验。 [种子契约](../resources/specialized-mesh-scripts.md#make_profile-人形比例种子) · [构建契约](../resources/specialized-mesh-scripts.md#build_character-权重输入接口) · [已有骨架适配契约](../resources/specialized-mesh-scripts.md#rig_adapter-已有骨架检查与调整) · [命令分派](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/run.py:8>) · [PCG 定义](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/pcg/architecture.yaml:27>)

## Hi3D 实现

### 决策

1. **新建骨架时先固定工作表面。** `prepare_mesh` 将基础坐标的 XY 包围盒中心和最低 Z 作为归一化基准；前向按实际工程及上游转向记录核对，随包准备 CLI 的目标前向约定为 `-Y`。标定使用最终基础局部三角网格和网格上的 `character_height_m`（记为 `H`）。先确认该局部空间与实际父级、世界变换及独立部件相容。视图不清时补截面。肢体粘连或独立层并入时回到准备步骤。 [归一化与转向](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/prepare_mesh.py:12>) · [转向参数](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/prepare_mesh.py:138>)
2. **已有骨架先判断是否确需改轴。** `inspect` 按对象名选择 Armature，输出骨名、父级、休止矩阵、头尾、世界矩阵与工程清单。由真实关节头和层级建立解剖对应。导入器显示骨尾与预期不同、但实际动作正确时可保留；确认会影响目标屈曲或掌轴时才制作调整配置。目标存在约束、驱动、父对象、共享骨架数据或非常规 FK 继承时，需专门适配。两条脚本路线的继承约定不同，`create_rig` 将 `inherit_scale` 设为 `NONE`，当前 `rig_adapter` 要求 `FULL`。 [检查与目标校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:105>) · [新骨架继承设置](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/blender_core.py:41>)

### 执行

**根据随包 CLI 重建的新建路线示例。** 第一条命令用标准库 Python 生成含 15 根骨的人形 T-pose 种子，标记为 `calibrated: false`，输入只有新输出路径。将种子另存为 `profile.json`，按最终网格完成几何标定，再执行 Blender 命令。 [种子与 CLI](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/make_profile.py:111>)

```powershell
$skill = 'D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget'
python "$skill/scripts/run.py" make_profile --output 'profile.seed.json'

# 在实际工程上标定，复核后另存 profile.json。
& 'D:/install/blender/blender.exe' --background --factory-startup `
  --disable-autoexec --python-exit-code 1 --python "$skill/scripts/run.py" `
  -- build_character --input 'prepared.blend' --profile 'profile.json' `
  --export-weight-input 'weight-input.npz'
```

| 配置 | 如何标定与执行 |
| --- | --- |
| `bones` | 对照正面、侧面及截面确定实际关节中心、父子链及屈曲平面。相邻肢段共用已确认的铰接点，`roll_axis` 随实际弯曲平面或掌面标定。`head`／`tail` 以 `H` 的比例记，构建器乘以 `H`，按父骨在前的顺序创建，拒绝长度小于 `H × 1e-5` 的骨段。以实际变形骨顺序作权重列。 |
| `default_bone`、`weight_regions` | 用明确的默认骨和有序区域规划种子。同一连续域中，顶点坐标除以 `H` 后按包含上下界的 `bounds` 命中。单骨区给该骨 100%，多骨区沿 `axis × sign` 作平滑过渡，`N` 根骨对应 `N−1` 组非递减中心和正半宽。后命中区域覆盖前者。可按肢体用途选择刚性中段或柔性脊柱。 |
| `part_rules`、`labels_npz`、`rigid_parts` | 默认及简单分件按面心逐条赋标签。复杂边界按材质、连通分量和视图建立逐面 `labels`，连同最终网格的 `mesh_sha256` 保存。完整构建时可从相对 profile 目录的 `labels_npz` 覆盖面标签，脚本核对摘要和面数。域内先求权重再拆件，`rigid_parts` 将指定部件覆盖为对应变形骨 100%；需隔断的独立软层在求解前分域。 |

[建骨与初始权重](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/blender_core.py:22>) · [面标签读取](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py:71>) · [拆件与刚性映射](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/blender_core.py:107>)

**根据随包 CLI 重建的已有骨架路线示例。** 沿用上例 `$skill`。先取得 `rig.json`，填入其 `rig_sha256`，按实际骨名在骨架休止空间给每项 `tail` 或引用另一关节头的 `tail_at`，并给 `roll_axis`。确认后将布尔 `calibrated` 置为 `true`。若目标 rig 已有活动 Action 或 NLA 轨道，默认拒绝。明确替换目标动作时才传 `--replace-animation`，候选中清除目标 rig 的旧动作引用，后续按新 rest 重烘。 [已有骨架配置](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/existing-rig.md:15>) · [轴向校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:142>)

```powershell
$blender = 'D:/install/blender/blender.exe'
& $blender --background --factory-startup --disable-autoexec --python-exit-code 1 `
  --python "$skill/scripts/run.py" -- rig_adapter inspect `
  --input 'bound.blend' --rig 'CharacterRig' --report 'rig.json'

# 按 rig.json 的现场摘要、骨名和休止空间另存 axis-spec.json。
& $blender --background --factory-startup --disable-autoexec --python-exit-code 1 `
  --python "$skill/scripts/run.py" -- rig_adapter calibrate `
  --input 'bound.blend' --rig 'CharacterRig' --spec 'axis-spec.json' `
  --output 'axis-candidate.blend' --report 'axis-report.json'
```

**根据源码重建的实现伪代码。** 新建构建器与已有骨架适配器对标记和资产身份使用不同的检查。完整构建和仅导出输入为二选一，已有骨架调整需要独立新工程和报告路径。

```python
def build_new(prepared, profile, destination, export_weight_input):
    require_new_path(destination)
    if not profile.get("calibrated"):
        raise ValueError("Fit and inspect the profile")
    surface = open_single_weld_marked_mesh(prepared)
    height, vertices, triangles = read_base_local_triangles(surface)
    rig = create_rig(profile["bones"], height)
    names = deform_bone_names(rig)
    initial = initial_weights(vertices, names, profile, height)
    if export_weight_input:
        return write_weight_input(destination, vertices, triangles, initial, names,
                                  mesh_digest(vertices, triangles),
                                  calibration_digest(profile, height))
    weights = resolve_weights(vertices, triangles, names, initial, profile, height)
    labels = resolve_labels(vertices, triangles, profile, height)
    return build_and_save_candidate(surface, rig, weights, labels, profile, destination)


def adjust_existing(source, spec, rig_name, destination, report_path, replace_animation):
    require_distinct_new_paths(destination, report_path, source)
    rig = open_and_select_armature(source, rig_name)
    protected, frame = snapshot_protected_assets()
    validate_target(rig, replace_animation)
    if spec.get("calibrated") is not True or spec.get("rig_sha256") != skeleton_digest(rig):
        raise ValueError("Calibration must match the inspected skeleton fingerprint")
    changes = apply_validated_tail_and_roll(rig, spec["bones"], replace_animation)
    require_joint_heads_preserved(changes)
    require_protected_assets_preserved(protected, frame)
    save_pack_and_reopen(destination)
    require_protected_assets_preserved(protected, frame)
    return write_report(report_path, changes, destination, pose_qa_pending=True)
```

### 验收

| 层次 | 放行与限制 |
| --- | --- |
| 标记与管线检查 | `calibrated: true` 表达执行者已完成几何核对。`build_character` 实际只查真值，再检查单 Mesh、焊接标记、身高属性、基础三角面以及建骨和配权时命中的规则。非布尔真值可绕过标记检查，空区域可跳过过渡检查。`rig_adapter calibrate` 严格要求布尔 `true`、匹配的骨架摘要及明确的修改项；尾点与滚转轴须有限，尾段须非退化，滚转轴须不平行。 |
| 新建几何 | 在实际工作工程核对骨点是否落在关节截面、左右及父子链、骨轴、有限尺度、区域覆盖和过渡带。检查独立层、对侧肢体和错误落回默认骨的点。NPZ 可核对初始权重、骨名顺序和两个摘要，逐面标签、刚性映射、权重收敛与动作质量需各自复核。必要时用 [P1 场景载入](../resources/p1/asset-scene.md) 或 [网格快照](../resources/p1/mesh-snapshot.md) 取证。 |
| 已有骨架候选 | `rig_sha256` 覆盖骨名、父级与 rest 矩阵。脚本报告实际改动骨及改动前后摘要，在容差内核对关节头。仅沿原方向延长骨尾时摘要实测可保持一致，验收需对照实际头尾、滚转和候选文件 SHA-256。脚本在保存前和重开后对照同一帧的受保护资产。检查覆盖网格、UV、形态键、权重组、材质槽及逐面分配、图像内容和附属件局部关系。报告写 `pose_qa_pending: true`，实际屈曲方向、变形与须重烘的动作保留到后续验收。 |

[新建检查及 NPZ 早返回](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py:174>) · [原骨架摘要与保护范围](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:44>) · [保存、重开与报告](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:373>)

## 完成与恢复

| 当前情况 | 恢复或交接 |
| --- | --- |
| 本地执行仍运行，或只有部分产物 | 按原 `cell_id` 或 `session_id` 续取。句柄失效时，对照原命令、源摘要和实际路径。已有骨架调整先保存工程，重开检查后才写报告。只落盘工程时保留它与诊断，重新核对实际内容；重跑用新工程和报告路径。 |
| 配置可读取但几何验收失败 | 保留源、失败候选、证据和配置。骨点或配权区有误时修订标定再导出；拓扑、空间或分域有误时返回网格准备。已有骨架摘要不符时从实际目标重做 `inspect`，按当前休止空间复核编辑。 |
| 新建标定可交求解 | 固定准备工程、语义域与逐面标签、标定配置及验收记录。完整构建可在具备兼容 SciPy 的 Blender 环境求解。高面数或缺兼容 SciPy 时，用 `--export-weight-input` 交顶点、面、初始权重、骨序及双摘要，再用外部 NumPy/SciPy 求解，用 `weights_npz` 提供相对 profile 目录的缓存路径，再回建。外部 CLI 的三个长度参数使用模型单位，要将 profile 比例乘 `H`。 |
| 权重输入、标签或缓存需要重算 | 实际基础局部顶点、三角索引、顺序或 `H` 改变时重新核对休止空间和标定，重导求解输入。改变骨规格、默认骨或初始配权区也须重导并重算。面标签以实际网格摘要及面数为准，面顺序改变时重新生成。只变求解方法、半径、容差等参数时重算并更新缓存路径，已有 `weights_npz` 会优先加载。只变标签或刚性映射时重新验证分件和候选，若同时改变求解域则重建网格和权重输入。 |
| 已有骨架调整可交动作 | 用重开后的候选及新骨架摘要更新目标映射。休止骨架改变时，按新基准校验动作映射与缓存归属；按已定范围重烘目标动作并实际验收，沿用经过保护核对的原网格和权重。 |

`mesh_sha256` 对有序基础局部顶点与三角索引计算，`calibration_sha256` 覆盖 `bones`、`default_bone`、`weight_regions` 和 `H`。材质、世界变换、面标签、刚性映射、动作和求解参数需要单独追溯。读取缓存还会校验骨名顺序、形状、有限非负值、行归一化和声明的固定锚点。 [摘要实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/weight_graph.py:12>) · [缓存校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py:24>) · [外部求解约定](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/dense-skinning.md:15>)

## Vet3D 迁移与核查范围

### 供应商无关的交接契约

- **身份和用途。** 保存最终网格与坐标基准、物种和形态、独立部件、绑骨用途及必保动作。已有骨架修改保存确切目标、休止摘要、允许改动的轴向及保护项。
- **几何验收与执行状态。** 保存关节定位依据、骨轴、区域覆盖、逐面标签及评审结果。配置拟定、几何复核、管线可执行和动作通过分别记录。缓存关联实际网格、骨序、标定版本和求解配置。
- **四足配置。** 以实际猫狗的休止网格定义前后肢关节、肩胛和骨盆、躯干与颈、足端及耳尾和软层的归属。底层配置和求解交接可作为工程参考。随包人形种子及动作例程使用人形关节语义，四足的标志点和动作映射需独立实现和核验。 [人形种子](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/make_profile.py:8>) · [人形动作链](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/motion.py:110>)

### 安装包证据、样例与缺口

- **固定版本。** 以 `D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime` 的 Windows x64 1.2.11 物化包为原件。归档与安装包的 `rig-retarget/SKILL.md` SHA-256 同为 `8237ec25a4cf0b06a49723f21c168eee36f5848f64256fd357993d0a2b04f17d`。`rig_adapter.py` SHA-256 为 `7f4bc80f4f268b4ff4b58764355fd5b7387e6e0ed9840186563f3f93cd9f04d7`。种子、构建和求解的安装包路径及哈希见专项资源页。 [安装清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json:2>) · [已有骨架脚本](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py>) · [专项脚本哈希](../resources/specialized-mesh-scripts.md#独立复核)
- **新建路线隔离实测。** Blender 4.5.16 LTS 中，真实随包 CLI 拒绝未标定种子和命中有误过渡的配置，却接受字符串 `"false"` 及空盒中的无效过渡。合成顶点复核顺序覆盖及中点 50/50。输入工程摘要保持一致。上游另有外部 CG 与重建的合成核查，旧标定权重缓存已测拒绝。 [随包构建入口](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py:174>) · [上游求解核查](build-and-review-local-continuous-skin-mesh.md#安装包证据样例与缺口)
- **已有骨架路线隔离实测。** 随包 CLI 拒绝数值 `1` 标记、不匹配的骨架摘要、默认情况下的活动动画和 `inherit_scale: "NONE"`。用 `tail_at` 修订后重开工程，确认关节头、权重、非变形组和 UV 保持，源文件 SHA-256 一致，候选 SHA-256 与报告一致，`pose_qa_pending` 为 `true`。验证了仅延长同方向骨尾时摘要可保持一致，以及显式替换动作只清除目标 rig 的引用。测试使用合成 FK 夹具。 [校验与证据字段](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:142>) · [重开与保存记录](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:373>)
- **样例覆盖。** 三个登记 GLB 均为静态模型，后两版有独立左右胡须。所查两份留存会话覆盖普通修订与通用执行，本节点专项标定和权重构建由包内原件及合成例核查。 [样例与会话证据](build-and-review-local-continuous-skin-mesh.md#安装包证据样例与缺口)
- **待实测。** 生产宿主中分支调度和长任务恢复，真实四足的关节定位与轴向、前后肢相贴时的作用范围、耳尾和独立软层跟随、复杂附件、关节大幅屈伸、足底接触及高面数求解资源消耗。所查本地入口未见随包四足自动标定。
