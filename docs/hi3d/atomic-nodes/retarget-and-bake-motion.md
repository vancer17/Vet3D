# 重定向并烘焙动作

以 Hi3D Agent 1.2.11（Windows x64）为核查基准。本节点接收已核验的源动作缓存、目标绑定及角色专属映射，执行或复用对应范围的动作烘焙，固定可重开的动作候选及其交接证据。通用实现是 `rig-retarget/scripts/run.py -- rig_adapter retarget`，在同一命令中计算目标姿态、写入原生 Action、保存并重开；回执仍标记 `pose_qa_pending: true`。 [归档 Skill](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) · [本地命令契约](../resources/specialized-mesh-scripts.md#rig_adapter-retarget-动作映射与烘焙)

这是业务职责的拆分。上游[校准骨轴与动作映射](calibrate-bone-axes-and-map-motion.md)可以使用同一命令验证映射并产出动作候选；源码没有独立的“试烘”和“最终烘焙”命令。同身份、同要求范围且已有充分证据的候选可直接进入本页的复用验收，不强制重复执行。随包 PCG 的 `retarget`、`bake` 图节点也不自动派发脚本或完成质量验收。 [随包架构](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/pcg/architecture.yaml:46>) · [图工具边界](../tools/workflow-report.md#已安装架构的加载范围)

## 业务定义

| 项目 | 契约 |
| --- | --- |
| 触发 | 目标绑定、休止基准与动作映射已核定，需要生成本次要求范围的可编辑动作；或已有上游烘焙候选，需要核对是否可以按同一要求复用。没有动作需求时不强制执行。 |
| 上游与输入 | 确切目标 `.blend`、Armature 与受驱动对象清单、目标当前 rest 摘要及必保项；源缓存、实际文件摘要、来源与时间／空间核验记录；已校准映射、根运动及条件 IK 配置；输出 Action 名、起始帧及允许替换范围。已有动作候选另交报告、实际覆盖范围和产物摘要。 [源缓存验收](fix-and-evaluate-source-motion.md#验收) · [映射交接](calibrate-bone-axes-and-map-motion.md#验收) |
| 图片角色 | 主图和补充方向图用于核对角色及必保外观；动作对照、骨架覆盖图和近景来自确切工程，关联方向、机位及帧号。本地命令接收工程、骨架、缓存和配置，图片、目标视向与保留项随验收记录交接，没有主图／参考图 URL 槽位。 [视觉取证](../infrastructure/workspace/acquire-model-visual-evidence.md) |
| 输出 | 可重开的动作 `.blend`、实际 Action／slot／帧段／fps、JSON 回执及输入、缓存、候选身份；实际使用的映射和其调用方摘要、保护结果、根比例／IK 诊断及待验范围。旧 builder 分支另交 profile、NLA 与 manifest。 |
| 完成条件 | 目标、映射和缓存身份与本次要求一致，实际候选中的 Action、时间及目标归属已核对，保留项通过；复用或新执行的依据明确。当前节点完成表示动作产物可追溯、可交后续验收，不表示完整形变与动画质量已经通过。 |
| 下游 | 交[重开并验收绑定与动作](reopen-and-review-rig-and-motion.md)，异常时交可复现的局部诊断；仅 Blender 交付按约定完成所需检查。需要游戏 GLB 时另做导出和目标加载器回读，模型版本登记及实际交付各自执行。 [动作验收](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/validation.md) · [版本登记](../infrastructure/workspace/import-or-register-model-version.md) · [文件交付](../infrastructure/workspace/preview-and-deliver-files.md) |

## Skill 绑定

通用入口负责工作区、确切文件、原件保护、运行环境及产物身份。骨骼语义、动作范围、映射、根运动和形变规则来自选用的领域 Skill。 [工作区通用规则](../upstream/1.2.11/archived-p0/resources/runtime/templates/AGENTS.md#操作规则)

| 归档入口或安装包参考 | 选用条件与作用 |
| --- | --- |
| [rig-retarget / SKILL.md](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) | 本节点主 Skill。保留认可的几何、贴图和蒙皮，按实际关节与休止空间适配动作，先求值、烘焙再按需组织 NLA。主要面向 T/A-Pose 人形角色。 |
| [existing-rig.md](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/existing-rig.md:49>) · [retarget-api.md](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/retarget-api.md>) | 采用已有骨架通用路线时，核对映射、目标兼容性、根位移、条件 IK、Action 及函数契约。这两份是随包参考，尚未进入当前仓库原文快照。 |
| [motion-and-hands.md](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/motion-and-hands.md>) | 仅在原比例骨架／BVH 路线或其时间、循环、掌腕与落地检查中使用。此安装包参考也未归档为仓库原文。 |
| [绑定与动作验收](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/validation.md) | 实际候选重开后，分别核对结构保护、指定范围数值、视口和目标格式；不得用保存成功代替动作通过。 |
| [游戏角色交付](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/game-delivery.md) | 明确需要游戏、LOD、影响数或引擎交付时追加相应检查；仅交 Blender 工程不自动增加这些任务。 |

动画编排包 `hi3d-model-gpt-animation` 在需要舞台、已有动作裁剪或其他专项时才另行选用，并显式交接独立 `rig-retarget`；它不是通用重定向的必经依赖。 [安装包编排入口](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d-model-gpt-animation/SKILL.md:17>)

## LLM Tools

| 独立工具说明 | 本节点的调用时机和条件 | 注册与核查范围 |
| --- | --- | --- |
| [exec](../tools/exec.md) · [exec_command](../tools/exec-command.md) | 读取输入及摘要、执行 Blender 重定向、重开检查或按任务范围取证。 | 随包 Codex 宿主工具。前序隔离测试运行了原包 CLI，留存生产会话没有本节点专项执行覆盖。 |
| [wait](../tools/wait.md) · [write_stdin](../tools/write-stdin.md) | 本地任务未结束时，分别用原 `cell_id` 或 `session_id` 续取同一执行。 | Code Mode 与 Unified Exec 的句柄分别处理，不能当作缓存或云端作业 ID。 |
| [view_image](../tools/view-image.md) | 有来自实际候选的指定姿势、近景或对照图时按需查看。 | 图片读取，候选身份、机位及帧号由取证记录绑定。 |
| [workflow_report](../tools/workflow-report.md) | 本轮实际选用 Skill 并维护图时，记录实际执行／复用、工程、配置、报告和待验项。 | Runtime 动态 LLM Tool。按现有规范图归属，`completed` 不校验 Action 或质量。 |
| [user_interaction](../tools/user-interaction.md) | 动作范围、根运动或旧动作替换意图仍有无法从现有任务确定的关键歧义时使用。 | Runtime 动态 LLM Tool，已有明确要求直接沿用。 |

`rig_adapter retarget` 是本地命令，`retarget_samples`、`bake_action` 是脚本函数；没有独立同名 LLM Tool，也没有 `run.py bake_action` 命令。正常本地重定向不调用 Hi3D／MDF 服务。模型可见 description 与工具通用实现由独立工具页维护。 [本地计算与烘焙函数](../resources/specialized-mesh-scripts.md#retarget_math-与-action-烘焙函数)

P0 启动包装、预算、摘要与计时由外层按需选用；专项 `run.py --timing-log` 使用随包物化的计时实现，不是持久恢复账本。`rig_adapter` 通过保护签名间接加载 P1 `skin_weights`，不因此自动执行权重归一、拉伸或完整动作 QA。`retarget_math` 是随包物化计算依赖，来源映射见 package，不能称为动态工具。 [P0 包装](../resources/README.md#专项-blender-命令的执行包装) · [P1 导入与调用](../resources/p1/README.md#rig-retarget-的导入与调用) · [发行映射](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/package.json:3>)

## Hi3D 实现

### 决策

1. **决定复用还是执行。** 上游已烘焙候选的目标基准、缓存、实际映射、Action、fps、范围及保留项均与本次要求一致，且可重开核验时，可直接进入产物验收。复用判断由业务编排作出，源码没有自动查找或复用既有候选的幂等账本。身份或要求变化时重新核对，不能仅按文件名复用。
2. **固定本轮执行基准。** 新执行优先接收明确的校准目标工程；若使用已有动作候选替换，记录允许替换的所选 rig 范围，显式传 `--replace-animation`。旧动作数据块与其他对象的引用另保留。源动作缓存及校准配置变化时，先回上游确认，不在本节点偷偷改 rest 或重建蒙皮。
3. **选择兼容路线。** 通用 `rig_adapter retarget` 消费 v1 缓存及目标映射；旧 profile／BVH 分支按独立消费契约处理。已有目标 Action 满足用途时不强制重新计算。通用单 Action 烘焙不包含 NLA 序列、循环闭合或脚锁。

### 执行

#### 通用重定向与烘焙

**根据随包 CLI 重建的 PowerShell 请求，非生产调用记录。** 从包外任务目录运行。输入为上游核定的 `TargetRig`，缓存及 `mapping.json` 已验收；配置填实际目标 rest 和缓存摘要。帧起点、Action 名和路径为示例，输出与报告须尚不存在。旧动作确需替换时才追加 `--replace-animation`。

```powershell
$rigSkill = 'D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget'
& 'D:/install/blender/blender.exe' --background --factory-startup --disable-autoexec `
  --python-exit-code 1 --python "$rigSkill/scripts/run.py" -- rig_adapter retarget `
  --input './inputs/calibrated-target.blend' --rig 'TargetRig' `
  --cache './cache/source-motion.npz' --spec './config/mapping.json' `
  --action 'TransferredMotion' --frame-start 1 `
  --output './exports/hi3d-animated-candidate.blend' `
  --report './reports/hi3d-retarget.json'
```

`--input/--rig/--cache/--spec/--action/--output/--report` 均必填。`--frame-start` 为整数，默认 0；`--replace-animation` 默认关闭。该命令没有 `--fps` 或重新选择源帧范围的参数，采用实际缓存的样本数和 fps。所需时间改变时回源缓存节点重采样并重新核对映射。 [CLI 参数](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:389>)

| 步骤 | 已核实执行 | 本步检查及失败边界 |
| --- | --- | --- |
| 1. 打开固定目标 | 预检新输出和报告、创建父目录；禁用内嵌脚本打开目标工程，按精确名称选 Armature，记录工程与 rest 摘要。 | 输出、报告与输入及彼此区分；输入或对象失败可能只留父目录。路径函数不检查工作区根、后缀或并发锁，调用方仍明确使用独立 `.blend/.json` 路径。 |
| 2. 检查目标和身份 | 读取实际 spec、记录保护快照，执行目标 FK 门槛；核目标 rest 摘要，用 `allow_pickle=False` 读 NPZ，检查 v1 schema 和缓存字节摘要。 | 目标不兼容、旧动作冲突或身份不符即拒绝。不会回源验证缓存内的源摘要，spec 本身也未自动入报告摘要，调用方另外对账。 |
| 3. 计算目标样本 | 核源／目标层级、非空姿态数组及刚体矩阵，按 global／local、根位移及可选 IK 生成目标局部四元数和根 location。 | 映射缺骨、退化或非法结构可失败；未映射骨保持中性局部姿态随父运动。返回没有质量 `pass`，IK 误差无内置放行阈值。 |
| 4. 创建 Action | 要求全局新 Action 名和 layered Action slots 能力，清所选 rig 动画引用，写全部目标骨 quaternion 与根 location 的 LINEAR 关键帧，设 scale=1。 | helper 无整体回滚，失败可能留下部分内存编辑；不创建 NLA。旧 Action 数据块不主动删除。 |
| 5. 设置时间并另存 | `frame_end = frame_start + F - 1`；按缓存 fps 设置 scene fps／fps_base，在原保护时间比较资产，打包保存新工程并禁用脚本重开，再核保护。 | 数学函数不重采样；坏 fps 等可在计算或 Action 创建之后失败。保存后的重开／保护失败可能已有候选文件。 |
| 6. 写回执 | 记录 saved inventory、输出摘要、保护通过及姿势待验，再次核对原输入工程摘要，最后普通 JSON 写报告。 | 报告非原子、无独占锁，可缺失或不完整。stdout 仅位置摘要，不能代替完整回执或业务验收。 |

[路径与执行](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:273>) · [目标门槛](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:105>) · [保存重开](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:373>)

目标门槛要求刚体世界变换、无对象父级／对象约束／对象驱动、无 Pose 约束、普通 FK 继承、Armature 单用户且无数据动画。已有 Action／NLA 默认拒绝；允许替换时，关联动作包含非 `pose.bones[...]` 通道仍拒绝。本地 builder 新骨常设 `inherit_scale=NONE`，该适配器要求 `FULL`，不能假定任意本地绑定都能直接串接，更不能为通过门槛悄悄去掉约束或改变继承。 [结构门禁](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:105>) · [本地骨架设置](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/blender_core.py:41>)

计算按上游真实映射进行：`source_to_target` 是刚体变换，默认单位阵；global 依据源全局相对 rest 的变化，local 提取源父子局部增量后转换到目标轴，避免重复继承父骨运动。显式 `alignment_wxyz` 优先，否则同时给出源／目标端点时计算对齐方向；只有一个端点时仍会采用单位对齐，不能称作完整字段 schema 拒绝。未映射骨没有自动完整性检查。 [映射计算](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/retarget_math.py:99>)

根平移取源根当前相对 rest 的位移，按对应头点链长度比例缩放，加目标 rest 和 offset，不自动以首样本归零。`in_place` 清目标空间 XY、保留 Z，并同步调整 IK 目标；一个比例用于根和全部 IK。比例链不强制直接相连，但配置 `limbs` 的源／目标都须是直接三关节链。固定长度 IK 不拉伸，退化时用经校准的 fallback pole；不可达只报告 `max_limb_reach_error`。实际鞋底点和 `floor_z` 使用目标 rig 空间，向上补偿不等于脚锁或碰撞。 [根与条件 IK](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/retarget_math.py:219>)

**根据已核实实现重建的控制流伪代码。** 业务复用判断发生在命令调用之外；以下仅表示需要新执行的通用分支。省略参数解析，保留身份、计算分支、烘焙及落盘顺序。

```python
output = new_path(args.output, forbidden=[args.input, args.report])
report_path = new_path(args.report, forbidden=[args.input])
source = open_input(args.input)  # use_scripts=False
rig = selected_rig(args.rig)
rest = skeleton(rig)
report = initial_report(source, rig, rest)
spec = read_json(args.spec)
protected, original_time = snapshot_assets_and_time()
validate_target(rig, args.replace_animation)
require(spec["rig_sha256"] == skeleton_digest(rest))

cache = load_npz(args.cache, allow_pickle=False)
require(cache["schema"] == "rig-retarget-cache-v1")
require(spec["cache_sha256"] == file_digest(args.cache))
# 内部按 global/local、root 和可选 limbs 处理，归一化并连续化四元数。
quats, locations, details = retarget_samples(cache, rest, spec)
bake_action(rig, rest["names"], quats, locations, details["root"],
            args.frame_start, args.action)
set_frame_range_and_fps(args.frame_start, len(quats), float(cache["fps"]))

require_preserved(protected, original_time)
pack_and_save(output)
reopen_without_scripts(output)
require_preserved(protected, original_time)
report.update(details, fps=float(cache["fps"]),
              frame_range=current_frame_range(),
              cache_sha256=file_digest(args.cache))
report.update(saved_inventory=inventory(), output=str(output),
              file_sha256=file_digest(output),
              protected_assets_preserved=True, pose_qa_pending=True)
require(file_digest(source) == report["input_sha256"])
write_json(report_path, report)
```

`bake_action` 检查的是 slots 能力，不是严格 Blender 版本号；本机 4.5.16 LTS 已通过合成测试。它创建 Action／OBJECT slot／layer／KEYFRAME strip／channelbag，用批量 F-Curve 写全骨旋转与根平移；相邻四元数符号连续在前面的数学函数中完成。分数 fps 用 `render.fps=round(fps)`、`fps_base=round(fps)/fps` 表达；`F/fps` 播放时长与 `(F-1)/fps` 首末采样差分开记录。 [烘焙 helper](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:229>) · [四元数输出](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/retarget_math.py:293>)

保护快照覆盖场景中有多边形的 Mesh：基础几何、面角拓扑、UV、shape key、材质槽和面分配、全部顶点组及成员顺序／权重；并核对支持类型的图片内容。骨父级道具比较局部变换、父级逆矩阵及挂接关系，允许随新动作移动。它不完整覆盖材质节点图、全部修改器／驱动、零面 Mesh 或所有对象属性。保存前后在同一原帧／subframe 比较，不等于全帧动画检查。 [保护实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:54>)

完整报告含 `input_sha256/rig_sha256/rig`、`scale/max_limb_reach_error/frames/root`、`fps/frame_range/cache_sha256`、`saved_inventory/file_sha256/output/protected_assets_preserved/pose_qa_pending`。Action 名主要通过实际 inventory 和工程对账，配置、源依赖、保留项及其摘要由调用方补充。缓存内 `input_sha256/rig_sha256` 不会在此回源复核，`sample_frames` 也不驱动再次重采样。 [报告构造与 stdout](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:340>)

#### 条件性的旧 BVH／profile 路线

此路线只适用于实际采用旧比例骨架和 profile 的任务。旧四字段缓存 `names/rest/poses/fps` 交 `motion.build_action`，不能补一个 schema 后冒充通用 v1 缓存。源缓存制作及字段边界由[固定并求值源动作](fix-and-evaluate-source-motion.md#旧-bvh-缓存)维护；本节点核对实际消费和动作组织。

| 步骤 | 已核实实现与验收边界 |
| --- | --- |
| 选择样本与映射 | `samples=[start,end]` 表示零基、右端不含的缓存索引；实现将 profile 和缓存 fps 均转为整数后比较，不是小数采样率的精确一致校验。依赖 `motion_map` 和固定比例骨语义，不自动识别任意服务骨架。 |
| 生成 Action | 按旧路线的 rest 修正和父骨空间计算。根 XY 基于所选首样本，身体 Z 有独立高度规则，与通用 rest 位移语义不同。整掌 `hand_offset` 不提供独立分指或音乐同步。 |
| 条件落地与循环 | `ground` 默认非循环为 `true`、循环为 `"source_flight"`。按实际目标网格在 rig 空间的最低点修高，`source_flight` 保留源腾空量；不是脚锁。循环尾窗混合并追加闭合键，不证明速度、接触或自然度连续。 |
| 组织 NLA | `sequence_actions` 先烘全部 Action，再建 `CharacterPerformance` track；strip 取 `timeline_start`，repeat 默认 1，REPLACE、NOTHING，检查帧须避开动作 strips。 |
| 保存 | 在新绑定／拆件 builder 内保存工程，再写 manifest。动作列表可为空，manifest 存在不证明本次动作已生成。已有认可蒙皮不应为增加动作重跑整个 builder。 |

[旧动作实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/motion.py:89>) · [NLA 组织](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py:84>) · [旧路线落盘](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py:220>)

**根据旧 builder 重建的顺序伪代码。** 这是构建器内部组合，不是新增的 LLM Tool，也不表示可以无条件对已有目标重新构建。

```python
actions = [build_action(rig, row, profile, profile_dir)
           for row in profile.get("animations", [])]
clear_active_action(rig)
track = create_performance_track(rig)
for row, action in zip(profile.get("animations", []), actions):
    add_strip(track, action, start=row["timeline_start"],
              repeat=row.get("repeat", 1),
              blend_type="REPLACE", extrapolation="NOTHING")
require_inspection_frame_outside_strips(profile, track)
```

通用 Action 后若另需 NLA、裁剪或重排，单独记录实际编排及新的时间身份。`stage_ops clip` 是已有烘焙姿态裁剪，不是跨骨架重定向；原 NLA 求值后写新 Action／NLA，也不保证原 Bezier 子帧行为无损。本节点不把旧 builder 的自动 NLA 宣称为通用 `bake_action` 已有行为。 [裁剪实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d-model-gpt-animation/scripts/character/stage_ops.py:145>)

### 验收

| 阶段 | 放行条件 | 未通过及下游 |
| --- | --- | --- |
| 执行／复用决策 | 目标工程、当前 rest、实际缓存及配置身份、输出用途和范围一致；已有候选记录足以核对 Action 与保留项。 | 不符时回映射或源缓存准备；同范围合格候选可复用，不制造第二次烘焙。 |
| 目标及配置入口 | 实际绑定有效并满足选定适配器门槛；映射覆盖本次所需关节，左右、轴、根位移和单位有依据。替换范围明确。 | 缺映射或错语义回上游，复杂控制结构转专门适配，不用未映射骨的中性结果冒充已跟踪。 |
| 计算与 Action | 四元数、根平移及 IK 诊断与要求一致；实际 Action／slot 作用于所选 rig，非空且覆盖缓存全部要求样本；fps 和范围符合本次意图。 | 无运动、缺部位、根漂移、reach error 或循环问题按真实部位和帧定位。数值误差没有内置质量阈值，由任务尺度与接触要求判定。 |
| 保存与保护 | 独立重开确切候选，报告和文件摘要对应，动作可实际求值，认可几何、UV、权重、贴图、附件及其他必保项符合要求。 | 保存或 `protected_assets_preserved:true` 不能代替全部检查。保护范围外必保项另核；缺回执保留候选待补证。 |
| 时间组织 | 通用路线明确只有单 Action；有 NLA／循环／裁剪时核对实际 strips、混合、重复、Action slot、fps 和完整范围。 | 旧 strips 污染、端点或时间错误先修编排，再使受影响检查失效并复验。 |
| 下游接收 | 交确切工程及摘要、实际 Action 与受驱动目标、映射／缓存／来源引用、诊断和已验范围。明确 `pose_qa_pending` 与后续动作 QA。 | 最终交付前完成用途所需全段数值、视口及条件性的格式回读，不能把本节点候选称为任意动作都通过。 |

后续单身体可用 `service_rig inspect`，准备过的三角部件集合可用 `validate_blend`；它们不在本次 `retarget` 内自动执行。新非循环动作检查全部整数帧，循环检查完整周期及拼接姿态／速度；复杂接触按需补充子帧。拉伸、接缝、穿插、足底接触和自然度分别给结论，不以 `motion_observed` 或集合 `pass` 代替真实动作覆盖。Solidify 等改变求值拓扑时建立相应休止基准。 [单身体检查](../resources/specialized-mesh-scripts.md#service_rig-inspect-单身体蒙皮检查) · [集合检查](../resources/specialized-mesh-scripts.md#validate_blend-已保存工程的数值检查) · [验收规则](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/validation.md)

## 完成与恢复

| 当前状态 | 恢复方式及交接条件 |
| --- | --- |
| 本地 pending、输出截断或句柄丢失 | 原进程仍运行时按原句柄续读。句柄失效先核实际进程、日志、文件、摘要和回执，不重复启动同路径写入；计时记录不是动作任务恢复账本。 |
| 路径、目标、旧动作或 slots 门槛失败 | 保留原目标及诊断。核对真实对象和替换意图、兼容环境，改用新候选／报告／Action 名。复杂结构返回专门适配，不在失败进程里继续累积修改。 |
| rest、缓存或配置身份不符 | 目标 rest 改变回映射校准；源动作、采样或缓存变化回源缓存及映射核验。保留原文件及实际 spec 摘要，不改字符串摘要以掩盖不同输入。 |
| 数学或 Action 烘焙中断 | 当前内存可能已经清除动画引用或创建部分 Action，没有整体回滚。从原固定目标重新打开，使用新的产物路径及 Action 名；不能把半成场景回填。 |
| 工程已存，重开／最终源摘要／报告失败 | 保留实际候选并独立重开，核对 Action、时间、文件身份及属性。缺失证据标明缺口，另验能证明的范围；不足时保留该候选并从原目标另建一轮，不伪造原回执。 |
| JSON 部分写入或并发归属不明 | 普通写入可留下不完整报告；入口新路径检查与末尾写入之间没有锁。核可解析性、输入和产物身份、实际 Action 及本轮范围，不能只看文件存在。 |
| 已有候选可复用 | 重新对账当前要求、目标／配置／缓存身份、实际输出和检查覆盖；记录复用来源及仍待验项。若直接交最终用户，仍需完成当前用途的质量检查。 |
| 候选成功但动作验收失败 | 保留版本、异常部位和复现帧。先分清 rest／轴、mapping、根或 IK、NLA／时间组织及实际权重问题；按原因退相应节点，实际权重缺陷交[定位形变并局部修权重](locate-deformation-and-repair-local-weights.md)，另存后重验受影响范围。 |
| 需要导出或工作区版本 | `.blend`、NPZ、配置和报告按常规文件交接。游戏格式另验实际蒙皮与加载器；登记 GLB 用独立版本工具，登记、Studio 就绪和实际交付分别记录。 [登记边界](../tools/workspace-commit-model.md) |

本地重定向不生成云端 jobId。若上游绑定服务缺件或原提交不明，回[原绑定作业恢复](submit-and-recover-auto-rig.md#完成与恢复)保留原任务身份，不为本地烘焙失败重新提交绑定。缓存已落盘但缺报告的恢复归[源动作节点](fix-and-evaluate-source-motion.md#完成与恢复)。

## Vet3D 迁移与核查范围

### 供应商无关的交接契约

| 记录 | 应表达的业务语义 |
| --- | --- |
| 目标与保留基准 | 确切资产、骨架 rest、受驱动对象、绑定及必保属性、原件、允许替换的动作范围。 |
| 动作与映射身份 | 源工程／缓存及来源、采样时间与空间、角色映射及实际文件摘要、根运动和肢链策略。 |
| 执行或复用 | 同身份同范围复用依据，或新执行尝试、执行句柄、独立产物路径、Action 名及阶段结果。 |
| 动作产物 | 实际 Action／slot、帧段和 fps；有序列时附 NLA、循环／裁剪规则及确切工程摘要。 |
| 验收与交接 | 分开记录计算完成、文件保存、保护通过、实际动作求值、全段形变、视口和目标格式回读；保留失败点及待验项。 |

Vet3D 的 LLM、动作来源／生成模型、3D 模型及 API 尚待选型。业务层先定义上述语义，再由适配器对接具体模型与工具。执行前后对目标、缓存和配置取摘要，独占尝试目录、分别记录候选保存和报告写入，并按身份与范围判定可否复用，属于 Vet3D 设计建议，不能写成 Hi3D 已有的事务或自动幂等保证。

数学函数按名称及树结构工作，但没有自动四足语义。前后肢、趾行关节、尾耳、多段链、相贴部件及真实步态需另建映射和验收依据。双骨 IK 只覆盖明确的直接三关节链，不因小型人形夹具通过就宣称动物动画可靠。

### 安装包证据、样例与缺口

核查日为 2026-11-20。完整证据资源位于 `D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime`，manifest 声明 `1.2.11`、`win32/x64`；当前主安装目录缺少完整 resources，引用实际事务副本。 [版本 manifest](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) · [归档入口及版本说明](../upstream/1.2.11/README.md#确定-lod-源网格与分档预算的随包证据)

| 相对 `rig-retarget/` 的原件 | SHA-256 及证明范围 |
| --- | --- |
| [SKILL.md](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) | `8237ec25a4cf0b06a49723f21c168eee36f5848f64256fd357993d0a2b04f17d`；领域指导，归档与安装包字节一致。 |
| [scripts/rigging/rig_adapter.py](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py>) | `7f4bc80f4f268b4ff4b58764355fd5b7387e6e0ed9840186563f3f93cd9f04d7`；门槛、缓存消费、Action、保护与落盘。 |
| [scripts/rigging/retarget_math.py](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/retarget_math.py>) | `fe49ac3a4ec82f487fcbf28476b241f88889ba6ba40fe14dc21015b29cd1142b`；旋转、根、IK 和四元数计算。 |
| [scripts/rigging/blend_common.py](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/blend_common.py>) | `54b0d588c8bfda7cd3640e6c0227a9a88e093b0a287885c5811282444909b9dd`；载入、普通 JSON 和 inventory。 |
| [scripts/rigging/motion.py](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/motion.py>) | `ba8e6dd9abcd6508c4972ffc37d535cbb26663e4170658938b461199a8bc54cf`；旧比例骨架动作、掌腕、落地及循环。 |
| [scripts/rigging/build_character.py](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py>) | `95cae0d242467669756f53b15ea28eabb01648d6f3b217fd7ad5cc6a7aa6bf53`；旧动作 NLA 与构建产物。 |
| [scripts/rigging/test_retarget.py](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_retarget.py:107>) | `839640d8936e91eb186cc663984e00752488c7175b33ed35ef2ffb50345b964c`；合成回归的精确覆盖。 |
| [references/existing-rig.md](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/existing-rig.md>) | `05d54095a9392d332525765b73ccb8158190aca4975c132da946736a366f264b`；路线、参数与适配指导。 |
| [references/retarget-api.md](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/retarget-api.md>) | `686318b9cf45ce74f7a9f7beb5a310f80e08830b9af8cca44752c75fefb0f501`；数学、缓存与 helper 契约。 |

**已核实的隔离执行。** 前序核查在 Blender 4.5.16 LTS 运行未改写的随包 `test_retarget`，16 项合成检查通过。本次编写读取既有实际结果，没有把静态复核写成新增运行。夹具为三帧、七骨、小型单三角表面，覆盖 rest 对齐、local 手指、根比例、源对象运动／IK、offset／in-place、IK 后子骨继承、断链／缩放拒绝、固定肢长、道具及权重成员顺序保护、保存重开和计时。 [16 项结果](<C:/Users/11408/AppData/Local/Temp/hi3d-retarget-adapter-82e1313820034f23bbdde467fb0039d5/checks.json>) · [实际适配报告](<C:/Users/11408/AppData/Local/Temp/hi3d-retarget-adapter-82e1313820034f23bbdde467fb0039d5/adapt.json>)

**既有合成执行报告的字段摘录。** 只代表该夹具，不是生产角色质量或全部分支通过。

```json
{
  "scale": 2.0,
  "max_limb_reach_error": 0.0,
  "frames": 3,
  "root": "hip",
  "fps": 30.0,
  "frame_range": [10, 12],
  "protected_assets_preserved": true,
  "pose_qa_pending": true
}
```

**根据随包测试入口重建的 PowerShell 复核请求。** `--work` 必填且目录须尚不存在；此命令只复核上述合成断言，不包含真实导入器或生产动作验证。

```powershell
$rigSkill = 'D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget'
$probeWork = Join-Path ([System.IO.Path]::GetTempPath()) ('hi3d-retarget-' + [guid]::NewGuid().ToString('N'))
& 'D:/install/blender/blender.exe' --background --factory-startup --disable-autoexec `
  --python-exit-code 1 --python "$rigSkill/scripts/run.py" -- test_retarget --work $probeWork
```

**样例覆盖。** [样例工作区](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40>) 的三个登记 GLB 均无 `skins/animations/JOINTS_*/WEIGHTS_*`；两份关联会话未见本节点专项动作调用。它们不代表完整工具或分支集合。 [活跃会话](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl>) · [归档会话](<D:/download/.sparc3d-runtime/environments/prod/codex-home/archived_sessions/rollout-2026-11-11T11-24-05-01a1c8a2-5bab-7df0-8557-d36af12e8411.jsonl>)

**待实测。** 真实 BVH／VMD／MMD／FBX／GLB 导入及时间解释；复杂源 NLA 和目标控制结构；真实高模、修改器／驱动、多层衣物和完整动作；四足语义、趾行链、尾耳、步态、循环速度和脚底接触；目标引擎回读。保存后报告失败、并发路径竞争、坏 fps 晚期失败等是源码边界，尚未逐项故障注入；旧路线的实际来源动作、落地及循环质量也未由本合成测试覆盖。离线入口或本地合成通过不证明云端输出或生产视觉效果。
