# 局部结构修订

以 Hi3D Agent 1.2.11（Windows x64）及随包 Codex 0.166.0 为核查基准。节点从一个已有的网格版本出发，修补、改形或重建明确的局部结构。Hi3D 的工作区指令规定本地执行和登记方式，Agent 根据实际网格编写 Blender 脚本并选择验收证据。工作区 `asset_04fbdc40` 的真实记录覆盖一次胡须重建和一次跨版本脸部修复。

## 业务定义

| 项目 | 契约 |
| --- | --- |
| 触发 | 用户要求修补破损、改变局部轮廓、重建或替换部件，或已有候选因明确局部缺陷退回。整体造型升级回到生成入口。整模或独立部件的纯尺寸、位置、旋转调整交给[模型与部件变换](transform-model-and-parts.md)。同轮需要两类修改时按几何依赖安排，对同一最终候选验收。 |
| 上游与输入 | [主模型选定](select-primary-model-and-confirm-handoff.md)或[工作区版本目录](../infrastructure/workspace/query-assets-and-model-versions.md)交付家族与可读取的源版本。本轮要求给出目标部位、预期变化、保留项。若要从旧版取件，另确定供体版本、对象与装配关系。上游明确选用未登记的候选时，交接工作区、实际相对路径和摘要。留存脚本以路径、对象名和顶点索引取件。 [候选适用性](check-model-candidate-suitability.md) |
| 图片角色 | 用户照片可作为外观比对依据。历史局部修订以已登记 GLB 为母版，以同区域正面、侧面近景作为修改前后和候选证据。方向由脚本的相机位置、目标和文件名落实，保留项由会话与脚本约束。`view_image` 只接收要查看的本地图片路径，样本未调用生图接口传主图或附加参考图。 |
| 输出与完成条件 | 输出一份指向确切导出文件的已验收候选，附源版本、实际改动、保留项检查以及局部渲染证据。候选可读、目标部位及接缝达标、相关保留项有证据时，才交给下游登记。样本以 Agent 发起显式登记作为可观察的交接。 |
| 下游 | [版本登记](../infrastructure/workspace/import-or-register-model-version.md)发布正式版本。需要在 Studio 展示时，[指定版本加载](../infrastructure/workspace/load-studio-revision.md)单独确认就绪。后续绑定或动作用途接收正式版本及其仍待核查的条件。 |

## Skill 绑定

| 入口或依赖 | 作用与选用条件 | 本次证据 |
| --- | --- | --- |
| [工作区 `AGENTS.md` 模板](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:23>) | **通用工作区入口指令。** 指定家族版本选择、局部改动走本地 Blender、脚本与导出目录、米制标记、稳定部件名以及新 GLB 登记。属于 Runtime 模板。 | 本机历史第 246 行注入了已填入 Blender 绝对路径的工作区指令。 |
| [归档 `hi3d/SKILL.md`](../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md#3d-任务工作流) | **通用生成入口。** 用于上游生成、整体造型升级和生成结果的登记契约。同主体修订可沿用原分类。 | 首次生成轮读取了该 Skill。两次本地修订的几何算法来自任务脚本。 |
| [归档 `image-to-assembly/SKILL.md`](../upstream/1.2.11/prebuilt-skills/image-to-assembly/SKILL.md#开始与续接) | **装配领域 Skill。** 选用部件装配路线后，从最后有效产物继续，并执行该领域规定的接口、干涉及验收规则。 | 猫修订样本未选用。 |
| [随包 `body-spring-connector/SKILL.md`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/body-spring-connector/SKILL.md:18>) · [人像流程的鼻部移植](../upstream/1.2.11/prebuilt-skills/.dependency-portrait-reconstruction/references/execution.md#鼻部移植可选) | **专项路线。** 前者用于已有模型的躯干弹簧接口，带逐面来源与 UV 的减料可调用随包 `solid-edit`。后者在选定人像鼻部移植且有同源注册 donor 时调用随包 `nose-repair`。两个依赖都是本地执行入口。 | 安装包静态核查。`body-spring-connector` 入口和两个依赖未入仓库快照，猫样本未选用。 |

归档的 `hi3d` 与 `image-to-assembly` 原文已逐字节核对安装包，SHA-256 分别为 `4c268ae14ece561234682d564cdfa6264c1f121a9ea118137c0388a9240c217d` 和 `cf4ec08dec0decfd69560a940cc26ea18fecf559ea87852c269fd2682555705f`。 [快照范围](../upstream/1.2.11/README.md) · [实际指令注入](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:246>) · [solid-edit 依赖](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-solid-edit/REFERENCE.md:8>) · [nose-repair 依赖](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-nose-repair/REFERENCE.md:8>)

## LLM Tools

| 工具说明 | 用途与调用条件 | 实际修订轮 |
| --- | --- | --- |
| Codex [`exec`](../tools/exec.md) · [`exec_command`](../tools/exec-command.md) | 在 Code Mode 中分派本地命令。通过 shell 启动分析程序或 Blender，传入具体脚本路径。Blender、bmesh 及任务脚本是本地执行程序或代码。 | 实际调用。用于读取原件、生成脚本、执行修改与核对导出。 |
| Codex [`write_stdin`](../tools/write-stdin.md) · [`wait`](../tools/wait.md) | 内层命令返回 `session_id` 时，用 `write_stdin` 续查命令。外层 Code Mode 返回 `cell_id` 时，用 `wait` 取该单元的后续结果。 | 最终 Blender 用 `write_stdin` 续查。`wait` 在前期交互单元出现。 |
| Codex [`view_image`](../tools/view-image.md) | 把指定图片交给模型。检查修改前后局部外观时，传各张本地渲染图的实际路径。 | 实际读取修改前、候选及最终近景。 |
| 桌面 [`studio_get_state`](../tools/studio-get-state.md) · [`studio_load_revision`](../tools/studio-load-revision.md) | 当用户指向视窗里的版本或部件时读取当前状态。登记后需要展示时，按确切版本加载。 | 修订阶段实际读取状态，两个正式版本各显式加载一次。 |
| Runtime [`user_interaction`](../tools/user-interaction.md) | 母版指代、目标取舍或执行依赖需要用户补充时，按需发起交互。 | Blender 不可用时调用 `kind: "input"` 询问路径，后由用户在对话中告知已安装并继续。 |
| Runtime [`workspace_commit_model`](../tools/workspace-commit-model.md) | 候选验收后，提交选定 GLB 的家族名和导出路径。工作流需要显式归属时可提供 `workflowNodeId`。 | 两次均只传 `name` 与 `exportPath`。 |
| Runtime [`workflow_report`](../tools/workflow-report.md) · [`skill_capture_suggest`](../tools/skill-capture-suggest.md) | 有适用的工作流图时，按相应契约报告状态和产物。适合提议沉淀可复用做法时，可在完成后记录 Skill 建议。 | 两个局部修订轮均未调用 `workflow_report`。加载后两次提交 Skill 建议，回包 `recorded: true`，属于辅助记录。 |
| Runtime [`hi3d_api`](../tools/hi3d-api.md) | 上游生成整模，或用户明确要求整体造型升级时使用对应动作。 | 在猫模型初版生成时调用。两次本地修订均无 `hi3d_api` 或 `mdf_api` 调用。 |

## Hi3D 实现

### 决策

工作区默认以同家族数字序号最大版本为起点。用户指向视窗时，先核对实际加载的文件和部件。样本第一轮以 `hi3d-猫_1.glb` 为母版，经 Blender 读取 `geometry_0` 的 1,022,866 个顶点与 2,000,000 个三角面，并查看正面、侧面口鼻近景。胡须与脸部共用网格，Agent 决定定位局部顶点。第二轮用户指出 `_2` 胡须根部后方脸部破损，Agent 将 `_1` 的身体和 `_2` 已完成的左右细须分别列为来源。 [基线脚本](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/scripts/hi3d-cat-whiskers_1.py:8>) · [基线实录](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:281>) · [用户反馈](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:519>)

### 执行

1. **定位与直接改形。** `_2.py` 用 trimesh 按原索引加载首个几何体，把 GLB 坐标变换为 Blender 侧的 `(x, -z, y)`，按口鼻坐标框取子网格。左右沿横轴切片，筛选细小闭合截面，以截面质心和半径表征胡须。按相邻切片质心距离配对得 21 条轨迹，报告保存根、尖、半径和样本数。KDTree 按到中心线的距离选点，径向压细并让根部渐变过渡。`_3.py` 核对顶点顺序及未选位置，再写入 Blender。进程退出为 `0`，日志显示改动 47,087 个顶点，975,779 个未选位置在赋值前比较相同。正面和侧面近景仍出现断头与粘连残片，该候选留在 `exports/`。 [轨迹与掩码](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/scripts/hi3d-cat-whisker-analysis_2.py:7>) · [顶点校验](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/scripts/hi3d-cat-whisker-edit_3.py:11>) · [候选退回](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:366>)
2. **切除后重建。** `_4.py` 在口鼻窗口内按共享面扩张掩码，同步重合点索引，并清理在区域内的非主体连通分量。`_5.py` 删除 48,536 个旧顶点，对整个身体合并近重合点，再填局部窗口内的边界。补面 UV 取自相邻未补面的 UV 环，以该补面首个有效 UV 作锚点，从各顶点的邻面 UV 中选取离锚点最近的值。随后从报告取左右各 8 条根尖轨迹，沿三次 Bézier 曲线各生成 57 个逐渐变细的八边形截面，连接并封口。左右各输出一个独立胡须对象。Agent 根据根部纹理异常及边界检查修订后，最终日志记录 3 个补面、16 根胡须。中间轮曾查看正面和侧面，登记 `_2` 前的最后一轮检查实际查看了正面。 [清理掩码](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/scripts/hi3d-cat-whisker-cleanup_4.py:6>) · [重建与导出](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/scripts/hi3d-cat-whisker-rebuild_5.py:8>) · [最终重建回包与视图调用](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:477>)
3. **跨版本恢复结构。** 修补旧补面和扩大到脸颊的曲面拟合均产出过中间候选，实际出现了网格有效性警告、接缝折叠。Agent 改用 `_1` 身体，保留 `_2` 的细须。`_9.py` 以原版的凸包和局部拟合曲面收紧粗须删除掩码，划出中央鼻唇保护区，保存顶点索引及原法线。第一次恢复用 `holes_fill`，近景仍可见根部黑色开口和粗须残段。最终 `_12.py` 改为逐环封口，要求边界顶点度数为二并验证每个环为简单环，用反向绕序构造扇形三角面，在根部及新增补面上做加权平滑，恢复区域外的原顶点法线。最后一轮针对嘴角残段降低平滑区域下缘，在嘴角下方向内扩展平滑范围，并把迭代增到 180 次。 [有效性警告](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:617>) · [恢复准备脚本](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/scripts/hi3d-cat-face-preserve-prepare_9.py:8>) · [恢复候选退回](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:868>) · [最终结构修复脚本](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/scripts/hi3d-cat-face-finish_12.py:16>)

逐环封口先在 `_11.py` 执行。该候选已通过闭合检查，近景仍发现嘴角下方的粗须残段。`_12.py` 沿用封口算法并调整局部平滑范围。 [闭合版验收与修订命令](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:908>)

**根据实际脚本重建的伪代码。** 脚本从 `_2` 留取左右细须并移除其身体，再从 `_1` 导入身体。删除索引应用到 `_1` 身体。焊接遍历身体网格，平滑使用局部权重。补面分配专用材质。渲染用正面、左侧、右侧相机。导出选中身体和胡须，携带稳定部件名和节点 `extras.sparc3dPhysicalUnits = {version: 1, unit: "meter"}`。 [最终修复源码](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/scripts/hi3d-cat-face-finish_12.py:6>)

```python
whiskers = import_parts("hi3d-猫_2.glb", ["Whiskers_Left", "Whiskers_Right"])
preserved = snapshot_positions_world_matrices_and_face_counts(whiskers)
body = import_body("hi3d-猫_1.glb")
indices, original_normals = read_preservation_data()
assert len(original_normals) == body.vertex_count

delete_vertices(body, indices)
weld_vertices(body, distance=1e-6)
for ring in require_simple_boundary_rings(body):
    cap_with_triangle_fan(body, ring, opposite_winding_to_rim=True)

smooth_weighted_root_region_and_caps(body, iterations=180)
restore_outside_region_normals_by_source_index(body, original_normals)
assert all(edge.face_count == 2 for edge in body.edges)
body.set_uniform_scale(0.075)
body.set_custom_property("sparc3dPhysicalUnits", {"version": 1, "unit": "meter"})
assert snapshot_positions_world_matrices_and_face_counts(whiskers) == preserved

render_closeups(body, whiskers, views=["front", "left", "right"])
export_selected_glb(body, whiskers, export_extras=True)
```

### 验收

- **执行与几何。** `exec_command` 调用 Blender 后返回 `session_id: 89385`。Agent 对同一进程用 `write_stdin`，取得 `exit_code: 0`、12 个闭合环、8,650 个平滑顶点，另有 951,019 个可追溯源顶点的局部坐标差小于 `1e-7`。修复脚本断言身体边全部有两个邻接面，并另行断言保留胡须的顶点坐标、世界矩阵和面数。951,019 是测量计数，焊接仍可能影响局部窗口外的重合顶点。 [启动与续查](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:921>) · [几何断言](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/scripts/hi3d-cat-face-finish_12.py:60>)
- **外观与产物。** 最终脚本生成三个方向的图片，最终轮 `view_image` 实际回传正面和左侧图，另有 GLB 文件检查。登记后的 `_2` 与 `_3` 对比显示，两组细胡须的 `POSITION`、索引和世界变换一致，导出法线有轻微变化。两个版本的身体网格和 UV 有变化，三版的两张嵌入 JPEG 字节一致。 [最终取证记录](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:932>) · [已登记 `_2`](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/hi3d-猫_2.glb>) · [已登记 `_3`](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/hi3d-猫_3.glb>)
- **与登记交接。** 两次均由 LLM 传选定 `exportPath` 给 Runtime。同家族分类沿用 `tag4: null`，回复给出工作区根目录下的编号文件。两次正式文件均与各自的候选摘要一致。本地修订登记回包没有原云端 `source`。随后调用 `studio_load_revision` 并核对 `loaded: true`、`state.ready: true` 和确切版本名。 [首次登记](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:486>) · [最终登记与加载](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:941>)

**实际登记调用摘录，调整排版。** 这是 `_3` 的登记请求。`name` 为家族名，`exportPath` 是已检查的工作区相对路径。 [调用记录](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:941>)

```javascript
text(await tools.workspace_commit_model({
  name: "猫",
  exportPath: "exports/face-repair/hi3d-cat-face-repaired-final.glb",
}));
```

## 完成与恢复

| 情况 | 恢复与交接 |
| --- | --- |
| 进程或执行单元仍运行 | 用原 `session_id` 或 `cell_id` 续查对应层。中间图片已经落盘时可以先检查，等同一进程终态和完整候选到齐后再验收。 |
| 启动或执行结果不明 | 保留原母版、供体、脚本、预定导出路径及已有日志。优先查活跃句柄和文件，再决定是否以同一输入开新尝试。若上游云端生成的受理还不明，回原 `jobPath` 与已知任务 ID 核对，可用模型到齐后再进入本节点。 [原作业续查](locate-job-and-qualify-resume.md) |
| 进程成功，候选未通过 | 保留脚本、候选与具体缺陷证据，回到局部范围掩码或修订策略。已确认的部件可从旧候选或正式版本继续复用。修订候选应重新核对实际变化、接缝和保留项。历史中已有 `_2` 收到后续用户反馈，`_3` 通过后才成为新版本。 |
| 登记需要补分类或关联工作流 | 收到 `classificationRequired` 时补分类并沿用原导出。需要时传 `workflowNodeId`，分别核对归属与节点完成。Runtime 依据实际路径和下载摘要匹配可信云端来源，其余派生关系由调用方留存。 [导出登记与来源](../infrastructure/workspace/import-or-register-model-version.md#执行) |
| 已通过，待登记或登记回执不明 | 将确切路径及验收证据交给登记。若回执不明，先核对工作区版本目录和候选摘要。补分类或恢复登记时沿用原家族与原导出。 [登记恢复](../infrastructure/workspace/import-or-register-model-version.md#完成与恢复) |
| 已登记，待展示或待下游接收 | 使用正式版本 ID 核对下游引用。Studio 未就绪时可单独恢复加载，复用同一正式版本。需要用户确认或绑定验收的交付要求由相应下游完成。 [Studio 加载恢复](../infrastructure/workspace/load-studio-revision.md#完成与恢复) |

## Vet3D 迁移与核查范围

### 供应商无关的契约

Vet3D 可先定义 `修订意图`、`执行尝试` 和 `候选验收` 三份业务记录。修订意图固定工作区、家族、母版及可选供体、目标部位、修改范围与保留项。执行尝试记录每个源文件的摘要、部件标识、坐标空间、掩码与拓扑校验值、算子或脚本的版本、进程句柄和预定导出路径。候选验收保存候选摘要、视角与相机依据、检查范围和失败原因。换母版或拓扑时重建掩码或验证迁移映射。用户的五方向参考图可用作外观依据，局部验收镜头按需要覆盖目标部位和接缝，并和实际检查的候选绑定。

保留项按任务选择可验证的指标。局部改形可测区域外位置，重建可检查封口、接缝和贴图连续性，跨版本取件可核对部件的几何、位置及来源。目标是可动画四足模型时，还应按任务检查关节区域、权重、绑定姿态和实际运动变形。候选通过当前节点要求后，以其摘要交版本登记，再用正式版本 ID 交付下游。这里的业务记录不依赖 LLM、生图、3D 模型或具体 API。

### 复核步骤与证据边界

要复核最终脸部修订，将 `hi3d-猫_1.glb` 和 `hi3d-猫_2.glb` 放入隔离目录根部，把 `_12.py` 原样放到 `scripts/hi3d-cat-face-finish_12.py`，把留存掩码放到 `exports/face-repair/hi3d-cat-face-preservation-data.npz`。从隔离目录启动原版 Blender。复放首次胡须重建时，隔离目录的同家族根文件只放 `_1`，原脚本会动态取最大序号并将留存索引直接应用到它。 [Blender 指令模板](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:47>) · [原掩码文件](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/exports/face-repair/hi3d-cat-face-preservation-data.npz>) · [首次重建取件代码](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/scripts/hi3d-cat-whisker-rebuild_5.py:6>)

| 隔离复跑输入 | SHA-256 |
| --- | --- |
| `hi3d-猫_1.glb` | `b217a0365f827657cabcda90aa427d5830e153cd4a7cf3271831ff1c568fb9f5` |
| `hi3d-猫_2.glb` | `bf7731b779177d2f593965382f310e7382093e3e0c59e1015f0f2caf3f438649` |
| `hi3d-cat-face-finish_12.py` | `2237eee0a0497223874162a86d8fefb136541a82150d2a8472b08667899ef161` |
| `hi3d-cat-face-preservation-data.npz` | `f8fabe062ddd124f73b53764caf32c749b96625dd8601bd48173d43b60d28512` |

**隔离复跑命令。** 相比历史调用，复跑加 `--python-exit-code 1` 以单独捕捉未处理的 Python 异常。该命令只生成候选和近景，登记由宿主另行执行。 [历史命令](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:921>)

```powershell
& 'D:\install\blender\blender.exe' --background --python-exit-code 1 --python 'scripts/hi3d-cat-face-finish_12.py'
```

| 核查层次 | 结论与局限 |
| --- | --- |
| 安装包静态证据 | 工作区规则、领域依赖与登记链均可在版本 `1.2.11` 的事务备份复核。`runtime.mjs` 原始零基字节偏移 `2695691` 对应 `commitExport`，`3197771` 对应显式工具分派附近。Runtime SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`，ASAR 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`。 [版本清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) · [Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) |
| 历史运行与产物复验 | 已核实直接改形失败后的重建、跨版本身体恢复、两次登记与精确加载。最终候选与正式 `_3` 的 SHA-256 同为 `f2ac766e877a6c1754ac2f22c870c63e51543bcade8a0b862e379aa85ac4c238`。 [历史最终回包](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:930>) |
| 本机隔离复跑 | Blender 4.5.16 LTS（`3f6797307da5`）复现 12 个闭环、8,650 个参与平滑的顶点、951,019 个在脚本公差内位置未变的源顶点，细须保护断言通过。复跑 GLB 的 SHA-256 与正式 `_3` 不同，身体主要材质图元对应顶点的最大位置差约 `0.000014 mm`。证据覆盖留存输入到候选的执行。 [临时复跑日志](<C:/Users/11408/AppData/Local/Temp/hi3d-struct-replay-d1533e5ce2c24f57b058fd36d4db33b8/blender-replay.log:9>) |
| 待实测 | 本样本的坐标窗、选取的轨迹 ID 与阈值属于该资产。不同动物、姿态和拓扑的部位定位与脚本复用仍待验证。第一次胡须重建的最终回包只统计补面数，第二次验证的是修复时身体网格的边邻接，自交及最终 GLB 的全量拓扑另需取证。三版 GLB 均无蒙皮或动画，带绑定模型的权重与动作保留需另行实测。 |
