# 向认可的高模或目标部件回迁权重

以 Hi3D Agent 1.2.11（Windows x64）为核查基准。此条件节点从已核验的服务绑定 GLB 取得骨架和权重，向已认可、尚未绑定的高模身体及指定软部件回迁，再保存新的 Blender 候选。随包实现为 `rig-retarget/scripts/run.py -- service_rig bind`；保存回执包含 `pose_qa_pending: true`，后续仍须从实际候选核对形变。 [归档 Skill](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) · [桌面本地阶段交接](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/runtime-service-rig.md#后续本地阶段) · [回迁脚本契约](../resources/specialized-mesh-scripts.md#service_rig-bind-服务权重回迁)

## 业务定义

| 项目 | 契约 |
| --- | --- |
| 触发 | 已核验一个服务蒙皮候选，且需要把它的权重迁入已认可的高模或其他目标软部件。本地求解或已有绑定已符合用途时，可以跳过此条件节点；已有绑定的局部缺陷走诊断和修复。 |
| 上游与输入 | 原服务 GLB、实际文件摘要及原作业记录；保留原件的未绑定目标 `.blend`、身体对象名、显式目标对象名单、休止空间、单位、容差依据及必保项。候选需具备实际骨架、蒙皮关系、关节语义和空间核验证据。 [候选交接](review-rig-and-skinning-candidate.md#验收) · [绑定域](define-body-and-accessory-binding-domains.md#验收) |
| 图片角色 | 主图和补充方向图用于确认角色、目标部件与必保外观；检查图来自实际候选，绑定文件身份、机位、视向和姿势／帧号。本地 `bind` 接收工程、GLB、对象名和容差，图片、目标方向与保留项随验收记录传递，没有 `baseImageUrl`、`referenceImageUrls` 等图片槽位。 [视觉证据](../infrastructure/workspace/acquire-model-visual-evidence.md) |
| 输出 | 新的绑定 `.blend` 和 JSON 回执；确切目标与骨架、原服务参考体、输入及输出摘要、属性保护结果和姿势待验状态。姿势／动作检查另附实际范围、结论和报告。 |
| 完成条件 | 重开实际保存的候选，确认目标名单、有效权重、Armature 关系、休止空间和必保属性；按本次交接用途完成所需姿势检查。只交后续动作适配时可明确保留动作待验状态，不能因此宣告最终动画通过。 |
| 下游 | 通过本节点交接门槛后，交动作输入与映射、[重开并验收绑定与动作](reopen-and-review-rig-and-motion.md)或已定位的局部权重诊断。需动作适配时，交确切回迁工程、实际骨架的 rest 摘要及源缓存身份，进入[校准骨轴与动作映射](calibrate-bone-axes-and-map-motion.md)。只需绑定工程时按约定完成验收再交付；需要游戏 GLB、Studio 版本或下载链接时，另做导出回读、登记与实际交付。 [验收状态](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/validation.md#交付状态) · [模型版本登记](../infrastructure/workspace/import-or-register-model-version.md) |

## Skill 绑定

通用入口负责定位工作区和确切文件、保留源文件、选择实际执行环境及记录产物身份。下面的回迁方法、身体与软部件边界、骨架语义和形变检查只在选用绑定领域 Skill 后执行。 [通用工作区规则](../upstream/1.2.11/archived-p0/resources/runtime/templates/AGENTS.md#操作规则)

| 归档入口或安装包参考 | 选用条件与作用 |
| --- | --- |
| [rig-retarget / SKILL.md](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) | 本节点主入口，按已认可几何、原始服务结果和本次用途选择回迁。要求另存、保留非骨骼组和独立衣层语义，依据真实关节及实际候选验收。原文主要面向 T/A-Pose 人形角色。 |
| [Runtime 服务交接](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/runtime-service-rig.md) | 桌面云端结果通过 `files.rigged_mesh` 进入本地阶段时采用。服务取件和原作业恢复归上游；已有结果继续本地处理。此文件是 Skill 参考文档。 |
| [service-rig.md（安装包参考）](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/service-rig.md:37>) | 解释同休止空间、显式软目标名单、最近面迁移、局部诊断和保存重开的验收要求。该参考未纳入当前仓库原文快照，以安装包路径与下文摘要复核。 |
| [mdf-api / SKILL.md](../upstream/1.2.11/prebuilt-skills/mdf-api/SKILL.md) | 仅在缺少服务文件且需要返回原作业恢复时选用。它不负责本地权重迁移。 |
| [绑定与动作验收](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/validation.md) · [游戏角色交付](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/game-delivery.md) | 候选重开时分层核验。目标明确涉及游戏、LOD 或引擎时，追加对应影响数、动作和目标加载器检查；仅 Blender 交付不自动追加这些任务。 |

## LLM Tools

| 独立工具说明 | 本节点的调用时机和条件 | 注册与核查范围 |
| --- | --- | --- |
| [exec](../tools/exec.md) · [exec_command](../tools/exec-command.md) | 读取确切文件、计算摘要、启动随包 Blender 命令，或按实际对象和姿势取证。Code Mode 内可调用本地执行工具。 | Codex 宿主执行入口。前序隔离核查调用了随包 CLI；留存生产会话不覆盖此次回迁。 |
| [wait](../tools/wait.md) · [write_stdin](../tools/write-stdin.md) | 本地任务仍在运行时，分别按原 `cell_id` 或 `session_id` 续取同一执行。 | 依返回的执行层句柄选择，不把两个标识混用。 |
| [view_image](../tools/view-image.md) | 已从实际候选生成对照图、关节近景或指定姿势图时按需查看。 | 本地图片读取；图像需附候选身份及取证范围。 |
| [workflow_report](../tools/workflow-report.md) | 已选 Skill 并维护工作流图时，按现有图节点归属记录实际产物、阶段和待验状态。 | Runtime 动态 LLM Tool；图回执不代替实际文件和形变证据。 |
| [user_interaction](../tools/user-interaction.md) | 目标部件、是否允许改动认可几何或最终用途仍有关键歧义，且现有任务与素材无法确定时使用。 | Runtime 动态 LLM Tool。可以由既定需求确定的输入直接采用。 |
| [mdf_api](../tools/mdf-api.md) | 缺少服务 GLB 时，按上游原作业的补下载条件恢复；取得并复核后再进入本地执行。 | Runtime 动态 LLM Tool。正常回迁不调用它。`download` 是动作，`auto-rig` 是 MDF 能力枚举。 |

`service_rig bind`、`service_rig inspect` 和 `validate_blend` 是本地命令，`skin_table`、`check_weights` 是脚本函数；它们没有独立注册为同名 LLM Tool。`rig-retarget` 是 Skill。P0 包装／预算可由调用方选用，P1 `skin_weights` 是已归档实现依赖，不能混称动态工具。 [单身体检查](../resources/specialized-mesh-scripts.md#service_rig-inspect-单身体蒙皮检查) · [集合检查](../resources/specialized-mesh-scripts.md#validate_blend-已保存工程的数值检查) · [P0 执行包装](../resources/README.md#专项-blender-命令的执行包装) · [P1 权重原件](../resources/p1/skin-weights.md)

工具注册、Skill 指导和实际调用分别取证：工具页维护模型可见 description 与通用契约；本节点记录使用条件；安装包及前序隔离执行证明本地实现行为，没有生产 Agent 自动选择此路线的完整轨迹。

## Hi3D 实现

### 决策

1. **固定源与目标。** 从上游核验记录取得实际服务 GLB、原作业标识与摘要；固定认可的目标工程和 `--body`。`--targets` 显式包含身体及本次需要软变形的对象。独立道具与刚性护甲按用途单独交接，不能因距离近就并入身体迁移。若已有绑定可复用，转已有绑定路线；不能直接把它作为 `bind` 的未绑定目标。 [目标与部件边界](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/service-rig.md:39>)
2. **确认共同休止空间。** 对照实际轮廓、关节头、左右语义、单位、方位及身体关系。容差使用世界坐标单位，由当前资产尺度和误差依据确定。脚本只比较服务身体与指定身体的基础顶点世界 AABB 极值，不自动配准或缩放；相同包围盒也不能证明部位和衣层对应。 [AABB 门槛](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:218>)
3. **选择新产物路径。** 保留原始未绑定工程和服务 GLB，在包外任务目录使用新的输出与报告路径，避免并发共用路径。调用前记录输入摘要及保留项，供保存后复核；这一步属于调用方补充记录，随包命令只在末尾读取输入摘要。

### 执行

**根据随包 CLI 重建的 PowerShell 请求。** 示例假定任务目录已有通过核验的 `inputs/high-model.blend` 与 `inputs/service-rigged.glb`，目标对象为未绑定的 `Body`、`SoftGarment`。没有软部件时只列身体。`0.001` 是示例世界坐标容差，须以实际资产重新确定；输出和报告必须为新路径。

```powershell
$rigSkill = 'D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget'
& 'D:/install/blender/blender.exe' --background --factory-startup --disable-autoexec `
  --python-exit-code 1 --python "$rigSkill/scripts/run.py" -- service_rig bind `
  --input './inputs/high-model.blend' --body 'Body' `
  --rigged-glb './inputs/service-rigged.glb' --targets 'Body' 'SoftGarment' `
  --alignment-tolerance 0.001 `
  --output './exports/hi3d-bound-candidate.blend' `
  --report './exports/hi3d-bind-report.json'
```

`run.py` 把 `service_rig` 分派至 `rigging.service_rig.main`。入口要求报告未存在且不等于输入，输出未存在且不等于报告。随后打开输入工程并切到 Object 模式。`bind` 另要求 `--rigged-glb`、`--targets` 和 `--alignment-tolerance`。共用 parser 虽接受 `--rig`、`--faces`、`--frames`、`--height` 和 `--rules`，该分支不读取这些参数；`--rig` 不能选择导入骨架。 [分派](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/run.py:26>) · [入口与条件参数](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:372>)

| 执行步骤 | 已核实的实现 | 本步检查与失败边界 |
| --- | --- | --- |
| 1. 核对目标 | 目标对象非空、唯一、包含身体；逐个要求 Mesh、有多边形且 `find_armature()` 为空；容差有限且大于零。 | 名称由实际工程解析，缺对象即失败。此门槛不等于已完成每个目标全部几何和语义检查。 |
| 2. 导入服务结果 | 从本次新导入对象中选出唯一 Armature，再选恰好一个关联它的 Mesh 作为参考身体。允许额外未绑定 Mesh。 | 所选 Armature 有活动 Action 或 NLA Track 即拒绝，要求先准备静止结果。此检查没有覆盖全场景动画、驱动或全部对象。 |
| 3. 校验源权重与空间 | 按 `use_deform` 骨名读取源权重；拒绝目标既有组与这些骨名重名；计算身体 AABB 最大极值差并比较容差。 | 权重须有限、非负且逐点归一，绝对容差 `2e-4`。空间不符退校准，不扩大容差掩盖问题。其他目标的基础坐标在逐目标读取时校验有限性，并记录保护签名。 |
| 4. 逐目标迁移 | 只删除导入参考上的非变形组；骨架切 REST。目标共享 Mesh 时先复制其数据；新增服务骨名组，用最近面插值和骨名匹配回迁。只应用临时 Data Transfer，再添加保体积 Armature 并置于修改器首位，归一化变形组。 | 每个目标重新 `skin_table` 校验，并比较保护签名，成功才记入 `targets`。前面目标完成后，后面目标仍可能失败；函数没有多目标事务回滚。 |
| 5. 整理并落盘 | 骨架切回 POSE；隐藏本次导入的全部 Mesh，保留参考对象。检查输出为 `.blend` 后打包资源、另存，计算输出及输入摘要，最后原子写报告。 | 输出扩展名检查发生在迁移之后。工程和报告分步保存；后段失败可能已有完整工程。没有在此生成动作、导出 GLB 或登记版本。 |

[目标与服务门槛](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:180>) · [逐目标执行](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:229>) · [落盘顺序](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:443>)

**源码摘录。** 下列组包决定迁移方法：参考身体为 `transfer.object`，目标是当前 `obj`；按名称接收全部源组，使用对象变换和最近面插值，以替换方式写入。骨架、目标方向和衣层对应没有由这些参数自动推断。 [实际迁移参数](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:247>)

```python
transfer = obj.modifiers.new("Service weight transfer", "DATA_TRANSFER")
transfer.object = source
transfer.use_vert_data = True
transfer.data_types_verts = {"VGROUP_WEIGHTS"}
transfer.vert_mapping = "POLYINTERP_NEAREST"
transfer.layers_vgroup_select_src = "ALL"
transfer.layers_vgroup_select_dst = "NAME"
transfer.use_object_transform = True
transfer.mix_mode = "REPLACE"
transfer.mix_factor = 1
```

**根据已核实实现重建的控制流伪代码。** 省略 Blender 上下文切换，保留拒绝分支、逐目标检查和保存顺序。

```python
def transfer_cli(input_path, output_path, report_path, glb, body_name,
                 target_names, tolerance):
    require_new_output_and_report(input_path, output_path, report_path)
    open_blend(input_path)
    body, targets = resolve_objects(body_name, target_names)
    require_unique_unbound_nonempty_targets(targets, body)
    require_finite_positive(tolerance)

    imported = import_gltf(glb)
    rig = require_one_armature(imported)
    require_no_active_action_or_nla_track(rig)
    source = require_one_mesh_linked_to_rig(imported, rig)
    bone_names, weights = read_and_check_deform_weights(source, rig)
    require_no_name_collisions(targets, bone_names)
    delta = max_abs(world_base_aabb(source) - world_base_aabb(body))
    require(delta <= tolerance)

    remove_reference_non_deform_groups(source, bone_names)
    set_rig_rest(rig)
    records = []
    for obj in targets:
        protected_groups = original_group_names(obj)
        before = preserved_signature(obj, protected_groups)
        copy_mesh_if_shared(obj)
        transfer_nearest_surface_by_bone_name(source, obj, bone_names)
        add_preserve_volume_armature_first(obj, rig)
        normalize_and_check_deform_weights(obj, rig)
        require(preserved_signature(obj, protected_groups) == before)
        records.append({"object": obj.name, "preserved": True})

    set_rig_pose(rig)
    hide_imported_meshes(imported)
    result = make_bind_report(rig, source, records, delta,
                              service_glb_sha256=file_digest(glb),
                              pose_qa_pending=True)
    require_blend_extension(output_path)
    pack_and_save(output_path)
    result["output_sha256"] = file_digest(output_path)
    result["input_sha256"] = file_digest(input_path)
    atomic_json(report_path, result)
```

报告字段为 `rig`、`reference_body`、`bones`（变形骨数）、`bounds_max_delta`、`targets`（每项为 `object` 和 `preserved`）、`service_glb_sha256`、`pose_qa_pending`、`output_sha256` 和 `input_sha256`。CLI 通过报告文件交出结构化结果，没有额外输出同一份 JSON 到标准输出。末尾的输入及服务摘要不构成执行前后防篡改比较；调用方需与已固定的身份对账。 [回执构造](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:277>)

### 验收

| 阶段 | 放行条件及证据 | 未通过时 |
| --- | --- | --- |
| 输入可回迁 | 服务文件身份与上游一致；唯一实际服务骨架及身体、有效权重、真实关节语义、共同休止空间和显式软目标名单成立。 | 缺件回原作业取件；空间、姿态或部件不符回输入准备；已有绑定转复用或诊断。 |
| 迁移数值与属性 | 回执中的目标完整对应请求，实际目标权重有限、非负、逐点归一，绑定到正确骨架；保护签名通过，并补查签名未覆盖的必保项。 | 保留原工程及失败部位，不以归一化代替语义检查。跨侧、跨衣层影响需定位原因后修订。 |
| 保存重开 | 独立重开输出，核对实际文件 SHA-256、目标非空、Armature 关系及可见求值，重查材料、贴图、shape keys、其他修改器的实际效果和原件保护。 | 报告和候选不符时暂停交接。确认当前文件身份和已保存范围，再决定另验或重做。 |
| 姿势与动作 | 按用途在候选副本准备或复用实际姿势／动作，检查本次全部目标、关节近景、接缝和接触。数值、视口与动作覆盖分别记录；尚未制作动作时明确待验。 | 先区分骨轴、父子空间、休止姿态、关节与动作映射错误，再对确切异常区域修权重；新候选重验受影响范围。 |
| 下游可接收 | 接收者持有确切工程、骨架和目标名单、源及输出身份、报告、保留项和剩余验收条件。交付用途要求的检查已完成；继续动作适配时携带明确的动作待验状态。 | 未明确的质量项留在交接记录中，不能用 `preserved:true`、进程成功或保存成功替代。 |

`preserved_signature` 比较基础顶点、角点拓扑、面材质分配、UV 层名与面角坐标、shape key 名与坐标、原顶点组成员及权重、材质槽名称和世界矩阵。它没有完整比较材质节点图、纹理字节、法线、所有修改器设置、父级和动作／驱动。其他修改器保留，但新增 Armature 排在首位，仍需检查实际求值。 [保护签名](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:90>)

单身体可用 `service_rig inspect`，准备过的三角部件集合可补充 `validate_blend`。帧段、高度、对象和骨架名取实际候选；命令本身不生成测试动作。前者要求求值前后顶点及三角索引一致，Solidify 等改变拓扑的表面需另建求值休止基准。`motion_observed` 表示相对休止网格观察到偏移，恒定非休止姿势也能置真，不能证明跨帧运动；集合检查还须显式确认预期部件非空及实际 Armature 关系。 [单身体检查契约](../resources/specialized-mesh-scripts.md#service_rig-inspect-单身体蒙皮检查) · [集合检查边界](../resources/specialized-mesh-scripts.md#validate_blend-已保存工程的数值检查)

严重拉伸按边长倍率 `>3` 且增加 `>H/120`、双面积倍率 `>8` 且增加 `>H²/81000` 检查，`H` 使用网格局部单位。新非循环动作核对全部整数帧，循环核对完整周期及拼接。数值零异常只覆盖已验范围；穿插、接触和动作自然度还需实际审看。导出游戏格式时另核实际线性蒙皮、影响数限制及目标加载器结果。 [验收规则](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/validation.md)

## 完成与恢复

| 当前结果 | 恢复办法与可交接条件 |
| --- | --- |
| 本地任务 pending | 保留原执行句柄，用对应 `wait` 或 `write_stdin` 续取同一任务。进程仍在运行时不另起同路径回迁。句柄失效后先查进程、日志及实际产物，再按落盘情况分支。 |
| 服务文件缺失，或上游提交状态不明 | 保留原 `jobPath`、`outputDir`、可用 `requestId` 和诊断。已有成功账本且符合补下载条件时按同一原任务 `download`；已入账文件后来丢失／变更须另按上游边界处理。`UNKNOWN`、断线或受理不明保留原尝试，找到原任务再续查，不为本地失败新提云端作业。 [原作业恢复](submit-and-recover-auto-rig.md#完成与恢复) |
| 目标、服务结构、权重或空间门槛失败 | 保留原输入及诊断。修正实际对象名单、服务静止结果、坐标或骨架来源后，从原未绑定工程用新输出与报告路径重新执行。错误提示不是自动配准或语义修复。 |
| 多目标中途失败，尚未进入保存 | 前面目标可能已在当前内存中绑定，后面目标尚未完成。`bind_result` 没有事务回滚。丢弃该失败进程的编辑状态，从原未绑定工程重新打开；不能把半成场景当完整候选。 |
| 输出后缀、打包、保存或摘要读取失败 | 保留日志，核对有无候选及其可重开性。输出后缀在迁移后才检查；迁移完成不表示文件已落盘。未完成保存的内存状态不供下游使用。 |
| 工程已保存，但报告缺失或写入失败 | 保留候选，计算实际摘要并独立重开，检查目标、骨架、原服务身份和保护证据。缺失的回迁证据标为缺口，用新的检查报告补证；不能伪造原回执。若证据不足，保留该候选并从原未绑定工程另建一轮。 |
| 报告存在但文件摘要、对象或范围不符 | 停止回填，保留两边记录，核对是否读错任务或出现并发写入。报告采用临时文件替换，但无并发独占锁；不能只看路径存在就认定归属正确。 |
| 成功取得候选，但姿势／保留项未通过 | 保留该候选、异常部位及复现帧。空间或骨架问题先校准，局部错误权重交[定位形变并局部修权重](locate-deformation-and-repair-local-weights.md)，动作问题回适配。每次另存、重新验收；不在已绑定候选上重复运行 `bind`。 |
| 已通过当前交接条件 | 回填确切候选、摘要、原始报告和已验范围。隐藏的服务参考网格仍在工程中，导出时使用明确的目标对象名单。`.blend` 与 JSON 是工作区文件；要展示或登记模型版本时另导出并回读 GLB，再按版本登记与交付契约执行。 [登记边界](../tools/workspace-commit-model.md) · [文件交付](../infrastructure/workspace/preview-and-deliver-files.md) |

`atomic_json` 在同目录临时文件中写 JSON，刷新并 `fsync` 后替换目标。入口的“报告未存在”检查与末尾写入之间没有锁，并发者后来创建的同路径文件可能被替换。输入摘要也只在末尾计算；恢复时结合调用前身份、实际文件和独立验收记录。可选 `run.py --timing-log ... --task-id ... --attempt ...` 参数须放在 `service_rig` 前，计时记录不是持久作业账本。 [报告写入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/io_utils.py:19>) · [可选计时](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/run.py:38>)

## Vet3D 迁移与核查范围

### 供应商无关的交接契约

| 记录 | 应表达的业务语义 |
| --- | --- |
| 认可的目标基准 | 主体及用途、确切目标资产和摘要、身体与软目标名单、刚性／独立部件、必保属性及原件位置。 |
| 权重来源 | 确切来源资产与摘要、骨架和关节语义、变形骨序、有效蒙皮证据；有云端服务时附原作业身份，不以供应商字段名作为业务定义。 |
| 空间与迁移计划 | 两边休止空间、单位、对齐依据及误差、所用表面映射方法、各目标适用范围及隔离规则。 |
| 本地执行尝试 | 输入身份、执行句柄、独立输出／报告路径、阶段和失败点；进程状态、文件保存、报告保存分别记录。 |
| 结果与证据 | 实际候选及摘要、真实骨架与绑定对象、属性检查、数值权重、指定姿势、完整动作、目标格式回读分别给结论和覆盖。 |
| 下游接收条件 | 明确交动作适配、局部诊断还是绑定交付；附当前通过项、未通过项、待补证项和后续导出对象范围。 |

Vet3D 的 LLM、3D 生成、绑定模型及 API 仍待选型。可以由适配器把“认可目标、权重来源、空间对齐、迁移策略、保存候选”映射到具体工具；业务层应持有明确的阶段状态和产物身份。为每个尝试预留独占产物目录、在执行前后核对源身份、将落盘和报告保存分开记录，属于 Vet3D 的迁移建议，不能写成 Hi3D 已有的事务保证。

动物的前后肢、尾部、耳部及左右对应、相贴肢体和独立毛发／附属壳体需要另建语义规则与实际动作证据。最近面算法、归一化和人形 Skill 都不能证明四足适用；这些能力需在选定模型及真实资产上确认。

### 安装包证据、样例与缺口

核查日为 2026-11-20。可复核资源位于 `D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime`，manifest 声明 Runtime `1.2.11`、`win32/x64`；主安装目录当前缺少完整 `resources`，证据引用实际事务副本。归档入口与安装包字节对账，执行脚本通过下表固定。 [版本 manifest](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) · [仓库归档说明](../upstream/1.2.11/README.md#确定-lod-源网格与分档预算的随包证据)

| 相对 `rig-retarget/` 的来源 | SHA-256 与证明范围 |
| --- | --- |
| [SKILL.md](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) | `8237ec25a4cf0b06a49723f21c168eee36f5848f64256fd357993d0a2b04f17d`；人形路线、原件保护和领域验收指导。 |
| [scripts/run.py](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/run.py>) | `ad7b270350d617baefd9d18ae8044db902b153502374cbecb61afaabdb4f7f6d`；本地命令分派和可选计时。 |
| [scripts/rigging/service_rig.py](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py>) | `b1090def180cd66ce35bb0c2f1ec4b2343df93ab039fc6fad7958bd989ffcd76`；校验、逐目标迁移、属性保护、报告及落盘顺序。 |
| [scripts/rigging/io_utils.py](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/io_utils.py>) | `ead12b0548776102ed0432cd6ce21f71bfb66040c5cb8f682f75ebcdde2c3ef7`；文件摘要和原子 JSON 写入。 |
| [scripts/rigging/skin_weights.py](../resources/p1/skin-weights.md) | `07668c30ed37172c5b0babf053eefc206a3fcc6077ff3ba901aee9b68a1c11e4`；权重数值与形变指标，P1 原件与安装包一致。 |
| [references/service-rig.md](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/service-rig.md>) | `c1b5ba250c49248205712d298b933748b18595e35cbd54703ef808ecf09f1e51`；目标选择、休止空间、回迁与验收指导。 |

**已核实的本地执行。** 前序隔离核查使用 Blender 4.5.16 LTS，在包外合成工程运行未改写的随包命令。下表区分随包夹具与额外探针，均未调用生产云端绑定。

| 证据 | 覆盖与观察 |
| --- | --- |
| [随包 `test_service_rig`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_service_rig.py:14>) | 小型两骨夹具完成导出、回迁、局部修复和保存重开。回迁检查保留 `attachment` 组与 Solidify，修改器顺序为 Armature 在前。复核须指定尚不存在的包外 `--work` 目录，完整请求见下文。 |
| 额外权重与空间探针 | 服务身体平移超容差、服务骨架带 Action、零变形权重顶点分别被拒绝。左右权重列对调且维持归一时，回迁仍成功并保留错误对应，报告姿势待验；说明数值门槛不能代替解剖与动态验收。 |
| 额外属性探针 | 含 Basis／Lift 形态键的目标完成迁移，形态键坐标和原 Solidify 保留，新 Armature 在前，原输入字节摘要未变。该观察仅覆盖所构造属性。 |
| 额外多目标失败探针 | 第二目标含非有限坐标，前一目标已在内存完成绑定，后续签名读取失败；未生成最终工程和报告，原输入摘要未变。该案例不属于随包测试的全部分支覆盖。 |
| 额外报告失败探针 | 把报告父路径预先建成普通文件，迁移和工程保存成功后，报告建目录失败；候选存在且重开后有实际绑定，报告不存在。可按同样构造复核“工程已存、报告失败”。探针捕获预期异常的外层成功退出不能解释为正常 CLI 业务成功。 |

**根据随包测试入口重建的 PowerShell 复核请求。** 生成唯一的包外工作目录名，由测试自行创建；它只覆盖随包夹具的检查，不包括表中额外探针。

```powershell
$rigSkill = 'D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget'
$probeWork = Join-Path ([System.IO.Path]::GetTempPath()) ('hi3d-bind-' + [guid]::NewGuid().ToString('N'))
& 'D:/install/blender/blender.exe' --background --factory-startup --disable-autoexec `
  --python-exit-code 1 --python "$rigSkill/scripts/run.py" -- test_service_rig --work $probeWork
```

**留存样例范围。** [样例工作区](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40>) 的三个登记 GLB 均无 `skins`、`animations`、`JOINTS_*` 和 `WEIGHTS_*`；两份关联会话未见此节点的专项回迁调用。它们是未绑定资产及通用交互的示例，不代表全部工具或分支。 [活跃会话](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl>) · [归档会话](<D:/download/.sparc3d-runtime/environments/prod/codex-home/archived_sessions/rollout-2026-11-11T11-24-05-01a1c8a2-5bab-7df0-8557-d36af12e8411.jsonl>)

**待实测。** 生产 `auto-rig` 结果与原作业在线恢复；真实高模及多软层的空间对应、耗时和内存；复杂 shape key、材质节点、驱动及修改器组合；真实四足的关节语义、跨部件权重、接缝、接触和步态；导出后在目标加载器中的影响数与形变表现。离线参数核查只证明本地入口接受参数并按上述方式执行，不能证明云端结果或最终画质。
