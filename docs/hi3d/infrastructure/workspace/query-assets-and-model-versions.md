# 查询工作区素材与模型版本

核查对象为本机 Hi3D Agent 1.2.11（Windows x64）和随包 Codex 0.166.0。本节点位于工作区基础设施层，负责把用户或流程指代的素材、模型家族和版本解析为实际引用。普通文件查询、宿主的模型列表和 Studio 当前加载状态各有自己的数据来源。

## 业务定义

| 项目 | 节点契约 |
| --- | --- |
| 触发条件 | 用户提到已有素材、以前生成的产物、指定模型版本或「最新版」，或下游需要确定拟复用的实际输入文件。用户指代正在显示的模型时，追加一次[当前视窗状态查询](read-studio-state.md)。 |
| 上游与输入 | 接收[当前轮的工作区上下文](llm-context.md)提供的 `assetId`、`cwd`、线程与轮次、正文和附件引用。可同时接收先前工具返回的文件、Skill 工作流产物、明确的文件名或模型家族名，以及本次任务给出的图片角色和约束。 |
| 输出 | 返回可访问的工作区路径及其来源。模型查询返回家族、实际文件名、相对路径、数字版本号、大小和修改时间，并附已有的版本元数据。视窗查询额外提供实际加载版本和就绪状态。存在歧义或目标暂不可用时，保留原指代和候选。 |
| 完成条件 | 查询范围仍对应原工作区，文件或版本已按明确条件解析，且下游能用返回引用访问同一份文件。用户指的是当前画面时，须核对实际加载版本。 |
| 下游交接 | 交付实际路径、版本与来源。[确认建模主体](../../atomic-nodes/confirm-modeling-subject.md)决定图片的证据用途，[整组视图验收与定稿](../../atomic-nodes/review-and-finalize-view-set.md)确定入选版本及用途，[多视图按位置配对](../../atomic-nodes/pair-multiview-inputs.md)映射后端槽位，[生成前预检](../../atomic-nodes/preflight-generation.md)核对本次提交文件和参数。已解析的模型版本也可交给本地编辑或 Studio 加载。 |

## Skill 绑定

工作区绑定、目录读取、模型版本扫描及 Studio 选择器由宿主和执行环境提供，可服务普通会话。选用建模 Skill 后，按该 Skill 决定素材能否复用和哪些证据需要审查。下表为仓库内归档的 1.2.11 快照。 [归档版本说明](../../upstream/1.2.11/README.md)

| 归档 Skill | 作用与选用条件 | SHA-256 |
| --- | --- | --- |
| [hi3d/SKILL.md](../../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md) | **通用建模入口。** 普通图片生成、编辑或图生 3D 选用。指导查看与复用参考素材、读取生成返回、核对已有作业，以及在需要时登记模型。普通多视图按用户明确的真实视图选图。 | `4c268ae14ece561234682d564cdfa6264c1f121a9ea118137c0388a9240c217d` |
| [image-to-assembly/SKILL.md](../../upstream/1.2.11/prebuilt-skills/image-to-assembly/SKILL.md) | **静态装配领域 Skill。** 仅在采用部件重建、配准和装配时，按部件查已审查的参考、方向和来源记录。提交装配视图时沿用专项清单与哈希校验。 | `cf4ec08dec0decfd69560a940cc26ea18fecf559ea87852c269fd2682555705f` |
| [head-reference/SKILL.md](../../upstream/1.2.11/prebuilt-skills/head-reference/SKILL.md) | **头部参考图领域 Skill。** 仅在选用头部参考图流程时，按其基准姿态、相对或标准视角及评审版本读取候选。相应的评审与确认要求随领域流程执行。 | `7e7fa5b0cd74928feac546a64edb0d71c77d66f6e5756bfef8c528523af95795` |

## LLM Tools

模型可见描述与通用实现由独立工具说明或固定版本工具定义维护。

| LLM Tool | 用途摘要 | 本节点的调用时机和条件 |
| --- | --- | --- |
| [`exec_command`](../../tools/exec-command.md) | 随包 Codex 的本地命令能力。 | 路径未知且当前会话暴露该工具时，在绑定的 `cwd` 内只读查找文件。实际会话以生效的本地命令工具为准。 |
| [view_image](../../tools/view-image.md) | 把已知本地图像交给模型查看。 | 取得实际路径后，用于核对画面、原件细节或候选内容。 |
| [workflow_report](../../tools/workflow-report.md) | 读取或续接当前 Skill 工作流记录。 | 引用的是该工作流的输出时，可用 `inspect` 查看当前图和未分配产物。仅在同一线程有中断图需要继续时用 `resume`。 |
| [studio_get_state](../../tools/studio-get-state.md) | 读取 Studio 实际加载的模型和视窗状态。 | 用户指代「现在看到的模型」或操作前需确认实际加载版本时调用。 |
| [user_interaction](../../tools/user-interaction.md) | 由宿主收集用户输入。 | 同名素材、多个家族或版本指代冲突，且取舍会改变操作对象时使用。 |
| [hi3d_api](../../tools/hi3d-api.md) | 查询和恢复已有生成作业。 | 查询目标仍由同一远端作业生成，或需要确认原作业的输出时，按原 `jobPath` 使用 `wait`、`query` 或 `download`。普通文件发现和版本枚举可在本地完成。 |
| [exec](../../tools/exec.md) | 承载 Code Mode 嵌套调用。 | 当前会话通过 `exec` 暴露命令、看图或 Studio 工具时，使用对应的 `tools.*` 方法。 |
| [wait](../../tools/wait.md) | 按 `cell_id` 续查 Code Mode 执行单元。 | `exec` 返回运行中的单元且需要该次查询结果时，沿用原 `cell_id`。 |
| [write_stdin](../../tools/write-stdin.md) | 按 `session_id` 续取同一命令进程的输出。 | 本地查询命令返回可续接的 `session_id` 时使用。 |

`workspace/open`、`workspace/models` 和 `workflow/read` 是宿主 RPC。`workspace/modelUpdated` 是宿主通知，`file:resolveImagePreview` 是 Electron IPC。`inspect`、`resume` 属于 `workflow_report` 的操作，`query`、`wait`、`download` 属于 `hi3d_api` 的动作。`localImage` 和 `mention` 属于会话输入类型。领域 Skill 的视图清单和评审脚本属于本地实现。工具注册和调用条件见各自说明。本地文件查询、工具看图与 Studio 状态查询的实际运行证据见本文核查范围。 [模型目录 RPC](interfaces/model-catalog-rpc.md) · [工作流读取 RPC](interfaces/workflow-read-rpc.md) · [图片预览 IPC](interfaces/image-preview-ipc.md)

## Hi3D 实现

### 决策

1. **识别用户指代。** 先用本轮附件、已确认的原件路径和先前工具返回的实际文件。用户指定文件名时解析精确版本，指定家族「最新版」时按数字版本号，指代「当前画面」时以 Studio 实际加载结果为准。只有路径或版本尚未确定时，才查询对应来源。
2. **区分候选图片和本次生成角色。** 用户正文或上游业务记录指定主体基准、操作主图、补充参考、目标方向和必保特征。查找过程保留这些语义与实际文件引用的关联。`localImage` 可能用于会话预览，`mention` 可指出原件路径。宿主文件引用本身没有主图、方向或必保特征字段。
3. **识别候选的来源和可用范围。** 工作区内可访问的文件、已登记的模型版本和当前 Skill 图产物可以有交集。任务涉及已登记版本或当前视窗时，分别检查对应的模型列表或实际加载状态。查询成功的素材仍由[主体确认](../../atomic-nodes/confirm-modeling-subject.md)、[补图](../../atomic-nodes/generate-new-view.md)或[修图](../../atomic-nodes/edit-existing-view.md)节点决定是否适用。

### 执行

**普通素材。** renderer 的 `cS` 和 `Yce` 把附件与原件路径交给会话。已知路径可直接交给读取工具，未知路径可在当前工作区查看 `inputs/`、`exports/` 或用户指定的目录。桌面预览来自消息、看图活动及工作流产物中的已知路径。`file:resolveImagePreview` 校验指定路径的工作区归属、扩展名及普通文件属性，再返回本地预览 URL。`artifact/register` 创建产物记录，内部产物读取用于提交和打印。核查的 RPC 和 LLM 工具定义中未发现通用 `artifact/list`、`artifact/get` 或工作区文件枚举接口。 [会话附件组装](llm-context.md#执行) · [工作流产物查询范围](../../tools/workflow-report.md#参数与结果)

**工作流产物。** `inspect` 返回当前图的节点摘要和未分配产物，`resume` 返回续接图的节点和产物引用。图的完成状态与产物的实际存在、模型登记和 Studio 加载分别核对。发生图写入故障或跨进程续接时，模型回包、桌面缓存与磁盘快照可能对应不同进度。用实际读回的图找到目标引用，再检查所指向的工作区文件或已登记模型版本。 [工作流图的状态发布与续接](workflow-graph-state.md) · [工作流读取 RPC](interfaces/workflow-read-rpc.md)

例如用户用正文指定「用正面照片作为主图，左侧照片仅供核对毛纹，生成后视并保持站姿和尾部弯曲」。查询分别解析两张照片的实际文件路径，将主图、补充参考、目标后视和两项必保特征原样交给补图节点。若下游采用普通 `EDIT` 图生图，本次操作主图排在 `images` 首项，补充参考排在其后，目标方向与必保特征写入 `prompt`。若下游采用普通多视图 3D，各入选路径和对应方向由配对节点分别传入 `images` 与 `views`，仅用于验收的参考和必保特征随业务记录保留。 [生成新视角的图片角色](../../atomic-nodes/generate-new-view.md#业务定义) · [3D 文件与方向组包](../../atomic-nodes/pair-multiview-inputs.md#执行)

**模型版本。** `workspace/open` 返回 `{workspace, models}`，`workspace/models` 返回 `{models}`。两者共用 Runtime 的 `Jg.listModels`。已核查的桌面路径以 `workspace/open` 初始化列表，并用 `workspace/modelUpdated` 对当前工作区增量合并版本。`model/list` 用于 LLM 模型选择。 [模型登记与提交说明](../../tools/hi3d-api.md#参数与结果)

**根据已验证行为重建的宿主请求。** 示例只展示方法及参数，假定 `asset_example` 已登记。

```json
{
  "method": "workspace/open",
  "params": { "assetId": "asset_example" }
}
```

Runtime 校验登记目录，再扫描工作区根目录。版本文件名匹配 `^(.+)_(\d+)\.glb$`，匹配时忽略大小写。符号链接和非普通文件跳过。家族名由第一组去掉可选的 `hi3d` 前缀及分隔符，第二组转为数字版本号。`size` 与 `updatedAt` 分别取文件大小和 `mtimeMs`，再按工作区 ID 与实际文件名补充登记的线程、轮次、标签或来源。登记元数据可以缺省。查询范围为根目录，`exports/` 中的 GLB 可按路径读取，进入版本列表要符合根目录的版本规则。

**实现伪代码。** 前一个函数概括 Runtime 的模型枚举，后一个函数概括 Studio 在已有列表上的选择分支。

```python
def list_models(asset_id):
    cwd = require_managed_workspace(asset_id)
    families = {}
    for entry in read_root_entries(cwd):
        match = indexed_glb_name(entry.name)
        if match is None or entry.is_symlink or not entry.is_regular_file:
            continue
        family = strip_optional_hi3d_prefix(match.family)
        version = {
            "name": family,
            "index": int(match.index),
            "fileName": entry.name,
            "path": entry.name,
            "size": entry.size,
            "updatedAt": entry.mtime_ms,
            **(model_metadata(asset_id, entry.name) or {}),
        }
        families.setdefault(family, []).append(version)

    result = []
    for family, versions in families.items():
        versions.sort(key=lambda version: version["index"])
        result.append({"name": family, "versions": versions, "latest": versions[-1]})
    return sort_families_by_name(result)


def select_studio_version(models, file_name=None, model_name=None):
    versions = [version for model in models for version in model["versions"]]
    if file_name:
        return find_exact_name_or_path(versions, file_name)
    if model_name:
        model = find_exact_family(models, model_name)
        return model["latest"] if model is not None else None
    return max(versions, key=lambda version: version["updatedAt"], default=None)
```

精确文件选择优先。明确文件或家族查无结果时，该选择分支返回空候选。两者都省略时，Studio 从所有家族的所有版本中选最近修改的文件。桌面打开工作区时也用该时间口径设置初始选中项。家族的 `latest` 只取最大数字版本号。涉及当前画面时，须另外查询实际加载状态。需要展示指定版本时，交给[加载指定版本并确认](load-studio-revision.md)，以实际加载结果确认目标。

实现出处为安装包 `resources/runtime/dist/runtime.mjs` 的 `Jg.listModels`、`listGlbFileNames`、`Xo` 及工作区 RPC 处理器。桌面代码位于 `resources/app.asar` 的 `out/renderer/assets/index-CDPCug_K.js` 中，`Jr`、`H0e` 和 `StudioHost` 分别负责列表、最近更新的选择与视窗加载状态。预览 IPC 位于 `out/main/index.js` 的 `fileResolveImagePreview` 和 `cl`。

### 验收

交接前核对实际路径、工作区归属、版本及查询依据。目录扫描可证明文件名和属性满足列表规则。后续读取或加载验证文件内容是否可用，主体、方向、姿态及画质由相应业务步骤验收。

| 核查用例 | 可确认的结果 |
| --- | --- |
| 模拟家族含 `cat_1.glb`、`hi3d-cat_2.glb`、`hi3d-cat_10.glb` | 三者归入 `cat` 家族，数字次序为 `1, 2, 10`，家族最新版是 `_10`。 |
| `_2` 的修改时间最近 | Studio 省略选择条件时选 `_2`，指定家族时仍选 `_10`。 |
| 文件选择明确指定不存在的版本，同时给出有效家族 | 精确查找返回空候选。 |
| 文件已定位，视窗未就绪或显示另一版本 | 文件操作可以基于已解析的版本执行。指代当前画面时需以 `studio_get_state` 的身份和就绪状态复核。生产样本中，同次查询确认工作区文件存在，同时视窗返回 `ready:false`。 [同次查询](</D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:160>) |

## 完成与恢复

| 情形 | 处理方式 |
| --- | --- |
| 文件或版本已找到 | 交付工作区、实际引用和查询依据。选择依赖预览或生成结果时，同时保留原件或候选版本的来源。 |
| 文件缺失、版本冲突或状态已变化 | 在原工作区重新检查路径和版本。明确指定的目标缺失时，保留原指代并收集必要的澄清。工作区或视窗已切换时重新核对上下文再交接。 |
| 候选生成仍为 `pending` | 保留原 `jobPath`、已有任务 ID 和对应输入版本。使用同一作业 `wait` 或 `query`，成功后从原作业下载。一次本地查询本身没有生成作业。 |
| 提交状态不明 | 保存原请求和作业记录。有任务 ID 时查询原任务，缺 ID 时核对平台任务历史。核对结果沿用同一任务。 |
| 候选已取得但未通过验收 | 保留原成功任务、候选文件和失败依据，按选用的 Skill 修订。若需要再次生成，使用新的作业和输出路径，随后复核受影响的输入和视图。 |
| 候选可回填或交给下游 | 查询端交付仍可读取的实际文件版本及来源。多视图候选由整组验收核对方向、主体、姿态、必保特征和允许用途，定稿后交给配对。 |

[生成作业完成与恢复](../../atomic-nodes/preflight-generation.md#完成条件与恢复) · [候选回填与复查](../../atomic-nodes/review-and-finalize-view-set.md#完成与恢复)

## Vet3D 迁移与核查范围

Vet3D 的 LLM、生图模型、3D 模型及 API 均待选型。工作区查询应输出供应商无关的素材引用。为每项记录工作区、资产与实际版本、可访问路径、来源及核对依据。把精确文件、家族最新版、最近修改文件和视窗实际加载版本作为不同查询条件。查询期间文件或视窗发生变化时，按引用和版本重新核对。下游再选择主体基准、本次操作主图、补充参考、目标视角和必保特征，由适配层生成供应商请求。

对于照片或视频帧，保留原件、预览及派生素材的关系。Vet3D 可以使用前、后、左、右、顶的业务方向，查询结果记录方向声明及其来源，视觉验收确认画面与声明是否一致。交给 3D 前的实际输入及方向集合仍由配对和预检决定。 [配对节点的迁移契约](../../atomic-nodes/pair-multiview-inputs.md#vet3d-迁移与核查范围)

- **实际运行观测。** 2026-11-11 的生产 rollout 第 19→24 行，在工作区 `cwd` 用 `exec_command` 执行 `rg --files`，查到三张 `inputs/` 下的原件。第 109→113 行用 `Get-ChildItem` 枚举导出文件，在同一次 `exec` 中通过 `view_image` 读入图像，工具回包含 `input_image`。第 154→160 行同一次 `exec` 用 `Get-Item` 确认已登记 GLB 存在，同时 `studio_get_state` 返回 `ready:false`。这三段记录可分别追溯原件定位、导出文件查找及看图，以及磁盘版本与视窗就绪状态的独立核对。 [原件查询](</D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:19>) · [导出查找及看图](</D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:109>) · [GLB 及状态查询](</D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:154>)
- **实际运行观测 · 宿主 RPC。** 桌面日志第 679–680 行和第 686–687 行分别记录 `workspace/open`、`workflow/read` 发出请求及对应队列请求完成。该日志保留方法和请求关联元数据，完整响应内容需要另行捕获。 [桌面日志](</D:/download/.sparc3d-runtime/environments/prod/logs/desktop-20261111T032128Z-23156.log:679>)
- **已静态核查。** 安装包的素材引用、RPC 边界、根目录扫描与元数据合并、桌面列表刷新、选择器和 Studio 状态。Runtime SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`，桌面包 SHA-256 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`。
- **已离线验证。** 以模拟目录项和文件属性执行提取的 `listModels`、`H0e` 和版本选择函数。验证了旧式文件名归组、数字排序、文件修改时间口径、元数据缺省、符号链接和非普通文件排除，以及显式目标查无结果的分支。
- **Skill 指导。** 通用素材复用和领域视图审查规则按所选路线适用。版本查询交付文件和来源，由下游依适用规则确认用途。 [Skill 绑定](#skill-绑定)
- **仍待验证。** 文件权限拒绝分支、桌面目录 RPC 完整内容、`workspace/modelUpdated` 增量刷新及 Studio 自动加载时序。云端生成结果和质量需另行实测。Vet3D 的素材引用、版本机制和查询接口是拟议设计。
