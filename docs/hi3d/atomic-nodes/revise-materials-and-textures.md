# 材质与纹理修订

以 Hi3D Agent 1.2.11（Windows x64）及随包 Codex 0.166.0 为核查基准。已有模型的定向材质修改由 Agent 编排 Blender 脚本。按参考图给已有网格重新生成纹理时，Runtime 通过 `hi3d_api` 提交独立纹理请求。两条路线均产出待验收的 GLB。留存会话与三个登记版本用于核对其中实际执行的分支。 [版本归档](../upstream/1.2.11/README.md) · [工作区模板](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:31>)

## 业务定义

| 项目 | 契约 |
| --- | --- |
| 触发 | 用户要求改已有模型的颜色、粗糙度等材质属性，修正局部纹样或贴图绑定，或为已有网格重新贴纹理。已选候选在外观验收中发现的问题也可进入本节点。改变轮廓、连接或拓扑时，先明确几何任务的输出，再对同一候选分别验收几何和外观。 |
| 上游与输入 | 源资产的确切版本、GLB 路径、目标对象或表面范围、待改通道、期望外观及必保项。普通入口默认从已确定家族的最新版本开始。用户点名历史版本时固定该版本。用户指向视窗时，在 `ready: true`、`assetId` 匹配的状态快照中读取实际加载的 `fileName`。返工时可用已选中但未登记的确切候选，并保留它与上游源版本的关联。 [模型版本查询](../infrastructure/workspace/query-assets-and-model-versions.md) · [当前视窗状态](../infrastructure/workspace/read-studio-state.md) |
| 图片角色 | 主资产是待修订的 GLB。局部修订可使用用户原图或源 GLB 中的贴图作为纹样依据，补充参考按表面和方向定位。在仅贴图请求中，参考图与方向分别用 `images` 和 `views` 传入。局部目标和必保项由本地脚本或验收承载，标准仅贴图请求未暴露这两类字段。验收渲染的相机方向单独记录。 |
| 输出与完成条件 | 输出候选 GLB、源版本、实际输入和绑定到候选 SHA-256 的验收证据。文件可重新载入、修改目标与必保项均通过检查后，候选可交登记，也可按确切路径和摘要供中间工程步骤使用。自动登记已发生时，仍须核对并验收正式文件。 |
| 下游 | 显式登记交接 `name` 和选定的 `exportPath`。通过回包路径重读正式文件并核对验收摘要，再交付确切版本名。绑定、动画和工程处理使用同一已核实的版本。需要在 Studio 展示时按该文件名加载。 [候选适用性](check-model-candidate-suitability.md) · [模型版本登记](../infrastructure/workspace/import-or-register-model-version.md) · [Studio 加载](../infrastructure/workspace/load-studio-revision.md) |

## Skill 绑定

**通用入口。** 工作区 `AGENTS.md` 是宿主注入的模板。它规定已有模型的局部材质修改优先复用现有资产，通过后台 Blender 执行。脚本放入 `scripts/`，结果导出到 `exports/` 下的新 GLB，保留以米为单位的标记 `extras.sparc3dPhysicalUnits` 和稳定部件名，再登记模型版本。 [随包工作区模板](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:31>)

| 仓库归档 Skill | 选用条件与作用 |
| --- | --- |
| [Hi3D 通用建模](../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md#默认行为) | 明确进入已有网格的云端仅贴图时，使用 v3.0、已有 GLB 和参考图，选择 `generation_type=texture`。按参数面板及 3D 任务规则处理后续。留存样本读取过该 Skill，远端生成使用的是 `both`，后续材质修订走本地执行。 |
| [图片到高精度组装模型](../upstream/1.2.11/prebuilt-skills/image-to-assembly/SKILL.md#主流程与阶段出口) | 仅在选用装配路线后应用其表面外观规则。若结构正确但原图上的文字、标识仍有问题，从用户原图做局部贴花或纹理修复，检查投影、UV 和朝向，保护周围材质。留存猫模型的局部取样使用的是已有 GLB 的贴图。 [装配审查与修复](../upstream/1.2.11/prebuilt-skills/image-to-assembly/references/multiview.md#审查与修复) |

安装包的 `.dependency-blender-tools` 和 `.dependency-texture-bake` 提供本地脚本依赖。重拓扑、LOD、发片等专项流程各自控制 UV、贴图或绑定的保留条件。公开 `mdf-api` 的 UV 和 LOD 是独立处理能力，其 Skill 明确限定了旧多视图、纹理渲染和烘焙服务的开放范围。 [随包静态资源与脚本工具](../infrastructure/bundled-assets-and-script-tools.md) · [材质 helper](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-blender-tools/scripts/material_nodes.py:5>) · [本地烘焙契约](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-texture-bake/references/contract.md:3>) · [随包 MDF Skill](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/SKILL.md:10>)

## LLM Tools

| 独立工具说明 | 在本节点的调用时机 | 安装包与实际记录 |
| --- | --- | --- |
| [`exec`](../tools/exec.md) · [`exec_command`](../tools/exec-command.md) | 读取源模型、运行后台 Blender、重开或渲染候选。PowerShell、Blender 和为任务编写的脚本是执行程序。 | 本地样本通过 Code Mode 调用。 |
| [`wait`](../tools/wait.md) · [`write_stdin`](../tools/write-stdin.md) | 分别续查未结束的 Code Mode 单元和返回 `session_id` 的命令进程。 | 本地 Blender 样本以 `write_stdin` 续查。 |
| [`hi3d_api`](../tools/hi3d-api.md) | 选定仅贴图时执行 `generate_3d`，按需用同一作业的 `query`、`wait`、`download` 续接。动作名与 `texture` 选项均属于同一 Tool 契约。 [仅贴图参数门禁](../tools/hi3d-api.md#仅贴图参数门禁) | 注册及组包已核实，留存样本只在初始生成段调用该 Tool。 |
| [`user_interaction`](../tools/user-interaction.md) | 缺少必须由用户确定的源版本、范围、关键参考或本地执行环境时，按需补齐。生成参数未齐时可能由 Runtime 直接发起偏好面板，使用其回包续调。 | 工具及 Runtime 面板均已核实。 |
| [`view_image`](../tools/view-image.md) · [`studio_get_state`](../tools/studio-get-state.md) · [`studio_capture_view`](../tools/studio-capture-view.md) | 查看本地渲染，或读取当前视窗的版本身份并按需截图。待登记候选可由本地 Blender 直接重开和取证。Studio 截图只有产物 ID 和尺寸，须另行确认实际路径、版本和观察方向。 | 样本用本地渲染及视窗状态取证。截图已核对注册、实现与离线画布测试，留存样本无截图调用。 |
| [`workspace_commit_model`](../tools/workspace-commit-model.md) · [`image_classification`](../tools/image-classification.md) · [`studio_load_revision`](../tools/studio-load-revision.md) | 登记选定候选并核对回包文件的摘要。登记缺标签时，可仅为本次登记传显式 `tag4`，或按需保存轮次分类。`image_classification` 同时更新同一工作区、同一线程和轮次已登记版本的分类元数据。需要展示时按核对后的确切版本加载。 | 样本实际登记和加载，同家族沿用 `tag4: null`。 |
| [`workflow_report`](../tools/workflow-report.md) | 选用已安装 Skill 的工作流时维护图状态与产物归属。登记参数 `workflowNodeId` 指向已有节点，节点完成状态由 `workflow_report` 上报。 | 已核对注册及分派。留存样本的调用发生在初始生成段。 [生成段工作流调用](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:171>) |
| [`skill_capture_suggest`](../tools/skill-capture-suggest.md) | 已完成修订并有可复用的操作经验时，可提议记录该做法。宿主接收建议后另行决定是否展示。 | 留存两次调用均发生于加载修订版之后，分别返回 `{"recorded":true}`。 [首次请求](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:504>) · [首次回包](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:507>) · [第二次请求](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:953>) · [第二次回包](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:956>) |
| [`model_retry_prepare`](../tools/model-retry-prepare.md) · [`hi3d_api` 免费重试](../tools/hi3d-api.md#免费重试与结果复用) | 用户明确要求对确切的已登记版本免费重试且满足来源、会话和额度条件时，以宿主提供或准备工具创建的 `retryRequestId` 执行 `retry`。需要传入新参考图和贴图设置时，使用 `generate_3d`。 | 已核对 Runtime 注册及重试分派。留存样本无此调用，原任务为独立贴图的免费重试结果待实测。 |
| [`mdf_api`](../tools/mdf-api.md) | 单独需要 UV 或 LOD 网格处理时，可由相邻步骤调用 `unwrap-uv` 或 `mesh-lod`，处理后的网格可作为后续输入。 | 已核对公开能力枚举，留存样本无此调用。 |
| [`studio_arrange`](../tools/studio-arrange.md) · [`studio_export_3mf`](../tools/studio-export-3mf.md) | 用户需要打印衍生版本时，在 Studio 摆盘并打开 3MF 打印计划。实际保存或发送由用户在面板确认。 | 已核对桌面注册及分派，留存样本无这两项调用。 |

## Hi3D 实现

### 决策

1. **锁定源和保护范围。** 固定家族、文件名、源路径和实际摘要。区分整模、对象、面区域或材质槽，检查哪些对象共享网格或材质，目标属性由常量还是节点连线驱动。对有非对称毛色的动物，单独固定左右方向及需要保留的标记。
2. **按编辑粒度选路线。** 定向调通道、修局部纹样或留住其他部位的外观时，使用本地 Blender。需要基于参考图给整个已有网格重新贴纹理时，使用 Hi3D 独立纹理选项。植入贴花所需的投影、目标面和周边保护由本地脚本控制。若上游已经改变拓扑，可在目标 UV 可用后从原表面转移贴图。 [工作区修订规则](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:23>) · [独立纹理参数](../upstream/1.2.11/prebuilt-skills/hi3d/references/desktop-parameters.md#独立纹理)
3. **核对宿主可达性。** `app.asar` 中的共享 Studio 编辑器含真实的涂绘和减面、修复后烘焙代码。桌面 `StudioHost` 隐藏头部和左工具栏，预览用 `viewer`，开放标签限于 `joint` 和 `arrange`，且未提供开启烘焙管理器的 `smartToolConfig`。该宿主的五个 Studio 动态工具为加载、状态、截图、摆盘和打印计划。已核实的宿主产物出口包括截图与 3MF，材质修订候选从 Blender 或 `hi3d_api` 路线进入 GLB 登记。 [ASAR 复核锚点](#安装包运行记录与缺口) · [模型视觉取证](../infrastructure/workspace/acquire-model-visual-evidence.md)

### 执行

**本地 Blender。** 脚本导入确切源 GLB，逐项检查对象、面索引、槽位和贴图绑定。需要局部独立控制时先隔离共享材质或网格。若目标端口已连贴图，沿连线更新实际驱动通道；若面域需要新贴图，可给目标面新建材质槽，写入 UV 和图像绑定。使用 `bpy.ops.export_scene.gltf` 输出 GLB 并启用 `export_extras=True`。具体编辑由 Agent 为当前任务编写。 [工作区模板](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:39>) · [实际局部贴图绑定](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/scripts/hi3d-cat-face-repair_7.py:14>)

**实现伪代码。** 依据随包规则、样本脚本与本地复现实验，省略输入解析和场景初始化。

```python
def revise_locally(source_path, output_path, edit, preserve):
    asset = import_glb(source_path)
    target = resolve_faces_and_slots(asset, edit.region)
    isolate_shared_mesh_and_materials_if_needed(target)

    if edit.kind == "material_factor":
        update_effective_channel(target, edit.channel, edit.value)
    elif edit.kind == "local_texture":
        patch, uv = project_or_sample_texture(edit.references, target, preserve)
        assign_patch_material_to_target_faces(target, patch, uv)
    else:
        raise ValueError("Unsupported local material edit")

    return export_glb(asset, output_path, export_extras=True)
```

**条件烘焙。** 本地 `bake_image()` 接收已对齐的源网格与具备 active UV 的独立目标网格，要求源与目标不共享材质。它在目标材质设置临时 active Image Texture 节点，执行 Cycles selected-to-active，输出并 pack 单通道 PNG，再恢复临时节点和场景设置。支持 `DIFFUSE`、调用方提供通道适配的 `EMIT`、切线空间 `NORMAL`。绑回目标模型和导出由调用方负责。后续通道失败时可保留成功贴图继续检查，完整通道组通过后再交接。 [随包烘焙实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-texture-bake/scripts/texture_bake.py:75>) · [拓扑变化后的外观恢复](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/quad-flow-plus/references/hi3d-budget-rebuild.md:108>)

**根据已验证行为重建的 `hi3d_api` 预检请求。** 示例假定三份输入文件已在工作区。

```json
{
  "action": "generate_3d",
  "kind": "model",
  "targetName": "猫",
  "mesh": "hi3d-cat_1.glb",
  "images": ["inputs/front.png", "inputs/left.png"],
  "views": ["front", "left"],
  "settings": {
    "model_type": "v3.0:quality",
    "generation_type": "texture"
  },
  "jobPath": "hi3d/cat-texture.json",
  "outputDir": "exports/hi3d-cat-texture",
  "dryRun": true
}
```

1. **规划和组包。** Runtime 将工作区 `mesh`、`images` 和方向传给随包 Python。此示例生成 `scene="texture"`、`version="v3.0"`、`otherParam.generationType="texture"`、`modelType="standard"` 和数字 `voxelResolution=2048`。正式 multipart 依次写入 `request`、`imageSlots=[0,2]`、两份 `images` 和 `mesh`，并复核实际文件的字节数和摘要。Python 最多收四张图，方向按前、后、左、右映射为 `0–3`，与文件按索引配对，校验数量和唯一性。通用 Skill 对普通多视图另要求包含正面。方向表示参考图拍摄方位。标准请求未露出目标面、材质槽、遮罩或必保特征字段。 [仅贴图 Skill](../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md#默认行为) · [随包组包实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_parameters.py:140>) · [3D 文件组包](../tools/hi3d-api.md#3d-本地文件组包)
2. **预检和参数面板。** 常规仅贴图用显式的 `settings.generation_type="texture"` 和 v3.0 档位。普通路径缺网格、缺参考图或给 `texture` 选 v2.x 会在提交前失败。Runtime 若拉起偏好面板，按 `parameters_selected` 回包的 `next_call` 采用答案，面板取消时停止。正式提交前检查当前预检展开后的 `request.scene="texture"`、`request.version="v3.0"` 和 `request.otherParam.generationType="texture"`。离线已复现旧 `request_type=2` 与显式 `both` 混用时，`consent.result` 为 `ready`，实际请求却是 `scene="texture"`、`generationType="both"`。按已确认的生成内容修正冲突后重新预检。核对后用相同输入、图序、设置及路径正式调用，去掉 `dryRun: true`。新作业的输出目录应尚不存在或为空。 [仅贴图参数门禁](../tools/hi3d-api.md#仅贴图参数门禁) · [Runtime 面板和续调](../tools/hi3d-api.md#返回与错误)
3. **提交、等待和下载。** 在 POST 前持久化 `submitting`，取得 `jobId` 后更新原账本。任务成功时在原输出目录下载，保留来源和文件路径。可先省略自动登记字段，在取得候选后做外观验收。正式组合动作同时收到 `registerName`、显式 `tag4` 且有唯一符合要求的 GLB 时，可以自动登记；该分支检查下载与登记条件，外观验收仍需针对实际文件进行。 [实际作业实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_jobs.py:192>) · [下载与登记回包](../tools/hi3d-api.md#已下载-3d-产物与登记)

底层组包器另可将 HTTPS 图片和网格地址写入 `multiViewSourceImageList` 和 `meshUrl`，纯 URL 且无本地文件时以 JSON 发送。原生请求中的非空 `parentGenerateId` 可以跳过客户端对参考图和网格的存在性检查。远端可用性及任务访问资格待实测。 [原生输入分支](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_parameters.py:171>) · [传输类型选择](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_jobs.py:182>)

### 验收

1. **重开确切导出。** 读取实际 primitive、面材质、UV 和图像绑定，确认贴图可解码。核对目标通道的改动和周边保留项。必要时以同一相机和不同光照对照 Base Color、粗糙度、金属度或法线，检查纹样方向、接缝和误烘入的高光。若要求保持姿态、网格、UV、蒙皮或动作，分别验证数据及回放。验收记录引用实际候选路径及其整文件 SHA-256。下载的 GLB 容器检查与 Studio `ready` 分别证明基本文件条件和视窗版本就绪。 [下载检查实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_artifacts.py:26>) · [视窗就绪判据](../tools/studio-get-state.md#参数与结果)
2. **用样本复核材质变化。** `_2` 给新胡须对象绑定 `Whisker_Ivory`。后续中间候选从原 albedo 的完整邻域取样，给修补区分配新 UV，并实际嵌入第三张 PNG。最终候选选用原猫脸材质，并给根部新增封口面分配常量材质 `WhiskerRoot_Surface`。三个登记 GLB 保留同一对 Base Color 与 Metallic-Roughness JPEG，逐张 SHA-256 一致。图像摘要只覆盖编码字节，面绑定和 UV 须独立核对。 [胡须脚本](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/scripts/hi3d-cat-whisker-rebuild_5.py:35>) · [贴图取样](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/scripts/hi3d-cat-face-repair-prepare_6.py:96>) · [中间绑定](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/scripts/hi3d-cat-face-repair_7.py:21>) · [最终材质](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/scripts/hi3d-cat-face-finish_12.py:28>)
3. **绑定 Studio 截图的版本与视角。** 截图前用 `studio_get_state` 核对 `assetId`、`fileName` 和 `ready: true`，回包后再次读取状态以发现切换。将可信的实际截图文件、版本和可核实的镜头方向或相机参数一起纳入验收证据。截图工具核对工作区和会话作用域，同工作区内的文件和相机未随调用锁定。截图期间发生切换，或实际镜头、文件归属无法确认时，应重取证，必要时从确切 GLB 做固定相机渲染。 [截图回包和作用域](../tools/studio-capture-view.md#版本与观察方向核对) · [视觉取证交接](../infrastructure/workspace/acquire-model-visual-evidence.md#验收与恢复)
4. **核对登记文件再交付。** 显式登记重读 `file.path`，自动登记重读 `registeredModel.path`，将整文件 SHA-256 与已验收候选比较。相同则可沿用该候选的验收证据。来源复用可能返回同任务中另一份字节不同的 GLB。文件不可读或摘要不同时应暂停交接并保留两份记录。若选用摘要不同的回包文件，须重新验收该文件后再交付。样本最终候选从正面和左侧近景取证，登记回包为 `hi3d-猫_3.glb`。导出与正式文件的 SHA-256 均为 `f2ac766e877a6c1754ac2f22c870c63e51543bcade8a0b862e379aa85ac4c238`。留存会话随后按该文件名加载 Studio 并确认就绪。 [登记文件身份与复用](../tools/workspace-commit-model.md#文件身份与复用) · [取证、登记和加载记录](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:932>)

## 完成与恢复

| 情况 | 续接与交付条件 |
| --- | --- |
| 本地脚本仍运行或结果不明 | 按返回的 `cell_id` 或命令 `session_id` 续查。保留源版本、脚本、输出路径和已有证据，核对进程终态与候选文件，再决定是否恢复执行。 |
| 云端返回 `pending` | 使用原 `jobPath`、原任务和原输出目录继续 `wait`，成功后下载。相同生成计划也可由组合动作续接。查询报错时保留最后一次有效观测及诊断，按 Tool 说明结束当前轮，待用户明确继续后沿原任务恢复。下载遇阻时继续使用原作业与原输出目录。 [等待交接](schedule-wait-and-handoff.md) · [下载恢复](confirm-download-source-and-recovery.md) |
| 提交不明 | 保留 `submitting` 或 `submission_uncertain` 的原账本与计划指纹。原账本有有效 `task_id` 时，显式 `query` 或 `wait` 使用原 `jobPath`。原账本缺 ID，但可靠回执能确认原任务 `jobId` 时，才能以 `adopt` 创建独立查询账本，再用该路径查询并保留原记录。仍缺确证时停在待核对状态，同计划重入受账本保护。普通贴图若需另开作业，先按 Runtime 的 `requiresRegenerationConfirmation` 提示取得用户确认。 [续查资格](locate-job-and-qualify-resume.md) · [Tool 作业恢复](../tools/hi3d-api.md#作业持久化与恢复) |
| 下载后返回 `attention/register-model` | 保留原 `jobPath`、任务 ID、输出目录和回包的 `files`。零份合规 GLB 时核对原下载来源与实际文件并保留诊断。多份时按来源和候选验收选出确切的一个，再显式登记。若已有文件但登记出错，先核对版本记录、回执和摘要，再恢复登记。以上分支沿用已下载结果或原作业恢复，下载与登记的异常各自处理。 [候选适用性](check-model-candidate-suitability.md) · [自动登记回包](../tools/hi3d-api.md#已下载-3d-产物与登记) |
| 已取得候选但验收未通过 | 保留候选、对应源版本和缺陷证据。按原因修订本地槽位、图像、投影或 UV。局部返工从与缺陷对应的候选或已确认源版本另存。确需新一轮纹理生成时，记录新的生成意图、参考图和独立账本，再重新验收。 |
| 已登记但验收未通过 | 保留已登记文件和缺陷证据。即使该文件是家族最高序号，下游仍应显式引用最后验收通过的版本。局部返工可按缺陷选择明确输入。全组没有验收通过的版本时保留待交付状态。这是本节点的交付判据，Hi3D 家族最新版仍按序号确定。 [家族版本查询](../infrastructure/workspace/query-assets-and-model-versions.md) |
| 已通过验收，余下登记或展示 | 使用选定的 `exportPath` 交登记。若只需为本次新登记补类，重试同一 `name`、`exportPath` 并传显式 `tag4`，复用版本的原标签以回包为准。若要记录轮次分类，另用 `image_classification` 并核对其同一线程和轮次的影响范围。回执不明时先核对版本记录及文件摘要，再决定是否重交同一候选。对账通过后按确切版本交付或恢复展示。 [分类范围](../tools/image-classification.md#补录范围与登记优先级) · [登记恢复](../infrastructure/workspace/import-or-register-model-version.md#完成与恢复) |

## Vet3D 迁移与核查范围

### 供应商无关的实现契约

由宿主固定源版本和资产摘要。让 LLM 表达修改来源、目标区域、通道、参考图方位、预期结果和必保项，再由执行层根据粒度选择本地处理或生成服务。前、后、左、右、上可作为统一参考方向。适配层声明哪些参考会实际送入所选能力。顶图若需要参与执行而能力不支持，应交给支持顶视图的实现或在能力检查阶段显式返回缺口。若顶图只用于核对，把该用途单独记入计划。

**Vet3D 设计示例。** 用侧面照修正左耳的局部颜色纹样，用顶视图验收头顶的保留标记。

```json
{
  "sourceVersionId": "version-17",
  "target": {"kind": "surface-region", "id": "left-ear-outer"},
  "operation": {"kind": "repair-pattern", "channel": "base-color"},
  "references": [
    {"assetId": "photo-left", "view": "left", "role": "edit-reference"},
    {"assetId": "photo-top", "view": "top", "role": "acceptance-reference"}
  ],
  "preserve": ["mesh", "uv-layout", "head-markings", "skinning", "clips"]
}
```

验收记录绑定候选摘要、实际参考、视角证据和保留项结果。分别保存供应商任务状态、候选验收状态和登记版本，再用实际文件摘要决定版本是否可供下游使用。对已绑定四足模型，验收范围包括关节层级、蒙皮权重、静止姿态和需要保留的动作。此处的字段为 Vet3D 业务设计，后续由选定的 LLM、生图模型、3D 模型和 API 适配。

### 安装包、运行记录与缺口

| 证据级别 | 核查结果 |
| --- | --- |
| 安装身份 | 事务备份的 Windows x64 1.2.11。`app.asar` SHA-256 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`，`runtime.mjs` 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`。本页引用的两个仓库 Skill 入口及装配审查参考文件均与对应随包文件逐字节一致。 [安装清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) · [Electron ASAR](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) · [Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) |
| 静态核查 | ASAR 的 `out/renderer/assets/index-CDPCug_K.js` 内，Studio 注册表约在 UTF-8 零基字节 `1090971`，共享烘焙配置门禁在 `3543919`，编辑标签过滤在 `4612618`，桌面 `StudioHost` 挂载在 `4725274`。也可搜索 `paintOnTexture`、`maker_studio_baking` 和 `initial-material-mode` 对照。 |
| 离线复现 | 在隔离目录为随包 Python 设置 `SPARC3D_TOOL_WORKSPACE`，用 `hi3d_api.execute()` 校验本页请求及缺输入和版本门禁，再用 `hi3d_parameters.multipart()` 核对实际组包。模拟传输核实提交前落盘、原 ID 续查及无 ID 的受理不明保护。Blender 4.5.16 LTS 的合成测试复现了隔离共享材质后只改目标对象粗糙度，并核对两对象原贴图及位置、UV、索引字节。另以合成源和目标验证随包脚本的 `DIFFUSE` 烘焙、PNG 和临时状态恢复。 |
| 实际运行记录 | 样本记录初次远端 `both` 请求、本地改槽与局部贴图候选、最终登记和 Studio 加载。这三份登记 GLB 与留存动作验证已发生的路径。 [初次远端请求](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:68>) · [最终 Blender 执行](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:921>) |
| 待实测 | 云端 `texture` 的实际 GLB、纹样保真度、PBR 通道、接缝、几何与 UV 是否保持、已绑定动物的蒙皮和动画保留。真实桌面截图的文件与回执在视角或版本切换时的对应关系，以及共享 Studio 烘焙的实际云端结果也待实测。离线预检和组包仅证明客户端行为。 |
