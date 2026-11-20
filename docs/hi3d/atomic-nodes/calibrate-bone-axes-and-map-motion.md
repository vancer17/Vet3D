# 校准骨轴与动作映射

以 Hi3D Agent 1.2.11（Windows x64）为核查基准。此节点接收已核验的目标绑定，按实际关节与休止空间决定是否校准骨轴；动作分支再接收已核验源缓存，建立角色专属映射并烘焙新的 Action。随包主入口为 `rig-retarget/scripts/run.py -- rig_adapter`，保存成功仍返回 `pose_qa_pending: true`。 [归档 Skill](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) · [安装包适配流程](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/existing-rig.md>)

本页按实际实现拆分业务职责。随包 PCG 使用较粗的 `retarget`、`bake` 阶段，而 `rig_adapter retarget` 在同一命令中计算映射并烘焙 Action；图状态更新不会自动派发脚本或完成质量验收。 [随包架构](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/pcg/architecture.yaml:46>) · [工作流工具边界](../tools/workflow-report.md#已安装架构的加载范围)

## 业务定义

| 项目 | 契约 |
| --- | --- |
| 触发 | 已有可用绑定，需要向其适配已确定的动作，或实际骨轴问题影响目标动作。只需交付绑定且无轴向问题、无动作需求时不强制执行。 |
| 上游与输入 | 确切目标 `.blend`、Armature 与受驱动对象、原件及摘要、休止空间与单位、必保项。进入动作分支时另需源缓存、实际摘要、来源和时间／空间核验记录，以及目标动作范围、fps、根运动及允许替换的范围；仅校准骨轴不要求源缓存。 [绑定候选](review-rig-and-skinning-candidate.md#验收) · [高模回迁](transfer-skin-weights-to-approved-mesh.md#验收) · [源动作交接](fix-and-evaluate-source-motion.md#验收) |
| 图片角色 | 主图与补充方向图用于确认角色和必保外观；骨架覆盖图、姿势及动作近景来自实际目标候选，并关联文件身份、方向、机位和帧号。CLI 接收工程、缓存、配置和对象名，图片及保留项随验收记录交接，没有主图／参考图 API 槽位。 |
| 输出 | 可选校准候选及报告；绑定目标 rest 与源缓存身份的映射配置；新动作候选、Action／帧段／fps、根比例与 IK 诊断、保护及保存重开报告、明确的待验范围。 |
| 完成条件 | 对应分支的目标兼容性、配置及来源身份成立；实际候选可重开，轴向、绑定及保留项通过。动作分支另核实实际 Action、时间和映射覆盖；仅校准分支交新休止基准及待重烘状态。根据当前交接用途记录数值及视口检查，不把保存或保护成功当作全动作通过。 |
| 下游 | 交[重定向并烘焙动作](retarget-and-bake-motion.md)，固定本次要求范围的动作产物；同身份、同范围且已有充分证据的候选可直接复用核对，不要求重复运行同一命令。随后交完整动作与形变验收、局部问题诊断，或按约定交付 Blender 工程。需要游戏格式时另做导出和目标加载器回读；Studio 版本登记与实际交付各自执行。 [动作验收](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/validation.md) · [版本登记](../infrastructure/workspace/import-or-register-model-version.md) |

## Skill 绑定

通用入口负责确切工作区、文件定位、源文件保护、执行环境与产物身份；骨架语义、轴向、映射与动作范围来自选用的绑定领域 Skill。 [工作区通用规则](../upstream/1.2.11/archived-p0/resources/runtime/templates/AGENTS.md#操作规则)

| 入口或参考 | 选用条件及作用 |
| --- | --- |
| [rig-retarget / SKILL.md](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) | 本节点主 Skill。已有合格蒙皮继续复用；只有真实轴向问题才修改 rest，按角色确定关节映射、保留项与验收。原文主要面向人形角色。 |
| [existing-rig.md（安装包参考）](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/existing-rig.md>) · [retarget-api.md（安装包参考）](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/retarget-api.md>) | 作为主 Skill 的执行与接口参考，解释已有骨架、缓存接收、global／local、根位移及可选 IK。这两份参考尚未纳入仓库原文快照，按实际安装包路径复核。 |
| [绑定与动作验收](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/validation.md) | 保存重开后按实际目标拓扑、动作范围、接缝和接触分别取证；修改 rest 或映射后复验受影响范围。 |
| [游戏角色交付](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/game-delivery.md) | 仅在用途涉及游戏、LOD、挂点或引擎时追加目标格式、影响数及加载器检查。 |
| [motion-and-hands.md（安装包参考）](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/motion-and-hands.md>) | 仅在明确采用原本地 profile／BVH builder 路线时使用。其固定人形骨名、掌腕种子和根运动规则不能套用到通用适配器。 |

`hi3d-model-gpt-animation` 选用绑定能力时显式交接独立 `rig-retarget`，舞台、布料、裁剪和展示仍属其自身范围；它不是本节点的另一套绑定实现。 [安装包交接约定](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d-model-gpt-animation/references/rigging.md>)

## LLM Tools

| 独立工具说明 | 本节点调用条件和时机 | 注册与核查范围 |
| --- | --- | --- |
| [exec](../tools/exec.md) · [exec_command](../tools/exec-command.md) | 读取目标及配置、核对文件摘要、启动本地 Blender 校准和重定向命令。 | Codex 宿主工具；安装包及隔离回归证明本地实现，留存会话未覆盖本节点。 |
| [wait](../tools/wait.md) · [write_stdin](../tools/write-stdin.md) | 原执行仍在运行时，分别按 `cell_id` 或 `session_id` 续取同一执行。 | Code Mode 与 Unified Exec 的句柄分别使用。 |
| [view_image](../tools/view-image.md) | 有实际候选生成、身份及帧号明确的骨架覆盖图、关节近景或动作图时查看。 | 图片读取，不执行骨架或权重判定。 |
| [workflow_report](../tools/workflow-report.md) | 本轮实际选用 Skill 且维护其工作流图时，按现有图记录阶段、文件和待验状态。 | Runtime 动态 Tool；图状态不执行适配或质量检查。 |
| [user_interaction](../tools/user-interaction.md) | 是否替换已有动作、根运动用途或允许改动的范围无法由现有任务确定时收集选择。 | Runtime 动态 Tool；不能把配置 `calibrated:true` 当用户审批。 |
| [studio_load_revision](../tools/studio-load-revision.md) · [studio_get_state](../tools/studio-get-state.md) · [studio_capture_view](../tools/studio-capture-view.md) | 仅当需对已登记 GLB 取 Studio 视觉证据时，核对确切版本与就绪状态后截图。 | 桌面动态 Tool，不代替 Blender 工程中的 rest、Action、权重和求值检查。 |

`rig_adapter` 是本地命令，`retarget_samples`、`bake_action` 是 Python 函数，`global/local` 是映射模式。它们未作为同名 LLM Tool 注册。模型可见 description 与通用实现由独立工具页维护。P0 启动包装、进程预算与摘要资源可由外层选用；P1 权重资源由同包导入链间接加载，不表示重定向已自动完成数值 QA。 [已有骨架脚本](../resources/specialized-mesh-scripts.md#rig_adapter-已有骨架检查与调整) · [P0 包装与计时](../resources/README.md#专项-blender-命令的执行包装) · [P1 导入与调用](../resources/p1/README.md#rig-retarget-的导入与调用)

## Hi3D 实现

### 决策

1. **固定目标与用途。** 接收上游核对过的实际绑定、Armature、对象名单和保留项。只有动作适配时沿用原蒙皮，不因动作困难重新生成角色。源动作的导入、求值和缓存生产由[固定并求值源动作](fix-and-evaluate-source-motion.md)承载，本节点接受其验收输出。
2. **判断骨轴是否真有问题。** 以真实关节头和父子链识别左右及部位，显示骨尾异常但动作正常时可跳过校准。多分支掌骨不能任取首个子骨决定方向；T/A 差异、整体坐标对齐和本关节增量分别处理。
3. **确认兼容性与已有动画处置。** 下表是随包适配器的硬门槛。复杂目标需要显式适配，不可删除约束后声称原行为保留。若目标旧动作也是需要保留或再适配的来源，先从原工程固定并求值，再允许清除目标引用，不能在唯一副本中先清动作再寻找来源。 [目标门槛](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:105>)

| 门槛 | 已核实校验 |
| --- | --- |
| 世界变换与控制结构 | 目标世界矩阵须符合刚体容差；拒绝父对象、对象约束／驱动和 Pose 约束。 |
| 骨继承与共享 | 要求 `inherit_scale == "FULL"`、继承旋转及局部位置；Armature 数据单用户，数据本体不带动画。随包 `build_character` 默认设 `inherit_scale="NONE"`，不能未经核对直接串入。 |
| 已有 Action／NLA | 默认拒绝；只有明确允许替换才传 `--replace-animation`。所关联 Action 中存在对象通道时，即使允许替换也拒绝。 |
| 骨架与源缓存 | 精确选定实际对象；映射绑定当前目标 rest 摘要和实际缓存字节，不能复用其他角色或旧 rest 的配置。 |

### 执行

#### 条件性的骨轴校准

`rig_adapter inspect` 先取得当前骨架。摘要覆盖有序骨名、父索引和 rest 矩阵，不覆盖全部骨尾信息；同方向延长骨尾时摘要可能不变。只有需要改轴时，提供与当前摘要匹配的配置。`tail_at` 和 `tail` 同时存在时优先前者，采用当前骨架休止空间；滚转轴须有限且不平行于骨段。

**根据随包契约重建的校准 JSON 示例。** 骨名、方向和摘要必须来自当前角色；`calibrated` 必须是布尔 `true`，表示执行者完成了实际几何核验。

```json
{
  "calibrated": true,
  "rig_sha256": "<当前目标骨架摘要>",
  "bones": {
    "upper_arm.L": {
      "tail_at": "forearm.L",
      "roll_axis": [0, 0, 1]
    }
  }
}
```

脚本要求非空编辑列表、实际骨名、有限且非退化的尾点和轴；明确替换时清除所选 rig 的动画引用，再进入 Edit 模式修改 tail／roll。退出编辑模式后，以 `atol=1e-7, rtol=0` 核对全部关节头保持，报告前后骨架摘要及编辑骨名单。报告顶层 `rig_sha256` 仍是输入摘要，后续映射使用实际校准输出的 `after_rig_sha256`，或重开后重新 inspect 所得摘要。原 Action 数据块不主动删除。 [校准实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:142>)

#### 接收源缓存并建立映射

从上游取得可追溯、时间和空间已核验的 `rig-retarget-cache-v1` NPZ、配套报告和实际摘要。缓存生产的采样、导入和恢复以[源动作验收](fix-and-evaluate-source-motion.md#验收)为准。`retarget` 使用 `allow_pickle=False` 读取，检查 schema、配置中的 `cache_sha256` 和当前目标 `rig_sha256`。源 rest 为骨架局部 rest，缓存 poses 以固定首采样源骨架空间表达并含后续对象运动。来源元数据不是全部在消费时重新统一校验，故仍需保留上游核验记录。 [缓存接收](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:340>)

| 配置字段 | 必填／条件及语义 |
| --- | --- |
| `calibrated`、`rig_sha256`、`cache_sha256` | 必需。分别为严格布尔标记、目标 rest 指纹和实际缓存字节摘要。 |
| `mapping` | 非空，键为目标骨名，各项 `source` 指定实际源骨。模式 `mode` 默认 `global`，也可为 `local`；local 源骨须有父骨。 |
| `source_to_target` | 可省略，默认单位阵；为把源坐标转到目标休止坐标的单个刚体 4×4，不兼任比例缩放。 |
| `alignment_wxyz`／端点 | 显式四元数优先；否则同时给 `source_end/target_end` 时由两边关节头方向求对齐，其余情况用单位旋转。仅给单侧端点也不会触发方向对齐；方向不能单独确定全部 roll。 |
| `root` | 必需。指定真实无父骨的目标根、源根及两条对应头点链；两条链关节数相同且至少两关节，用于计算比例，不要求都是直接三关节链。`offset` 默认零，`in_place` 默认 false。 |
| `limbs` | 可省略。每项源／目标都须为直接相连的三关节链，并提供有限非零 fallback `pole`。 |
| `sole_points/floor_z` | 仅在有实际鞋底点和地面依据时设置；使用时检查有限性。`preserve_flight` 默认 true。 |

**根据随包契约重建的映射 JSON 示例。** 假定目标 `pelvis` 是真正无父骨的根，示例仅展示字段形状。实际应逐项覆盖本次用途需要的双侧、躯干和手指；未列出的骨不会自动视为已跟踪。

```json
{
  "calibrated": true,
  "rig_sha256": "<实际目标 rest 摘要>",
  "cache_sha256": "<实际 motion.npz 摘要>",
  "source_to_target": [[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]],
  "mapping": {
    "pelvis": {"source": "Hips"},
    "upper_arm.L": {
      "source": "LeftArm",
      "source_end": "LeftForeArm",
      "target_end": "forearm.L"
    },
    "index.1.L": {
      "source": "LeftIndex1",
      "mode": "local",
      "alignment_wxyz": [1, 0, 0, 0]
    }
  },
  "root": {
    "target": "pelvis",
    "source": "Hips",
    "source_chain": ["LeftUpLeg", "LeftLeg", "LeftFoot"],
    "target_chain": ["thigh.L", "shin.L", "foot.L"],
    "offset": [0, 0, 0],
    "in_place": false
  },
  "limbs": [{
    "source_chain": ["LeftUpLeg", "LeftLeg", "LeftFoot"],
    "target_chain": ["thigh.L", "shin.L", "foot.L"],
    "pole": [0, -1, 0]
  }]
}
```

映射硬校验要求骨名和父级合法、矩阵及维度有效、帧数非零；矩阵按容差拒绝缩放、剪切和反射。`mapping` 只要求非空且所引骨名存在，未映射骨随目标父骨保持中性局部姿态，**没有硬校验必须覆盖全部身体或手指**。覆盖完整性由本次任务和实际动作验收确定。 [配置校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/retarget_math.py:99>)

#### 旋转、根位移与条件 IK

`source_to_target=B` 先左乘源 rest 和各帧 pose，把两者置于同一目标坐标。逐骨 `A` 则是目标中性方向到已变换源中性方向的校准旋转，两者职责不同。global 使用源全局相对 rest 的变化；local 提取本关节的父子增量，适合保留目标自然张开同时迁入屈指。最终还要转为目标父骨局部 basis，不能直接复制源 Euler 或四元数。

**根据实际实现重建的旋转公式。** `Rs/Ps` 为统一坐标后的源 rest／pose，`Rt` 为目标 rest，`Dt` 为目标期望姿态；下标 parent 表示父骨。以下仅表达旋转部分。

```text
global:
    Dt = Ps × inverse(Rs) × A × Rt

local:
    Ls = inverse(Rs_parent) × Rs
    Pl = inverse(Ps_parent) × Ps
    delta = inverse(Ls) × Pl
    C = inverse(Rt) × inverse(A) × Rs
    neutral = Dt_parent × inverse(Rt_parent) × Rt
    Dt = neutral × C × delta × inverse(C)

写入目标 pose bone 的局部 basis：
    q = inverse(Rt) × (Rt_parent × inverse(Dt_parent)) × Dt
    根骨省略父项；逐帧归一化并保持四元数符号连续。
```

根位移来自源根相对 rest 的位移，乘目标／源对应关节头链长度比例，再加显式 offset。通用适配器不自动以首动作帧归零；`in_place` 清除目标空间 XY 位移，Z 保留。offset 和 in-place 同步作用于 IK 目标，根 location 最后转入目标根局部轴。

可选 `limbs` 用目标实际链长做双骨 IK，源屈曲平面退化时才使用 fallback pole，不伸长骨段。鞋点分支仅按实际 `sole_points/floor_z` 做向上补偿。返回 `max_limb_reach_error`，非零值没有内置失败阈值；它不是脚锁、接触估计或碰撞求解。IK 改变父骨后，未映射／local 子骨重新继承局部关系，global 保持所请求的绝对朝向。 [旋转与 IK 实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/retarget_math.py:190>)

#### 具体执行与保存

**根据随包 CLI 重建的 PowerShell 请求。** 从任务目录运行，输入和 `motion.npz` 已通过上游验收，配置填实际摘要；仅有真实轴向问题时执行第一条。跳过校准时第二条的输入改用原已核验目标。已有动作确需替换才添加 `--replace-animation`，不要将其作为默认参数。

```powershell
$rigSkill = 'D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget'
$blender = 'D:/install/blender/blender.exe'
$launch = @('--background', '--factory-startup', '--disable-autoexec',
            '--python-exit-code', '1',
            '--python', "$rigSkill/scripts/run.py", '--')

& $blender @launch rig_adapter calibrate `
  --input 'target.blend' --rig 'TargetRig' --spec 'axes.json' `
  --output 'calibrated.blend' --report 'calibration.json'

& $blender @launch rig_adapter retarget `
  --input 'calibrated.blend' --rig 'TargetRig' `
  --cache 'motion.npz' --spec 'mapping.json' `
  --action 'TargetMotion' --frame-start 1 `
  --output 'animated.blend' --report 'retarget.json'
```

`bake_action` 检查新 Action 名不存在，并检测 `Action.slots` 能力，不按严格版本号分派。它清除所选 rig 的动画引用，重置 pose rotation／location／scale，批量写全部目标骨的 quaternion 和所选根的 location，采用整数帧、线性插值，设置场景范围及实际 fps/fps_base。输出 layered Action，不创建 NLA，不自动添加音乐、检查段或渲染。 [烘焙入口](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:229>)

**根据已核实实现重建的控制流伪代码。** 配置、源缓存和目标的业务核验在进入对应调用前完成。

```python
output, report_path = require_new_distinct_paths(input_path, output_path, report_path)
source, rig, rest = open_and_inspect_target(input_path, rig_name)
source_sha = file_digest(source)
protected, original_time = snapshot_protected_assets_and_time()
validate_target(rig, replace_animation)
if operation == "calibrate":
    result = calibrate_axes(rig, axes_spec, replace_animation)
else:
    require(mapping_spec["rig_sha256"] == skeleton_digest(rest))
    cache = load_npz(cache_path, allow_pickle=False)
    require(cache["schema"] == "rig-retarget-cache-v1")
    require(mapping_spec["cache_sha256"] == file_digest(cache_path))
    quats, locations, result = retarget_samples(cache, rest, mapping_spec)
    bake_new_action(rig, quats, locations, result["root"], action_name, frame_start)
    set_output_time_range_and_fps(cache, frame_start, len(quats))
require_assets_preserved(protected, original_time)
pack_and_save(output)
reopen_without_embedded_scripts(output)
require_assets_preserved(protected, original_time)
result.update(saved_output_report(output), pose_qa_pending=True)
require(file_digest(source) == source_sha)
write_json(report_path, result)
```

保护覆盖场景非空 Mesh 的基础几何、UV、shape key 坐标、材质槽与面分配、全部顶点组及成员顺序／权重，以及图片内容。骨骼父级道具改比较局部变换、父级逆矩阵和挂接关系，允许随动作移动；不是完整材质节点图、任意驱动或所有对象属性的保护证明。校准／烘焙后先在原时间复核，打包保存、禁用嵌入脚本重开，再复核保护与源摘要，最后普通 JSON 写报告。 [保护范围](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:54>) · [落盘顺序](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:373>)

#### 原 BVH／builder 专项分支

采用原 profile 骨架时，`cache_bvh → motion.build_action → build_character` 有独立的人形骨名和动作假设。旧缓存缺少通用 schema／层级／空间元数据；其根 XY 按所选首样本归零，掌腕可由整掌 `hand_offset` 覆盖，另有落地、循环尾窗及先烘全部 Action 再建 NLA 的编排。它不等于独立分指或通用服务骨架映射。若需要这条路线，按其配置和实际产物验收，不能只改缓存 schema 冒充新适配器输入。 [专项原文](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/motion-and-hands.md>) · [旧动作实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/motion.py:89>)

### 验收

| 阶段 | 放行条件 | 未通过及下游 |
| --- | --- | --- |
| 目标与改轴决策 | 实际绑定及对象名单有效，真实关节与休止空间有依据，满足适配器门槛；只修改确有问题的轴。 | 复杂控制结构转专门适配，空间／骨架错误回输入核验，保留原蒙皮。 |
| 骨轴候选 | 配置与实际目标一致；关节头、几何、权重和必保项保持；重开后记录新 rest、头尾及编辑名单。 | 失败保留诊断，重新标定。只同向延长骨尾也记录编辑，不以摘要相同推断未改。 |
| 缓存与映射 | 上游来源／时间／空间证据有效，当前缓存字节与目标 rest 匹配；映射实际覆盖本次所需关节，坐标变换、比例、根语义及局部／全局模式正确。 | 摘要不符重取实际身份；缺关节、错左右或重复分摊由当前角色重新校准。 |
| 烘焙与保存 | 实际候选可重开，存在预期非空 Action、正确 slot、帧段和 fps，真实骨架仍驱动预期网格，保护及源摘要成立。 | 保存或保护失败不回填完成；按已落盘范围恢复。报告无统一动作质量 `pass`。 |
| 姿势与动作 | 最终拓扑及完整目标范围的数值、关节近景、接缝与接触分开验收；IK 误差按当前尺度和用途判断，必要时修骨盆或步幅。 | 先区分 rest／空间／映射、不可达目标和权重问题，再修订对应范围。 |
| 下游接收 | 交确切工程及摘要、Action／时间、轴向和映射配置、缓存与来源引用、诊断、已验范围和待验项。 | 继续完整动作 QA 时明确 `pose_qa_pending`；最终交付须满足本次用途所需检查。 |

单身体可选 `service_rig inspect`，准备过的三角部件集合可选 `validate_blend`；两者不证明任意动作质量。新非循环动作检查全部整数帧，循环检查完整周期及拼接，按需检查接触切换。静态图、恒定非休止偏移或集合 `pass:true` 均不能替代实际动作覆盖；目标游戏格式另核实际蒙皮和影响数。 [单身体检查](../resources/specialized-mesh-scripts.md#service_rig-inspect-单身体蒙皮检查) · [集合边界](../resources/specialized-mesh-scripts.md#validate_blend-已保存工程的数值检查) · [验收规则](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/validation.md)

## 完成与恢复

| 当前状态 | 恢复与交接 |
| --- | --- |
| pending／输出截断 | 按原句柄续取。句柄失效先核对进程、日志、输入身份和实际文件，避免并发重跑同路径。 |
| 源缓存缺失、损坏或身份不符 | 保留当前目标与失败记录，返回源动作节点按其原来源和执行恢复；取得新缓存后重核映射归属。本地失败不触发新的云端绑骨请求。 |
| rest 改变或配置过期 | 从实际目标重新 inspect，按当前基准更新轴向／映射并重烘。源缓存未变且仍合格时可保留；缓存改变则重新核对映射摘要及动作范围。 |
| 目标不兼容或已有动作 | 不能绕过门槛宣称保留原行为。需要专门烘焙／隔离时另做；明确替换旧动作后仍从原输入另存，不覆盖已有候选。旧动作作为来源时先固定并求值，再清目标引用。 |
| 校准／烘焙中途异常 | 当前进程可能已改轴、清除引用或创建部分 Action，没有事务回滚。保留诊断，重新打开原有效输入，用新产物路径和新 Action 名执行。 |
| 工程已保存、报告缺失或不完整 | 重开核对文件摘要、真实 Action、绑定、保护和来源；缺失证据明确保留为缺口，独立补验不能冒充原回执。证据不足时保留候选并另建一轮。 |
| 报告存在但对象、摘要或范围不符 | 暂停回填，核对是否旧回执或并发写入。输出／报告虽要求新路径，但没有锁，普通报告写入可能留下半份 JSON；JSON 可读也不证明与当前候选配对。 |
| 数值／视口未通过 | 保存失败帧、部位、误差和配置。先排除轴向、父子空间、映射和 IK 可达性，再进入局部权重诊断；另存并重验受影响范围。 |
| 当前交接条件通过 | 以确切文件、摘要、Action、配置和检查范围回填。工程／JSON 是普通工作区文件；需要登记模型时另导出并回读 GLB，再按登记和交付契约执行。 [登记边界](../tools/workspace-commit-model.md) · [文件交付](../infrastructure/workspace/preview-and-deliver-files.md) |

## Vet3D 迁移与核查范围

### 供应商无关的交接契约

业务层保存目标绑定与休止基准、关节语义和覆盖清单、源动作及时间／空间来源、缓存和配置身份、根运动与 IK 意图、候选和检查范围。适配器再把这些语义映射为具体工具参数。目标 rest 身份、源动作字节身份、映射覆盖、执行状态、保存保护和最终质量分别记录。

Vet3D 的 LLM、生成／绑定模型和 API 仍待选型。建议以独占尝试目录管理输出，关联实际文件摘要与阶段；明确缺映射和不可达误差的业务失败阈值，避免把底层“允许输出”当质量通过。这些是迁移设计建议，不是 Hi3D 已实现的强制状态机。

四足的前后肢、肩胛、骨盆、足端、耳尾和独立软层需要另建语义与动作证据。随包通用数学和恢复方法可参考，人形种子、掌腕短句及双腿接触假设不能直接证明四足可用。

### 安装包证据、样例与缺口

核查日为 2026-11-20，实际完整原件位于 `D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime`，manifest 为 `1.2.11 win32/x64`。主安装目录资源不完整，采用实际事务副本。Skill 入口及归档参考保留原字节，未归档执行参考与脚本通过安装包链接和下表固定。 [版本 manifest](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) · [归档说明](../upstream/1.2.11/README.md#确定-lod-源网格与分档预算的随包证据)

| 相对 `rig-retarget/` 的来源 | SHA-256 |
| --- | --- |
| [SKILL.md](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) | `8237ec25a4cf0b06a49723f21c168eee36f5848f64256fd357993d0a2b04f17d` |
| [scripts/rigging/rig_adapter.py](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py>) | `7f4bc80f4f268b4ff4b58764355fd5b7387e6e0ed9840186563f3f93cd9f04d7` |
| [scripts/rigging/retarget_math.py](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/retarget_math.py>) | `fe49ac3a4ec82f487fcbf28476b241f88889ba6ba40fe14dc21015b29cd1142b` |
| [references/existing-rig.md](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/existing-rig.md>) | `05d54095a9392d332525765b73ccb8158190aca4975c132da946736a366f264b` |
| [references/retarget-api.md](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/retarget-api.md>) | `686318b9cf45ce74f7a9f7beb5a310f80e08830b9af8cca44752c75fefb0f501` |
| [scripts/rigging/test_retarget.py](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_retarget.py>) | `839640d8936e91eb186cc663984e00752488c7175b33ed35ef2ffb50345b964c` |

- **已执行的合成回归。** 前序核查以未改写随包 `test_retarget` 在 Blender 4.5.16 LTS 运行，16 项结果均为 true，覆盖 rest 对齐、local 手指、根比例、源对象运动／IK 求值、固定链长、断链与缩放拒绝、权重顺序、保存重开及耗时记录。 [实际 checks.json](<C:/Users/11408/AppData/Local/Temp/hi3d-retarget-audit-722b3e5c5b2a434ebd672a9dcb8a3090/checks.json>) · [测试断言](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_retarget.py:107>)
- **仅源码核实的边界。** 映射缺项保持中性、IK 误差没有整体失败阈值、全部缓存元数据未统一重验、普通报告写入及失败落盘顺序，按上述实现说明复核；不能扩写为所有异常均已实测。
- **留存样例范围。** 三个登记 GLB 无 `skins`、`animations`、`JOINTS_*` 和 `WEIGHTS_*`；关联两份会话不覆盖本节点专项适配。它们是静态资产和通用交互示例，不代表工具或分支全集。 [样例工作区](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40>) · [活跃会话](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl>) · [归档会话](<D:/download/.sparc3d-runtime/environments/prod/codex-home/archived_sessions/rollout-2026-11-11T11-24-05-01a1c8a2-5bab-7df0-8557-d36af12e8411.jsonl>)
- **待实测。** 生产宿主中的实际选路与长任务恢复；真实四足关节及步态、完整手指、复杂控制 rig、修改器／驱动和材质组合；所有鞋底／循环／旧 builder 条件；跨部件形变、衣层、接触和目标引擎回读。合成通过不证明真实动作或最终画质。
