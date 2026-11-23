# 多视图按位置配对

核查版本为 Hi3D Agent 1.2.11（Windows x64）。本文中的「位置」指文件和方向在两个数组中共用的索引。本节点将已定稿的建模视图转换为指定后端的有序输入。普通桌面图生 3D 为主例，静态装配路线另有方向清单校验。

## 业务定义

| 项目 | 节点契约 |
| --- | --- |
| 触发条件 | 任务选用多视图 3D，且已定稿视图组明确了参与建模的图片版本。只使用一张图时交给单图路线。 |
| 上游与输入 | 接收[整组视图验收与定稿](review-and-finalize-view-set.md)选定的视图版本、方向、用途及可用的审查依据。Vet3D 按定稿时确认的资产版本和摘要解析实际工作区文件。Hi3D 普通路线由 Agent 将选定路径及方向传给工具，审查依据由调用方保留。 |
| 输出 | 形成实际文件与后端方向的一组有序配对。Hi3D 工具接收同序的 `images` 和 `views`，或 `images` 和显式 `imageSlots`。仅用于验收或补充参考的图像按既定用途保留。 |
| 完成条件 | 参与建模的每张定稿图都能解析到其确切版本，文件与后端支持的方向逐项对应，排列后仍可追溯到原定稿依据。发现文件、方向、用途或版本与定稿不符时，返回上游处理。 |
| 下游 | 向[生成前预检](preflight-generation.md)交付实际文件路径、顺序、语义方向及适用的评审依据。下游检查生成参数、槽位和提交条件。 |

## Skill 绑定

| 归档 Skill | 作用与选用条件 | SHA-256 |
| --- | --- | --- |
| [hi3d/SKILL.md](../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md) | **通用入口。** 普通多视图只使用用户真实提供且标明方向的前、后、左、右图，包含正面。允许缺少其他方向，缺位不复制、镜像或臆造。`images` 与 `views` 逐项对应。 | `4c268ae14ece561234682d564cdfa6264c1f121a9ea118137c0388a9240c217d` |
| [image-to-assembly/SKILL.md](../upstream/1.2.11/prebuilt-skills/image-to-assembly/SKILL.md) | **静态装配领域 Skill。** 选用逐部件重建、配准和装配时，按部件审查方向、来源及图像一致性。允许进入生成的视图写入方向清单，脚本检查方向证据与哈希并按固定顺序交接。 | `cf4ec08dec0decfd69560a940cc26ea18fecf559ea87852c269fd2682555705f` |
| [head-reference/SKILL.md](../upstream/1.2.11/prebuilt-skills/head-reference/SKILL.md) | **头部参考图领域 Skill。** 选用人像头部参考图流程时，用其姿态基准和版本化评审确定可交接的候选。 | `7e7fa5b0cd74928feac546a64edb0d71c77d66f6e5756bfef8c528523af95795` |

部件清单、粗模环绕关卡和头部评审矩阵仅在选用相应领域 Skill 后生效。顶视可作为装配路线的结构证据，具名 3D 槽位仍限前、后、左、右。 [归档版本说明](../upstream/1.2.11/README.md) · [装配方向约定](../upstream/1.2.11/prebuilt-skills/image-to-assembly/references/view-conventions.md) · [头部评审契约](../upstream/1.2.11/prebuilt-skills/head-reference/references/review.md)

## LLM Tools

| LLM Tool | 注册来源与用途 | 本节点的调用时机和条件 |
| --- | --- | --- |
| [view_image](../tools/view-image.md) | 随包 Codex 提供的图像查看工具。 | 文件引用有疑问时读取对应的工作区路径。若实际内容需要重新认定方向或视觉质量，交回整组验收。 |
| [user_interaction](../tools/user-interaction.md) | Hi3D Runtime 动态工具，向用户收集必要信息。 | 需要用户澄清会影响配对的文件指代时使用。Vet3D 若需修改因后端能力不匹配的定稿用途，可用宿主交互收集用户选择。生成参数面板由 Runtime 在下游处理。 |
| [hi3d_api](../tools/hi3d-api.md) | Hi3D Runtime 动态工具，提供计划校验和生成动作。 | 将配对传入 `generate_3d`。只核对客户端计划时可显式传 `dryRun: true`。正式生成及作业续查按下游状态执行。 |

工具的模型可见描述和通用实现见独立工具页。`generate_3d` 是 `hi3d_api` 的动作，`front` 等是方向枚举，`imageSlots` 是请求字段。`view_contract.py` 和 `reviewed_submit.py` 是装配路线的本地脚本。`image_classification` 记录主体类别，配对沿用上游主体结果。工具注册和 Skill 指导来自安装包，正式调用证据另见本文的核查范围。 [主体分类工具](../tools/image-classification.md) · [工具索引](../tools/README.md)

## Hi3D 实现

### 决策

1. **取到实际文件路径。** 桌面端按附件顺序传入图像。新导入的原件进入工作区 `inputs/`。生成会话预览时，`localImage` 指向预览，原件另以含名称和路径的 `mention` 提供。附件入参没有方向字段。`images` 中的具体路径决定本次读取的字节，传入预览路径时直接读取预览。来源见 `resources/app.asar` 内 `out/renderer/assets/index-CDPCug_K.js` 的 `GS`、`Wa`、`QI`、`Yce`，以及 `out/main/index.js` 的附件导入处理。 [附件落盘与会话交接](../infrastructure/workspace/llm-context.md#组装本轮正文和附件)
2. **把已选文件绑定到后端方向。** 普通路线由同一个 Agent 根据用户标注、目标主体和姿态执行选图与配对。这里从选定的路径及语义方向开始组包。通用 Skill 要求提供正面图及其方向配对，可以排在数组的任意位置。普通客户端校验方向合法性和索引对应关系，离线模拟提交可接受仅有左、右两图。同一方向存在多张候选时，已核查链路中未发现固定打分规则、按文件名自动配位或按像素识别方向的客户端步骤。主体基准、仅作补充的参考图以及必保特征留在上游记录。普通 3D 的本地图组包没有独立的主图、辅助图或必保特征字段。 [通用方向规则](../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md#默认行为) · [整组视图验收与定稿](review-and-finalize-view-set.md)
3. **按专项规则交接。** 静态装配路线把已审查部件的路径、方向证据和图片 SHA-256 交给 `view_contract.py`。该脚本要求清单使用 `hi3d-front-neg-y-z-up-v1`，有两到四个方向且包含正面。逐图检查 `direction_reviewed`、非空证据、相机方向、上方向和画面前向地标声明。对明确标记旋转对称且无法观察前向地标的对象，允许 `not_observable`。脚本也检查后缀、非空、每张不超过 20 MiB，以及当前字节是否匹配审查哈希。实际画面方向由审查者确认。 [专项视图规则](../upstream/1.2.11/prebuilt-skills/image-to-assembly/references/view-conventions.md) · [装配视图审查](../upstream/1.2.11/prebuilt-skills/image-to-assembly/references/multiview.md)

### 执行

**根据已验证行为重建的预检请求。** 用户已确认 `IMG_5081.png` 是左视、`IMG_5082.png` 是正视，两份都选用工作区原件。面板所需选项已齐全，预期返回 `file_count=2`、`image_slots=[2,0]` 和 `consent.result="ready"`。

```json
{
  "action": "generate_3d",
  "kind": "model",
  "targetName": "猫",
  "images": ["inputs/IMG_5081.png", "inputs/IMG_5082.png"],
  "views": ["left", "front"],
  "settings": {
    "model_type": "v3.0:quality",
    "generation_type": "both"
  },
  "jobPath": "hi3d/cat-model.json",
  "outputDir": "exports/hi3d-cat-model",
  "dryRun": true
}
```

Runtime 将 `images` 依次转成重复的 `--image` 参数，并传 `--views left,front`。显式数字槽使用 `--image-slots`。Python 检查最多四张工作区图片，验证文件存在、非空、后缀受支持且每张不超过 40 MiB，并计算 SHA-256。多张图的方向数组须与文件等长，方向或数字槽位各自唯一，两种参数互斥。单图无方向时使用槽 `0`。空缺方向省略，相应位置无需补文件。来源见安装包 `resources/runtime/dist/runtime.mjs` 的 `Kj`，以及 `hi3d/scripts/hi3d_parameters.py` 的 `file_info`、`build_plan`、`multipart`。

具名 `views` 由客户端按固定映射换成数字。调用者直接传入的数字槽按原值和原序组包，例如桌面参数契约中的 `[0,2]` 仍为 `[0,2]`。显式数字槽的组包核查只证明客户端传值，云端如何解释该数值需要另行验证。 [桌面参数契约](../upstream/1.2.11/prebuilt-skills/hi3d/references/desktop-parameters.md)

**实现伪代码。** 概括普通 3D 的本地图分支。入参已经过 Runtime 类型检查和转发，空方向数组按省略处理。示例省略与视图无关的参数。

```python
def plan_local_model_images(images, views=None, explicit_slots=None):
    require(1 <= len(images) <= 4)
    require(views is None or explicit_slots is None)

    slot_for = {"front": 0, "back": 1, "left": 2, "right": 3}
    if views is not None:
        require_matching_unique_values(views, images, slot_for.keys())
        slots = [slot_for[view] for view in views]
    elif explicit_slots is not None:
        require_matching_unique_values(explicit_slots, images, range(4))
        slots = list(explicit_slots)
    else:
        require(len(images) == 1)
        slots = [0]

    files = [inspect_workspace_image(path, field="images") for path in images]
    return files, slots
```

#### 从方向标签追踪到上传字节

普通路径的 multipart 先写 `request` 和 `imageSlots` 两个 JSON 字段，再按原顺序写入重复的 `images` 文件字段。`imageSlots[i]` 对应第 `i` 个 `images` 文件部分。组包时按路径重读原始字节，在写入同一临时流时核对本次正式计划记录的大小和 SHA-256。Python 将这份流交给本地代理，Electron 按原 boundary 转发请求体，上传使用分块传输。归档 `calling.md` 记载 Runtime 会按前后左右重排。1.2.11 普通 Runtime 的转发、Python 规划和模拟 POST 均保留调用顺序。 [归档调用说明](../upstream/1.2.11/prebuilt-skills/hi3d/references/calling.md) · [本地组包契约](../tools/hi3d-api.md#3d-本地文件组包)

装配桌面路径先由 `load_views` 按 `front → back → left → right` 提取已审查的文件和方向，跳过缺位。`reviewed_handoff` 校验显式 `multi_images_bit` 与清单是否一致，前加左为 `1010`，仍填写 `1111` 会拒绝。通过后从 `settings` 移除该位图，并将排序后的 `images` 和 `views` 交给通用桌面工具组包。来源见安装包 `image-to-assembly/scripts/view_contract.py:34` 和 `reviewed_submit.py:78`。

**离线捕获结果。** 使用两张内容不同的合成 PNG。表中哈希为实际解包所得图片字节的 SHA-256 前 12 位。

| 调用路径与输入 | `imageSlots` | 第一个 `images` 文件部分 | 第二个 `images` 文件部分 |
| --- | --- | --- | --- |
| 通用路径，左视文件、正视文件配 `left,front` | `[2,0]` | `input-0.png`，左视 `509df3ad328f` | `input-1.png`，正视 `91836062eef0` |
| 通用路径，只将方向标签换成 `front,left` | `[0,2]` | `input-0.png`，左视 `509df3ad328f` | `input-1.png`，正视 `91836062eef0` |
| 装配清单以左视、正视写入，交接时输出正视、左视配 `front,left` | `[0,2]` | `input-0.png`，正视 `91836062eef0` | `input-1.png`，左视 `509df3ad328f` |

后两行的槽位相同，文件顺序不同。核对配对时，必须把槽位和实际文件部分一起看。若将原件路径换成同名预览路径，槽位可以保持原值，multipart 则包含预览的字节。 [预检与正式提交的分支](preflight-generation.md#执行)

#### 装配审查哈希的交接范围

`reviewed_submit.py --backend runtime` 将逐图审查哈希和 `manifest_sha256` 放在独立的 `views` 审计对象中。交给 `hi3d_api` 的 `arguments` 只有实际路径、方向及其他生成参数。正式 Runtime 调用会按当时的路径重新计算哈希。因此，清单审查到正式规划之间有文件替换窗口。正式规划之后，普通组包的哈希检查才约束本次计划对应的上传字节。来源见安装包 `image-to-assembly/scripts/reviewed_submit.py:78`、`hi3d/scripts/hi3d_api.py:177` 和 `hi3d_parameters.py:198`。

装配的 `--backend public` 分支另有 `ReviewedClient`，在转发前回读即将发送的同一份 multipart，与原审查记录逐项比对，并保存审计文件。该分支检查公共请求格式的 `multi_images`。本次用合成公共格式的请求体验证了审计函数会拒绝文件重排、字节替换和位图变化。桌面 `--backend runtime` 只执行上述本地交接。来源见安装包 `image-to-assembly/scripts/reviewed_submit.py:44` 和 `view_contract.py:70`。

### 验收

核对每个输入文件版本和方向仍与定稿记录一致，再按索引核对 `images[i]` 与 `views[i]`，以及预检返回的 `image_slots[i]`。预检通过表示本地规划接受了该配对。主体、姿态和视图实际内容的结论来自整组验收。已提交时，可用当轮工具参数或 job 中的 `files[].path`、`files[].sha256` 和 `parameters.imageSlots` 追溯正式计划。来源见安装包 `hi3d/scripts/hi3d_jobs.py:192`。

| 核查用例 | 通用桌面路径 | 装配 Skill 的桌面交接 |
| --- | --- | --- |
| **方向非法** | 未知方向（如 `top`）、重复方向、长度不匹配、多图缺方向、非法或重复数字槽、同时提供两组非空方向数组以及第五张图均在本地拒绝。只互换合法标签或将同一路径分给两个不同方向，可以通过组包。 | 未知方向键在检查视图集合时拒绝。合法键下的相机向量、上方向或地标声明冲突，在检查对应方向时拒绝。 |
| **缺正面** | 普通 Skill 要求正面。底层接受 `left,right`，模拟 POST 捕获到 `[2,3]` 和对应的两份图片。 | 清单入口强制包含 `front`。同一左、右组合在 `load_views` 被拒绝，无交接参数。 |
| **文件被替换** | 正式计划建好后再换成等长的不同字节，组包报 `Input changed after planning; no task was submitted`，发生在鉴权、建 job 和 POST 前。按替换字节重建计划并使用已存在的旧 `jobPath`，会因指纹不同拒绝。 | 原清单重新交接报 `Image changed after direction review: left`。若直接沿用旧交接参数，替换发生在首次正式规划前且尚无 job，Runtime 会按新字节规划。模拟 POST 捕获到左视槽 `2` 对应的新字节 `3505350828f3`，旧审计仍记录 `509df3ad328f`。 |
| **清单版本过期** | 通用路径接收文件和方向，没有清单版本输入。 | 未知 `convention` 和图片哈希不匹配都会被拒绝。把 `manifest_version` 或审查日期改为旧值，或另存一份新清单且保留旧清单与旧图原样，旧清单仍可通过。`manifest_sha256` 用于追溯读到的清单内容，脚本未将其与项目指定的当前版本比较。 |

矩阵中的具体错误来自函数级核查。装配 `reviewed_submit.py --backend runtime` 的 CLI 将此类异常包装为通用错误 JSON，退出码为 `2`。来源见安装包 `image-to-assembly/scripts/reviewed_submit.py:117`。

### 摘要与指纹的用途

| 记录 | 检查或追溯的对象 |
| --- | --- |
| 装配清单中每张图的 `sha256` | 装配交接读取的文件是否与审查时一致。 |
| 装配审计中的 `manifest_sha256` | 此次读取的清单内容，可用于事后比对。 |
| 正式计划中每张图的 `sha256` | 从本次计划到组包，实际写入请求体的字节是否一致。 |
| job 的计划 `fingerprint` | 现有 `jobPath` 是否可复用。指纹覆盖参数和有序文件记录，含实际路径与文件哈希。 |

显式 `dryRun` 返回本地预检信息。正式调用会重新构建计划，预检的哈希和指纹没有冻结下一次调用的文件。 [预检验收](preflight-generation.md#验收)

## 完成与恢复

| 情形 | 处理方式 |
| --- | --- |
| 配对完成 | 将定稿对应的配对和实际路径交给预检。后续面板续调使用原配对。 |
| 图片字节、方向、用途或定稿版本变化 | 保留原候选、审查记录和已有 job。交还整组验收以更新受影响的图片和依赖。在取得新定稿后重新配对、执行适用的装配交接及预检。按装配 Skill 的依赖失效规则，将依赖旧图的高模候选标为失效。 |
| 上游候选或下游生成返回 `pending` | 保留原 `jobPath`、已有任务 ID、对应的输入配对和输出位置。用 `hi3d_api` 的 `wait` 动作继续等待原 job，成功后从同一 job 下载，已完成下载时直接使用返回文件。 |
| 提交状态不明 | 保留原 job、配对和请求参数。有任务 ID 时查询原任务，缺 ID 时先核对平台任务历史。等待核对期间保留原任务意图。 |
| 取得了新候选，整组尚未定稿 | 保留成功作业、候选版本和观察依据，交回整组验收与定稿。以其新选定的版本和用途作为配对输入。 |

装配的修订和依赖失效规则见安装包 `image-to-assembly/references/contracts.md:51`。 [装配视图修订](../upstream/1.2.11/prebuilt-skills/image-to-assembly/references/multiview.md) · [通用作业恢复规则](../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md#3d-任务工作流) · [预检节点的完成与恢复](preflight-generation.md#完成条件与恢复)

## Vet3D 迁移与核查范围

Vet3D 的 LLM、生图模型、3D 模型和 API 均待选型。整组定稿固定每张入选图的资产引用、实际版本、方向依据、摘要和用途。供应商适配层读取同一份定稿，按参与建模的记录一次导出文件与方向参数。排序时移动整条记录。

**Vet3D 拟议的提交约束。** 将当前已审查清单的版本、逐图方向、资产版本和审查 SHA-256 一并交给提交适配器。适配器先核对该清单仍是当前有效版，再对即将上传的同一份字节计算哈希，并按方向逐项与审查记录比对。一致时提交这份已核对的输入。清单过期或字节不符时，返回具体的受影响方向重新审查和预检。已有远端作业继续使用原记录续查。

**Vet3D 设计示例。** 方向名称是业务语义，图片引用和版本由资产管理解析。

```json
{
  "subjectRef": "cat-01",
  "anchorRef": "photo-5082@v1",
  "pose": "自然站立",
  "preserve": ["耳缘轮廓", "尾部姿态"],
  "selectedViews": [
    {"direction": "left", "imageRef": "photo-5081@v1", "evidence": "用户标注，已核对画面"},
    {"direction": "front", "imageRef": "photo-5082@v1", "evidence": "用户标注，已核对画面"}
  ],
  "auxiliaryReferences": [
    {"direction": "top", "imageRef": "photo-5083@v1", "purpose": "核对背部轮廓"}
  ]
}
```

业务方向支持前、后、左、右、顶，并约定动物自身侧别、相机方向和顶视的头部朝向。顶视已定稿为验收或结构参考时，适配器保留该用途。顶视已定稿为建模输入时，须由支持顶视的后端映射。若任务要求五图参与建模且后端只有四槽，报告能力不匹配。用户同意改为四图建模与顶视验收时，先由上游更新顶视用途，再重新配对。

- **实际运行观测。** 2026-11-11 的生产 rollout 第 53、68 行记录同一生成计划的首次工具调用及参数续调。`images` 按原顺序指定三份 `inputs/` 下的原件，`views` 对应为 `front`、`back`、`right`。第 103 行回包含同一作业路径、任务 ID 和下载文件。原作业记录的 `state` 为 `success`，`parameters.imageSlots` 为 `[0,1,3]`。本次读取的三份本地原件逐项与 `files[].sha256` 相符。作业保存的服务返回值 `result.multiViewInfo.multiViewSourceImageList` 中非空下标也为 0、1、3。证据覆盖该次选图、客户端保存的正式计划和服务回传的来源图位置。 [首次工具调用](</D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:53>) · [续调](</D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:68>) · [同一作业记录](</D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/hi3d/hi3d-cat-multiview.json>)
- **已静态核查。** 安装包的附件原图与预览分支、Runtime 路径转发、随包 Python 的配对和组包、装配清单与交接，以及 Electron 代理。Runtime SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`。
- **已离线验证。** 用合成 PNG 和模拟 Python HTTP 传输捕获正式 multipart，验证槽位、文件顺序、实际字节和异常矩阵。随包装配 Runtime 交接测试也已通过。另一项独立模拟执行 `app.asar` 的 `out/main/index.js` 第 29 行中的 `_l.handle` 和 `Nl.requestTool`，确认 multipart 的 boundary 与实体字节原样到达模拟 Electron 请求写入器。以上测试未联网。
- **Skill 指导。** 通用入口要求真实视图中包含正面。选用静态装配时，另按其方向清单、逐图证据及哈希规则交接。 [Skill 绑定](#skill-绑定)
- **仍待验证。** 该次真实网络请求的 multipart 原始字节、云端如何解释各槽位、同方向多候选或不明标注的处理、建模精度和跨视角一致性。Vet3D 的五视图交接与视觉验收需要在模型选型和实现后验证。
