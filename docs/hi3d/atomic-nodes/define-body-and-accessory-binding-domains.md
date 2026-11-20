# 划定身体与附属部件的绑定域

以 Hi3D Agent 1.2.11（Windows x64）为核查基准。Agent 在确认的休止空间中，按部件的预期运动和实际表面边界确定绑定域。分域结果决定哪些网格可共同准备或求权重，哪些对象需独立回迁、随骨或挂接。随包脚本消费明确的对象、配置和面标签。 [绑定 Skill](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) · [安装包分域规则](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/geometry-and-binding.md:11>)

## 业务定义

| 项目 | 契约 |
| --- | --- |
| 触发 | 已确定用途、休止姿态和绑定路线，需要准备新绑定输入，或已有工程需要按原休止空间替换网格。已有绑定及部件已满足本次任务时沿用原结果。 |
| 上游与输入 | 确切的源和工作副本、角色对象、文件摘要、休止姿态、轴向、单位、必须保留的部件及实际运动要求。换网格时附原骨架和已有部件约束。 [上一节点](confirm-rigging-purpose-pose-and-route.md) · [换网格规则](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/mesh-lod.md#准备与替换网格) |
| 图片角色 | 有身份对应的主图用于辨认角色和必保外观。补充视图用于核对正侧背轮廓、附着位置或遮挡。实际网格的固定视图、近景与截面用于判断边界，分别记下模型版本、方向和观察依据。 [视觉取证](../infrastructure/workspace/acquire-model-visual-evidence.md) |
| 输出与完成条件 | 为影响下游的部件确认实际对象或表面范围、连续性、预期运动及归属。确定身体提交名单、软部件目标、随骨部件或独立道具，或定义可共同准备的本地网格范围。关键边界仍无依据时，保留已确认部分和待查区域。 |
| 下游 | 云端路线交身体对象、原高模和拟回迁的部件清单，进入 [导出并验收云端绑定身体 GLB](export-and-review-cloud-rig-body-glb.md)。本地路线交可共同焊接求权重的表面范围与须保留的独立边界，进入 [构建并验收本地连续皮肤网格](build-and-review-local-continuous-skin-mesh.md)。逐面标签对应准备后的实际拓扑，交本地标定与分件绑定。 |

## Skill 绑定

通用工作区规则负责版本、文件位置和原件保护。绑定域的判断在选用领域 Skill 后进行。 [工作区模板](../upstream/1.2.11/archived-p0/resources/runtime/templates/AGENTS.md#建模路线选择)

| 入口 | 选用条件与作用 |
| --- | --- |
| [rig-retarget](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) | 新绑、换网格或已有绑定修复时选用。执行者从实际角色和运动要求校准身体范围、衣物域与接触点。 [Runtime 身体输入](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/runtime-service-rig.md#身体输入与服务交接) |
| [hi3d-model-gpt-animation（安装包）](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d-model-gpt-animation/SKILL.md:20>) · [flex-motion（安装包）](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/flex-motion/SKILL.md:22>) | 有独立披风、尾部或惯性随动要求时按需选用。上层动画 Skill 补充复杂拆件的证据与接触检查，柔性专项区分附着点、自由端和保护区。 [拆件依据](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d-model-gpt-animation/references/garments-and-secondary-motion.md:3>) · [柔性区域](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/flex-motion/references/regions.md:5>) |
| [mdf-api](../upstream/1.2.11/prebuilt-skills/mdf-api/SKILL.md) | 选用云端自动绑定后采用其公开输入契约。`auto-rig` 的预检、提交和下载在下游执行。 [桌面提交约定](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/runtime-service-rig.md) |

游戏道具与挂点要求从 `rig-retarget` 的交付参考读取。指定最终 LOD 时接续已有 LOD 节点，并复核各档绑定边界。 [游戏交付参考](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/game-delivery.md#挂点和独立道具) · [LOD 整组定稿](review-and-finalize-lod-set.md)

## LLM Tools

| 独立工具说明 | 本节点的调用时机与条件 | 注册与核查情况 |
| --- | --- | --- |
| [exec](../tools/exec.md) · [exec_command](../tools/exec-command.md) | 读取确切资产、计算摘要，按需在 Blender 核对对象、局部拓扑、材质或截面。 | Code Mode 与本地执行入口。分域可用的场景与取样函数属于本地资源。 |
| [view_image](../tools/view-image.md) | 取得对应模型和视向的图片后，按实际路径查看外观与部件边界。 | 本地图像查看工具。取证可复用固定相机，也可比对已确认的参考素材。 |
| [studio_get_state](../tools/studio-get-state.md) | 只有用户指代当前视窗且源版本待确认时读取实际加载身份。 | 桌面动态工具。留存会话仅核实普通模型加载与版本状态。 |
| [user_interaction](../tools/user-interaction.md) | 当部件运动方式或保留要求有实质歧义，且实际资产与已知要求无法解决时，可用于澄清。 | Runtime 动态工具。专项 Skill 有澄清指导，本节点暂无生产面板回放。 |
| [workflow_report](../tools/workflow-report.md) · [wait](../tools/wait.md) · [write_stdin](../tools/write-stdin.md) | 选用工作流图时上报实际进度和产物。若本地检查仍运行，按已有 `cell_id` 或 `session_id` 续取结果。 | 分别对应 Runtime 工作流工具、Code Mode 执行单元和本地进程。 |

`service_rig export`、`service_rig bind`、`prepare_mesh` 和 `build_character` 是 Blender 本地脚本入口。`mdf_api` 是下游 Runtime 动态工具，`invoke` 是动作，`auto-rig` 是能力枚举。分域可选用 P1 资源读取场景、取样基础或求值网格、生成方向明确的视图。 [随包分派](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/run.py:8>) · [MDF 工具](../tools/mdf-api.md) · [场景载入](../resources/p1/asset-scene.md) · [网格快照](../resources/p1/mesh-snapshot.md) · [固定视图](../resources/p1/source-views.md)

## Hi3D 实现

### 决策

1. **固定休止空间和实际观察对象。** 根据已确认的资产定位身体与附属对象，在副本核对原始几何、世界变换、轴向和单位。已有动画时以指定休止基准为准。记录取证用的工作副本、方向及截面位置。 [身体输入与休止空间](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/runtime-service-rig.md#身体输入与服务交接)
2. **以运动意图确定候选域，以实际网格核对边界。** 结合用户要求、对象或语义组、材质、连通分量、正侧背视图及必要截面。材质、颜色和近邻位置提供辅助线索。随包披风示例说明，按躯干后方阈值会把内背和尾毛误分类，生成网格相接处可能粘连，衣内也可能缺少身体。遇到这类问题，先标出具体部位与待查项。 [几何判据](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/geometry-and-binding.md:5>) · [拆件案例](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d-model-gpt-animation/references/garments-and-secondary-motion.md:7>)

| 类别 | 判定依据 | 分域记录 |
| --- | --- | --- |
| 连续身体 | 同一解剖皮肤在关节及接缝处应共享形变。分成多个对象或存在 UV 接缝时，核对对应边界是否属于同一连续表面。相贴肢体和衣物边界需实查，尤其关注融合处。 | 身体对象或面范围、应共享的边界、明确隔离的近邻面。可在副本合并同一连续域。 |
| 独立软部件 | 柔性表面有自己的附着范围、衣层或自由端。按预期形变决定可接受身体权重回迁、需要局部配权重，还是进入辅助骨或布料专项。 | 对象、附着位置、层次和权重来源。专项另记录自由端、锚骨及保护区。 |
| 刚性部件 | 有意独立的壳体需要保持整体形状，整体跟随明确的骨。肩甲、发冠等按实际安装部位及动作确定随骨关系。 | 部件标签、目标骨名及刚性意图。接缝例外只适用于确认为独立的壳体。 |
| 独立道具 | 应按要求作为单独资产握持、背负、挂接或替换。固定随手骨的武器可以按刚性部件处理，需独立挂接时走道具交付。 | 独立对象、实际握点或背负点、命名挂点、父骨、局部位移和旋转、主轴及用途。 |

共用皮肤边界、衣层相贴和道具接触各有不同的运动要求。对附着关系未确定的部件，保留原对象及证据，待确认后再合入对应路线。 [连续域与独立壳体](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/geometry-and-binding.md:11>) · [柔性判定顺序](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/flex-motion/references/regions.md:21>) · [独立道具](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/game-delivery.md#挂点和独立道具)

### 执行

#### 云端路线

将拟提交的身体在副本落实为确切对象，交下游用 `service_rig export --body` 生成静止身体 GLB。保留工作工程中的高模身体及附属部件，记录代理与高模的休止空间对应。公开 `auto-rig` 调用以 `file` 接收身体文件，部件归属记录留在本地工作工程和交接清单中。已有合格的身体代理可沿用，最终 LOD 和提交代理分别确认。 [导出实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:127>) · [公开参数](../upstream/1.2.11/prebuilt-skills/mdf-api/references/mesh-invoke-api.md#37-自动绑定auto-rig)

**根据随包请求重建的下游预检示例。** `file` 已经是按当前分域导出的身体，`jobPath` 与 `outputDir` 仅用于后续作业身份。部件处理继续依据本地清单。

```json
{
  "action": "invoke",
  "capability": "auto-rig",
  "file": "exports/hi3d-body-proxy.glb",
  "params": {
    "use_skeleton": false,
    "use_transfer": true,
    "num_beams": 10
  },
  "jobPath": ".hi3d/mdf/body-rig.json",
  "outputDir": "exports/hi3d-body-rig",
  "dryRun": true
}
```

服务返回后，拟回迁的身体与软部件以确切对象名交给 `service_rig bind`。例如 `--body BodyHigh --targets BodyHigh CoatSoft`，其中外套仅在已确认适合该权重来源时列入。脚本要求目标唯一、非空、未绑定、包含身体且没有与服务骨重名的顶点组。返回 GLB 须有一个骨架及一个关联的蒙皮身体。调用方以世界空间单位传入有限正值 `--alignment-tolerance`。代码只比较服务身体与高模身体的世界 AABB，随后从同一服务身体向每个显式目标做最近面插值。软部件的侧别、衣层和可接受形变仍需实际检查。刚性部件与道具按已确认的随骨或挂点要求交接。 [回迁说明](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/service-rig.md:37>) · [对象门禁与包围盒](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:180>) · [逐目标插值](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:236>)

#### 本地路线

先落实允许共同准备的连续皮肤范围，再交 `prepare_mesh`。它会合并收集到的全部 Mesh 并按距离焊接，因此不同衣层、独立软部件或道具在准备输入时保留各自边界。`build_character` 要求准备工程有一个 Mesh、焊接标记及校准配置，先按实际三角网格求权重，再读取分件标签并拆件。若工作表面中含已确认可一起准备的独立刚性壳体，可用 `rigid_parts` 明确随骨关系。 [合并与焊接](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/prepare_mesh.py:32>) · [权重求解与分件](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py:181>)

**根据已核实本地实现重建的伪代码。** `labels_npz` 是可选的逐三角面标签，路径相对 profile。`mesh_sha256` 根据局部顶点和有序三角面计算，与源和结果文件的 SHA-256 分别保留。面标签用于拆件，准备输入时确定的焊接边界仍以实际几何为准。

```python
def resolve_labels(vertices, faces, height, profile, profile_dir):
    centers = vertices[faces].mean(axis=1) / height
    labels = np.full(len(faces), profile.get("default_part", "Body"), dtype="<U80")
    for rule in profile.get("part_rules", []):
        labels[region_mask(centers, rule)] = rule["name"]
    if profile.get("labels_npz"):
        data = np.load(profile_dir / profile["labels_npz"], allow_pickle=False)
        require(str(data["mesh_sha256"]) == mesh_fingerprint(vertices, faces))
        labels = data["labels"]
        require(len(labels) == len(faces))
    return labels
```

后匹配的面心规则覆盖先匹配结果，NPZ 整体替换规则标签。代码校验网格摘要及标签数量，逐面语义仍由执行者判断。拆件复制原面材质、面角 UV 和来自同一源顶点的共享权重。`rigid_parts` 中的部件被赋予当前骨架中指定变形骨的单权重，并标记 `intentional_rigid_shell`。该标记把壳体排除出普通皮肤接缝分组，权重、拉伸及实际接触仍按交付范围检查。 [面心规则和拆件](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/blender_core.py:99>) · [标签校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py:71>) · [网格摘要](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/weight_graph.py:12>) · [接缝分组](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/validate_blend.py:42>)

### 验收

| 范围 | 放行依据 |
| --- | --- |
| 共用分域 | 关键部件能定位到实际对象或表面，休止空间可复核。连续身体的共享边界、独立衣层、随骨壳体和道具的运动意图均明确。对疑似粘连、缺失身体或跨层接触保留观察证据。 |
| 云端准备与回迁 | 提交身体回读后只含拟提交的连续身体范围，代理与目标高模在同一休止空间。回迁名单符合对象约束，实际软部件另查同侧、同层及形变。`pose_qa_pending` 的候选继续交姿态和动作验收。 |
| 本地准备与分件 | 拟共同求权重的输入范围已隔离。准备后回读网格、接缝、UV 和材质。使用标签时，以实际准备网格和面顺序校验摘要和标签数量。拆件后核对共享接缝以及刚性骨对应。 |
| 道具 | 记录独立文件或目标对象及挂点约定。最终交付时核对实际握点、父骨、局部轴和动作中的位置及朝向。 |

下游应按实际交付所需的范围验收。工作流图进度和本地报告用于关联观察，动作品质以最终候选的实际网格和动作证据为准。 [绑定与动作验收](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/validation.md) · [游戏导出回读](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/game-delivery.md#导出后回读)

## 完成与恢复

| 当前结果 | 后续处理 |
| --- | --- |
| 检查仍运行或部件边界待确认 | 沿原本地执行句柄续查。源文件及休止空间仍匹配时沿用有效报告，只补需要的视图、截面或动作需求。 |
| 云端原作业不明或文件未齐 | 保留原 `jobPath`、`outputDir`、可用的 `requestId` 和当时的分域。交下游按原账本核对。已保存 `SUCCEEDED` 时沿用原作业恢复下载，提交不明时保留该尝试并暂停重提。 [原作业恢复](../tools/mdf-api.md#实现伪代码) |
| 候选已取得，软部件回迁不合格 | 保存候选、复现姿态和异常部件。重新核对源与目标的休止空间、侧别、衣层和名单。身体服务结果仍适用时可复用该结果，调整本地回迁输入。 |
| 工作拓扑、局部坐标或面序改变 | 保留原候选和标签作对照。建立实际新网格的摘要并重建逐面标签。更换对象变换或部件运动意图时，重核受影响的空间和分域依据。 |
| 分域通过 | 将确认的对象、域边界及证据交对应准备节点。新取得的导出和绑定结果分别经过各自的核验，再交付或登记。 |

## Vet3D 迁移与核查范围

### 供应商无关的交接契约

| 记录 | 应表达的业务语义 |
| --- | --- |
| 静止资产 | 源版本与摘要、工作副本、角色和身体对象、轴向、单位、实际休止空间。 |
| 部件归属 | 可共同求权重的连续表面、独立软部件的附着区和层次、刚性随骨的目标或待定语义、道具的挂接要求。每项附对象或面范围、判断依据和待核查区域。 |
| 执行交接 | 云端身体、代理与原高模的对应、允许回迁的目标，以及另行处理的部件。本地则交允许合并和焊接的网格范围、需保留的独立边界和后续标签依据。 |
| 验收关联 | 供检查追溯的文件及拓扑身份、视图和截面、共享接缝、目标姿态、接触范围及适用的保留要求。 |

Vet3D 的绑定方案和供应商仍待选型。四足角色先按真实解剖与运动语义记录相贴四肢、耳部、尾根、须部及佩戴物。需要随身体连续变形、独立软运动或挂接的部件，在得到角色和动作证据后再决定其路线。

### 下游接收检查

云端准备能由同一工作副本定位身体输出对象和日后回迁目标。本地准备能定位实际可共同焊接的连续范围，且隔离其余独立层与道具。后续分件标签和验收证据按实际准备文件和工作拓扑关联。已有合格绑定或 LOD 时，确认其空间与用途匹配后复用。 [既有 LOD 与替换网格](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/mesh-lod.md#准备与替换网格)

### 安装包证据、样例与缺口

- **版本与原件。** 仓库归档的 `rig-retarget/SKILL.md` 与 1.2.11 安装事务备份相同。`service_rig.py` 的 SHA-256 为 `b1090def180cd66ce35bb0c2f1ec4b2343df93ab039fc6fad7958bd989ffcd76`，`build_character.py` 为 `95cae0d242467669756f53b15ea28eabb01648d6f3b217fd7ad5cc6a7aa6bf53`，`blender_core.py` 为 `3dd41ea41b64d6297ca88ad7231526a6ff404d88a4cda1011f84c3b56e19a1cc`。 [版本清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) · [Skill 归档校验](../upstream/1.2.11/README.md#确定-lod-源网格与分档预算的随包证据)
- **隔离复核。** Blender 4.5.16 LTS 合成试验复现了身体 AABB 通过时远处软部件仍获得最近一侧骨权重。连续身体与独立刚性片试验复现了面心规则顺序、NPZ 覆盖、旧面序摘要与标签数量不符时的拒绝，以及共享权重、面角 UV、逐面材质和刚性骨单权重。改变刚性标记会改变接缝分组。证据覆盖脚本的输入与处理边界。 [云端结果回迁脚本](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:236>) · [本地分件与接缝](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/blender_core.py:107>)
- **样例覆盖。** 留存三个登记 GLB 的首版只有 `geometry_0`，后两版另有 `Whiskers_Left` 与 `Whiskers_Right`。三份 JSON 块均无 `skins` 和 `animations`。两份关联会话的实际工具调用未观察到该分域流程、`service_rig export`、`prepare_mesh` 或 `auto-rig`。样例支持静态对象结构和版本差异，绑定归属还需实际证据。 [留存工作区](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40>) · [关联样例说明](confirm-rigging-purpose-pose-and-route.md#安装包证据样例与缺口)
- **待实测。** 生产会话分域决策及实际产物、真实猫狗的相贴四肢、耳部、尾根与须部判断、软部件回迁和接触质量，以及目标动作和加载器中的接缝、挂点与道具姿态。
