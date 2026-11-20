# 定位形变并局部修权重

以 Hi3D Agent 1.2.11（Windows x64）为核查基准。本节点从实际动作中的异常追溯到静止位置、骨架与权重，确认错误归属后局部修订、另存候选，并用相同动作范围复验。确定性入口为 `rig-retarget/scripts/run.py -- service_rig inspect / repair`；归因、区域和禁用骨由执行者依据 Skill 与实际资产确定。`repair` 不生成动作，保存回执仍标记 `pose_qa_pending: true`。 [归档 Skill](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) · [检查契约](../resources/specialized-mesh-scripts.md#service_rig-inspect-单身体蒙皮检查) · [修订 CLI 契约](../resources/specialized-mesh-scripts.md#service_rig-repair-局部权重修订) · [P1 修复函数](../resources/p1/skin-weights.md#repair_regions-局部数组修复)

这是对随包本地阶段的业务细化。PCG 将局部拉伸的 `inspect/repair` 放在 `retarget`，之后交 `bake`；`fix_skin` 路线为 `pose → retarget → bake`。图声明不自动诊断、选择修复策略或验收质量。 [随包架构](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/pcg/architecture.yaml:46>) · [图工具边界](../tools/workflow-report.md#已安装架构的加载范围)

## 业务定义

| 项目 | 契约 |
| --- | --- |
| 触发 | 已绑定候选在实际姿势／动作中出现尖刺、跨侧牵拉或局部过渡异常，或需比较原服务与迁入权重。已有绑定可以直接进入，不要求重新请求骨架。 |
| 上游与输入 | 确切 `.blend` 与调用前摘要、身体和实际 Armature、复现动作及有效 Action/NLA、帧范围／fps、休止空间及网格单位高度 `H`、必保项与部件边界。有服务来源时附原始结果及回迁记录。 [候选核验](review-rig-and-skinning-candidate.md#验收) · [高模回迁](transfer-skin-weights-to-approved-mesh.md#验收) · [动作产物](retarget-and-bake-motion.md#验收) |
| 图片角色 | 主图和补充方向图核对角色及必保外观；异常图、修前修后近景和骨架覆盖来自确切候选，关联摘要、机位、方向及帧号。命令接收工程、身体、帧段或规则，图像和视向随取证记录交接，没有主图／参考图 URL 槽位。 [视觉证据](../infrastructure/workspace/acquire-model-visual-evidence.md) |
| 输出 | 可复现诊断、修前检查、角色专属规则、新候选与修复回执、重开后的同范围检查及视口结论。无需改权重时交归因及退回路线。 |
| 完成条件 | 归因、规则和实际输入版本一致；所需候选可重开，改动与保留项符合约定，原失败动作及受影响范围复验完成。仍有问题时保留最佳候选和待验项，不能标为最终通过。 |
| 下游 | 权重缺陷解决后交[重开并验收绑定与动作](reopen-and-review-rig-and-motion.md)，按当前用途完成检查再交付。骨架／映射原因回[校准骨轴与动作映射](calibrate-bone-axes-and-map-motion.md#完成与恢复)，动作组织问题回[重定向并烘焙动作](retarget-and-bake-motion.md#完成与恢复)。导出回读、版本登记和实际交付分别执行。 [验收状态](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/validation.md#交付状态) |

## Skill 绑定

通用入口负责工作区、确切文件、原件保护、运行环境及产物身份。关节语义、归因次序、局部规则和动作验收来自选用的领域 Skill。 [通用工作区规则](../upstream/1.2.11/archived-p0/resources/runtime/templates/AGENTS.md#操作规则)

| 归档入口或安装包参考 | 选用条件与作用 |
| --- | --- |
| [rig-retarget / SKILL.md](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) | 主 Skill，指导已有绑定的局部诊断、原件与非骨组保护、皮肤域及实际动作验收。主要面向 T/A-Pose 人形。 |
| [service-rig.md](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/service-rig.md:53>) · [existing-rig.md](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/existing-rig.md:93>) | 服务／回迁结果和已有绑定的异常定位、当前角色规则及同范围复验。它们是参考文件，不是额外 Skill。 |
| [dense-skinning.md](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/dense-skinning.md:38>) · [geometry-and-binding.md](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/geometry-and-binding.md>) | 删除错误归属后仍有过渡问题、需诊断种子、局部图修正或拓扑时按需采用，没有自动选平滑策略的承诺。 |
| [绑定与动作验收](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/validation.md) | 重开候选后分别核对结构、指定范围数值、视口及条件性的目标格式，保持修前修后可比。 |
| [游戏角色交付](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/game-delivery.md) | 明确涉及游戏、LOD 或引擎时追加对应检查；近共线点插值是其中的条件性指导。 |
| [mdf-api / SKILL.md](../upstream/1.2.11/prebuilt-skills/mdf-api/SKILL.md) | 仅在缺少对照所需原服务文件且要返回原作业取件时选用；正常本地修复不依赖它。 |

上述 `service-rig.md`、`existing-rig.md`、`dense-skinning.md`、`geometry-and-binding.md` 尚未进入当前仓库原文快照，以实际安装包路径复核。归档 Skill 与验收参考保留原件字节，版本和摘要见末节。

## LLM Tools

| 独立工具说明 | 本节点的调用时机和条件 | 注册与核查范围 |
| --- | --- | --- |
| [exec](../tools/exec.md) · [exec_command](../tools/exec-command.md) | 取摘要、读报告、运行 Blender 检查／修复或生成实际候选的取证图。 | 随包 Codex 宿主工具。前序隔离核查执行了专项 CLI，留存会话无本节点专项轨迹。 |
| [wait](../tools/wait.md) · [write_stdin](../tools/write-stdin.md) | 本地任务未结束时，分别按原 `cell_id` 或 `session_id` 续取。 | 续接同一执行，不是云端作业或候选缓存身份。 |
| [view_image](../tools/view-image.md) | 已有实际候选的异常帧、局部近景或对照图时按需查看。 | 图片读取；摘要、机位及帧号由取证记录绑定。用户不渲染时用视口和数值证据。 |
| [workflow_report](../tools/workflow-report.md) | 实际选用 Skill 并维护图时，按规范图既有节点记录工程、规则、报告及待验项。 | Runtime 动态 LLM Tool；本页业务拆分不意味着可替换包内 PCG 拓扑，图状态不验收质量。 |
| [user_interaction](../tools/user-interaction.md) | 允许改动的域、保留范围或用途仍有无法从现有任务确定的关键歧义时使用。 | Runtime 动态 LLM Tool，已明确的约束直接沿用。 |
| [mdf_api](../tools/mdf-api.md) | 需要回原成功作业补取对照文件时才使用 `download`，先在上游核对恢复条件。 | Runtime 动态 LLM Tool；`auto-rig` 是能力枚举，`download` 是动作。 |

`service_rig inspect/repair`、`validate_blend`、`weight_graph` 是本地命令，`repair_regions`、`write_changed_weights` 是函数，没有独立同名 LLM Tool。P1 `skin_weights` 是实际数值依赖；P0 包装、预算和指纹由外层按需采用。`run.py --timing-log` 使用专项物化计时，不是持久任务账本。模型可见 description 与通用实现由独立工具页维护。 [P1 资源](../resources/p1/skin-weights.md) · [P0 包装](../resources/README.md#专项-blender-命令的执行包装)

工具注册、Skill 指导和实际调用分别取证。已登记 GLB 如需 Studio 辅助，可[加载确切版本](../tools/studio-load-revision.md)、[核对视窗身份](../tools/studio-get-state.md)并[截图](../tools/studio-capture-view.md)；这些工具不检查工程内的权重和动作，不是本地修复必经入口。

## Hi3D 实现

### 决策

1. **固定基准与复现。** 保存可信工程、身体与实际骨架、调用前字节摘要、动作／帧段、单位及必保项。有服务来源时对照原始与迁入权重；已有绑定直接从可信工程进入。输入权重须已有效，空影响或未归一候选不能由本入口自动补绑定。
2. **先排除其他原因。** 检查骨向、父子空间、rest／T-A 对齐、姿态、缩放和真实关节。依据实际骨头与层级识别部位，不从骨编号猜左右，不用改权重掩盖映射错误。 [归因次序](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/service-rig.md:55>)
3. **核对皮肤域。** 身体、独立软层与刚性部件分别处理。同对象内精确同坐标的独立壳体不能靠坐标盒区分，须另行组织域或专项实现。拆分、拓扑改变后重新固定规则与检查基准。

| 归因 | 路线及交接 |
| --- | --- |
| 明确的跨侧或其他非局部错误影响 | `inspect` 定位，标定局部盒与禁用骨，再 `repair`。删除错误归属即可解决时停止，不追加平滑。 |
| 骨轴、休止空间、关节或映射错误 | 交工程、部位及复现帧回校准／映射；新候选使受影响旧检查失效。 |
| 连续、近共线几何的中间点权重异常 | Skill 允许按空间位置局部插值并保护其余区域；没有独立通用插值 CLI，需要额外实现和复验。 |
| 删除错误影响后仍有过渡不连续 | 检查截面、弧长权重剖面、种子和锚点，再考虑有物理宽度的过渡区或受限图修正。 |
| 退化三角、拓扑或碰撞问题 | 转对应处理；不以删面、细分或放宽阈值制造通过。平滑扩大异常时回较好版本重新归因。 |

[局部修复及停止条件](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/service-rig.md:77>) · [插值指导](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/game-delivery.md#动作和局部修复) · [种子及过渡](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/dense-skinning.md:40>)

### 执行

#### 1. 从实际动作定位异常

`service_rig inspect` 打开已保存工程，要求身体、骨架和对应 Armature 修改器参与视口求值，读取有效权重并逐帧取求值网格。它检查顶点形状与三角索引对应，报告网格／绑定矩阵摘要、有序变形骨名、真实骨头位置、逐帧指标及最坏面的顶点、静止坐标与权重。详细最坏清单每帧最多 20 面，不能替代完整异常计数。 [检查实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:288>)

**根据随包 CLI 重建的 PowerShell 请求。** 输入已有实际绑定和复现动作，帧段及高度是示例。数值未过可以先写报告再非零退出；前提错误可能没有报告。先核对本轮新报告的身份、完整性与实际范围。

```powershell
$rigSkill = 'D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget'
$blender = 'D:/install/blender/blender.exe'
$launch = @('--background', '--factory-startup', '--disable-autoexec',
            '--python-exit-code', '1',
            '--python', "$rigSkill/scripts/run.py", '--')

& $blender @launch service_rig inspect `
  --input 'sample-bound.blend' --body 'SampleBody' --rig 'SampleRig' `
  --frames '1:60' --height 1.8 --report 'sample-before.json'
```

本步放行要求是异常可复现，能从面和静止位置追溯错误影响。`pass` 只覆盖数值阈值；`motion_observed` 只表示相对基础网格有偏移，恒定非休止姿势也能置真，不能代替实际跨帧运动。前提失败先修读取／求值条件。

#### 2. 标定规则并绑定来源

从本次报告原样复制 `mesh_sha256`、`rig_sha256` 和完整有序 `bone_names`，据真实异常与骨段确定 `regions`。区域使用身体基础网格局部休止坐标，包含边界；禁用骨是已确认错误的实际变形骨。

**根据随包契约重建的 JSON 示例。** 摘要为待替换占位值，骨名和坐标仅示范格式；实际须采用完整报告骨序与当前角色标定值。

```json
{
  "mesh_sha256": "<本次检查报告的 mesh_sha256>",
  "rig_sha256": "<本次检查报告的 rig_sha256>",
  "bone_names": ["retained_bone", "reviewed_wrong_bone"],
  "regions": [
    {
      "bounds": [[0.9, -0.1, -0.1], [1.2, 0.1, 0.1]],
      "forbidden_bones": ["reviewed_wrong_bone"]
    }
  ]
}
```

| 身份项 | 实际覆盖与本步核对 |
| --- | --- |
| `mesh_sha256` | 基础局部 `float32` 顶点和 `int32` 三角索引，按当前身体重算匹配。 |
| `bone_names` | 实际 `use_deform` 骨顺序，与权重列逐项一致。 |
| `rig_sha256` | 全部骨名、父骨名、`use_deform` 及身体局部空间表达的绑定矩阵。 |
| 调用方补充身份 | 原工程字节、当前权重版本、身体名、原报告及复现动作／帧段；它们没有进入以上三个硬匹配项。 |

硬匹配不绑定旧权重、动作、输入工程字节或身体名。同网格和骨架但权重已换版时，旧规则仍可能通过，必须另对账来源。每条区域恰有 `bounds`、`forbidden_bones`；顶层 JSON 没有同等键白名单。 [规则门槛](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:425>) · [网格摘要](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/weight_graph.py:12>)

#### 3. 计算并回写局部权重

`repair` 必须给 `--input`、`--body`、`--rules`、新的 `--output` 和 `--report`。`--rig` 可省略，取 `body.find_armature()`；提供时必须匹配。共用 parser 的 `--frames`、`--height` 不参与修复；`--targets`、`--faces`、`--rigged-glb` 和 `--alignment-tolerance` 也不参与。 [入口分派](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:372>)

入口先检查新路径，打开工程、切 Object 模式并核对实际骨架。基础表面须非空且坐标有限；原权重须为非空浮点、有限非负，行和绝对容差 `2e-4`。身份匹配后记录保护签名，在数组副本完成全部规则，成功才写回 Blender。

**根据已核实源码重建的实现伪代码。** 保留数组计算与场景写回的边界，同坐标平均发生在全部规则之后。

```python
def repair_arrays(vertices, before, bone_names, rules):
    old = check_weights(before, vertices)
    require_unique_ordered_bones_and_nonempty_rules(bone_names, old, rules)
    after = old.copy()
    selected = empty_vertex_mask(vertices)
    rule_reports = []
    for rule in rules:
        require_exact_keys(rule, {"bounds", "forbidden_bones"})
        bounds, columns = validate_bounds_and_find_columns(rule, bone_names)
        ids = vertices_inside_inclusive_box(vertices, bounds)
        require_nonempty(ids)
        selected[ids] = True
        removed = after[ids][:, columns].sum(axis=1)
        affected = ids[removed > 0]
        zero_selected_columns(after, affected, columns)
        require_remaining_weight_above(after, affected, 1e-12)
        normalize_rows(after, affected)
        rule_reports.append(summarize_rule(ids, affected, removed))
    average_exact_shared_positions(after, vertices, selected)
    check_weights(after)
    return after, summarize_final_changes(old, after, rule_reports)


def apply_repair(body, rig, rules):
    vertices, faces = surface(body)
    names, before = skin_table(body, rig)
    require_rule_identity_matches(rules, vertices, faces, body, rig, names)
    protected = non_deform_group_names(body, names)
    signature = preserved_signature(body, protected)
    after, report = repair_arrays(vertices, before, names, rules["regions"])
    write_changed_weights(body, names, before, after)
    require(preserved_signature(body, protected) == signature)
    report["pose_qa_pending"] = True
    return report
```

硬拒绝包括非有限／倒置边界、空或重复禁骨、未知骨、空区域，以及清理后剩余总权重不大于 `1e-12`。各规则按当前结果顺序执行；后条移除量基于前次归一后的权重。不猜替代骨、不做邻域平滑、top-k 或几何编辑。 [P1 原件](../upstream/1.2.11/archived-p1/resources/runtime/prebuilt-skills/.dependency-skin-weights/scripts/rigging/skin_weights.py)

最后对全部选区并集内精确同坐标行平均。它不识别连通壳体／衣层，`rules[].affected` 不是全部实际改动数：禁用影响已零时，重复点也可能改变。`changed_vertices` 按最终数组差异统计；最终零改动也能成功，CLI 仍另存并标姿势待验。

`write_changed_weights` 只回写变化行；有变化且 Mesh 多用户时先复制所选数据。删除变为零的组成员，以 `REPLACE` 更新变化的正权重，避免清空重建组成员而改变双四元数累积顺序。 [写回实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:61>)

#### 4. 保存候选与修复回执

**根据随包 CLI 重建的 PowerShell 请求。** 沿用前面的变量，规则已经完成标定与来源核对。输出与报告均为新路径。

```powershell
& $blender @launch service_rig repair `
  --input 'sample-bound.blend' --body 'SampleBody' --rig 'SampleRig' `
  --rules 'sample-repair-rules.json' `
  --output 'sample-repaired.blend' --report 'sample-repair-result.json'
```

保护签名通过后，才检查输出后缀为 `.blend`，再创建父目录、`pack_all`、保存工程、计算输出摘要、输入摘要，最后原子写报告。CLI 不向 stdout 输出同份结构化修复 JSON。 [落盘顺序](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:443>)

| 回执字段 | 含义与核对 |
| --- | --- |
| `changed_vertices` | 最终变化顶点数，含共享点平均的变化，须符合本轮意图。 |
| `rules[].vertices / affected / max_removed_weight` | 每条命中数、删除正影响的行数和最大移除量；不能直接当去重总改动数。 |
| `shared_position_duplicates` | 选区并集中精确重复位置的重复顶点数，不证明连通或衣层语义。 |
| `pose_qa_pending` | 固定 `true`，修后姿势仍待验。 |
| `output_sha256 / input_sha256` | 末尾读取的文件摘要；输入只有一次末尾读取，不是前后比较。 |

报告没有 `pass`、完整规则、身体／骨架名、网格／骨架指纹或修后逐帧结果。规则、输入身份及前后检查必须共同交接，不能仅凭修复回执回填质量通过。

#### 5. 重开并复查原失败范围

**根据随包契约重建的 PowerShell 请求。** 重开保存的候选，使用同一实际动作、范围和高度，报告为新路径。

```powershell
& $blender @launch service_rig inspect `
  --input 'sample-repaired.blend' --body 'SampleBody' --rig 'SampleRig' `
  --frames '1:60' --height 1.8 --report 'sample-after.json'
```

核对修复输出摘要与修后报告 `input_sha256`，再核对实际身体、动作、范围及必保项。边长异常为倍率 `>3` 且增长 `>H/120`，双面积异常为倍率 `>8` 且增长 `>H²/81000`，`H` 使用网格局部单位。新非循环动作检查全部整数帧，循环检查完整周期及拼接。接触切换需子帧证据时，另做求值或视口取证，可按需选用场景采样；本 CLI 的 `--frames` 只解析整数，不直接接收小数帧。 [验收参考](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/validation.md#数值与视觉) · [可选场景采样](../resources/p1/scene-samples.md)

`inspect` 要求求值前后顶点及三角索引对应，Solidify 等改变拓扑时另建求值休止基准。三角部件集合可补 `validate_blend`，但须另确认非空对象清单和实际 Armature：空集合或无实际绑定也可能 `pass:true`，子集合不递归，接缝按局部坐标完全重合点比较。其报告可覆盖已有文件，需新且与输入不同的路径。数值、穿插、接触及自然度分别报告。 [集合检查边界](../resources/specialized-mesh-scripts.md#validate_blend-已保存工程的数值检查)

#### 6. 条件性的插值或图修正

删除错误影响即可解决时停止。插值／受限图修正是额外策略，不由 `repair` 自动选用。`weight_graph.solve_weights` 及 CLI 没有 `free_mask`、`fixed_mask`、区域列表或 `forbidden_bones` 参数；锚点来自初始单骨权重，再按占优骨边界的测地半径释放，原混合点为自由点。 [图解入口](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/weight_graph.py:26>) · [独立接口](../resources/specialized-mesh-scripts.md#weight_graph-外部权重求解)

不能说图 CLI 自动继承 `repair.json` 或保证区外不变、禁骨硬零。由算法可推知，局部为零的骨影响在自由区与含该影响的邻点求解时仍可能重新引入。真正局部域、边界和种子的约束须额外组织并验证，这是编排缺口。域、拓扑或骨架改变时重建身份及基准，不重跑整套构建覆盖认可资产。

### 验收

| 步骤 | 放行条件 | 失败处理与交接 |
| --- | --- | --- |
| 诊断基准 | 输入、身体和绑定有效，复现动作明确，异常可定位，非权重原因已排查。 | 读取／求值先恢复；骨架或映射原因回对应校准，不直接删权重。 |
| 规则标定 | 三项硬指纹匹配，来源与当前工程／权重版本一致；局部坐标、禁用骨、皮肤域和共享点已核实。 | 换版重新标定；混入独立壳体先处理域隔离。 |
| 数组与写回 | 权重有限非负归一，保留影响有效，最终变化符合意图，非骨组等保护签名通过。 | 输入不合格回绑定准备；数组失败不写模型，写回后失败丢弃进程编辑状态。 |
| 保存重开 | 候选可重开、摘要与回执一致，身体和动作正确，属性和范围符合要求。 | 缺回执或保护证据时保留候选待补证，保存成功不放行。 |
| 同范围复验 | 原失败及用途所需范围数值／视口完成，其他部件、接缝、接触与保留项通过。 | 恶化回退重新归因；新候选使受影响旧检查失效，残留明确标注。 |
| 下游接收 | 确切工程及摘要、规则、诊断、前后报告、实际动作范围和待验项齐全。 | 继续完整验收或按用途交付，未过部分不能称最终适配完成。 |

保护签名覆盖基础坐标、角点拓扑、面材质分配、UV 层名／坐标、形态键名／坐标、指定非骨组成员权重、材质槽名称及世界矩阵。不完整覆盖节点图、纹理字节、法线、所有修改器、父级和 Action/NLA／驱动。`repair` 不主动改骨架动作，也不能凭该签名证明以上全部已验。 [保护实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:90>)

## 完成与恢复

| 当前状态 | 恢复与交接条件 |
| --- | --- |
| 本地 pending／输出未完 | 用原 `cell_id` 或 `session_id` 续取。句柄失效先查进程、日志和文件，避免同路径重复写；计时不代替结果。 |
| 检查失败且有报告 | 区分数值未过与前提错误。前者保留面／帧／权重诊断，后者先恢复读取求值；不能沿用旧报告。 |
| 规则失配、空区域、未知骨或清空影响 | 保留原输入与错误，核对版本、坐标及保留影响。数组在副本计算，尚未写 Blender，不猜替代骨或扩大区域强行通过。 |
| 写回／保护失败 | 内存可能已修改，没有事务回滚。从可信工程重开，用新路径重做，不把失败场景当合格候选。 |
| 后缀、打包、保存或摘要失败 | 查候选是否存在且可重开；后缀在修改后检查，计算成功不代表已经落盘。保留诊断。 |
| 工程已存、报告失败 | 保留候选，独立重开、取摘要并核对改动、规则及输入身份。新检查不能伪造原回执；证据不足时保留该件并从可信基准另建一轮。 |
| 回执与文件来源不一致 | 停止回填，对账摘要、规则和范围。原子替换没有独占锁，入口预检后并发出现的同路径报告仍可能被替换。 |
| 候选仍不通过 | 保留部位及复现帧，采用最新可信身份和重新核实的规则继续修已绑定候选，或回较好版本。它不同于 `bind` 的未绑定目标限制。 |
| 缺原服务对照文件 | 回[原作业恢复](submit-and-recover-auto-rig.md#完成与恢复)，沿成功账本和目录按条件补下载。`UNKNOWN`／受理不明保留原尝试，不为本地修复重新提交绑定。 |
| 当前交接已通过 | 回填确切候选、规则与已验范围，继续动作验收或按约定交付。GLB 另导出回读后按需登记；工程／JSON、图归属、版本登记和实际另存分别确认。 [版本登记](../infrastructure/workspace/import-or-register-model-version.md) · [文件交付](../infrastructure/workspace/preview-and-deliver-files.md) |

`atomic_json` 在同目录临时文件写入、刷新并 `fsync` 后替换。工程和报告不是一次事务，输入摘要仅末尾读取，仍需调用前身份。零改动也可另存且保持姿势待验。 [写入实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/io_utils.py:19>)

## Vet3D 迁移与核查范围

### 供应商无关的交接契约

| 记录 | 应表达的业务语义 |
| --- | --- |
| 修订基准 | 确切资产、字节及权重版本、骨架和皮肤域、休止空间、单位、原件及必保项。 |
| 复现与归因 | 动作栈、fps、范围、异常面与部位、关节语义、非权重原因排查及证据图身份。 |
| 修复计划 | 规则来源、选区和坐标系、禁止／保留影响、共享点和独立壳体处理、策略与允许改动范围。 |
| 执行与恢复 | 尝试及句柄、独立产物路径、数组／写回／保存／报告阶段和失败点，原云端身份另保留。 |
| 验收与交接 | 候选、回执、规则及前后检查，分别表达结构、数值、视口、接触和条件性格式回读。 |

Vet3D 的 LLM、3D／绑定模型及 API 待选型，先定义业务语义再由适配器映射。为规则绑定权重／输入版本、记录最终修改行及共享点原因、明确局部求解约束、分配独占产物目录，是迁移建议，不能写成 Hi3D 已有保证。

四足的前后肢、趾行链、尾耳、毛发／附件需真实关节与步态规则。人形例子的骨名、区域、刚性策略、混合比例和阈值适用性不能直接泛化；插值、图解或加速均须对最终拓扑与实际动作复验。

### 安装包证据、样例与缺口

核查日为 2026-11-20，来源 `D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime`，manifest 为 `1.2.11 / win32 / x64`。主安装目录当前没有完整 `resources`，证据使用实际事务副本。 [版本 manifest](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) · [Skill 归档](../upstream/1.2.11/README.md#确定-lod-源网格与分档预算的随包证据)

| 相对 `prebuilt-skills/rig-retarget/` 的来源 | SHA-256 与用途 |
| --- | --- |
| [SKILL.md](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) | `8237ec25a4cf0b06a49723f21c168eee36f5848f64256fd357993d0a2b04f17d`；归档与安装包一致。 |
| [scripts/rigging/service_rig.py](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py>) | `b1090def180cd66ce35bb0c2f1ec4b2343df93ab039fc6fad7958bd989ffcd76`；检查、门槛、写回、保护与保存。 |
| [scripts/rigging/skin_weights.py](../resources/p1/skin-weights.md) | `07668c30ed37172c5b0babf053eefc206a3fcc6077ff3ba901aee9b68a1c11e4`；P1 与专项物化副本一致。 |
| [scripts/rigging/io_utils.py](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/io_utils.py>) | `ead12b0548776102ed0432cd6ce21f71bfb66040c5cb8f682f75ebcdde2c3ef7`；摘要与原子报告。 |
| [scripts/rigging/weight_graph.py](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/weight_graph.py>) | `60136c85a89991342d512ccbff5d5fe2b827567fb5f746eed0ee6cf9a472018f`；网格摘要和图解边界。 |
| [references/service-rig.md](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/service-rig.md>) | `c1b5ba250c49248205712d298b933748b18595e35cbd54703ef808ecf09f1e51`；归因、规则和复验指导。 |
| [scripts/rigging/test_service_rig.py](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_service_rig.py>) | `04283a9af7ba9c83a2c36c3d7a9fbe3dc13c819b90b6573b6020318128e33b07`；两骨夹具的修复和重开断言。 |
| [scripts/rigging/test_skin_weights.py](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_skin_weights.py>) | `919210871da0e7f9d774de90176f6b20bcefd0f2f010ae7c15f1501076356e9f`；纯数值 5 项测试。 |

**已核实执行。** 前序隔离复核用 Blender 4.5.16 LTS 运行未改写的 `test_service_rig`，通过错误跨侧权重定位、修复、保存重开、两帧检查、非骨组保护与共享 Mesh sibling 不被改动；stale 骨架指纹拒绝且不保存候选。随包运行参考列 Blender 5.x，这些合成分支不代表其他版本或全部资产兼容。

本轮文档核对时仍可读取前序回执：`changed_vertices:1`，命中 3 点、删除影响 1 点、最大移除量约 `0.2`；修后报告输入摘要与修复输出一致，`pass:true`、`motion_observed:true`，仅覆盖两帧。临时路径会失效，安装包测试是重建证据入口。 [修复回执](<C:/Users/11408/AppData/Local/Temp/hi3d-repair-audit-e324aee0f980433caf2927c8ecd31e97/repair.json>) · [重开检查](<C:/Users/11408/AppData/Local/Temp/hi3d-repair-audit-e324aee0f980433caf2927c8ecd31e97/after.json>)

纯数值复核用随包 Python 3.12.14／NumPy 2.5.3，5 项测试通过。额外探针区别于随包夹具：坐标唯一且禁用影响已零时零改动；同坐标点 `[0.8,0.2,0]`、`[0.3,0.7,0]` 统一为 `[0.55,0.45,0]`，`affected:0` 而 `changed_vertices:2`；顺序重叠规则基于前次归一结果计移除量；清空影响及输入全零权重拒绝。

**根据随包入口重建的 PowerShell 复核请求。** 从包外执行，第一个为纯数值测试，第二个的 `--work` 目录须尚不存在。此夹具不包含额外探针或生产云端调用。

```powershell
$runtime = 'D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime'
$rigSkill = "$runtime/prebuilt-skills/rig-retarget"
& "$runtime/.runtime-python/python/python.exe" -B "$rigSkill/scripts/run.py" test_skin_weights

$probeWork = Join-Path ([System.IO.Path]::GetTempPath()) ('hi3d-repair-' + [guid]::NewGuid().ToString('N'))
& 'D:/install/blender/blender.exe' --background --factory-startup --disable-autoexec `
  --python-exit-code 1 --python "$rigSkill/scripts/run.py" -- test_service_rig --work $probeWork
```

**样例覆盖。** [留存工作区](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40>) 的三个登记 GLB 均无 `skins`、`animations`、`JOINTS_*` 和 `WEIGHTS_*`；两份会话未见本节点专项调用，不代表完整分支与工具。 [活跃会话](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl>) · [归档会话](<D:/download/.sparc3d-runtime/environments/prod/codex-home/archived_sessions/rollout-2026-11-11T11-24-05-01a1c8a2-5bab-7df0-8557-d36af12e8411.jsonl>)

**待实测。** 生产 Agent 对真实异常的策略选择、四足跨侧／尾耳权重、相贴肢体与独立软层、复杂形态键／节点／驱动／修改器、高模密集权重表内存与耗时、完整步态接触、局部插值／图策略和目标引擎表现。修复专属的写回中断、保护失败、保存／报告故障及并发尚未逐项注入；恢复说明来自源码顺序，不能与前序 `bind` 报告失败探针混作同一操作实测。离线入口和合成通过不证明云端结果或最终视觉效果。
