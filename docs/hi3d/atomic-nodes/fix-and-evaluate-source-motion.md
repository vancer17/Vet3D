# 固定并求值源动作

以 Hi3D Agent 1.2.11（Windows x64）为核查基准。通用入口 `rig-retarget/scripts/run.py -- rig_adapter cache` 把已准备源 Blender 工程中的指定骨架求值成动作缓存。旧 `cache_bvh` 另为原比例骨架构建器提供 BVH 缓存。两种缓存的时间、空间和消费契约分别记录；目标映射、目标 Action 烘焙及最终蒙皮验收在后续完成。 [归档 Skill](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) · [安装包源动作指导](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/existing-rig.md:35>)

本页是对真实实现的业务拆分。随包 PCG 使用较粗的 `retarget`、`bake` 阶段，没有独立命名为本页标题的自动状态机。图状态更新不派发缓存命令，也不验证动作质量。 [随包架构](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/pcg/architecture.yaml:46>) · [工作流工具边界](../tools/workflow-report.md#已安装架构的加载范围)

## 业务定义

| 项目 | 契约 |
| --- | --- |
| 触发 | 已确认本次动作意图及来源，需要为目标角色映射固定源动作；或要复用与本次来源、时间及求值条件一致的已验收缓存。 |
| 上游与输入 | 原始动作文件及身份、来源与使用依据；准备好的源工程、精确源 Armature、实际动作栈、单位和轴向；源帧范围、有效场景 fps 与可选时间解释覆盖、输出 fps。目标角色身份、用途和保留项随任务交接。 [用途与路线](confirm-rigging-purpose-pose-and-route.md) · [候选绑定交接](review-rig-and-skinning-candidate.md#验收) |
| 图片角色 | 主图和补充方向图用于确认目标角色及必保外观；源动作视频或截图辅助选择及对照，实际求值证据来自源工程并关联骨架、样本和视向。本地命令没有图片 URL、目标方向或保留项槽位，这些语义随任务与验收记录传递。 [视觉取证](../infrastructure/workspace/acquire-model-visual-evidence.md) |
| 输出 | 通用路线交 `rig-retarget-cache-v1` NPZ、JSON 报告及缓存摘要；旧 BVH 路线交四字段 NPZ 和 stdout 摘要。两者均附调用方保存的来源、导入环境、时间与空间解释及验收范围。 |
| 完成条件 | 实际缓存可完整读取，来源、骨架、字段、时间和空间契约一致，覆盖本次选定动作。需要运动时已确认实际跨样本变化，缺失部位及静态段明确记录。缓存保存成功本身没有这些质量结论。 |
| 下游 | 通用缓存固定实际 `cache_sha256`，与确切目标工程及当前 rest 摘要汇合后交[校准骨轴与动作映射](calibrate-bone-axes-and-map-motion.md)；旧缓存交兼容的 profile 比例骨架 builder。接收者同时取得骨语义、坐标单位、实际样本范围和剩余缺口。仅缓存产物无需模型版本登记。 |

## Skill 绑定

通用工作区入口负责确切文件、原件保护、实际运行环境和产物身份。动作来源、骨语义、时间解释与求值检查来自选用的领域 Skill。 [通用工作区规则](../upstream/1.2.11/archived-p0/resources/runtime/templates/AGENTS.md#操作规则)

| 归档入口或参考 | 选用条件与作用 |
| --- | --- |
| [rig-retarget / SKILL.md](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) | 本节点主入口。已有绑定、服务骨架或本地绑定需要动作适配时选用。保留认可几何与原动作，先求值源约束、IK 和对象运动，再按目标 rest 建立映射。原文主要面向 T/A-Pose 人形角色。 |
| [existing-rig.md（安装包参考）](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/existing-rig.md:35>) | 通用源工程准备、VMD／FBX／GLB 条件、子帧缓存和后续映射契约。是领域参考文档，不是另一项 LLM Tool。 |
| [motion-and-hands.md（安装包参考）](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/motion-and-hands.md:3>) | 使用 BVH、旧 builder 或核对源时间时阅读；说明来源、单位、缓存索引与原帧号的区别。 |
| [retarget-api.md（安装包参考）](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/retarget-api.md:1>) | 核对函数、固定空间、新旧 schema 和消费者约束时使用。上述三份详细参考尚未进入当前仓库原文快照，按实际安装包路径复核。 |
| [绑定与动作验收](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/validation.md) | 规定实际文件身份、完整动作范围和后续质量证据。源缓存检查与目标角色全帧形变检查分别报告。 |

## LLM Tools

| 独立工具说明 | 本节点的调用时机和条件 | 注册与核查范围 |
| --- | --- | --- |
| [exec](../tools/exec.md) · [exec_command](../tools/exec-command.md) | 定位文件、读取摘要、启动 Blender 源盘点或缓存命令、读取实际 NPZ 与报告。 | 随包 Codex 宿主执行工具。前序隔离测试运行了随包脚本，留存生产会话不覆盖本节点。 |
| [wait](../tools/wait.md) · [write_stdin](../tools/write-stdin.md) | 原本地执行未结束时，按返回的 `cell_id` 或 `session_id` 续取同一执行。 | 分别属于 Code Mode 与 Unified Exec，标识不可互换。 |
| [view_image](../tools/view-image.md) | 已从确切源工程或缓存对照生成指定样本图时按需查看。 | 图片读取；源工程、骨架、帧号和机位由取证记录关联。 |
| [workflow_report](../tools/workflow-report.md) | 实际选用 Skill 并维护工作流图时，按现有图节点归属上报缓存、报告和待验项。 | Runtime 动态 LLM Tool。报告完成不证明缓存包含所需动作。 |
| [user_interaction](../tools/user-interaction.md) | 动作意图、来源选择或允许的替换范围仍有关键歧义且无法从现有任务确定时使用。 | Runtime 动态 LLM Tool。已有明确要求直接沿用。 |

`rig_adapter cache`、`cache_bvh` 是本地命令，`cache_rig`、`rigid_matrices` 是脚本函数，`rig-retarget` 是 Skill；没有同名缓存 LLM Tool 注册。模型可见 description 和通用实现由独立工具页维护。本节点正常本地执行不调用 Hi3D／MDF 服务。P0 启动包装、预算和摘要可由外层选用；`cache_rig` 自行进行子帧和依赖图求值，P1 `scene_samples` 不是必经入口。 [P0 包装](../resources/README.md#专项-blender-命令的执行包装) · [可选场景取样](../resources/p1/scene-samples.md)

## Hi3D 实现

### 决策

1. **固定来源与动作意图。** 保存原始文件、作者或转换来源、使用依据及字节身份，确认本次需要的动作段、身体部位、根运动和输出 fps。Skill 要求执行者核对来源及实际内容；脚本没有许可数据库、自动下载或动作质量分类。 [来源规则](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/motion-and-hands.md:5>)
2. **固定源工程的实际动作栈。** 通用 CLI 没有 `--action`、`--clip` 或 `--take`。在独立源工程中配置目标源骨架的活动 Action、NLA、约束／IK、对象运动和依赖，确认实际求值符合所选动作后保存。缓存综合求值，不自行挑选一条曲线。 [源工程准备](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/existing-rig.md:35>)
3. **选择消费契约并固定时间。** 已有服务骨架等通用映射采用 `rig_adapter cache`；原比例骨架 builder 可选旧 `cache_bvh`。固定源有效 fps、单位、轴向、起止帧与输出 fps。已有缓存只有在来源、动作栈、时间和空间证据仍匹配时才复用。

| 来源分支 | 进入执行前的检查 |
| --- | --- |
| 已有 Blender 动作 | 选定精确源 Armature，确认实际 Action／NLA 组合与帧段；不能只凭 Action 名称或“已绑定”判断。 |
| FBX／带动画 GLB | 通过适用导入器进入源工程，核对单位、轴向、动作及时间后保存，再执行通用缓存。CLI 不自动选择导入器。 |
| VMD／MMD | 提供匹配的参考骨架、控制骨／IK 及可信导入器，先正确求值。VMD 不是独立完整 rig，不能直接把脚 IK 曲线套给目标 FK 腿。 |
| BVH | 导入源工程后可用通用缓存；直接服务旧 builder 时可用下述旧路线。导入器须在当前 Blender 环境可用。 |

### 执行

#### 通用缓存

**根据随包 CLI 重建的 PowerShell 请求。** 在包外任务目录运行，源工程含已准备的 `SourceRig`，输出和报告尚不存在。帧段与 30 fps 为示例，实际请求采用本次确认值。

```powershell
$rigSkill = 'D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget'
& 'D:/install/blender/blender.exe' --background --factory-startup --disable-autoexec `
  --python-exit-code 1 --python "$rigSkill/scripts/run.py" -- rig_adapter cache `
  --input './inputs/source-motion.blend' --rig 'SourceRig' `
  --start 1 --end 121 --fps 30 `
  --output './cache/source-motion.npz' --report './reports/source-motion-cache.json'
```

`--input`、`--rig`、`--output`、`--report`、`--start`、`--end`、`--fps` 均必填。可选 `--source-fps` 覆盖源时间解释；省略时取场景 `render.fps/render.fps_base`，不会修改源场景 fps。输出以文件流写入，不依赖 NumPy 自动追加后缀；仍以明确的 `.npz` 命名。 [参数](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:389>)

| 步骤 | 已核实执行 | 本步检查与结果边界 |
| --- | --- | --- |
| 1. 打开固定输入 | 检查互不冲突的新输出／报告路径并创建父目录；用 `use_scripts=False` 载入源工程，按精确名称选 Armature，记录工程及骨架摘要。 | 名称、类型或文件不符失败；预建父目录可能保留。骨架摘要仅覆盖骨名、父索引及局部 rest。 |
| 2. 生成采样时间 | 按源时间解释与输出 fps 计算样本数及实际源帧，支持子帧。 | 末端仅在采样网格可达时包含，不额外拼帧。调用方另存请求范围，报告只记实际首末样本。 |
| 3. 求值到固定空间 | 要求源当前可见且为 POSE；逐子帧读取 depsgraph 已求值 Armature。全部骨骼进入缓存，包括控制骨。 | 源 IK、NLA、约束及对象运动进入结果；可见性只在开始检查。首样本世界矩阵与全部合成姿态接受刚体校验。 |
| 4. 写缓存 | 全部采样完成后，`output.open("xb")` 独占新建，压缩写 NPZ，再计算缓存摘要。 | 一次在内存收集后落盘，无逐帧追加和断点恢复；写入中断可能留下部分 NPZ。 |
| 5. 写报告 | 末尾再次核对源工程摘要，普通 UTF-8 JSON 写报告，stdout 返回简短位置摘要。 | NPZ 完成后仍可失败；报告写入非原子，无并发独占锁；此分支不保存源工程或生成目标 Action。 |

[路径与分支](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:273>) · [求值函数](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:198>) · [落盘与报告](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:311>)

**根据源码归纳的时间采样示例。** `source_fps` 的显式覆盖会改变步长，不能作为备注使用。脚本以 `or` 取值，因此显式 `--source-fps 0` 被当作省略；NaN／Infinity 没有完整统一预检，可能在计数或后续有限帧检查失败。调用方应在业务入口明确校验有限正 fps 和有限帧范围。

```python
source_fps = supplied_source_fps or scene.render.fps / scene.render.fps_base
count = floor((end - start) * output_fps / source_fps + 1e-8) + 1
sample_frames = start + arange(count) * source_fps / output_fps
```

**根据已核实实现重建的核心伪代码。** 省略分派和参数解析，保留固定空间、恢复时间及分步落盘。`rest` 仍来自原骨架局部静止矩阵，首动作姿势不替换 rest。

```python
require_new_output_and_report(input_path, output_path, report_path)
source = open_blend_without_scripts(input_path)
rig = require_named_armature(rig_name)
source_sha = file_digest(source)
data = skeleton_of_all_bones(rig)
rig_sha = skeleton_digest(data)
frames = build_sample_frames(start, end, output_fps, effective_source_fps)
require_nonempty_finite_frames(frames)
require_visible_pose_position(rig)
original = (scene.frame_current, scene.frame_subframe)
poses, anchor = [], None
try:
    for frame in frames:
        base = floor(frame)
        scene.frame_set(base, subframe=frame - base)
        evaluated = rig.evaluated_get(depsgraph)
        if anchor is None:
            anchor = require_rigid(evaluated.matrix_world)
        transform = inverse(anchor) @ evaluated.matrix_world
        poses.append([transform @ evaluated.pose.bones[n].matrix
                      for n in data["names"]])
finally:
    scene.frame_set(original[0], subframe=original[1])
data["poses"] = require_rigid(poses)
add_cache_metadata(data, frames, anchor, effective_source_fps,
                   output_fps, source_sha, rig_sha)
write_compressed_npz_exclusive(output_path, data)
report = make_cache_report(data, output_path, file_digest(output_path))
require(file_digest(source) == source_sha)
write_json_nonatomically(report_path, report)
```

锚点为首采样已求值 Armature 的世界矩阵。输出 `inverse(anchor) × current_world × pose_matrix` 把所有姿态放进固定的首采样源骨架空间：首样本对象世界放置被消去，后续相对对象运动保留；不自动把首姿势根位移归零。`finally` 恢复原帧及 subframe。源控制系统不受目标 `validate_target()` 的 FK 门禁，但最终合成矩阵须满足有限仿射、正交旋转及 det≈1，拒绝不符合契约的尺度、剪切和反射。 [矩阵检查](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/retarget_math.py:8>)

| 通用 NPZ 字段 | 含义 |
| --- | --- |
| `schema` | `rig-retarget-cache-v1`。 |
| `names`、`parents` | 全骨骼名称和父索引；消费者要求唯一名称、父先于子且根为 `-1`。 |
| `rest`、`heads`、`tails` | 源骨架局部静止数据，分别为 `B×4×4`、`B×3`、`B×3`。 |
| `poses`、`sample_frames` | `F×B×4×4` 已求值姿态及 `F` 个实际源采样帧。 |
| `fps`、`source_fps`、`source_world_at_first_sample` | 输出采样率、本次采用的源时间解释、固定世界锚点。覆盖源 fps 时，原场景有效 fps 需另存。 |
| `input_sha256`、`rig_sha256` | 源工程和骨架摘要；不覆盖原始动作文件、导入器、外部依赖及全部求值环境。 |

完整报告含 `input_sha256/rig_sha256/rig/output/frames/source_frames/source_fps/fps/cache_sha256`。`source_frames` 是实际首末采样。stdout 仅含 `operation/report/output/pose_qa_pending`；cache 的最后一项为 `null`，不是姿势通过结论。生产端没有回读 NPZ，也未完整核验 rest 和父级消费者契约。 [报告构造](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:319>)

#### 旧 BVH 缓存

**根据随包旧 CLI 重建的 PowerShell 请求。** 仅在原比例骨架 builder 路线使用；尺度和轴向需按实际 BVH 核实。下面 `0.0254` 是脚本默认值，不表示所有 BVH 都用英寸。

```powershell
$rigSkill = 'D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget'
& 'D:/install/blender/blender.exe' --background --factory-startup --disable-autoexec `
  --python-exit-code 1 --python "$rigSkill/scripts/run.py" -- cache_bvh `
  --input './inputs/source.bvh' --output './cache/source-legacy.npz' `
  --fps 30 --scale 0.0254 --forward=-Z --up Y
```

`cache_bvh` 必填输入和输出；默认整数 fps 为 30、尺度 0.0254、前向 `-Z`、上向 `Y`。它设置场景 fps，经 `import_anim.bvh` 用 `use_fps_scale=True` 和 `update_scene_duration=True` 导入，取当前对象的活动 Action 帧段，端点转整数后闭区间遍历，读取 pose 矩阵。仅写 `names/rest/poses/fps`，stdout 返回 `frames/bones/fps`。没有通用固定世界锚点、来源摘要或独立报告。 [完整旧实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/cache_bvh.py:10>)

旧入口不清空场景、不恢复帧、不重置 fps_base，没有通用刚体门禁。输出预检只检查原路径，NumPy 可能为无后缀路径追加 `.npz`，因此显式指定新 `.npz` 路径。写入非原子，失败可留不完整文件。下游 `motion.build_action` 要求缓存与 profile fps 一致；`samples=[start,end]` 是零基、右端不含的缓存索引，不能直接使用原 BVH 帧号。旧四字段不能只补 schema 就冒充通用缓存。 [旧消费契约](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/motion.py:89>)

### 验收

| 层次 | 放行条件 | 未通过与交接 |
| --- | --- | --- |
| 来源与导入 | 原始文件、来源记录、导入器及参考骨架明确；源工程实际动作栈和所选骨架对应任务，坐标及时间已核对。 | 回源准备，不把缓存脚本能运行当作导入正确。 |
| 时间与空间 | 请求范围、实际样本及源／输出 fps 与采样计划和公式对应；单位、rest、固定首样本空间和对象运动解释明确。区分 `N/F` 播放时长与 `(N-1)/F` 首末样本时差。 | 纠正源时间解释、导入尺度或空间后重新缓存，原候选保留。 |
| 实际文件 | 独立以 `allow_pickle=False` 读 NPZ，核对字段、骨数／帧数、数组形状、层级和有限矩阵；与报告、源及缓存摘要对账。 | 部分文件或缺字段不得交下游。回读属于调用方验收，不能说生产端已自动完成。 |
| 选定动作内容 | 需要运动时核对实际跨样本变化、关键部位及样本对照；静态段是任务有意保留还是缺失动作需明确。 | 无 Action／NLA 的静态骨架也能成功缓存，报告没有 `motion_observed` 或运动门槛。选错轨道、IK 不符或缺部位回源工程修订。 |
| 下游可消费 | 通用缓存带实际摘要、源骨语义、空间时间说明，交目标映射；旧缓存只交兼容 builder。动作栈和依赖变化会使旧证据失效。 | 下游用实际缓存摘要绑定映射，目标动作烘焙和全帧蒙皮 QA 继续单独验收。 |

消费者以 `allow_pickle=False` 读 NPZ，检查 schema 和映射中的 `cache_sha256`，再由 `retarget_samples` 核对骨名、父级、rest／poses 刚体及数组形状。没有独立完整 `validate_cache()`；`sample_frames`、`source_fps`、世界锚点及 NPZ 内来源摘要未逐项复核或用于再次重采样，输出 fps 直接取缓存。缓存可加载不代表全部时间和来源已验。 [消费入口](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py:344>) · [层级与形状门槛](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/retarget_math.py:99>)

## 完成与恢复

| 当前结果 | 恢复与下游条件 |
| --- | --- |
| 本地执行 pending 或输出截断 | 用原执行句柄续取，进程仍在运行时不并发重跑同路径。句柄失效先查进程、日志、实际缓存和报告。 |
| 路径、输入、导入器或源骨架失败 | 保留诊断；父目录可能已建。补齐可信导入能力、实际对象及准备工程，用新的缓存／报告路径重跑。 |
| 求值、时间或矩阵失败 | 帧与 subframe 由通用函数恢复，但不是源场景事务回滚。修正源动作栈、空间或时间，从固定源工程重新执行。 |
| NPZ 压缩写入中断 | 文件可能存在但不完整。保留失败件，独立检查，不按路径存在回填。没有逐采样恢复或追加入口，重做使用新路径。 |
| 缓存完成，源摘要核对或报告失败 | 保留 NPZ，按实际字节和源身份回读核验，明确缺失回执；不伪造原报告。证据不足从原固定源另建一轮。报告普通写入可能半截，并发者后来写入的同路径也没有锁保护。 |
| 已有缓存但未通过内容验收 | 保存缓存、异常样本和实际来源，回源工程修正。换 Action／NLA、约束／IK、对象运动、rest、导入环境或采样设置后重新生成摘要，更新下游映射。 |
| 旧 BVH 中断或恢复 | 保留源 BVH、实际导入参数与诊断，用干净独立进程及新缓存路径重跑。旧脚本无来源账本、独立报告或自动恢复。 |
| 可以回填或交下游 | 当前缓存通过本次来源、文件、时间空间和动作内容验收，按确切路径／摘要回填。交原始来源、源工程、骨架与骨语义、缓存报告、样本覆盖及待验项；不宣告目标动作或绑定质量通过。 |

通用源工程摘要在打开后记录、末尾对比，不是源与依赖的独占快照。外部库、插件及导入设置由调用方固定。可选 `run.py --timing-log ... --task-id ... --attempt ...` 位于 `rig_adapter` 前，记录阶段耗时，不提供断点续算。 [输入与写盘](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/blend_common.py:108>) · [命令计时](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/run.py:38>)

## Vet3D 迁移与核查范围

### 供应商无关的交接契约

| 记录 | 应表达的业务语义 |
| --- | --- |
| 动作来源与意图 | 原始动作及摘要、来源与使用依据、目标主体／用途、必保动作内容及预期运动部位。 |
| 固定的求值环境 | 源工程与骨架身份、选定 Action／NLA 组合、约束／IK、对象运动、导入器和外部依赖。 |
| 时间空间计划 | 实际场景有效 fps、采用的源时间解释、请求范围、输出 fps、实际样本、单位与固定坐标基准。 |
| 缓存尝试 | 输入身份、进程句柄、新输出／报告、阶段和失败点；采样、缓存落盘、报告落盘与验收分别记录。 |
| 下游接收 | 缓存类型、实际摘要、骨序与语义、检查覆盖和待验项；映射绑定同一缓存，目标烘焙与质量验收独立完成。 |

Vet3D 的 LLM、生成及动作模型／API 仍待选型。业务入口可先定义上述语义，适配器再调用具体导入和求值工具。建议显式验证有限参数、实际动作变化和完整缓存字段，为独立尝试预留目录，并把来源环境纳入复用依据；这些是 Vet3D 设计建议，不能写成 Hi3D 已实现的强制门禁。人形 Skill、合成骨架和刚体矩阵通过均不证明真实四足关节对应、步态、接触或次级运动适用。

### 安装包证据、样例与缺口

核查日为 2026-11-20。资源根为 `D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime`，manifest 为 `1.2.11 / win32 / x64`；主安装目录当前缺少完整 resources，本页使用实际事务副本。归档 Skill 与安装包同字节，未归档参考和脚本以固定路径及摘要复核。 [版本 manifest](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) · [仓库快照](../upstream/1.2.11/README.md#确定-lod-源网格与分档预算的随包证据)

| 相对 `rig-retarget/` 的证据 | SHA-256 |
| --- | --- |
| [SKILL.md](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) | `8237ec25a4cf0b06a49723f21c168eee36f5848f64256fd357993d0a2b04f17d` |
| [scripts/run.py](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/run.py>) | `ad7b270350d617baefd9d18ae8044db902b153502374cbecb61afaabdb4f7f6d` |
| [scripts/rigging/rig_adapter.py](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/rig_adapter.py>) | `7f4bc80f4f268b4ff4b58764355fd5b7387e6e0ed9840186563f3f93cd9f04d7` |
| [scripts/rigging/retarget_math.py](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/retarget_math.py>) | `fe49ac3a4ec82f487fcbf28476b241f88889ba6ba40fe14dc21015b29cd1142b` |
| [scripts/rigging/blend_common.py](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/blend_common.py>) | `54b0d588c8bfda7cd3640e6c0227a9a88e093b0a287885c5811282444909b9dd` |
| [scripts/rigging/cache_bvh.py](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/cache_bvh.py>) | `824c40407a96b38eabf2763487ffe446571e6093a8a6496bc07127c265cf6d16` |
| [references/existing-rig.md](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/existing-rig.md>) | `05d54095a9392d332525765b73ccb8158190aca4975c132da946736a366f264b` |
| [references/motion-and-hands.md](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/motion-and-hands.md>) | `3901b1731f41c2bd6b579710924a368315bd37157921f21a328001713efed701` |

**已核实的隔离执行。** 前序核查使用 Blender 4.5.16 LTS（`3f6797307da5`）及未改写的随包实现，未调用云端服务。随包运行参考建议 Blender 5.x；测试版本与运行约定分别记录。

| 证据 | 覆盖 |
| --- | --- |
| [随包 test_retarget](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_retarget.py:57>) · [16 项结果](<C:/Users/11408/AppData/Local/Temp/hi3d-source-cache-54af2857c76e480c9f387c7d719edbc5/checks.json>) | 小型合成源含对象运动和腿部 IK，实际缓存后映射、保存重开等 16 项通过。只证明夹具覆盖，不代表真实格式导入或全部 NLA 分支。 |
| [额外探针与结果](<C:/Users/11408/AppData/Local/Temp/hi3d-source-cache-54af2857c76e480c9f387c7d719edbc5/probe-results.json>) · [探针脚本](<C:/Users/11408/AppData/Local/Temp/hi3d-source-cache-54af2857c76e480c9f387c7d719edbc5/probe.py>) | 验证原帧 `1`／subframe `0.25` 恢复；场景 `24/1.001`、输出 30fps、源 `[0,2]` 得约 `[0,0.79920076,1.59840152]`；覆盖源 fps 为 60 得 `[0,2]`；NLA-only 与原活动 Action 求值一致；完全静态源仍成功生成三帧相同缓存。文件级探针核对原输入摘要未变。 |

**根据随包测试入口重建的 PowerShell 复核请求。** 工作目录名必须尚不存在，由夹具创建；只覆盖随包测试，不包含额外探针。

```powershell
$rigSkill = 'D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget'
$probeWork = Join-Path ([System.IO.Path]::GetTempPath()) ('hi3d-motion-' + [guid]::NewGuid().ToString('N'))
& 'D:/install/blender/blender.exe' --background --factory-startup --disable-autoexec `
  --python-exit-code 1 --python "$rigSkill/scripts/run.py" -- test_retarget --work $probeWork
```

**样例范围。** [留存工作区](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40>) 的三个登记 GLB 均无 `skins`、`animations`、`JOINTS_*` 或 `WEIGHTS_*`；两份关联会话没有提供专项源缓存轨迹。它们是示例，不代表全部工具或分支。 [活跃会话](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl>) · [归档会话](<D:/download/.sparc3d-runtime/environments/prod/codex-home/archived_sessions/rollout-2026-11-11T11-24-05-01a1c8a2-5bab-7df0-8557-d36af12e8411.jsonl>)

**待实测。** 旧 BVH 路线本轮只核对源码，未运行真实 BVH 导入器；真实 FBX／GLB／VMD 和 MMD 控制系统、复杂 NLA 混合与动画化约束开关、外部链接和插件依赖、长动作内存及中断恢复、跨 Blender 版本求值、真实四足源动作与下游步态接触均待验证。本页本地合成结果不证明生产动作质量或云端能力。
