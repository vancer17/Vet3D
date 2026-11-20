# 确认用途、姿态和绑定路线

以 Hi3D Agent 1.2.11（Windows x64）为核查基准。`rig-retarget` 将 `pose` 声明为本地「确认姿态与动作」检查点。Agent 对照任务要求与实际模型，确定复用已有绑定、新建绑定或诊断局部缺陷的路线。上层「角色动画」Skill 先选定或取得角色模型，再交接到本节点。 [归档 Skill](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) · [随包架构](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/pcg/architecture.yaml:12>)

## 业务定义

| 项目 | 契约 |
| --- | --- |
| 触发 | 已有定稿模型、绑定工程或可追溯的绑定候选，且本轮要求绑定、蒙皮修复、动作适配或带绑定的资产交付。 |
| 上游与输入 | 当前工作区、确切的角色 GLB 或 `.blend`、目标身体与可用骨架、已有动作或目标动作要求。记录保留的几何、材质、骨架和动作，以及适用的格式、fps、帧段、时长和渲染要求。已有服务结果时保留原始 GLB 和作业引用。 [主模型交接](select-primary-model-and-confirm-handoff.md) · [工作区素材与版本查询](../infrastructure/workspace/query-assets-and-model-versions.md) |
| 图片角色 | 主参考图可用于辨认当前角色及必保外观，附加参考图可辅助核对遮挡部位。检查实际静止网格时按确切模型生成或读取所需正侧视图，方向由相机或观察记录给出，保留项来自本轮要求。引用文字、参考图或已加载画面时，仍从实际网格或工程核实部件、空间与绑定。 [模型视觉证据](../infrastructure/workspace/acquire-model-visual-evidence.md) |
| 输出与完成条件 | 固定源文件、目标角色与对象，确定交付范围和可查证的静止空间，记录已有绑定及动作的检查覆盖范围，并给出具备前提的路线。缺少影响路线的关键证据时，保留已知输入和待查项。 |
| 下游 | 新绑定需准备网格时，先[划定身体与附属部件的绑定域](define-body-and-accessory-binding-domains.md)，再交云端身体导出或本地连续皮肤网格准备。已有绑定候选或已下载的服务 GLB 交[骨架与蒙皮候选核验](review-rig-and-skinning-candidate.md)，已验过的范围随证据沿用。通过后按用途交动作输入与映射或绑定验收，局部缺陷交诊断，未完成作业交原作业续接。最终 LOD 要求交已有派生节点。 [LOD 源与预算](plan-lod-source-and-budgets.md) |

## Skill 绑定

工作区模板提供版本选取、文件位置与保留原件的通用规则。角色形态、T/A 休止姿态、身体及衣物分域和动作适配要求来自选用的领域 Skill。 [工作区模板归档](../upstream/1.2.11/archived-p0/resources/runtime/templates/AGENTS.md#建模路线选择) · [领域 Skill 归档](../upstream/1.2.11/README.md#确定-lod-源网格与分档预算的随包证据)

| 入口 | 选用条件与作用 |
| --- | --- |
| [rig-retarget](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) | 新绑、复用已有绑定或局部修复时选用。按角色实际资产确认用途、姿态、骨架、权重和目标动作。桌面执行按 Runtime 约定交接。 |
| [hi3d-model-gpt-animation（安装包）](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d-model-gpt-animation/SKILL.md:20>) | 需要上层角色动画编排时选用。`source` 解决模型来源，绑定或适配时显式交接 `rig-retarget`。已有工程仅需裁剪、舞台调整等场景可按上层需求继续。 [模型来源](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d-model-gpt-animation/references/model-generation.md:3>) · [宿主交接](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d-model-gpt-animation/references/rigging.md:3>) |
| [mdf-api](../upstream/1.2.11/prebuilt-skills/mdf-api/SKILL.md) | 选定云端自动绑定后，按需查阅公开 `auto-rig` 输入与结果约定。预检、正式调用和下载属于下游。 [桌面绑定交接](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/runtime-service-rig.md) |

## LLM Tools

| 独立工具说明 | 用途、调用时机与条件 | 注册与核查情况 |
| --- | --- | --- |
| [workflow_report](../tools/workflow-report.md) | 选用已安装 Skill 时按宿主指令 `inspect`，保留原架构节点和拓扑上报 `plan` 与 `node`。同一 Skill 的中断任务可用 `resume` 恢复图。 | Runtime 动态工具。安装包的架构投影和状态更新已隔离复核。 |
| [studio_get_state](../tools/studio-get-state.md) | 仅当身份依赖当前画面时读取实际加载版本，核对 `ready`、`assetId` 与 `fileName` 后解析源文件。 | 桌面动态工具。留存会话有普通版本状态与加载记录。 |
| [exec](../tools/exec.md) · [exec_command](../tools/exec-command.md) | 核对文件、计算摘要、读取 GLB 元数据，或通过 Blender 执行 `rig_adapter inspect`。 | Code Mode 和本地执行入口。随包检查命令已在隔离工程实测。 |
| [wait](../tools/wait.md) · [write_stdin](../tools/write-stdin.md) | 检查仍在运行时，分别按原 `cell_id` 或 `session_id` 续取结果。 | 两类句柄对应各自的执行入口，按实际返回值选择。 |
| [view_image](../tools/view-image.md) | 只有已有参考图或对应具体候选、相机和姿态的本地图片时，按路径查看外观证据。 | 本地图片读取工具，按实际取证需要调用。 |
| [user_interaction](../tools/user-interaction.md) | 缺少会改变路线的要求或选择，且已读输入无法确定时，可按宿主契约澄清。 | Runtime 动态工具。`choices_example` 是选项声明，隔离核查未见 `pose` 自动发起面板。 |
| [request_user_input](../tools/request-user-input.md) · [request_user_input_async](../tools/request-user-input-async.md) | 仍缺决定路线的关键业务输入，且当前模式与宿主支持对应工具时，可选其直接函数入口澄清。已有答复沿用当前任务。 | Codex 直接函数工具。前者在 Plan 模式等待结构化答复，后者先回接受结果，实际答复随后进入消息。两份样本仅有声明证据。 |
| [studio_load_revision](../tools/studio-load-revision.md) · [studio_capture_view](../tools/studio-capture-view.md) | 需要查看指定已登记 GLB 或当前画面证据时，按确切版本加载并核对状态，再按需截图。已有可信本地图像时可直接读取。 | 桌面动态工具。截图当前镜头的 `artifactId` 需解析为可信文件引用，版本与方向另行关联。通用模型侧路径解析仍有缺口。 |

`workspace/models` 是宿主 RPC。`rig_adapter inspect` 是 Blender 本地命令，`workflow_report inspect` 是 Runtime 工具动作。PCG 的 `pose` 是业务检查点，MDF 的 `pose` 是接收图片的二维人体关键点能力。后续云端自动绑定使用 `mdf_api` 的 `invoke` 动作和 `auto-rig` 能力枚举。 [模型目录 RPC](../infrastructure/workspace/interfaces/model-catalog-rpc.md) · [MDF 工具说明](../tools/mdf-api.md) · [人体关键点契约](../upstream/1.2.11/prebuilt-skills/mdf-api/references/mesh-invoke-api.md#38-人体关键点pose)

## Hi3D 实现

### 决策

1. **解析用户指代并固定角色。** 明确指定的文件、附件和上游已选候选按实际引用定位。家族「最新版」取该家族最大的数字版本号，指代「当前画面」则先读 Studio 实际加载身份。记录工作区相对路径和文件摘要。已有 `.blend` 可包含多个角色，按对象名确认本轮身体和目标 Armature。仅有照片时，上层 `source` 负责模型生成或选取，取得实际模型后再判断绑定。 [模型版本查询](../infrastructure/workspace/query-assets-and-model-versions.md#执行) · [Studio 快照](../tools/studio-get-state.md#使用视窗快照)
2. **确定用途和保留项。** 区分仅交骨架与蒙皮、适配指定序列、局部修复和游戏资产。按用途确定需保留的源工程、骨架、贴图、动作与部件，以及适用的时间和格式约束。执行者从实际角色确定骨骼语义、身体比例和衣物域。缺少可能改变路线的输入时才澄清。 [Skill 输入要求](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md#独立入口与输入)
3. **从实际文件核对静止姿态与绑定。** 区分当前播放帧与模型 rest pose，确认单位、轴向、世界变换和身体范围。新绑人形查看全身 T/A 休止姿势、手臂与躯干间隙、双腿和手指的实际可分性。衣物、毛发、护甲和道具按语义记录。已有非标准姿态先判断可否校准。已有绑定要核对身体与 Armature 的实际关联、关节头与层级、骨名对应的权重及需要保留的 Action/NLA。GLB 声明可以用于初筛，实际导入与所需形变证据支撑可用性结论。 [几何判据](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/geometry-and-binding.md:5>) · [已有骨架检查](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/existing-rig.md:5>) · [场景导入资源](../resources/p1/asset-scene.md)

| 所见条件 | 路线与交接 |
| --- | --- |
| 当前绑定可用 | 传既有工程、确切骨架和复用依据。要附加动作时交源动作及适配约束。已有动作满足本次要求时按已有验收证据继续。 |
| 已有绑定出现尖刺或跨侧牵拉 | 传复现动作、帧段与缺陷位置。下游先排查骨轴、父子空间、休止姿态和动作。确认需要改轴时交 [标定本地骨架与蒙皮范围](calibrate-local-skeleton-and-skinning-scope.md#决策)，其余问题按实际缺陷决定是否局部修权重。 |
| 未绑定且人形静止身体适合服务 | 优先交身体准备和 `auto-rig`。已有同一资产的可用服务结果时，交原始结果及账本去核验。 |
| 服务不适用或需要控制骨架 | 评估当前模型可校准性，交给本地骨架标定与图权重路线。关键部位因粘连、遮挡或缺失而无法判断时，保留问题与需补的证据。 |
| 既定专用骨架、头部表情或打印关节 | 继续相应专项。游戏目标明确要求最终 LOD 时衔接 LOD；服务代理的预算和最终交付面数分别记录。 |

本地与服务路线由 Skill 指导 Agent 选择。`routes.yaml` 将新绑写为 `pose → rig → retarget → bake`，将已有绑定路线 `fix_skin` 写为 `pose → retarget → bake`。只交绑定时按本轮范围进入绑定验收，随包路线表以包含动作的两个示例路线表达。 [路线与选项声明](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/pcg/routes.yaml:50>) · [输入及专项条件](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/runtime-service-rig.md#身体输入与服务交接)

### 执行

选用绑定 Skill 后，宿主允许从有效 Skill 目录读取 `pcg/architecture.yaml`。Runtime 维护图及节点进度，`pose` 的文件槽声明保留产物。Agent 根据输入证据填写路线或检查记录，并按需上报实际文件引用。安装包隔离投影复现了 5 个节点和 4 条树形父子边，在 `pose` 为 `pending` 时上报 `retarget` 完成仍可以更新图。业务交接应查看实际证据与执行结果。 [架构定义](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/pcg/architecture.yaml:12>) · [宿主编排说明](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-pcg-view/references/host-orchestration.md:3>) · [图的加载和投影](../tools/workflow-report.md#已安装架构的加载范围)

**按已核实契约重建的工具请求示例。** 本轮实际选用该 Skill 时读取图，参数交给 `workflow_report`。

```json
{
  "operation": "inspect",
  "skillName": "rig-retarget"
}
```

**根据随包调用示例改写的 PowerShell 命令。** 已有 `.blend` 时，按其确切骨架对象名运行 `rig_adapter inspect`。将示例路径和对象名换成实际值，报告使用新的路径。

```powershell
$blender = 'D:/install/blender/blender.exe'
$rigSkill = 'D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget'

& $blender --background --factory-startup --python-exit-code 1 `
  --python "$rigSkill/scripts/run.py" -- rig_adapter inspect `
  --input './inputs/character.blend' --rig 'Armature' `
  --report './exports/hi3d-rig-inspect.json'
```

`inspect` 以 `use_scripts=False` 读取工程，按名称选择 Armature，报告包含 `input_sha256`、`rig_sha256`、骨名、父索引、休止矩阵、关节头尾、世界矩阵和场景动作清单。`rig_sha256` 来自骨名顺序、父级及休止矩阵。报告另含对象世界矩阵，恢复时应一并比对工程和场景基准。命令使用新报告路径并复核原件字节，实现的骨骼兼容性校验在后续 `calibrate` 或 `retarget` 执行路径。 [检查脚本](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:281>) · [工程读取](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/blend_common.py:108>) · [适配门槛](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:105>)

需要先盘点多角色工程或骨架对象名称，且已选上层动画包时，可运行 `stage_ops inspect`，取得场景清单后再选定目标骨架。该脚本可覆盖报告，本节点调用方先提供独立的新报告路径并记录输入摘要。已有骨架检查可直接启动 `rig_adapter inspect`；P0 包装器与 P1 场景或网格资源按取证需要另行选用。 [骨架检查合同](../resources/specialized-mesh-scripts.md#rig_adapter-已有骨架检查与调整) · [场景盘点合同](../resources/specialized-mesh-scripts.md#stage_ops-inspect-场景与朝向盘点) · [P0 执行包装](../resources/README.md#专项-blender-命令的执行包装) · [P1 导入与调用](../resources/p1/README.md#rig-retarget-的导入与调用)

**根据随包路线归纳的实现伪代码。** 以下条件来自调用方已经检查的任务和资产证据。返回项用于说明交接去向。

```python
def choose_binding_route(source, task, evidence):
    if source is None or not task.has_essential_requirements:
        return "补齐模型来源或关键任务条件"
    if task.requires_specialized_binding:
        return "专用流程"
    if evidence.existing_rig and evidence.motion_defect_to_diagnose:
        return "诊断已有绑定的变形"
    if evidence.binding_usable_for_task:
        return "复用绑定"
    if evidence.original_service_result_available:
        return "核验原服务候选"
    if evidence.original_service_attempt_unresolved:
        return "移交原作业续接"
    if evidence.humanoid_ta_rest_suitable_for_service and task.allows_service:
        return "准备服务绑定输入"
    if evidence.local_calibration_feasible:
        return "标定本地骨架"
    return "补静止网格与姿态证据"
```

### 验收

源文件和角色身份明确，关键交付条件与对应证据已记录，所选路线具有可执行的下游输入。已有骨架盘点成功只确认对象和结构已读取。是否可复用还要核对身体关联、权重及本次需要的动作。新绑定路线需交付身体对象、衣物与独立部件划分和静止空间依据。图节点可在实际交接后上报完成。 [输入与分域](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/runtime-service-rig.md#身体输入与服务交接) · [绑定与动作验收范围](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/validation.md)

## 完成与恢复

| 当前结果 | 后续处理 |
| --- | --- |
| 输入已确认，检查仍在运行 | 沿原本地句柄续取报告。结束后检查报告可读、对应源摘要和指定骨架。进程句柄不可用时先检查已有报告，再按同一实际工程与对象重新取证。 |
| 缺少必要证据或打开失败 | 保留原文件引用、目标对象、已有报告和失败信息。对象名不匹配时先重查实际场景。旧报告路径已占用时使用新路径。 |
| 有服务作业，提交结果不明或下载未完成 | 保留原 `jobPath`、`outputDir` 和可用的 `requestId`，交下游沿原账本核对。已保存 `SUCCEEDED` 时可用 `download` 恢复原下载。提交不明时保留原尝试并暂停重提。 [MDF 恢复逻辑](../tools/mdf-api.md#实现伪代码) |
| 有候选但未通过检查 | 保留原候选和失败依据。静止空间或对象不符时返回输入准备，已有绑定变形问题交诊断。只有经实际核验的候选可作为下游绑定或动作的输入。 |
| 本轮中断或换源 | 用实际文件与证据恢复，选用该图时可用 `workflow_report resume`。源摘要、角色对象、空间基准或用途改变时重查受影响的条件。 [图续接](../tools/workflow-report.md#实现伪代码) |

## Vet3D 迁移与核查范围

### 供应商无关的交接契约

| 记录 | 下游需要的业务语义 |
| --- | --- |
| 源资产 | 工作区及版本引用、实际文件摘要、角色和身体对象、可选现有骨架或服务产物。 |
| 交付意图 | 仅绑定、动作适配、局部修复或专项交付。附需保留的对象和属性，以及适用的动作、格式和验收范围。 |
| 静止空间与结构 | 朝向、上轴、单位、静止姿态来源、身体和独立部件、可观察关节与待确认区域。已有绑定时附骨架层级、世界变换与绑定证据。 |
| 路线和恢复依据 | 所选路线、支持该路线的观察与报告、尚待后续验证的能力或质量，已有服务作业的原身份与可恢复状态。 |

Vet3D 的 LLM、生图、3D 生成和绑定能力仍待选型。业务层先表达物种、实际部件、休止姿态、必保项及可接受的形变，再由适配器确定参数与可执行路线。Hi3D 的人形 T/A 条件用于解释已核实路线。四足角色的可绑定姿态、四肢与尾部语义以及足部接触需单独建立证据。

### 下游接收检查

准备网格的节点收到同一份已确认网格和明确的身体域。复用或诊断节点能定位原工程、目标骨架和动作证据。特定路线没有足够证据时，保留候选或原作业，待补查后继续。获得新的结果文件后，按其实际摘要重新关联检查。

### 安装包证据、样例与缺口

- **版本与原件。** 1.2.11 安装事务备份的 `rig-retarget/SKILL.md` 与仓库归档逐字节一致。`pcg/routes.yaml` SHA-256 为 `dca6c21980dd904e8fb1b242aa3e941fd8db30fe9ca13036b5c6ea24ff0e6520`，`pcg/architecture.yaml` 为 `3b7779376dd94ad259a393c267cfb7ba8e0d21805715d9704fc62d395fca8d51`，`rig_adapter.py` 为 `7f4bc80f4f268b4ff4b58764355fd5b7387e6e0ed9840186563f3f93cd9f04d7`。图投影和节点状态更新可在 `runtime.mjs` 的零基字节偏移 `3045196`（`Mge`）与 `3072320`（`reportNode`）复核。 [版本清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) · [Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) · [Skill 归档校验](../upstream/1.2.11/README.md#确定-lod-源网格与分档预算的随包证据)
- **离线实测。** Blender 4.5.16 LTS 用随包 `rig_adapter inspect` 读取有对象约束、无网格和无动作的单骨夹具，成功写出骨架盘点，工程摘要一致。指定不存在的骨架时退出码为 1，未生成新报告。测试覆盖对象选择和只读报告边界。图投影实测覆盖本地状态记录及其与业务执行的边界。 [命令与参数](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:389>)
- **样例覆盖。** 留存工作区的三个登记 GLB 只有静态网格，JSON 块均无 `skins`、`animations`、`JOINTS_*` 或 `WEIGHTS_*`。关联会话可复核普通版本登记和 Studio 加载，未观察到该绑定检查点的完整运行。以上样例覆盖部分素材定位路径。 [样例工作区](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40>) · [显式加载记录](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:164>)
- **待实测。** 已登录桌面真实选择绑定 Skill 后的判断与面板轨迹，各类真实角色工程的绑定复用、四足部件可分性和静止姿态判据，以及四足 `auto-rig` 的可用性和实际变形质量。
