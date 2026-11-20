# 模型与部件变换

以 Hi3D Agent 1.2.11（Windows x64）及随包 Codex 0.166.0 为核查基准。本节点处理已有 GLB 中整模或部件的尺寸、位置和朝向。正式模型修订由 Agent 编写 Blender 脚本、导出候选，再交 Runtime 登记。Studio 的打印场景变换可用于摆盘，按用户操作保存 3MF 或多盘 ZIP，也可向切片器发送工作区登记的 3MF。留存样本验证了局部结构修订中的统一缩放、登记与加载。 [工作区模板](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:23>) · [版本归档](../upstream/1.2.11/README.md)

## 业务定义

| 项目 | 契约 |
| --- | --- |
| 触发 | 用户要求调整已有整模或部件的尺寸、位置或朝向，包含对已有对象的非等比缩放。需要编辑局部网格、补缺、重建或替换部件时，进入[局部结构修订](revise-local-structure.md)。同轮有两类要求时按几何依赖组合，在同一最终候选上分别验收。只为适配打印机尺寸或安排盘面时，进入 Studio 打印分支。 |
| 上游与输入 | 已有模型的家族、确切源版本和 GLB 路径。组合执行也可接收上一步已选定的未登记 GLB，交接实际路径、摘要、来源角色及已有验收依据，开始前复核指定文件。目标是整模或明确部件，操作区分绝对值和增量，以及单轴或等比缩放。需要精确控制时明确轴向、坐标系、枢轴、物理单位依据、允许误差及必保关系。打印分支以 Studio 已加载的确切版本为操作对象。 [候选取证与交接](check-model-candidate-suitability.md#完成与恢复) · [工作区模型版本](../infrastructure/workspace/query-assets-and-model-versions.md) · [Studio 状态](../infrastructure/workspace/read-studio-state.md) |
| 图片角色 | 几何主输入是源 GLB。若用户提供图片，主参考图用于核对目标姿态、朝向或个体特征，补充图用于核对被遮挡的关系。验收相机或截图方向由取证环节指定，必保项记录在任务要求及检查中。实际样本将本地前、侧近景的 `path` 传给 `view_image`，变换参数及保留项由脚本和轮次上下文承载。 [模型视觉取证](../infrastructure/workspace/acquire-model-visual-evidence.md) |
| 输出与完成条件 | 本地修订输出通过验收的 GLB 候选、源引用、候选摘要及对应测量和保留项证据。进程已结束、文件可读且要求通过后才交登记。用户需要展示时，再确认正式版本已在 Studio 就绪。打印布局以所需尺寸及盘面通过检查为准，下载以实际保存路径为准，发送以已登记的 3MF 和切片器交接回执为准。 |
| 下游 | 显式登记交接 `name`、选定的 `exportPath` 及适用的分类和工作流归属。用登记回包的 `file.fileName` 加载 Studio 或引用正式版本开展后续质检、绑定和动画。打印下载交接实际保存路径，发送切片器交接工作区文件产物引用及外部交接结果。 [版本登记](../infrastructure/workspace/import-or-register-model-version.md) · [Studio 加载](../infrastructure/workspace/load-studio-revision.md) · [文件交付](../infrastructure/workspace/preview-and-deliver-files.md#验收) |

## Skill 绑定

**通用入口。** 安装包的工作区 `AGENTS.md` 是宿主注入的指令模板。它规定已有模型的局部缩放和位置调整优先复用现有资产，从最新家族版本开始，本地 Blender 往 `exports/` 导出并显式登记，保留物理单位标记和稳定部件名。需要用户在视窗确认的摆盘、尺寸和打印步骤由 `studio_*` 承载。历史会话在 Blender 可用后注入了绝对路径。 [随包模板](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:31>) · [会话注入](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:246>)

| 仓库归档 Skill | 选用条件与作用 |
| --- | --- |
| [Hi3D 通用建模](../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md#3d-任务工作流) | 普通图生 3D 或明确进入对应云端能力时使用。第 75 行说明同主体后续修改可继承原分类，收到 `classificationRequired` 时补分类后沿用原导出。样本在上游生成时读取该 Skill，本地修订依工作区规则运行，留存修订轮未调用 `hi3d_api`。 [上游读取记录](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:19>) |
| [图片到高精度组装模型](../upstream/1.2.11/prebuilt-skills/image-to-assembly/SKILL.md#主流程与阶段出口) | 只在选用部件配准与装配路线后，执行其逐件变换记录、尺寸锁、在位环绕、承接和干涉验收，再按配合要求推动下游。猫模型修订样本未选用。 [随包配准说明](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/image-to-assembly/references/registration.md>) |

## LLM Tools

| 独立工具说明 | 在本节点的调用时机 | 样本或核查状态 |
| --- | --- | --- |
| [`exec`](../tools/exec.md) · [`exec_command`](../tools/exec-command.md) | 读取模型及矩阵、运行本地 Blender、检查候选。PowerShell、Blender 与工作区 Python 脚本属于工具执行的程序。 | 实际调用。 |
| [`wait`](../tools/wait.md) · [`write_stdin`](../tools/write-stdin.md) | `wait` 续查 Code Mode 单元，`write_stdin` 续查已返回 `session_id` 的命令进程。 | 前者用于等待 Blender 路径交互，后者用于 Blender 进程。 |
| [`user_interaction`](../tools/user-interaction.md) | 缺少执行环境、目标部件或关键物理依据，需要用户补充才能继续时使用。 | 样本询问 Blender 的绝对路径或安装状态。 |
| [`studio_get_state`](../tools/studio-get-state.md) · [`view_image`](../tools/view-image.md) · [`studio_capture_view`](../tools/studio-capture-view.md) | 按需读取视窗身份与统计、查看本地渲染、截取视窗画面。调用打印工具前复核已加载身份和就绪状态。候选位于 `exports/` 时可直接本地渲染。 | 实际读取状态和本地近景，`studio_capture_view` 属于按需工具。 |
| [`workspace_commit_model`](../tools/workspace-commit-model.md) · [`studio_load_revision`](../tools/studio-load-revision.md) | 通过验收后登记选定 GLB。需要展示时按返回的确切版本加载。 | 两次修订都发生登记和显式加载。 |
| [`image_classification`](../tools/image-classification.md) | 仅在登记缺少所需分类时补充分类型结果，用原家族和导出继续。 | 两次修订登记都继承 `tag4: null`，未重新分类。 |
| [`studio_arrange`](../tools/studio-arrange.md) · [`studio_export_3mf`](../tools/studio-export-3mf.md) | 核对 Studio 当前版本后，按请求启动摆盘或触发打印计划。毫米目标值来自面板，文件保存或发送由用户操作。 | 工具已注册，桌面行为来自安装包核查，所查生产会话未记录这两项调用。 |
| [`skill_capture_suggest`](../tools/skill-capture-suggest.md) | 宿主具备能力且发现可复用经验时，可在交付后记录建议。 | 局部修订的模型加载成功后有调用。 |

## Hi3D 实现

### 决策

1. **按交付目标分流。** 新 GLB 版本进入本地 Blender 路线。打印尺寸和盘面调整进入 Studio 摆盘编辑态，需要下载或发送时再触发打印计划。安装包 renderer 的 `S0e` 注册加载、状态、截图、摆盘和打印计划五项 Studio 动态工具。`studio_arrange` 只接收 `profileId` 和 `plateMode`，`studio_export_3mf` 接收空对象，两者都依赖当前已加载模型。 [桌面 ASAR](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) · [摆盘参数](../tools/studio-arrange.md#参数与结果) · [打印计划参数](../tools/studio-export-3mf.md#参数与结果)
2. **确定本地源文件与保留对象。** 用户选定确切版本时沿用该版本。默认最新版本按家族数字序号确定。脚本导入源 GLB 后可按对象名及网格结构定位部件。实际检查脚本用 `matrix_world @ Vector(c)` 把局部包围盒八角变到世界空间并记录矩阵。最终修订从 `_2` 保留已缩放胡须，从 `_1` 恢复身体，`0.075` 应用于重新引入的身体，保留胡须按导入时的矩阵检查。首次修订脚本取最大序号，复放须在隔离副本中固定当时的 `_1`。 [原始检查脚本](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/scripts/hi3d-cat-whiskers_1.py:8>) · [首次重建选版](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/scripts/hi3d-cat-whisker-rebuild_5.py:6>) · [最终修订输入](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/scripts/hi3d-cat-face-finish_12.py:6>)
3. **核对 Studio 实际操作对象。** 宿主检查当前工作区、活动调用和视窗可用性，工具参数没有确切版本选择项。调用摆盘或打印工具前，用 `studio_get_state` 核对 `assetId`、`fileName` 与 `ready: true`。缺少所需版本时，用 `studio_load_revision` 指定确切文件名并确认加载结果。目标版本已就绪时沿用当前打印场景。恢复超时或视图切换后，先重新核对模型身份与盘面。这个核对是节点调用方的交接条件。 [读取视窗状态](../infrastructure/workspace/read-studio-state.md#验收) · [按版本加载](../infrastructure/workspace/load-studio-revision.md#验收)

### 执行

**本地 Blender 导出。** Agent 将任务脚本写到 `scripts/`，用工作区注入的 Blender 绝对路径运行 `--background --python <脚本>`。第一版修订将身体及新建两侧胡须的现有缩放分量都乘以 `0.075`，再导出所选网格。最终修订给新引入的身体赋 `(0.075, 0.075, 0.075)`，并断言保留胡须的顶点坐标、世界矩阵与面数匹配导入状态。两次导出都启用 `export_extras`。下面是首次缩放与导出的**根据已验证行为重建的代码摘录**，省略几何生成及选择设置。 `obj` 是身体，`new_objects` 是两侧新胡须。 [首次导出脚本](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/scripts/hi3d-cat-whisker-rebuild_5.py:69>) · [最终保留检查和导出](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/scripts/hi3d-cat-face-finish_12.py:73>)

```python
for mesh_object in [obj] + new_objects:
    mesh_object.scale = tuple(component * 0.075 for component in mesh_object.scale)
    mesh_object["sparc3dPhysicalUnits"] = {"version": 1, "unit": "meter"}

bpy.ops.export_scene.gltf(
    filepath=str(export),
    export_format="GLB",
    use_selection=True,
    export_extras=True,
    export_cameras=False,
    export_lights=False,
)
```

**Studio 的单位与坐标。** 加载后的场景以最长边 8 个视窗单位做归一化。默认 `auto` 策略遇到节点 `extras.sparc3dPhysicalUnits = {"version":1,"unit":"meter"}` 时，按 `1000 / normalizeScale` 计算每视窗单位的毫米数并返回 `source: "file"`。缺少可信标记时，按 `75 / normalizedLongestU` 建立默认显示尺度，返回 `source: "default-longest"`。状态工具用网格变换后的世界轴对齐包围盒乘换算比，数值缩放则取模型局部包围盒乘根缩放与换算比。多网格导入时，编辑器会把输入网格的矩阵烘入坐标并重组对象，核对枢轴时须确认当前使用的是哪一套对象层级。 [尺寸状态实现](../infrastructure/workspace/read-studio-state.md#执行) · [桌面 ASAR](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>)

| Studio 编辑操作 | 从安装包核查的核心行为 |
| --- | --- |
| 人工入口 | 普通预览是 `viewer`，快捷键关闭。摆盘面板使用 `editor`，即使左工具栏隐藏也接入 `G/R/S/Q`。宿主按最近一次指针按下是否在 Studio 内判断普通快捷键是否拦截，处理器另外跳过 `INPUT`、`TEXTAREA`、`SELECT`。网格可从画布拾取，移动和旋转作用于活动网格，已摆盘时缩放快捷键提示先撤销摆盘。 |
| 平移 | 数值输入是目标对象原点在指定世界轴的绝对坐标。用 `毫米值 / mmPerUnit` 替换该轴，再经父节点 `worldToLocal` 写回 `position`。 |
| 旋转 | 度数转弧度写入该对象的局部 Euler 分量。未摆盘时可能按世界包围盒重新贴地。已摆盘的拖拽手柄可临时使用所选网格世界包围盒中心。 |
| 缩放 | 数值操作作用于模型根。目标毫米值除以当前模型局部尺寸得到倍率。锁定等比或指定 `max` 时三轴一起缩放，解锁且指定单轴时只调整该轴。 |

**根据已核查实现重建的伪代码。** 只展示物理尺寸已就绪时的数值路径。平移和旋转作用于活动网格，毫米缩放作用于模型根。包装器先比较应用前后的变换快照，实际产生变化时才运行适用的重新贴地、历史记录和包围盒更新。贴地逻辑本身跳过已摆盘场景。

```python
def apply_numeric_transform(active_mesh, model, kind, axis, value, lock_ratio):
    if kind == "scale_mm":
        target = model.root
        if target is None or model.is_arranged():
            return
    else:
        target = active_mesh
        if target is None:
            return

    before = snapshot_transform(target)
    if kind == "translate_mm":
        mm_per_unit = model.mm_per_unit
        if not isfinite(value) or mm_per_unit <= 1e-9:
            return
        target.update_world_matrix()
        world_origin = target.world_position()
        world_origin[axis] = value / mm_per_unit
        target.position = (
            target.parent.world_to_local(world_origin)
            if target.parent else world_origin
        )
    elif kind == "rotate_degrees":
        target.rotation_euler[axis] = radians(value)
    elif kind == "scale_mm":
        size = model.size_mm(space="model-local")
        if size is None:
            return
        current = max(size.values()) if axis == "max" else size[axis]
        if not isfinite(value) or value <= 1e-6 or current <= 1e-9:
            return
        factor = value / current
        if lock_ratio or axis == "max":
            target.scale *= factor
        else:
            target.scale[axis] *= factor
    else:
        return

    target.update_matrices()
    if transforms_equal(before, snapshot_transform(target)):
        sync_transform_inputs()
        return
    if kind in ("rotate_degrees", "scale_mm"):
        model.reground_transform_target(target)
    record_history(target, before, snapshot_transform(target))
    notify_bounds_changed(kind)
    refresh_viewport()
```

**打印尺寸卡。** 尺寸卡把「输入毫米值 ÷ 原轴毫米值」作为等比因子，把「原最长边 × 因子」通过 `{targetMm, axis: "max"}` 交给摆盘编辑器。`Ir` 尝试恢复组装位姿，清理上一轮盘面，收合已展开关节，然后请求模型根等比缩放，读取尺寸并触发重排。隔离执行安装包函数时，`20 × 40 × 75 mm` 的模型把 X 改成 `30 mm`，发出 `{targetMm: 112.5, axis: "max"}`，正常缩放得到 `30 × 60 × 112.5 mm`。用替身让位姿恢复返回 `false` 时，`Ir` 仍调用后续缩放和重排。通用尺寸入口在模型仍处于已摆盘状态时跳过缩放。重排抛错时 `Ir` 更新错误状态并返回 `false`，先前已执行的缩放可能保留。 [源码锚点](#安装包运行记录与缺口)

**打印文件。** 需要下载或发送时，`studio_export_3mf({})` 发出打开打印计划的操作。后续由用户在面板确认。单盘可保存 3MF，多盘可保存合并 3MF 或包含各盘 3MF 的 ZIP。发送切片器分支支持非 SLA 路线，使用合并 3MF 写入工作区并登记为 `export-3mf` 后再尝试外部交接。 [打印计划工具](../tools/studio-export-3mf.md#参数与结果) · [文件交付](../infrastructure/workspace/preview-and-deliver-files.md#验收)

### 验收

1. **检查进程、候选与变换证据。** 最终修订调用返回 `session_id: 89385`，沿同一进程续查取得退出码 `0`，再读取正面和左侧近景，以及 GLB 声明的节点缩放和单位。事后复验留存 GLB 时，`_1` 无米制标记，Studio 报 `default-longest`。两份修订版的三个网格节点缩放均约为 `[0.075, 0.075, 0.075]`，均带米制标记。复算的世界包围盒约为 `17.460 × 40.252 × 74.995 mm`，与 Studio 的 `source: "file"` 回包一致。两版导出胡须的位置与索引缓冲相同，法线有变化。样本中的毫米值来自文件尺度。 [进程与候选检查](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:927>) · [原版尺寸](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:167>) · [修订版尺寸](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:949>)
2. **以确切文件登记，再加载正式版本。** 第 941 行的实际调用参数如下。Runtime 在 `exports/` 下校验路径及 GLB 容器，样本继承同家族的 `tag4: null`，第 944 行返回 `file.fileName: "hi3d-猫_3.glb"`。随后按该文件名显式加载，确认 `loaded: true`、`state.ready: true`。两次修订的候选和正式文件分别通过 SHA-256 对账。调用方在交接前核对验收摘要与实际导出。存在工作流归属时可传 `workflowNodeId`，节点完成另按工作流要求报告。分类解析、云端来源匹配、容器校验和版本发布由登记入口执行。 [实际登记与加载](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:941>) · [版本登记交接](../infrastructure/workspace/import-or-register-model-version.md) · [工作流产物归属](../infrastructure/workspace/workflow-graph-state.md)
3. **按打印目标确认交付。** 先核对确切版本，再核对实测尺寸、盘面和超床提示。`arranged` 回包确认收到摆盘事件，盘数还可能来自宿主回退值。`opened: true` 表示已发出打开打印计划的操作。保存以 Electron `file:downloadEvent` 的 `completed` 与实际路径为准。发送先确认工作区的 `artifact/registered`，再核对系统打开应答与 Runtime 的 `handed-to-slicer` 记录。外部软件实际读取、解析和打印需要各自的证据。 [摆盘回包](../tools/studio-arrange.md#参数与结果) · [文件交付的验收](../infrastructure/workspace/preview-and-deliver-files.md#验收)

**实际 `workspace_commit_model` 请求参数。**

```json
{
  "name": "猫",
  "exportPath": "exports/face-repair/hi3d-cat-face-repaired-final.glb"
}
```

## 完成与恢复

| 情况 | 续接与交付条件 |
| --- | --- |
| 本地执行仍在进行 | 使用原 `cell_id` 续查 Code Mode 单元，或用原 `session_id` 续查 Blender 命令，按实际返回的句柄类型选择。中间渲染可以提前取证，候选交接要等进程终态及 GLB 验收。 |
| 命令启动或登记结果不明 | 保留原脚本、源引用、候选路径、摘要、句柄及已有结果。先确认进程状态和实际导出。若登记可能已发生，先查工作区版本文件、元数据和摘要，再按原家族和原导出恢复。Runtime 可复用与最新版本相同的导出，收到 `unchanged: true` 时仍核对返回版本和落盘状态。 [登记对账](../infrastructure/workspace/import-or-register-model-version.md#完成与恢复) |
| 有候选但验收未过 | 保留候选及测量或渲染证据，沿用锁定的源引用，按缺陷修订目标、枢轴、单位换算或脚本。用新候选重新测量受影响的尺寸、位置、角度及保留项，再交候选复核或登记。样本修复时依据近景发现粗须残留，修订脚本并重取证后才登记最终版本。 [候选复核](check-model-candidate-suitability.md#完成与恢复) · [返工至最终候选](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:920>) |
| 登记成功，视窗加载结果不明 | 保留正式文件名，读取 Studio 状态。需要展示且尚未就绪时，针对同一版本恢复加载。 |
| 摆盘等待超时或重排失败 | `oversize-pending` 表示宿主等待摆盘事件超时。先核对 `assetId`、`fileName`、`ready`，再看当前尺寸、姿态、盘面及用户面板状态。失败或超时后仍可能留有已应用的缩放。继续前使用当前测量评估剩余操作，避免重复应用比例。摆盘没有公开的任务句柄供续查，再调用会发起新操作。 [摆盘等待](../tools/studio-arrange.md#实现伪代码) |
| 打印计划已触发 | `opened: true` 后，沿当前面板核对是否成功打开及用户选择。下载需等实际保存事件，发送需等文件登记与交接回执。保存取消或失败时沿当前计划重新选择。切片器交接失败而文件已经登记时，核对同一 `artifactId`、路径和摘要，再按需重发原文件。 [打印计划结果](../tools/studio-export-3mf.md#参数与结果) · [文件恢复](../infrastructure/workspace/preview-and-deliver-files.md#完成与恢复) |

## Vet3D 迁移与核查范围

### 供应商无关的实现契约

输入可由 LLM 形成结构化意图。由宿主固定源版本和内容摘要，明确操作目标、单位、坐标系、枢轴、绝对值或增量及允许误差。未知单位应保留为未知，显示尺度可用于预览。需要达到物理尺寸时，使用带依据的文件单位或有记录的校准尺寸。整模和部件采用明确的 ID 及变换顺序。局部移动如果依赖骨骼、附件或父节点，按任务约束记录应联动的对象，验收时再检查关系。

**Vet3D 设计示例。** 以工作区模型的世界坐标为准，将已知部件及其附属对象沿 Z 增量移动 2 mm，保持它们之间的相对位置与现有材质。字段表示业务语义，可由后续适配层映射。

```json
{
  "sourceVersionId": "version-17",
  "target": {"kind": "part", "id": "part-08", "linkedPartIds": ["part-09"]},
  "operation": {
    "kind": "translate",
    "mode": "delta",
    "frame": "asset-world",
    "valueMm": [0, 0, 2]
  },
  "unitBasis": {"kind": "calibrated-source", "referenceId": "measurement-04"},
  "toleranceMm": 0.1,
  "preserve": ["child-attachment-offsets", "materials"],
  "delivery": "model-revision"
}
```

执行后重新读取候选，按请求的坐标系复验位置、朝向及尺寸。模型局部尺寸适合核对纯旋转后的尺寸保留，世界轴对齐包围盒适合核对摆放及打印床占用。验收记录绑定候选摘要，列出坐标系、目标值、实测值、偏差、保留项及证据。达到门槛后交登记，返回正式版本 ID。对可动画的四足模型，若任务要求保留绑定，检查蒙皮、关节层级、静止姿态、动作回放和必要的接缝。样本三版 GLB 均无蒙皮或动画数据，这组检查属于 Vet3D 待验证的契约。

### 安装包、运行记录与缺口

- **安装身份。** 使用事务备份的 Windows x64 1.2.11。`app.asar` SHA-256 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`，`runtime.mjs` SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`。本页链接的 `hi3d/SKILL.md` 与 `image-to-assembly/SKILL.md` 仓库副本分别与随包入口逐字节一致，其 SHA-256 分别为 `4c268ae14ece561234682d564cdfa6264c1f121a9ea118137c0388a9240c217d` 和 `cf4ec08dec0decfd69560a940cc26ea18fecf559ea87852c269fd2682555705f`。 [版本清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) · [桌面 ASAR](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) · [Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>)
- **静态与隔离测试。** 下表是安装归档中 `out/renderer/assets/index-CDPCug_K.js` 的零基 UTF-8 字节偏移。隔离调用原始函数核对单位分支、世界坐标平移、局部旋转换算、毫米缩放、尺寸卡与快捷键分派。可按 `Ir` 锚点提取函数，让 `ts()` 返回 `false`，以替身记录 `setModelSizeValue("max", 112.5, true)`、`getRealSizeMm()` 和 `Vt.trigger` 的调用。该测试验证恢复失败后仍继续控制流，实际编辑器对模型和盘面的效果需桌面实测。
- **实际运行与文件。** 留存会话验证局部修订中的统一缩放、登记和加载，留存 GLB 验证米制导出及对象位置。独立平移、独立旋转、按用户给定毫米值交付 GLB，以及 Studio 实际摆盘、键盘交互、保存 3MF 或 ZIP、发送切片器，仍待端到端实测。 [留存脚本](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/scripts/hi3d-cat-face-finish_12.py:73>) · [留存登记记录](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:941>)

| ASAR 成员内锚点 | 核查内容 |
| --- | --- |
| `1090971`、`4725412` | `S0e` 注册表、`StudioHost` 的 viewer/editor 模式与工具栏配置。 |
| `2927109`、`2832326`、`2854216`、`2854506` | 场景归一化、`X6` 单位初始化、世界和局部尺寸计算。 |
| `3545549`、`3546880`、`3547440`、`2856640`、`3409037` | `CWe` 平移、变换前后比较、数值变换、模型根毫米缩放、拖拽枢轴。 |
| `3618534`、`3622182`、`4707451` | 编辑器快捷键、画布拾取、宿主的快捷键作用域。 |
| `4268913`、`2859524`、`4630896` | 尺寸卡与等比因子、组装位姿恢复、缩放后重排。 |
| `4223602`、`4558955`、`4712090` | 3MF / ZIP 下载分支、面板格式选项和 3MF 发送回调。 |
