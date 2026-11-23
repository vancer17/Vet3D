# 核对骨架与蒙皮候选

以 Hi3D Agent 1.2.11（Windows x64）为核查基准。这个节点把云端自动绑定、本地求解和已有绑定三类输入汇入同一次候选核验。随包 `rig-retarget` 由 `rig` 或既有绑定向 `retarget` 交接，检查骨轴、休止姿态与实际绑定。本节点的结论用于决定能否回迁、复用、修订或继续补证。 [归档绑定 Skill](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) · [随包架构](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/pcg/architecture.yaml:46>)

## 业务定义

| 项目 | 契约 |
| --- | --- |
| 触发 | 已取得云端 `auto-rig` 的本地 GLB、已经保存本地求解的 `.blend`，或要复用／诊断一个已有绑定。 |
| 上游与输入 | 既定角色、用途、保留项和休止空间。云端交确切 GLB、原账本、提交件和目标高模。本地求解交实际 `.blend`、manifest、配置和求解依据。已有绑定交实际工程或含绑定的模型、目标对象、骨架和已知动作。 [用途与路线](confirm-rigging-purpose-pose-and-route.md#下游接收检查) · [云端取件](submit-and-recover-auto-rig.md#验收) · [本地求解](solve-local-skin-weights-and-bind.md#验收) |
| 图片角色 | 原任务主图用于确认所选角色及必保外观，补充图用于核对其他部位和方向。休止姿态、关节头和形变证据应来自实际候选，绑定文件身份、视向及适用帧号。Blender 命令接收工程、对象和帧范围，图像与保留项随检查记录交接。 [视觉证据](../infrastructure/workspace/acquire-model-visual-evidence.md) |
| 输出 | 确切候选及文件摘要、对应骨架和实际受驱动部件、权重与空间证据、已检查的姿势或帧段，以及可回迁、可复用、待补证或退回修订的结论。 |
| 完成与下游 | 同一份实际候选具备当前用途所需的结构和空间证据。云端结果按需交高模回迁，本地或已有绑定按需交动作输入与映射、局部诊断或仅绑定交付的验收。需动作适配时，固定目标工程及当前 rest 摘要，与已核验源缓存身份汇合后交[校准骨轴与动作映射](calibrate-bone-axes-and-map-motion.md)。交接明确仍待检查的姿势、动作和导出范围。 [后续本地阶段](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/runtime-service-rig.md#后续本地阶段) |

## Skill 绑定

通用入口确认工作区、确切文件及原件保护。骨架语义、休止空间、局部权重与动作范围的规则来自选用的领域 Skill。 [工作区模板](../upstream/1.2.11/archived-p0/resources/runtime/templates/AGENTS.md#操作规则)

| 归档入口 | 选用条件与作用 |
| --- | --- |
| [rig-retarget](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) | 骨架和蒙皮候选核验的主入口。检查实际层级、静止空间、权重和保留项。角色动作、游戏资产等按本次要求追加对应检查。 [绑定与动作验收](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/validation.md) |
| [mdf-api](../upstream/1.2.11/prebuilt-skills/mdf-api/SKILL.md) | 云端候选按原请求和取件记录对账。缺件时按上游恢复契约处理。本地或已有绑定直接从实际文件复核。 [桌面绑定输入与结果](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/runtime-service-rig.md#身体输入与服务交接) |

## LLM Tools

| 独立工具说明 | 用途、调用时机与条件 | 注册与核查情况 |
| --- | --- | --- |
| [exec](../tools/exec.md) · [exec_command](../tools/exec-command.md) | 从实际文件取摘要、读取 GLB，或执行 Blender 的检查命令。 | Code Mode 与本地执行入口。隔离核查运行了随包脚本。 |
| [wait](../tools/wait.md) · [write_stdin](../tools/write-stdin.md) | 本地检查未结束时，按原 `cell_id` 或 `session_id` 续读。 | 依实际返回的执行层句柄选择。 |
| [view_image](../tools/view-image.md) | 已生成与候选身份、相机或帧号对应的图像时按需查看。 | 本地图片读取。形变数据来自实际工程求值。 |
| [workflow_report](../tools/workflow-report.md) | 已选 Skill 并维护工作流图时，把核验和产物按现有节点归属上报。中断续接可读取原图记录。 | Runtime 动态工具。随包架构由 `rig` 向 `retarget` 交接。 |
| [mdf_api](../tools/mdf-api.md) | 云端文件缺失且符合原成功作业的补下载条件时，回提交与恢复节点按原身份执行 `download`。 | Runtime 动态工具。原账本与取件证据在上游核对。 |

`auto-rig` 是 MDF 能力，`invoke` 和 `download` 是动作。`service_rig`、`rig_adapter`、`validate_blend` 是 Blender 本地命令，`skin_table` 和 `check_weights` 是脚本函数。 [MDF 参数与动作](../tools/mdf-api.md#参数与结果) · [单身体蒙皮检查](../resources/specialized-mesh-scripts.md#service_rig-inspect-单身体蒙皮检查) · [部件集合检查](../resources/specialized-mesh-scripts.md#validate_blend-已保存工程的数值检查) · [P1 权重检查](../resources/p1/skin-weights.md)

## Hi3D 实现

### 决策

| 候选路径 | 进入检查前确认的依据 |
| --- | --- |
| 云端自动绑定 | 从原账本和 `downloadIssues` 定位 `files.rigged_mesh`，核对实际路径、GLB 和 SHA-256，再选择服务身体及目标高模。客户端的 GLB 校验覆盖魔数、版本及长度。可选的服务计数与导入结构另行对照。 [原作业取件](submit-and-recover-auto-rig.md#验收) · [下载实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:114>) · [容器校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/hi3d_artifacts.py:26>) |
| 本地求解 | 以已保存的 `.blend` 为候选。对照工作网格、标定、求解和拆件记录。外部求解时核对实际采用缓存及收敛报告。Manifest 的 `mesh_sha256` 对应求解工作网格，另取候选工程文件的 SHA-256。 [求解及回建验收](solve-local-skin-weights-and-bind.md#验收) · [落盘与 manifest](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py:213>) |
| 已有绑定 | 固定资产及实际要使用的身体和 Armature，保留已有动作。`rig_adapter inspect` 按对象名盘点骨名、父级、休止矩阵、关节头尾、世界矩阵和 Action/NLA。后续 `calibrate` 或 `retarget` 才按其适配契约校验约束、驱动和继承等结构。 [已有骨架盘点](../resources/specialized-mesh-scripts.md#rig_adapter-已有骨架检查与调整) · [适配门槛](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:105>) |

### 执行

1. **从实际候选核对蒙皮关系。** 导入 GLB 或重开保存的工程，逐一确认预期网格非空、网格与目标 Armature 实际关联，以及关节索引、层级、关节头和左右语义。显示用骨尾只用于观察，关节位置结合真实头点和矩阵判断。需要保留的材质、贴图、各身体部件及已有动作也从实际文件复核。 [服务结果检查](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/runtime-service-rig.md#身体输入与服务交接) · [骨架与静止空间](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/service-rig.md:37>)
2. **核对数值权重和实际归属。** `service_rig.skin_table` 只收集匹配 `use_deform` 骨名的顶点组。`check_weights` 要求非空浮点矩阵、数值有限且非负、每顶点权重和与 `1` 的绝对误差不超过 `2e-4`。还需按实际部位检查跨侧或跨衣层影响、连续皮肤接缝和应保留的独立刚性部件。求解器的收敛证据随本地路线来，候选仍需要重开核验。 [蒙皮权重读取](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:30>) · [数值契约](../resources/p1/skin-weights.md#参数返回与副作用)
3. **确认休止空间与用途。** 需回迁时，在同一休止空间比较服务身体和目标身体的尺度、方位、轮廓、实际关节及层级，传递已确定的身体和部件名单。已有绑定出现尖刺或跨侧牵拉时，保留原候选和复现帧，先排查骨轴、休止姿态、父子空间和动作映射，再判断是否进入局部权重修复。 [回迁与局部诊断](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/service-rig.md:37>)

#### 回迁硬校验

`service_rig bind` 执行回迁时重新检查入口。目标列表须唯一且包含身体，各对象为未绑定的非空网格。服务导入物须有一个 Armature，且恰有一个网格关联该骨架。所选 Armature 有活动 Action 或 NLA Track 时要求先准备休止姿态。脚本校验服务权重、目标顶点组名冲突和正的有限对齐容差，并比较服务身体和目标身体的世界 AABB 极值。其他目标部件的解剖和衣层对应由调用方确认。通过后该命令继续写权重并另存工程，回执记录 `pose_qa_pending: true`。 [硬校验和回迁](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:180>) · [待验回执](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:277>)

**根据随包实现归纳的回迁入口伪代码。** `source` 和 `body` 的 AABB 都来自基础顶点乘各自的世界变换。语义检查由前面的候选核验提供。

```python
def check_transfer_inputs(imported, body, targets, tolerance):
    require_unique_unbound_meshes_including_body(targets, body)
    require(isfinite(tolerance) and tolerance > 0)
    rig = require_one_armature(imported)
    require(not has_active_action_or_nla_track(rig))
    source = require_one_mesh_linked_to_rig(imported, rig)
    names, weights = read_deform_groups_by_bone_name(source, rig)
    check_weights(weights)
    require_no_target_group_collisions(targets, names)
    delta = abs(world_base_aabb(source) - world_base_aabb(body)).max()
    require(delta <= tolerance)
    return rig, source
```

#### 已有工程的姿势取证

**根据随包示例改写的 PowerShell 请求。** 仅在候选已有实际绑定且需检查已有测试姿势或动作时使用。参数取实际身体名、骨架名、含首尾的帧段和以网格局部单位计的高度。这里的帧段、高度和对象名为示例，报告用新路径。 [单身体检查契约](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/validation.md#数值与视觉)

```powershell
$rigSkill = 'D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget'

& 'D:/install/blender/blender.exe' --background --factory-startup --python-exit-code 1 `
  --python "$rigSkill/scripts/run.py" -- service_rig inspect `
  --input './exports/hi3d-bound-character.blend' --body 'Body' --rig 'CharacterRig' `
  --frames '1:24' --height 1.72 --report './exports/hi3d-skin-inspection.json'
```

`service_rig inspect` 在每个采样帧检查身体、骨架和目标 Armature 修改器是否参与视口求值，并核对求值后的三角索引。`validate_blend` 可对已准备的三角部件集合补充数值与接缝检查，求值时校验顶点数并沿用原三角索引。隔离测试中，空集合和只有同名骨组的未绑定网格均可得到 `validate_blend` 的 `pass: true`。`motion_observed` 只记录采样帧相对休止网格的偏移，恒定的非休止姿势也能置真。动作证据须另查实际绑定、帧段及跨帧变化。 [单身体求值](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:288>) · [部件集合检查](../resources/specialized-mesh-scripts.md#validate_blend-已保存工程的数值检查)

### 验收

| 候选路径 | 通过条件 | 下游 |
| --- | --- | --- |
| 云端自动绑定 | 实际路径和候选摘要与原下载记录一致。核实单个服务 Armature、唯一关联身体、关节结构和有效权重，确认服务结果在休止空间可用。目标身体与回迁部件已确定且未绑定，坐标、尺度、轮廓和身体对应关系具备回迁依据。 | 交原服务 GLB 与摘要、目标工程和对象名单、休止空间及容差依据，进入[权重回迁](transfer-skin-weights-to-approved-mesh.md)。回迁后还要检查实际迁入的权重与姿势。 |
| 本地求解 | 实际工程可重开，求解或缓存依据与该次配置、工作网格和部件对应。预期网格关联正确骨架，权重、接缝与约定保留项通过当前用途检查。 | 交工程、文件摘要、manifest、骨架与部件清单、检查报告及覆盖范围。按本次用途进入动作适配或绑定验收。 |
| 已有绑定 | 确切的身体及所用骨架有实际蒙皮证据，保留的结构与动作符合当前用途。复用旧形变证据前先对账候选、测试范围和条件。 | 可复用时交原工程、目标骨架与动作证据。已有缺陷时交原候选、异常部位和复现帧，进入[局部形变诊断](locate-deformation-and-repair-local-weights.md)。 |

结构通过、已有姿势检查和完整动作通过分别记录。只有明确通过当前交接条件的文件可进入后续执行。后续导出及 Studio 版本登记按各自契约核对。 [交付状态](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/validation.md#交付状态) · [模型版本登记](../tools/workspace-commit-model.md)

## 完成与恢复

| 当前结果 | 恢复或交接 |
| --- | --- |
| 本地检查仍在运行 | 按原执行句柄取回报告。若句柄已结束，先检查实际报告、候选摘要、对象和帧段，再决定是否用新报告路径复验。 |
| 云端成功账本有未入账的缺件 | 保存原 `jobPath`、`outputDir`、可用的 `requestId` 与诊断。已有 `SUCCEEDED` 且原下载描述符可用时，用同一账本和原目录补取，重新核对 `files.rigged_mesh` 和摘要。 [上游恢复](submit-and-recover-auto-rig.md#完成与恢复) |
| 云端文件已入账后丢失或变更，或结果不明 | 下载实现会报告已入账文件异常并跳过该项，摘要里仍可能保留旧路径。保留账本和诊断，核对可信同摘要副本或交服务侧处理。`UNKNOWN`、中断或受理不明时保存原尝试并暂停重提。 |
| 本地候选与 manifest、配置或权重证据不符 | 保留不匹配的文件和检查结果。按原因回到标定、求解或回建，只复用身份与求解条件仍匹配的已验收缓存。工作网格或骨架基准改变时重核受影响的证据。 [本地恢复与缓存](solve-local-skin-weights-and-bind.md#完成与恢复) |
| 已有绑定的对象、环境或动作取证失败 | 在同一工程重新确认对象名、实际 Armature 关系、求值可见性与帧段。若已定位局部缺陷，附原工程与异常帧进入诊断。保留本轮检查覆盖，等待缺失证据后再交使用。 |
| 取得候选但休止空间、解剖对应或形变未通过 | 保留原件、具体部位、帧和失败依据。空间不符退输入准备或校准，数值权重和绑定关系问题退候选生成或局部修复，动作映射异常退动作适配。新候选按实际摘要复验。 [回迁和修复说明](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/service-rig.md:37>) |

## Vet3D 迁移与核查范围

### 供应商无关的交接契约

| 记录 | 业务语义 |
| --- | --- |
| 候选身份与来源 | 主体、候选文件与字节摘要，原项目、配置／求解证据，或云端原作业与实际下载记录。 |
| 骨架与目标网格 | 确切骨架和受驱动网格列表、休止空间和单位、关节层级与侧别、权重证据、保留属性。 |
| 证据类型与覆盖范围 | 区分资产文件、工作网格、骨架与绑定矩阵的摘要。分别记录实际结构、静态权重、指定姿势、实际动作和目标格式回读的检查范围。 |
| 结论与交接 | 可回迁、可复用、需诊断或待补证。交相应对象、原始证据及仍需验收的条件。 |

Hi3D 中 `rig_adapter` 的 `rig_sha256` 覆盖骨名、父索引和骨架局部休止矩阵。`service_rig` 同名字段还按身体网格局部空间表达绑定矩阵，并纳入骨名、父骨名和 `use_deform`。记录时附算法及坐标空间。Vet3D 的 LLM、3D 生成与绑定模型仍待选型，候选结果按上述业务语义对账。四足关节对应、部件隔离和步态检查阈值需用真实资产建立依据。 [骨架摘要](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:44>) · [绑定摘要](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:44>)

### 安装包证据、样例与缺口

- **安装包与归档。** 核查基于 `D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime` 的 Windows x64 1.2.11。`service_rig.py` SHA-256 为 `b1090def180cd66ce35bb0c2f1ec4b2343df93ab039fc6fad7958bd989ffcd76`，`rig_adapter.py` 为 `7f4bc80f4f268b4ff4b58764355fd5b7387e6e0ed9840186563f3f93cd9f04d7`，`validate_blend.py` 为 `e4148c625c13ea9048a065b8c514aa2d4106236aeee7866e03e4af147d41535c`。`skin_weights.py` 与 P1 原件逐字节一致。 [版本清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) · [专项原件与摘要](../resources/specialized-mesh-scripts.md#独立复核) · [Skill 归档](../upstream/1.2.11/README.md#确定-lod-源网格与分档预算的随包证据) · [P1 权重原件](../resources/p1/skin-weights.md#依赖权限与前置-hook)
- **合成实测。** Blender 4.5.16 LTS 使用随包 `test_service_rig` 通过导出、回迁、局部修复和重开检查。隔离负例确认服务身体平移超容差、零权重顶点和附动作的服务 Armature 会被拒绝。左右权重对调且仍归一的候选通过了 `bind_result`，产物保留错误权重并处于姿势待验。集合检查及 `motion_observed` 的边界见上文。 [随包夹具](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_service_rig.py:14>)
- **样例覆盖。** 留存的三个登记 GLB 均无 `skins`、`animations`、`JOINTS_*` 或 `WEIGHTS_*`。两份关联会话的工具调用未见候选绑定核验，样例提供三份未绑定资产的结构证据。 [样例工作区](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40>) · [活跃会话](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl>) · [归档会话](<D:/download/.sparc3d-runtime/environments/prod/codex-home/archived_sessions/rollout-2026-11-11T11-24-05-01a1c8a2-5bab-7df0-8557-d36af12e8411.jsonl>)
- **待实测。** 已登录桌面中的生产 `auto-rig` 结果、同作业线上补下载、真实四足关节语义、跨部件权重和实际步态，以及回迁与导出后在目标加载器中的表现。
