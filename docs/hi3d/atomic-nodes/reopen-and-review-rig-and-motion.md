# 重开并验收绑定与动作

以 Hi3D Agent 1.2.11（Windows x64）为核查基准。本节点从实际保存的候选重新取证，核对绑定、保留项和本次要求的动作，再按结构、数值、实际审看及条件性的目标格式分别记录结论。随包实现由 Skill 约定、保存重开、盘点和检查脚本共同组成，没有统一完成全部验收的命令。 [归档 Skill](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) · [随包验收约定](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/validation.md)

保留为一个原子业务节点。已有动作与新烘焙动作是候选来源；仅绑定、非循环、循环和序列是验收范围或模式，二者可以组合。下文拆分内部步骤及条件，不为每种组合建立另一套业务节点。该划分用于 Vet3D 交接，包内 PCG 没有同名独立节点，也不会自动执行本页全部步骤。 [实际架构](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/pcg/architecture.yaml:46>) · [图工具边界](../tools/workflow-report.md#已安装架构的加载范围)

## 业务定义

| 项目 | 契约 |
| --- | --- |
| 触发 | 新绑定、高模权重回迁、局部修复、骨轴校准或动作烘焙已保存候选；已有绑定或指定动作工程也可直接进入。 |
| 上游与输入 | 确切候选 `.blend`、调用前文件摘要、来源工程与生成／修订报告、实际骨架和目标部件、休止空间及单位、必保项。有动作时另交源动作／缓存／映射身份、目标 Action／slot／NLA、fps、要求范围和循环／序列意图。 [候选核验](review-rig-and-skinning-candidate.md#验收) · [本地绑定](solve-local-skin-weights-and-bind.md#验收) · [权重回迁](transfer-skin-weights-to-approved-mesh.md#验收) · [动作烘焙](retarget-and-bake-motion.md#验收) · [局部修复](locate-deformation-and-repair-local-weights.md#验收) |
| 图片角色 | 主图与补充方向图确认角色及必保外观；关节近景、骨架覆盖和动作图来自实际候选，关联摘要、帧号、机位及方向。本地命令接收工程、对象、帧段和高度，图像、目标视向及保留项随取证记录交接，没有主图／参考图 URL 参数槽。 [视觉证据](../infrastructure/workspace/acquire-model-visual-evidence.md) |
| 输出 | 与确切候选配对的结构、属性保护、已验数值、实际审看及条件性回读结论；实际对象、骨架、动作和时间清单；报告、失败帧／部位、残留缺陷及待验项。没有随包统一的验收汇总 JSON，汇总由执行者记录。 |
| 完成条件 | 实际保存文件与本轮证据一致，当前用途所需检查完成。通过、未通过、未要求和待补证分别记录。仅绑定用途不强制制作动作；有动作用途须核对实际动作及要求覆盖。仍缺必要证据时不标为最终通过。 |
| 下游 | 合格的绑定／动作工程交[导出、回读与交付](export-readback-and-deliver.md)，按用途处理原生工程、GLB、LOD 或目标加载器；需 Studio 版本时另按登记契约执行。缺陷交对应修订节点，新候选返回本节点复验。 [格式与游戏交付](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/game-delivery.md#导出后回读) · [版本登记](../infrastructure/workspace/import-or-register-model-version.md) · [实际文件交付](../infrastructure/workspace/preview-and-deliver-files.md) |

## Skill 绑定

通用入口负责工作区、确切文件、原件保护、实际运行环境和产物身份。骨架语义、动作范围、拉伸判据、部件接缝和接触审看来自所选领域 Skill，不是每次普通工作区读取都会自动执行的规则。 [通用工作区规则](../upstream/1.2.11/archived-p0/resources/runtime/templates/AGENTS.md#操作规则)

| 归档入口或安装包参考 | 作用和选用条件 |
| --- | --- |
| [rig-retarget / SKILL.md](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) | 主 Skill。要求保留认可资产、最终重开、核实际动作与检查范围。主要面向 T/A-Pose 人形角色，四足适用性需另验。 |
| [绑定与动作验收](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/validation.md) | 主 Skill 的参考文件；规定不变量、完整非循环范围、循环拼接、数值和视口分层及交付状态。 |
| [游戏角色交付](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/game-delivery.md) | 目标明确涉及 GLB、LOD、游戏挂点或引擎时，补充逐交付件回读、影响数与实际加载器检查。它是参考文件，不是另一份 Skill。 |
| [service-rig.md](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/service-rig.md:79>) · [existing-rig.md](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/existing-rig.md>) · [motion-and-hands.md](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/motion-and-hands.md>) | 按来源选读回迁／局部修复、已有骨架适配及旧 BVH／profile 的时间与循环约定。这些参考尚未纳入当前仓库原文快照，使用固定安装包路径复核。 |
| [hi3d-model-gpt-animation / SKILL.md（安装包）](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d-model-gpt-animation/SKILL.md>) | 仅在实际选用舞台、动作裁剪、布料或次级运动等编排时使用，显式接入独立绑定包。该 Skill 尚未归档为仓库原文；其[最终工程验收参考](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d-model-gpt-animation/references/validation-and-runtime.md>)要求重开最终工程、检查可见高模和条件性缓存，不是默认必经依赖。 |

## LLM Tools

| 独立工具说明 | 本节点调用时机与条件 | 注册与核查范围 |
| --- | --- | --- |
| [exec](../tools/exec.md) · [exec_command](../tools/exec-command.md) | 取摘要、读取工程／报告、启动 Blender 重开检查，或按要求从候选生成取证图。 | 随包 Codex 宿主工具；前序隔离核查执行了随包命令，留存生产会话没有本节点专项执行覆盖。 |
| [wait](../tools/wait.md) · [write_stdin](../tools/write-stdin.md) | 检查未结束时，分别按原 `cell_id` 或 `session_id` 续取同一执行。 | 两种执行层句柄分别处理，不是模型、缓存或云端作业身份。 |
| [view_image](../tools/view-image.md) | 已有来自确切候选的指定姿势、关节近景或对照图时按需读取。 | 返回图像；文件身份、机位和帧号由取证记录绑定。用户不渲染时按 Skill 使用视口及数值证据。 |
| [workflow_report](../tools/workflow-report.md) | 本轮实际选用 Skill 并维护图时，上报文件、报告、检查范围及待验状态。 | Runtime 动态 LLM Tool。归属包内规范图的既有节点，本页业务名称不自动成为可传的 `nodeId`；`completed` 不检查绑定或动作质量。 |
| [user_interaction](../tools/user-interaction.md) | 用途、动作范围或必保项仍有现有任务和素材无法确定的关键歧义时使用。 | Runtime 动态 LLM Tool，已明确的约束直接沿用。 |
| [studio_load_revision](../tools/studio-load-revision.md) · [studio_get_state](../tools/studio-get-state.md) · [studio_capture_view](../tools/studio-capture-view.md) | 仅在已登记的 GLB 需要 Studio 辅助取证时，按确切版本加载、核身份并截图。 | 桌面动态 LLM Tools。不能读取 BLEND 的 Action/NLA、权重和绑定矩阵，截图也不代替动作求值。 |

`service_rig inspect`、`rig_adapter inspect`、`validate_blend` 和 `stage_ops inspect` 是本地命令；`inventory`、`protected_assets`、`check_weights`、`stretch_metrics` 是函数，没有独立同名 LLM Tool。P1 `skin_weights` 被 `service_rig inspect` 和 `validate_blend` 实际调用；`rig_adapter inspect` 仅间接加载该依赖，不执行这些数值函数。P0 启动包装、预算和文件指纹由外层按需采用。模型可见 description 与通用实现由独立工具页维护。 [检查与盘点契约](../resources/specialized-mesh-scripts.md#service_rig-inspect-单身体蒙皮检查) · [P1 数值资源](../resources/p1/skin-weights.md) · [P0 包装](../resources/README.md#专项-blender-命令的执行包装)

正常验收不提交 Hi3D／MDF 生成或绑定请求。来源文件缺失时返回上游按原作业恢复；模型版本登记由[独立登记工具](../tools/workspace-commit-model.md)负责，不能把本节点取得 `pass:true` 当作登记或最终交付已经发生。工具注册、Skill 指导、隔离执行和生产实际调用分别记录。

## Hi3D 实现

### 决策

先按来源核对已有保障，再按用途确定本轮范围。已有证据仅在候选身份、目标、要求范围和检查条件均匹配时复用；文件名或旧报告存在不是复用依据。

| 候选来源 | 上游自动行为 | 本节点接收检查 |
| --- | --- | --- |
| `rig_adapter calibrate/retarget` | 保存前比较保护签名，打包保存后禁用脚本重开，再比较保护签名，取 inventory／摘要并写报告。仍返回 `pose_qa_pending:true`。 | 对账真实输出及保护证据，继续绑定、动作和实际表现验收；该命令没有自动调用数值检查 CLI。 |
| `service_rig bind/repair` | 权重与保护检查后保存工程、摘要及报告。 | 没有自动重开，独立打开保存产物复核。 |
| `build_character`／旧 profile 构建 | 构建绑定、按配置生成动作，保存工程与 manifest。 | 没有自动重开或完整动作数值 QA；manifest 是构建／求解证据。 |
| `stage_ops clip` 等专项编辑 | 使用 `save_candidate`，按配置打包、保存后重开，取清单及文件摘要。 | 共享保存 helper 没有绑定和动作质量验收，继续核实际裁剪、序列和保留项。 |
| 已有绑定或动作工程 | 依原始证据而定。 | 直接从实际保存工程进入，核对旧报告适用性，不强制重建骨架或重新烘焙。 |

[适配器保存重开](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:373>) · [回迁与修复保存](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:443>) · [构建保存](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py:213>) · [专项编辑保存](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d-model-gpt-animation/scripts/character/stage_ops.py:319>)

| 本次用途或模式 | 必须明确的验收范围 |
| --- | --- |
| 仅绑定工程 | 非空目标、实际绑定、有效权重、休止空间、保留项及约定测试姿势；记录动作未要求或未验，不隐含追加动作制作。 |
| 已有或新烘焙的非循环动作 | 实际动作归属、时间和跨帧求值，检查要求范围的全部整数帧，包含端点。 |
| 循环动作 | 完整周期及拼接姿态、根位移与速度；源码不会自动识别循环并给出闭合验收。 |
| NLA 序列 | 实际条带贡献、叠加、缩放、重复和接点；实际动作已烘焙后再按需组织序列，不以场景起止代替条带检查。 |
| 游戏、LOD、布料或舞台等专项 | 只在本次需求包含时补相应目标格式、逐档、接触、缓存及最终可见高模检查，不从身体动作推断次级运动完成。 |

### 执行

| 步骤 | 已核实实现及执行者职责 | 本步验收与恢复门槛 |
| --- | --- | --- |
| 1. 固定实际文件 | 对账候选路径和调用前 SHA-256、上游回执、目标名单、保留项、动作及时间要求。记录来源模型、服务结果、缓存和配置身份。 | 身份或范围不符先回上游核对。源文件与候选分开，检查报告使用独立路径。 |
| 2. 重开并核对结构 | 从磁盘候选打开工程，确认非空目标、真实 Armature 修改器、变形骨组与权重、休止空间、部件和属性。`blend_common.open_input` 以 `use_scripts=False` 载入；`service_rig` 与 `validate_blend` 的载入未显式传此项，启动可加 `--disable-autoexec`。 | 打开成功只证明载入。缺骨架、缺目标、失联贴图或保护项不符时保留候选及诊断，不继续宣告整体通过。 |
| 3. 核对动作和时间 | `inventory` 盘点帧段、有效 fps、各骨架活动 Action／NLA、条带范围／缩放／重复、全部 Action 及图片打包标记。执行者再核非空曲线、slot 与对象归属、NLA 实际贡献和真实跨帧求值。 | 盘点不证明动作有效、循环闭合或实际播放。仅绑定分支记录动作未要求；动作缺失或混入旧序列回动作产物处理。 |
| 4. 执行适用数值检查 | 单身体用 `service_rig inspect`；已准备的三角部件集合用 `validate_blend`。按实际对象、帧段、网格局部高度和拓扑基准运行。 | 前提失败与数值失败分开处理；报告配对到本轮文件、对象和范围。拓扑不对应时先准备适用基准。 |
| 5. 审看完整要求范围 | 按 Skill 检查关节、皮肤接缝、跨侧牵拉、道具、脚底滑动和穿插；循环、NLA、接触及专项按上述条件补查。图片来自最终候选，关联身份和帧号。 | 数值零异常不证明自然度、碰撞或脚锁。抽查记录为抽查；需要时增加半帧／接触切换，不能扩大成连续时间保证。 |
| 6. 汇总并交接 | 分开记录结构保护、已验数值、实际审看和条件目标格式。保留生成报告中的 `pose_qa_pending`，本轮验收另记范围与结论。 | 当前用途必需项通过后交工程或下游导出；未通过项交修订，待补证项继续保留。没有随包自动清除姿势待验标志的实现。 |

[载入函数](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/blend_common.py:108>) · [实际盘点](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/blend_common.py:141>) · [分层验收原文](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/validation.md)

#### 自动重开与保护的边界

`rig_adapter` 的保护快照覆盖当前场景有多边形的 Mesh：基础顶点和角点拓扑、UV、逐面材质分配、材质槽名、shape key 名与坐标、各受保护顶点组的实际成员及权重。对象使用局部变换、父级逆矩阵和父对象／类型／父骨关系比较，允许骨挂道具随动作移动。支持类型的图片按 Generated 像素、Packed 字节或外部 FILE 摘要比较；VIEWER 跳过。比较固定在原 frame／subframe，不是全帧动作 QA。 [保护实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:54>)

签名不完整覆盖材质节点图、任意修改器／驱动、shape key 的 value／slider／驱动、空顶点组目录或零面对象。`blend_common.save_candidate` 虽提供保存、重开和 inventory／摘要，但本身没有资产签名或动作质量检查，也不是所有绑定保存分支的共同入口。 [签名数据](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:90>) · [保存 helper](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/blend_common.py:128>)

#### 具体检查请求

**根据随包 CLI 重建的 PowerShell 请求，非生产调用记录。** 假定候选已有真实绑定和本次需要检查的动作；身体、骨架、帧段与高度为示例。`1:120` 包含端点，`1.8` 与身体网格局部坐标同单位。报告使用新路径，输入和原件不覆盖。

```powershell
$rigSkill = 'D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget'
& 'D:/install/blender/blender.exe' --background --factory-startup --disable-autoexec `
  --python-exit-code 1 `
  --python-expr 'import sys; sys.dont_write_bytecode=True' `
  --python "$rigSkill/scripts/run.py" -- service_rig inspect `
  --input './exports/animated-candidate.blend' `
  --body 'Body' --rig 'CharacterRig' `
  --frames '1:120' --height 1.8 `
  --report './reports/skin-full-range.json'
```

该请求重新打开磁盘文件，不生成动作。`--rig` 可省略，取身体当前 Armature；提供时须与其一致。命令要求实际视口求值，逐帧核对求值顶点形状及三角索引，报告包含网格和绑定摘要、有序骨名、真实骨头位置、权重误差及异常面权重。`pass:false` 在报告写出后抛错，前提异常可能没有新报告。 [CLI 与完整结果](../resources/specialized-mesh-scripts.md#service_rig-inspect-单身体蒙皮检查)

**根据已核实脚本行为与 Skill 要求归纳的实现伪代码。** 下列函数名表达业务职责；不是安装包已有的统一函数、LLM Tool 或硬编码状态机。

```python
def review_saved_candidate(candidate, requirements):
    identity = verify_candidate_and_upstream_evidence(candidate)
    scope = determine_required_objects_actions_and_coverage(requirements)
    reopen_actual_file_without_embedded_scripts(candidate)
    verify_nonempty_targets_actual_binding_and_preserved_assets(scope)

    if scope.requires_motion:
        verify_saved_actions_slots_nla_fps_and_actual_motion(scope)
        frames = required_full_ranges_and_cycle_boundaries(scope)
    else:
        frames = agreed_binding_inspection_poses(scope)

    # 按实际身体／集合选择检查；前提异常时可能没有报告。
    reports = run_applicable_numeric_checks(candidate, scope, frames)
    if any(not report["pass"] for report in reports):
        retain_candidate_reports_and_failure_frames(identity, reports)
        return handoff_to_cause_specific_revision()

    review = review_actual_views_contacts_and_required_boundaries(scope)
    if required_review_failed(review):
        retain_actual_defects_and_route_to_revision(review)
        return record_failed_acceptance()
    if required_evidence_missing(review):
        return record_pending_evidence_without_handoff()
    # 各项结论分别记录，未要求／待补证不当作通过。
    return record_scoped_acceptance_and_handoff(
        identity, scope, reports, preserve_original_generation_reports=True
    )
```

### 验收

| 层次 | 通过条件 | 已核实限制与未通过去向 |
| --- | --- | --- |
| 文件及结构 | 实际重开文件与本轮摘要一致；目标非空、骨架与 Armature 关系正确，休止空间和必保项符合要求。 | 盘点、签名或保存成功不单独证明实际绑定。缺件回来源准备，属性问题回对应修订。 |
| 静态权重 | 实际变形骨名与部位对应，权重有限、非负、逐点归一，无未绑定点；独立衣层与刚性部件按语义核对。 | `check_weights` 的行和绝对容差为 `2e-4`，左右骨列交换且仍归一也可通过。语义异常先定位原因。 |
| 指定数值范围 | 覆盖所有本次要求目标和帧，实际拓扑与单位有效。边长倍率 `>3` 且增长 `>H/120`、双面积倍率 `>8` 且增长 `>H²/81000` 计为异常；集合接缝容差 `H×1e-6`。 | 保留原始最大倍率和失败面，不靠删面、细分或放宽阈值变绿。异常交[形变诊断](locate-deformation-and-repair-local-weights.md#决策)，骨轴／rest／映射问题回[校准](calibrate-bone-axes-and-map-motion.md#完成与恢复)。 |
| 实际动作与审看 | 非循环核完整整数帧；循环核完整周期及拼接姿态／速度；NLA 核实际贡献与接点。关节、接缝、道具和接触按当前用途审看。 | 无动作或恒定姿势不能替代动作用途。映射／序列问题回[动作产物](retarget-and-bake-motion.md#完成与恢复)；接触与衣物问题不自动归为权重错误。 |
| 当前交接可用 | 当前用途必需项通过，交确切工程、实际对象和动作清单、时间、报告及残留／待验项。只需绑定工程时明确动作未要求。 | 后续导出与引擎另验。输出范围改变或文件修订后重核受影响证据，不能静默沿用旧报告。 |

数值工具需要附以下覆盖说明：

- `service_rig inspect` 要求身体、骨架及相应 Armature 修改器可求值，检查顶点和三角索引。`motion_observed` 只表示相对休止网格有偏移，恒定非休止姿势也能为真。恢复原整数帧，不保存原 subframe。
- `validate_blend` 只处理集合直接 Mesh，不递归子集合，没有非空集合门槛，也不检查实际 Armature 连接。只核求值顶点数，未重新核三角索引；接缝按各网格局部坐标的精确重合点比较，不乘世界矩阵。返回文字虽出现 UV，代码没有读取 UV；特定人形腕角仅统计，不参与 `pass` 阈值。报告不含输入摘要或受检对象清单，需外层补充。
- Solidify 或动态拓扑等需要另建适用的求值休止基准，不能套基础索引。完整高模可分块／加速，但须覆盖最终拓扑和实际范围，并先与 Blender 求值对照；安装包未提供统一 GPU 验收器。

[数值检查边界](../resources/specialized-mesh-scripts.md#validate_blend-已保存工程的数值检查) · [P1 函数](../resources/p1/skin-weights.md#参数返回与副作用) · [高模与审看约定](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/validation.md#高模与加速边界)

## 完成与恢复

| 当前状态 | 恢复与交接条件 |
| --- | --- |
| 本地检查 pending／输出截断 | 依原 `cell_id` 或 `session_id` 续取。句柄失效后先查进程、日志和产物；不在原进程仍运行时重复同路径检查。可选计时不提供进程或迭代级恢复。 |
| 上游提交不明或来源缺失 | 保留原作业身份、路径和诊断，回[原任务恢复](submit-and-recover-auto-rig.md#完成与恢复)。`UNKNOWN` 不重提，符合条件的成功作业按原账本补下载。正常验收本身没有云端提交／查询任务。 |
| 保存已完成，但重开、保护核验、摘要或报告失败 | 候选可能已经存在。先核真实文件、摘要、可重开性及对象／动作范围，保留产物为待验；缺证据时另用新报告取证，不重复已经完成的绑定或烘焙。报告缺失不能推断没有候选。 |
| 输入／求值前提异常，没有新报告 | 保留错误，修正对象、可见性、帧段或基准后用新报告路径检查。`service_rig inspect` 拒绝旧报告；`validate_blend` 和 `stage_ops inspect` 可能留下旧报告，不能只读取其 `pass` 或文件存在。 |
| 数值检查完成且不通过 | `service_rig inspect` 和 `validate_blend` 先写失败报告再抛错。保留帧、面、顶点权重及阈值，先排查骨轴、父子空间、rest、映射和动作，再决定局部权重修订。新候选按同范围、动作与阈值复验，并补查受影响部分。 |
| 报告写入失败／与候选不配对 | `service_rig inspect` 在新路径检查后原子写报告，但无并发独占锁；`rig_adapter inspect` 普通写 JSON，可能不完整。`validate_blend`／`stage_ops inspect` 可覆盖报告且未禁止输入同址。外层固定独立路径，并按退出状态、文件摘要、对象和覆盖核对本轮归属。 |
| 数值通过但实际审看失败，或只完成抽查 | 保留各项原结论与实际缺陷，不将抽查扩成全段。局部修复、动作调整或专项接触处理后另存，再验证新文件；必要检查未完成时继续标待补证。 |
| 已满足工程交接要求 | 交候选路径及摘要、骨架／目标对象、Action／slot／NLA、fps／帧段、各层结论、原报告与待验范围。`pose_qa_pending:true` 不回写清除；用本轮独立结论表达当前验收。 |
| 条件性的导出／登记／交付 | 另固定导出对象白名单，排除隐藏服务参考体和骨骼显示辅助体，检查实际输出的 skin、材质、clip、尺寸与时间。各交付 LOD 回读，按目标影响数和实际加载器验收后再声明对应通过。`.blend`／报告是普通工作区文件；GLB 版本登记、Studio 就绪及实际另存按各自契约执行。 |

[报告写入边界](../resources/specialized-mesh-scripts.md#绑定脚本的文件与报告写入) · [游戏导出后回读](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/game-delivery.md#导出后回读) · [版本登记](../tools/workspace-commit-model.md) · [交付状态](../infrastructure/workspace/preview-and-deliver-files.md)

Blender 保体积蒙皮通过不代表目标线性蒙皮、影响数限制或导入器通过。仅 Blender 工程交付不自动增加引擎、LOD、布料或渲染任务。实际选用布料／次级运动时，内嵌缓存后需移开外部缓存重开验证，身体循环也不证明尾巴或布料闭合。 [专项工程验收](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d-model-gpt-animation/references/validation-and-runtime.md>)

## Vet3D 迁移与核查范围

### 供应商无关的交接契约

| 记录 | 业务语义 |
| --- | --- |
| 候选与来源 | 固定实际文件摘要、原件和生成／修订证据；标明来源是回迁、本地构建、已有绑定或动作烘焙。 |
| 目标和保留项 | 明确骨架、受驱动网格、刚性附件、休止空间及单位，逐项规定允许改变的数据。 |
| 用途与验收模式 | 仅绑定或要求动作；动作来源与循环／非循环／序列分开记录。固定 Action、slot、NLA、时间及所需覆盖。 |
| 分层证据 | 保存重开、结构保护、静态权重、指定帧数值、实际审看、条件性目标格式分别关联文件身份和范围。 |
| 结论与恢复 | 通过、未通过、未要求、待补证分开表达；记录失败点、报告来源及受影响范围，修订产生新候选重新验收。 |
| 下游 | 当前用途需要的项通过才交工程或下一阶段；导出、登记、就绪和实际交付分别核对。 |

Vet3D 的 LLM、生图、3D、绑定和动作模型及 API 仍待选型。先定义上述语义，再由供应商适配器执行。可为每次验收建立独占目录、检查前后摘要及逐动作检查清单，按身份与完整条件复用证据；这些是迁移建议，不能写成 Hi3D 已有的硬编码状态机或事务保证。此时仍保留一个节点，不按已有／新动作或循环模式复制节点。

### 安装包证据、样例与缺口

核查日为 2026-11-20，实际资源基准是 `D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime`，manifest 声明 `1.2.11`、`win32/x64`。主安装目录当前缺完整 `resources`，这里引用可复核的事务副本。归档主 Skill 与安装包 SHA-256 一致，参考文件的归档缺口已在上文注明。 [版本 manifest](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) · [归档版本说明](../upstream/1.2.11/README.md#确定-lod-源网格与分档预算的随包证据)

| 安装包来源 | SHA-256 与证明范围 |
| --- | --- |
| [rig-retarget / SKILL.md](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) | `8237ec25a4cf0b06a49723f21c168eee36f5848f64256fd357993d0a2b04f17d`；领域路线、保留及最终重开要求。 |
| [scripts/rigging/blend_common.py](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/blend_common.py>) | `54b0d588c8bfda7cd3640e6c0227a9a88e093b0a287885c5811282444909b9dd`；载入、保存 helper 与盘点。 |
| [scripts/rigging/rig_adapter.py](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py>) | `7f4bc80f4f268b4ff4b58764355fd5b7387e6e0ed9840186563f3f93cd9f04d7`；自动重开和保护边界。 |
| [scripts/rigging/service_rig.py](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py>) | `b1090def180cd66ce35bb0c2f1ec4b2343df93ab039fc6fad7958bd989ffcd76`；保存、独立检查及报告。 |
| [scripts/rigging/validate_blend.py](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/validate_blend.py>) | `e4148c625c13ea9048a065b8c514aa2d4106236aeee7866e03e4af147d41535c`；集合数值及失败落盘。 |
| [scripts/rigging/build_character.py](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py>) | `95cae0d242467669756f53b15ea28eabb01648d6f3b217fd7ad5cc6a7aa6bf53`；保存与 manifest，不含最终重开 QA。 |
| [P1 skin_weights 原件](../resources/p1/skin-weights.md) | `07668c30ed37172c5b0babf053eefc206a3fcc6077ff3ba901aee9b68a1c11e4`；数值判据，与专项物化副本一致。 |
| [hi3d-model-gpt-animation / SKILL.md](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d-model-gpt-animation/SKILL.md>) | `e51c6d060c00f12da2bebb48a63bdac82ddde28d9ffdf86b225b8a8fe6f2e9ac`；仅选用专项编排时的入口。 |

**前序隔离实测。** 使用 Blender 4.5.16 LTS，未改写原包测试，并设置 `sys.dont_write_bytecode=True` 避免在包内生成缓存。未调用生产云端服务，未修改三个用户 GLB。

| 测试与证据 | 实际结果与覆盖 |
| --- | --- |
| [test_service_rig.py](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_service_rig.py:117>) | 两骨、小型两三角夹具完成导出、回迁、错误权重检出、局部修复、保存后重开及非目标保护，退出码 0。 |
| [test_retarget.py](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_retarget.py:226>) | 三帧七骨的小型夹具，16 项检查通过，包含 `saved_reopened`、`protected_assets`、映射、源求值及权重顺序。 |
| 独立新进程重开修复产物 | 重开 `repaired.blend`，指定 `1:2` 两帧数值通过。报告输入摘要为 `48542a58c63b3ef4d191f3eb80d5452acd8426fef1464067d1df409395b60ac4`。 |
| 独立新进程重开动作产物 | 重开 `result.blend`，指定 `10:12` 三帧数值通过。报告输入摘要为 `759a870845d88cba755bbd381285cf4a2b7a2434596882a77d6b69186a00e1dd`。 |
| [test_pipeline.py](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_pipeline.py:117>) | 本次相关核查只静态读取：源码包含保存后显式重开、5 帧集合检查、动作／NLA 和 root 位移断言。没有把它计作本轮新增实测。 |

临时证据为[重定向检查汇总](<C:/Users/11408/AppData/Local/Temp/hi3d-reopen-retarget-03981f32224a42aea9a9e50bd3302301/checks.json>)、[动作产物独立重开报告](<C:/Users/11408/AppData/Local/Temp/hi3d-reopen-retarget-03981f32224a42aea9a9e50bd3302301/independent-inspection.json>)和[修复产物独立重开报告](<C:/Users/11408/AppData/Local/Temp/hi3d-reopen-service-605f66896a924677ae87afb7465d25eb/independent-inspection.json>)。临时目录可能被清理，长期复核使用固定安装包和下列重建命令；样本文件字节摘要不要求重跑逐字节复现。

**根据随包测试入口重建的 PowerShell 复核请求。** 两项 `--work` 都必须指定尚不存在的包外目录，测试自行创建。它们只覆盖各自合成夹具。`test_pipeline` 则另需 `--work-dir` 和与 Blender Python ABI 兼容的 `--python-packages`，这里不隐含安装依赖或执行该测试。

```powershell
$rigSkill = 'D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget'
$launch = @('--background', '--factory-startup', '--disable-autoexec',
            '--python-exit-code', '1',
            '--python-expr', 'import sys; sys.dont_write_bytecode=True',
            '--python', "$rigSkill/scripts/run.py", '--')
$serviceWork = Join-Path ([System.IO.Path]::GetTempPath()) ('hi3d-service-' + [guid]::NewGuid().ToString('N'))
$retargetWork = Join-Path ([System.IO.Path]::GetTempPath()) ('hi3d-retarget-' + [guid]::NewGuid().ToString('N'))
& 'D:/install/blender/blender.exe' @launch test_service_rig --work $serviceWork
& 'D:/install/blender/blender.exe' @launch test_retarget --work $retargetWork
```

**留存样例范围。** [样例工作区](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40>) 的三个登记 GLB 均无 `skins`、`animations`、`JOINTS_*` 或 `WEIGHTS_*`；两份关联会话无本节点专项路径覆盖。它们不宣告覆盖全部工具或分支。 [活跃会话](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl>) · [归档会话](<D:/download/.sparc3d-runtime/environments/prod/codex-home/archived_sessions/rollout-2026-11-11T11-24-05-01a1c8a2-5bab-7df0-8557-d36af12e8411.jsonl>)

**待实测。** 生产绑定候选、真实高模和四足关节语义、跨部件权重、长动作完整范围、循环拼接、连续时间接触／穿插、多衣层、复杂 shape key／驱动／修改器、布料缓存迁移，以及目标格式和加载器表现。离线入口与合成运行只证明上述本地行为及所验范围，不能证明云端输出、任意动作或最终画质。
