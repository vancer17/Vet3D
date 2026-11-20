# 获取模型的视觉证据

本节点属于工作区基础设施。核查对象为 Windows x64 的 Hi3D Agent 1.2.11、同版 Runtime 和随包 Codex 0.166.0。用户当前看到的画面从 Studio 视窗取证。指定方向的外观从已解析的模型版本渲染。需要检查几何时，将同一版本的 GLB 交给本地检查脚本。

## 业务定义

| 项目 | 节点契约 |
| --- | --- |
| 触发条件 | 用户要求查看、比较或检查模型外观，或所选流程要求提供实际画面。只需确定版本或查询 Studio 尺寸时，直接读取状态。只需读取网格时，按文件交接执行几何检查。 |
| 上游与输入 | [当前轮的工作区上下文](llm-context.md)提供工作区、线程、轮次和用户指代。[读取当前视窗状态](read-studio-state.md)确认用户指代的已加载版本。[素材与模型版本查询](query-assets-and-model-versions.md)解析指定版本与实际模型文件。检查任务另提供所需角度、检查区域及适用的参考图。 |
| 输出 | 可访问的图像及其证据来源。交接时记录对应工作区、模型版本、截图或渲染来源、已确认的观察方向及仍缺少的信息。需由 LLM 检查画面时，再交付该文件的图像内容。 |
| 完成条件 | 计划内的图像均可打开，模型版本和观察方向已核对，覆盖所需区域。仅有截图产物 ID 时仍需解析文件。若需要 LLM 看图，确认对应的图像内容已通过工具回包进入本轮上下文。固定相机渲染按下文分别记录进程终态、可交付的单帧和整组完成状态。 |
| 下游 | 将已核对版本和方向的图像交给外观或摆盘验收。若需要修订，保留旧证据供比较，修订后按新版本重新取证。结构检查交付同版本 GLB 或工程文件的实际路径，并附已有的几何检查结果。 |

## Skill 与工具绑定

| 依据 | 在本节点中的作用 |
| --- | --- |
| 通用桌面宿主 | `templates/AGENTS.md` 第 42 行指导视窗操作使用 `studio_*`。renderer 的 `mS` 在创建线程时提供相应动态工具和指令。是否取证由当前任务和生效工具决定。 |
| [hi3d/SKILL.md](../../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md) | 普通图片和模型生成的通用入口。普通生成流程不会自动追加 Blender 渲染或审计。用户要求质量检查时，根据检查目的取得所需画面。 |
| [image-to-assembly/SKILL.md](../../upstream/1.2.11/prebuilt-skills/image-to-assembly/SKILL.md) | 选用静态装配流程时，按阶段检查实际粗模、逐件高模、可见部件和遮挡，记录视角及推断依据。保存的固定视图和实际打开工程环绕各有验收要求。 |
| [scene-render/SKILL.md（安装包原文）](</D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/scene-render/SKILL.md>) | 选用场景渲染流程时，指导保存模型、相机、渲染设置和输出文件。验收阶段实际打开交付静帧。 |

| LLM Tool | 本节点的调用条件 |
| --- | --- |
| [studio_get_state](../../tools/studio-get-state.md) | 指代依赖当前视窗，或截图前需要确认已加载的目标版本时查询。 |
| [studio_load_revision](../../tools/studio-load-revision.md) | 用户指定的版本尚未加载，且任务需要在 Studio 展示或截图时加载该版本，等待匹配的就绪结果。 |
| [studio_capture_view](../../tools/studio-capture-view.md) | 目标已确认加载，且当前镜头满足检查目的时截取画面。 |
| [view_image](../../tools/view-image.md) | 确认了截图或渲染文件的实际路径，且需要让模型看到图像时读取。 |
| [exec_command](../../tools/exec-command.md) | 工作区文件引用需要核对，或需运行固定相机渲染、GLB 几何检查等本地脚本时使用。 |
| [exec](../../tools/exec.md)、[wait](../../tools/wait.md)、[write_stdin](../../tools/write-stdin.md) | 按当前会话暴露的方式调用工具。Code Mode 返回运行中的单元时用原 `cell_id` 续查。若本地命令另返回进程 `session_id`，用同一进程 ID 续取输出。 |

`studio_*` 由 Electron renderer 注册为 LLM 动态工具。`workspace/models`、`artifact/register` 是宿主 RPC，`file:writeArtifact` 是 Electron IPC，`artifact/registered` 是宿主事件。`view_image` 是随包 Codex 的看图工具。各工具的原始描述和通用约束见[独立工具索引](../../tools/README.md)。

## Hi3D 的实现

### 决策

1. **锁定证据对应的模型。** 用户指代「当前模型」时，先查 `studio_get_state({})`，使用返回的实际 `assetId`、`fileName` 和 `ready` 判断。已登记、界面已选中和 Studio 已确认加载的版本在切换期间可能不同。用户明确指定文件时，先按工作区目录解析，若要截图，再加载并核对该版本。 [读取当前视窗状态](read-studio-state.md#验收)
2. **按检查目标选择取证方式。** 要复核用户正在看到的内容，沿用当前 Studio 镜头截图。要核对指定方向、重复前后对比或控制可见部件，则使用已解析的同版模型，按相机或工程要求取证。已核查的 Studio 工具未提供指定截图相机、返回相机参数或锁定模型版本的字段。 [截图工具参数](../../tools/studio-capture-view.md#参数与结果)

### 执行

#### Studio 当前视窗截图

**根据包内定义重建的 Code Mode 调用示例。** 示例假定调用方已经确认具体版本加载就绪，且当前会话通过 `exec` 暴露 Studio 工具。本调用交付产物编号，图像交接见后续步骤。

```javascript
const result = await tools.studio_capture_view({ width: 960, height: 720 });
text(result);
```

1. **分派与作用域检查。** Codex 发出 `item/tool/call`，Runtime 经过通用会话额度检查后，把 Studio 请求按桌面 `requestId` 送给 renderer。`vi` 核对当前线程、轮次及工作区 `cwd`，记录会话代次和取消信号。`M0e` 核对 Studio 已挂载、已加载身份属于调用方工作区。截图分支使用这一身份检查，未单独要求 `ready:true`。调用方需先确认实际版本及就绪状态。 [桌面分派与回传](read-studio-state.md#执行)
2. **取出画面并编码。** `StudioHost.capture` 取视窗内的 canvas。`ht` 把可选宽高和 1024 像素最长边作为约束，等比缩小，保留原尺寸上限。`Ue` 以质量参数 0.85 编码 JPEG。工具描述写 PNG，1.2.11 实际写 `.jpg`。若缩放画布无法取得 2D 上下文，实现回退到原画布，返回宽高仍是计划值。没有 canvas 或编码无结果时，截图失败。 [尺寸与编码细节](../../tools/studio-capture-view.md#参数与结果)
3. **落盘并登记。** 编码和读取字节期间复核会话及工作区。`Ce` 经 preload 的 `files.writeArtifact` 把字节交给 Electron 主进程。主进程在该工作区 `exports/` 下以唯一名称独占写入，再通过 Runtime `artifact/register` 登记角色 `screenshot`。IPC 应答 `{artifact}` 内含 `artifact.artifactId` 和工作区相对路径 `artifact.path`，Runtime 还发送 `artifact/registered`。工具分派在回包前复核当前作用域、句柄和工作区，沿原请求回传。 [登记文件产物](register-file-artifact.md)
4. **从文件引用交付像素。** 工具成功负载只有 `artifactId`、`width`、`height`。宿主可在文件写入应答或登记事件中按同一 ID 取到实际路径。已核查的模型可见接口中未发现通用 `artifact/get` 或 `artifact/list`。此截图登记带 `threadId`，缺少工作流自动挂接需要的 `turnId`，因此不能依赖 `workflow_report(inspect)` 按该 ID 自动取回路径。仅有文件读取能力时，可在当前工作区定位本次创建的导出文件。存在多个可能文件时，先核实来源，再交给 `view_image`。 [工作区可查询范围](query-assets-and-model-versions.md#执行)

**根据已核查工具契约重建的像素交接示例。** 路径为占位值，实际调用使用前一步已核实的文件。Code Mode 用 `image()` 把读取结果附为图像内容。 [Code Mode 图像输出](../../tools/exec.md)

```javascript
const shot = await tools.view_image({ path: "exports/hi3d-view-example.jpg" });
image(shot);
```

**实现伪代码。** 以下重建已核查的 Studio 截图路径，省略额度检查和通用 RPC 包装。只有宿主能从写入应答中直接取得完整产物，最终文本负载保留三个字段。

```python
async def capture_current_canvas(call, desktop):
    scope = desktop.require_current_scope(call.thread_id, call.turn_id)
    studio = desktop.require_mounted_studio()
    scope.require_loaded_workspace(studio)
    canvas = studio.first_canvas()
    if canvas is None:
        return tool_error("capture unavailable")

    planned_size = fit_without_upscaling(canvas, call.arguments, max_edge=1024)
    jpeg = await encode_jpeg_with_canvas_fallback(canvas, planned_size, quality=0.85)
    if jpeg is None:
        return tool_error("capture unavailable")
    scope.require_same_session_and_workspace()
    data = await jpeg.array_buffer()
    scope.require_same_session_and_workspace()

    reply = await desktop.write_and_register(data, role="screenshot")
    scope.require_same_loaded_workspace_and_handle(studio)
    return text_result({
        "artifactId": reply["artifact"]["artifactId"],
        "width": planned_size.width,
        "height": planned_size.height,
    })
```

#### Blender 固定相机渲染

1. **绑定模型和相机。** 先确定实际工作区路径和模型版本。若用户指代当前 Studio 模型，以已确认加载的 `fileName` 定位 GLB。渲染脚本导入对应文件，设置本次需要的相机、可见部件、材质和渲染参数，并为每个方向指定输出路径。相机取自脚本定义。只渲染已解析的文件时，可以直接使用该文件。
2. **启动并续取进程状态。** Agent 通过 `exec_command` 以 `--background --python` 运行 Blender 脚本，由脚本把各方向保存为本地图像。命令返回 `session_id` 时，用 `write_stdin` 沿用原进程 ID 取得日志或终态。若外层 Code Mode 执行单元也交回了 `cell_id`，由 `wait` 续查执行单元。
3. **读取成图并交付像素。** 按渲染脚本记录的输入、相机和输出路径，核对每张图片来自目标版本或对应的修订中场景。需要 LLM 检查画面时，调用 `tools.view_image({ path })` 读取实际文件，并用 `image(result)` 将图像附入外层 `exec` 的工具结果。回包里的 `input_image` 是像素已交付的证据。已写完的静帧可以在后台进程结束前单独查看。进程退出码、图片可读性以及静帧是否覆盖检查目标分别验收。 [进程续查](../../tools/write-stdin.md) · [图像回传](../../tools/view-image.md#核查依据)

**根据实际运行行为重建的 Code Mode 示例。** 示例假定当前环境可以调用 Blender，渲染脚本和工作区路径均为占位值。脚本接收已核对的版本文件和本次独立的输出目录，预设正面及侧面相机，写出约定的文件。示例在进程会话收尾后尝试逐帧读取，单张读取失败时保留其余图像，并另报退出码和失败文件。

```javascript
const workdir = "D:/workspaces/example";
const modelPath = "hi3d-sample_2.glb";
const outputDir = "exports/review/run-01";

let run = await tools.exec_command({
  cmd: `blender --background --python "scripts/render_views.py" -- "${modelPath}" "${outputDir}"`,
  workdir,
});
while (run.session_id !== undefined) {
  run = await tools.write_stdin({ session_id: run.session_id, chars: "" });
}
const readable = [];
const unreadable = [];
for (const file of ["front.png", "side.png"]) {
  try {
    const result = await tools.view_image({ path: `${workdir}/${outputDir}/${file}` });
    image(result);
    readable.push(file);
  } catch (error) {
    unreadable.push({ file, error: String(error) });
  }
}
text({ exitCode: run.exit_code ?? null, readable, unreadable, output: run.output });
```

**Skill 指导。** 使用静态装配 Skill 时，按阶段保存可复查的 Blender 工程，渲染前、后、左、右、上、下及所需斜视。逐件高模交接后，检查实际装配位置、单件外观、整体和遮挡。专项环绕须实际打开工程并旋转。场景渲染 Skill 另要求保留场景和相机配置，并打开交付静帧验收。这些要求随选用的 Skill 生效。已核查的普通桌面轮次没有自动执行固定相机渲染。 [粗模固定视角与环绕](../../upstream/1.2.11/prebuilt-skills/image-to-assembly/references/proxy-segmentation.md) · [安装包高模配准](</D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/image-to-assembly/references/registration.md:3>) · [安装包渲染交付规则](</D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/scene-render/references/render-delivery.md:7>)

#### 同版本 GLB 几何检查交接

需要检查顶点和面数、边界或连通分量时，将已确认的工作区、版本文件名和实际 GLB 路径交给检查脚本。用户指代当前模型时，先将 Studio 确认的版本名解析到该工作区的实际文件。照片和渲染图继续作为外观证据。几何检查从该 GLB 读取网格，检查结果按该脚本使用的坐标及单位解释。 [模型版本和路径解析](query-assets-and-model-versions.md#执行)

活跃样本中，Agent 用 `exec_command` 启动 Python `trimesh` 检查，再用 `write_stdin` 读取原进程的终态和文本。输出含顶点数、面数、边界及连通分量统计。脚本选择的模型家族和输出中的数字版本号与先前成功加载的已登记版本相符。交接时可把同版文件引用、检查范围和统计一并交给结构验收。 [本机几何检查记录](</D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:261>)

### 验收与恢复

| 触发条件 | 执行者 | 读取或写入的状态 | 返回或判定 | 下游动作 |
| --- | --- | --- | --- | --- |
| 确认实际模型 | Agent、Studio | 读已加载身份和就绪状态 | `ready:true` 且版本匹配，或空状态、错误 | 匹配时取证；未就绪时等待状态变化或加载确切版本。 |
| 截图成功 | Studio、Electron、Runtime | 读当前 canvas，写文件并登记 | 工具交付 ID 和计划尺寸 | 解出实际路径，打开文件并核实实际编码和尺寸。 |
| 固定相机进程可续接，尚未取得退出码 | Agent、Blender | 用原 `session_id` 取状态，检查已写完的静帧 | 进程终态待确认，已核对的可读帧可先交付 | 标注已交付和待补的方向，保留原进程继续取状态。 |
| 固定相机进程非零退出 | Agent、Blender | 读退出码、日志及已落盘的静帧 | 本次进程失败，来源及内容已核对的帧仍可作为部分证据 | 记录失败原因与受影响方向，按故障范围恢复。 |
| 固定相机进程零退出，部分所需帧缺失或无法读取 | Agent、`view_image` | 对照计划路径、相机和读图结果 | 命令成功，整组证据仍待补 | 保留可用帧。定位路径或读取故障，缺失或损坏的帧按需补渲染。 |
| 固定相机进程零退出，所需帧齐全且核对通过 | Agent、`view_image` | 逐方向记录模型版本、相机、路径和图像回包 | 渲染及整组取证完成 | 移交外观验收。需 LLM 看图时核对相应的 `input_image`。 |
| 路径已确认 | Agent、`view_image` | 读该文件的实际图像 | 本轮得到图像内容 | 检查是否覆盖目标部位、方向及参考要求。 |
| 需要几何检查 | Agent、本地脚本 | 读同版 GLB 及其网格 | 指定文件的几何统计文本，或读取错误 | 将文件引用和已取得的统计交给结构验收。 |
| 切换版本、镜头或会话 | Agent、宿主 | 重新读受影响的视窗与证据引用 | 旧观测可保留为历史证据 | 核对当前实际版本，必要时重新截图或按固定相机渲染。 |
| 截图报错、取消或回包过期 | renderer、Runtime | 中止当前调用或拒绝旧回包 | 无可交付结果；文件或登记可能已写入 | 检查本次已有文件。只有需要一份新画面时才重新调用。若是运行中的 `exec`，先续查原 `cell_id`。 |
| 画面不足以完成验收 | Agent、评审流程 | 保留目标版本、图像、观察及缺口 | 证据待补，或模型需要修订 | 补拍对应镜头，或生成修订版后重新取证。实际画面验收由下游处理。 |

**固定相机渲染的交接判定。** 单帧在能够关联到本次输入模型或修订中场景、计划相机及输出路径，并可实际打开时即可供下游检查。可续接进程的结果可同时带 `session_id` 和 `exit_code`，此时保留已知退出状态并继续读取剩余输出。若进程终态未取得，记录为待确认。能复原同一模型状态和相机设置时，只补缺失或失效的方向，并保留已有帧及补跑来源。若场景、版本或相机条件已变化，按当前目标重新取证，旧图保留为历史证据。已通过读图的静帧无需因回包传递失败而重新渲染，可从原路径重新读取。以上是取证交接条件，实际运行观测见下方核查表。 [进程返回字段](../../tools/write-stdin.md#参数与结果)

例如，用户要求检查「当前猫模型的尾巴」，列表选中 `hi3d-cat_3.glb`，`studio_get_state` 仍确认 `_2` 已就绪，则目标是 `_2`。如果切换已清除加载身份，先处理未就绪状态。截图开始后，Hi3D 的护栏检查会话、句柄和工作区，未锁定同工作区内的 `fileName`、加载代次或镜头。即使截图登记成功，版本或观察方向不能确认时，仍须保留不确定性或重新取证。

## Vet3D 迁移与核查范围

Vet3D 可把目标模型和证据图分开引用。针对指定文件的固定渲染，从已解析的模型版本读取；针对当前视窗的截图，由宿主在同一次取证中记录实际加载版本和所用镜头，并把这些信息与实际图像一起持久化。若捕获期间版本或镜头发生变化，按本次采集契约标记失效或重新采集。尺寸和 MIME 以最终编码后的文件为准。相机能确认时可记录相机引用或参数；只知道这是当时的自由视角时如实记录。模型所需的图像内容可直接随工具结果送入上下文，或者先返回可解析的文件引用，再由看图工具取得。

**Vet3D 设计示例。** 字段为业务建议，未对应某个供应商 SDK。`cameraRef` 在固定相机路线指向可复现的相机定义。

```json
{
  "workspaceRef": "workspace-01",
  "modelRevisionRef": "cat-v2",
  "source": "fixed-camera-render",
  "cameraRef": "cat-left-profile",
  "image": {
    "artifactRef": "evidence-01",
    "path": "exports/cat-v2-left.jpg",
    "mimeType": "image/jpeg",
    "width": 960,
    "height": 720
  }
}
```

| 证据等级 | 已核查与下一步 |
| --- | --- |
| 安装包静态实现 | [Runtime 清单](</D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) 确认 1.2.11。[桌面包](</D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) 的 SHA-256 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`。`out/renderer/assets/index-CDPCug_K.js:146–148` 的 `S0e`、`mS`、`M0e`、`vi` 和第 5546 行的 `StudioHost.capture`、`ht`、`Ue`、`Ce` 可复核注册、分派、编码和写入，`capture` 成员字节偏移为 `4717572`。`out/preload/index.js:1` 提供文件 IPC。`out/main/index.js:29` 的 `fileWriteArtifact` 落盘和登记，成员字节偏移为 `178361`。[Runtime](</D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs:2>) 的 `forwardServerRequest`、`handleServerResponse`、`registerArtifact` 和宿主通知处理提供请求关联及产物交接。 |
| 离线复现 | 已有替身 canvas 测试覆盖等比缩放、JPEG 参数与原画布回退。可按包内 `M0e` 用替身 `StudioHost` 重现同句柄、同工作区切换模型后旧状态仍可能返回。两者分别验证函数分支。 [截图工具核查依据](../../tools/studio-capture-view.md#核查依据) |
| Skill 指导 | 静态装配 Skill 规定取证方向、环绕和装配位置，场景渲染 Skill 规定保存相机设置和打开静帧验收。 [装配视角规则](../../upstream/1.2.11/prebuilt-skills/image-to-assembly/references/proxy-segmentation.md) · [渲染交付规则](</D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/scene-render/references/render-delivery.md:7>) |
| 实际运行观测 · Studio 状态 | 本机 2026-11-11 活跃 rollout 第 154→160、327→330 及 523→528 行记录 Studio 空状态与就绪状态。第 164→167 行记录指定版本成功加载。 [状态工具核查依据](../../tools/studio-get-state.md#核查依据) · [加载工具核查依据](../../tools/studio-load-revision.md#核查依据) |
| 实际运行观测 · Blender 渲染 | 同一 rollout 第 282→284 行启动 Blender 并返回进程 ID。第 289→293 行续查同一进程并读取正面、侧面图，外层工具结果含退出码 0 和两个 `input_image` 项。第 336→338 行按同一组相机渲染修改后的场景，第 342→344 行续查仍返回原 `session_id`，未附 `exit_code`。第 349→353 行另一次调用读取已写出的正面、侧面图，收到两个 `input_image` 项。这个样本记录了终态尚未取得时的单帧交付，进程终态、GLB 导出、登记和 Studio 加载各需独立证据。图像项通过 `call_id` 关联对应的 `exec` 调用，完整出站模型请求仍待采集。 [第一次渲染记录](</D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:282>) · [第二次渲染记录](</D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:336>) |
| 实际运行观测 · GLB 几何 | 第 261→263 行启动 `trimesh` 检查并取得进程 ID，第 267→269 行续查同一进程，第 274→276 行收到退出码 0 及几何统计。脚本按模型家族取最大数字版本，输出版本号与第 164→167 行确认加载的版本相符。终端中的中文文件名显示存在编码损坏，该次核对依据是脚本中的家族名和输出的版本号，未做文件哈希比对。 [本机几何检查记录](</D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:261>) |
| 待验证 · Studio 截图端到端 | 已核查的活跃样本未出现 `studio_capture_view` 调用。仍需用同一实际截图对齐 `item/tool/call`、桌面 `requestId`、`file:writeArtifact` 应答、`artifact/registered`、磁盘字节和后续 `view_image` 回包。另实测捕获过程中切换同工作区版本或镜头、取消以及 renderer 重载，确认何时能定位已写文件和复用证据。 |
