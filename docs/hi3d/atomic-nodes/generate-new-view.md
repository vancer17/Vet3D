# 生成新视角

分析对象为本机 Hi3D Agent 1.2.11（Windows x64），原安装根目录为 `D:/install/Hi3DAgent`。本地 Skill、参考文档和工具包脚本的路径以 `resources/runtime/prebuilt-skills/` 为基准。已有目标图的定向修订见[编辑已有视角](edit-existing-view.md)。

## 业务定义

根据已有图片，为同一主体生成一个或多个指定的新视角。节点从已知主体、参考图和目标方向开始，交付候选图、实际输入、任务引用及单图检查结果。通过单图检查的候选可以进入[整组视图验收与定稿](review-and-finalize-view-set.md)，存在缺陷或方向不明的候选留存供修订和复查。所选领域 Skill 可以要求先确认基准图，再据此生成其余方向。

| 输入 | 在任务中的用途 |
| --- | --- |
| 主图或已验收的基准图 | 确定要保持的主体、姿态和可见外观。 |
| 补充参考图 | 补充特定角度、结构或纹理依据。角色与主图分别传递。 |
| 已有视角与可选粗模渲染 | 为对应方向提供已知外观，或约束比例、体块和相机。具体用法由领域 Skill 决定。 |
| 目标方向、姿态约定和必保特征 | 指定要产生的观察方向，以及换视角时需要保持的条件。 |

普通 `$hi3d` 图生 3D 路线复用合格照片，缺失方向可以留空，只有一张图时走单图路线。生成新视角是显式选择的图片任务或领域流程。来源见 `hi3d/SKILL.md:18`。

## Skill 绑定

下表链接到仓库内的 Hi3D Agent 1.2.11 原文快照。路径保留安装包 `resources/runtime/prebuilt-skills/` 下的结构，SHA-256 用于核对文件版本。

| Skill 文档 | 在此节点中的角色 | SHA-256 |
| --- | --- | --- |
| [`hi3d/SKILL.md`](../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md) | 桌面通用生图入口，定义提示词校验、提交、恢复及结果查看。 | `4c268ae14ece561234682d564cdfa6264c1f121a9ea118137c0388a9240c217d` |
| [`head-reference/SKILL.md`](../upstream/1.2.11/prebuilt-skills/head-reference/SKILL.md) | 选用头部参考图流程时，建立各自的姿态基准并生成四视图。 | `7e7fa5b0cd74928feac546a64edb0d71c77d66f6e5756bfef8c528523af95795` |
| [`image-to-assembly/SKILL.md`](../upstream/1.2.11/prebuilt-skills/image-to-assembly/SKILL.md) | 选用静态装配流程时，在阶段 C 按独立部件准备四视图。适用范围包括动物。 | `cf4ec08dec0decfd69560a940cc26ea18fecf559ea87852c269fd2682555705f` |

头雕工作流还会组合 `head-reference`，增加品类约束及几何交接检查。通用图片任务与领域 Skill 的选用条件各自独立。当前安装包中未发现由 `editTaskType` 自动加载这两个领域 Skill 的绑定。 [头雕工作流分发入口](../upstream/1.2.11/prebuilt-skills/.dependency-portrait-reconstruction/REFERENCE.md)

## LLM Tools

| 工具 | 模型可见说明摘要 | 在本节点的调用时机 |
| --- | --- | --- |
| [`hi3d_api`](../tools/hi3d-api.md) | 通过 Hi3D Runtime 生成、编辑图片或生成 3D，支持续查同一任务。 | 使用 Hi3D 原生补视角时，调用 `generate_image`，并用 `request.editTaskType` 显式选择 `MULTI_VIEW` 或 `MULTI_VIEW_3VIEWS`。 |
| [`view_image`](../tools/view-image.md) | 查看磁盘上已有的本地图片。 | 查看参考图、基准和新候选。工具把图片送入模型上下文，由 Agent 逐图判断身份、方向及必保项。 |
| [`workflow_report`](../tools/workflow-report.md) | 在使用 Skill 的轮次上报工作流、节点进度和产物归属。 | 执行 Skill 时读取并上报计划，更新实际生成节点及图片归属，使用选中 Skill 的规范节点 ID。 |
| [`user_interaction`](../tools/user-interaction.md) | 通过宿主面板收集输入、偏好或授权。 | 生图前需要补充目标方向、姿态约定或确认生成范围时使用。 |

以下是已选用 `head-reference` 时的候选生成编排示意。整组评审、适用的人工确认及建模交接由下游处理。完整工具描述与执行伪代码见[工具索引](../tools/README.md)。

```text
workflow_report(operation="inspect", skillName="head-reference")
→ workflow_report(operation="plan", 沿用架构返回的节点 ID 与拓扑)
→ view_image(检查原图与基准)
→ hi3d_api(action="generate_image", 宿主选用 Hi3D 时提交候选图任务)
→ view_image(逐张查看候选并记录方向、身份和必保项)
→ workflow_report(operation="artifact" 或 "node", 记录产物与生成阶段)
→ 交接候选及本次实际输入，供整组评审或定向修订
```

## Hi3D 的实现

### 显式选择多视图操作并分配输入角色

官网工作台从单图启动时选择 `MULTI_VIEW`，从多视图面板已有的正面图启动时选择 `MULTI_VIEW_3VIEWS`。下面是根据前端构造逻辑重写的请求字段节选，URL 为示例。

```json
{
  "editTaskType": "MULTI_VIEW_3VIEWS",
  "baseImageUrl": "https://assets.example.invalid/cat-front.png",
  "referenceImageUrls": ["https://assets.example.invalid/cat-left.png"]
}
```

`baseImageUrl` 是本次操作的主体基准，`referenceImageUrls` 只收另外选入的参考图。左图在此提供附加依据，字段本身没有声明它是左侧视角。即使面板已显示其他方向，生成分支也不会自动把这些槽位变为具名输入。页面依据返回位置回填图片。实际张数、方向顺序及原正面是否保留仍需用任务结果验证。 [官方图片编辑教程](https://www.hi3d.ai/blog/hi3d-ai-image-editing-tutorial) · [网页建模入口](https://hitem3dstatic.zaohaowu.net/website/nuxt-app/public/_nuxt/BheEpZCgRKhjb2fe.js) · [网页图片编辑器](https://hitem3dstatic.zaohaowu.net/website/nuxt-app/public/_nuxt/BuglGjIy6m903F7u.js)

桌面 `generate_image` 默认根据有无本地图和 `imageMode` 选择普通文生图或图生图。这里用 `imageMode: "edit"` 进入图生图，再在原生请求里显式选择多视图模式。以下示例使用假定已存在于工作区的照片和未使用的输出路径，`dryRun` 用于检查本地计划。

```json
{
  "action": "generate_image",
  "targetName": "猫",
  "imageMode": "edit",
  "images": ["inputs/cat-front.png", "inputs/cat-left.png"],
  "prompt": "以正面图为主体基准，侧面图用于核对体型与花纹。生成同一只猫的新观察方向，保持姿态、耳缘、毛色和体型。",
  "aspectRatio": "1:1",
  "request": { "editTaskType": "MULTI_VIEW_3VIEWS" },
  "jobPath": "hi3d/cat-new-views.json",
  "outputPath": "exports/hi3d-cat-new-views.png",
  "dryRun": true
}
```

下面按随包 Python 的行为展开 multipart 结构。`request` 是包含模型、提示词、比例和任务类型的 JSON part，图片以二进制 part 传入。图生图新视角分支用首图作主图，其余作为参考。

```text
request          application/json  {..., "editTaskType": "MULTI_VIEW_3VIEWS"}
baseImage        image/png         inputs/cat-front.png 的字节
referenceImages  image/png         inputs/cat-left.png 的字节
```

`MULTI_VIEW` 和 `MULTI_VIEW_3VIEWS` 接收相同的本地图角色。随包规划器会拒绝这两个模式中的逐图 `views` 参数。因此这个调用能证明如何选择模式和绑定主图，尚不能指定某个输出必须对应背面或顶面。来源见安装目录内 `resources/runtime/dist/runtime.mjs` 的 `Kj`、`hi3d/references/desktop-parameters.md:64`、`hi3d/scripts/hi3d_parameters.py:131`。

### 领域 Skill 怎样组织新视角

1. **头部参考图先验收基准。** `head-reference` 定义了输入、提示词、生成、评审四个检查点。转正模式先验收标准正面，再以它约束其余视角的身份、裁切和外观。保留原姿态模式先验收基准图的朝向、俯仰和侧倾，再要求固定主体、只换观察方向。后一模式使用 `view_0/90/180/270` 相对标签，角度是生成目标。头部单图和正面单图也可独立执行。来源见 `head-reference/SKILL.md:10`、`head-reference/pcg/routes.yaml:7`、`head-reference/references/prompts.md:39`。
2. **头部提示词按角色组合。** 先组合主体身份、必选造型、姿态和外观来生成基准图。后续视角使用已验收的基准图、目标方向与完整的必选造型约束。宿主支持独立图片时可直接返回独立图，采用 2×2 拼图时须拆成单张并实际核对方向。生成工具由宿主提供。来源见 `head-reference/SKILL.md:23`、`head-reference/references/prompts.md:41`。
3. **装配流程为同一部件建立共用规范。** `image-to-assembly` 先统一部件范围、局部坐标、比例、地标和材质，再用证据最强的一面建立基准，建立有证据的相反面，然后结合主图、粗模体块和已验收的前后视角约束侧图。用户原图决定可见外观。补充参考和粗模按各自用途使用，隐藏区域保留观测或推断标记。各方向交付独立图片，对照拼图用于评审。来源见 `image-to-assembly/references/multiview.md:5`、`image-to-assembly/assets/view-prompts.md:5`。

以下伪代码重写了 `head-reference` 的提示词组合和基准关卡。Skill 用文档指导 Agent 调用宿主生图工具，代码中的函数是流程名称。

```python
anchor_prompt = compose(identity, required_shape, pose_clause[pose_mode], appearance)
anchor = generate_with_host(source=original, prompt=anchor_prompt)

if review_anchor(anchor, pose_mode) == "pass":
    views_prompt = compose(view_instructions[pose_mode], required_shape, approved_appearance)
    candidates = generate_with_host(source=anchor, prompt=views_prompt)
    review_views(candidates, anchor=anchor, pose_mode=pose_mode)
```

以保留原姿态为例，基准提示词要求原图的俯仰与侧倾在 `view_0` 中保持一致。生成其余方向时，以验收后的 `view_0` 为参考，提示词改成固定主体、只换观察方向，并继续带上必选造型和外观约束。装配 Skill 的同类提示词会明确列出各张参考的用途，例如「主图约束身份，粗模约束外轮廓和地标，已验收前后图约束共有结构」。这样可以追查某项外观来自哪张图，或属于对遮挡区域的推断。来源见 `head-reference/references/prompts.md:5`、`head-reference/references/prompts.md:57`、`image-to-assembly/assets/view-prompts.md:5`。

### 执行和交付共用图片任务链路

**提交。** 桌面 Agent 准备提示词、输入文件和任务类型，经 Runtime 执行 `generate_image`。Skill 要求记录实际发送的提示词和校验长度，Runtime 的正式调用内置预检。独立 `dryRun` 在 Python 构造计划后返回。Runtime 接受显式 `jobPath`，否则由解析后的 `outputPath` 派生路径。计划指纹覆盖合并后的请求参数、文件角色、路径、大小与 SHA-256。已有路径的后端和指纹一致时复用 job。第一次提交按计划验证待上传字节，鉴权后排他写入 `state=submitting`，再从桌面代理向 `POST /v1/image-task/img-edit` 发起请求。收到有效 `data.taskId` 后先保存它，再进入 `queueing`。来源见 `hi3d/scripts/hi3d_api.py:126–146`、`hi3d/scripts/hi3d_parameters.py:192–230`、`hi3d/scripts/hi3d_jobs.py:192–253` 和 Runtime 的 `Kj`。

**轮询。** Python 对原 `taskId` 发送 `GET /v1/image-task/image-edit/result?taskId=…`，检查原账号及环境。有效任务响应要求 HTTP 200、业务码 200，以及整数 `data.status` 为 0、1 或 2，分别映射处理中、远端成功及远端失败。图片的 `taskStatus` 仅细化处理中阶段。默认等待预算为 1800 秒，轮询间隔为 30 秒，预算内按进度变化通知宿主。达到等待预算仍在处理时，返回 `pending`，作业记录里的 `state` 仍是最近一次已知状态。来源见 `hi3d/scripts/hi3d_client.py:9–16`、`hi3d/scripts/hi3d_jobs.py:269–355`、`hi3d/scripts/hi3d_progress.py:18–68`。

**下载与导出。** 未完成下载时，下载函数先重新查询同一任务，要求本次查询成功、任务仍成功、并有 HTTPS 结果 URL。它对结果 URL 去重，按收集顺序写入原目录内的索引子目录。索引检查点保存 URL 的协议、主机、路径所构成的身份指纹，以及本地文件大小与哈希，重新运行下载时可复用已完成项。完整下载后保存 `artifact.files`。完整缓存可经账号、路径和哈希检查后复用。Runtime 默认保存到 `<outputPath>.originals`，从返回文件筛出 PNG、JPEG、WebP 路径并去重。恰好一张时另行调用 `export-image` 转成目标 PNG，已有文件须与本次转换字节一致才能复用。零张或多张均返回原件列表，宿主还需选择能实际查看的图片。来源见 `hi3d/scripts/hi3d_artifacts.py:120–288` 和 Runtime 的 `Kj`。

工具的外层 `result`、job 的 `state`、候选的视觉评审是三个独立状态。以下伪代码按正式图片调用展开关键条件，函数用于说明职责。等候与下载使用同一 job 和任务 ID，发现质量问题后才考虑新作业。

```python
def generate_image_call(plan, job_path, output_path):
    job = load_matching_job_or_submit_once(plan, job_path)
    if job.submission_unconfirmed or job.submission_rejected:
        return report_submission_outcome(job)
    if job.is_terminal_failure_without_recoverable_query_error():
        return failed(job)

    outcome = wait_on_task_id(job_path, job.task_id)
    if outcome.result != "success":
        return outcome  # pending、查询异常或远端失败均由轮询层保留

    download = fetch_or_verify_cached_files(job_path, output_path + ".originals")
    if download.error:
        return report_download_outcome(job_path, download.error)
    return package_paths_or_export_single_png(download.files, output_path)
```

### 候选登记与单图检查

下载 JSON 的 `files` 以及 Runtime 追加的 `images`、`originals` 或导出文件信息用于定位结果。索引目录和文件序号没有语义方向。带有 Skill 工作流时，可以用 `workflow_report(operation="artifact")` 把实际图片路径归到 `head-reference` 的 `generate` 或 `image-to-assembly` 的 `C` 节点。宿主只检查工作区文件、图片扩展名和工作流节点归属，归入工作流图不等于认定其方向或内容已通过。

随后逐张调用 `view_image`，把实际核对的方向与候选文件绑定。`head-reference` 的四格结果先拆出独立图，再核对各图实际方向。逐图检查姿态、身份、尺寸比例、稳定地标及必保特征。遮挡或源图不可见区域仍标为推断。保存原图、实际参考图、提示词、候选和单图观察。整组一致性、适用的确认和建模可用性由下游依据这些证据判定。来源见 `hi3d/SKILL.md:65–68` 与 `head-reference/references/prompts.md:83–84`。 [工作流产物工具](../tools/workflow-report.md) · [整组视图验收与定稿](review-and-finalize-view-set.md)

下面的实现伪代码展示候选登记和单图检查。`remember_candidate` 和 `inspect_candidate` 表示所选 Skill 的记录及视觉判断职责。

```python
for path in usable_image_paths(delivery, split_contact_sheet=skill.uses_sheet):
    candidate = remember_candidate(path, job=job_path, direction="unknown")
    if workflow_is_active:
        workflow_report(operation="artifact", artifacts=[{
            "kind": "image", "nodeId": generation_node_id, "path": path,
        }])
    evidence = view_image(path=path)
    assessment = inspect_candidate(evidence, anchor, references, required_features)

    if assessment.needs_evidence:
        keep_for_review(candidate, assessment)
    elif assessment.passed:
        queue_for_set_review(candidate, assessment, direction=assessment.confirmed_direction)
    else:
        retain_rejected_candidate(candidate, assessment)
        revise_or_return_to_user(candidate, assessment, skill.revision_policy)
```

## 图片任务状态与恢复

| 分支 | 识别依据 | 执行和恢复条件 |
| --- | --- | --- |
| 正常等待结束 | `result=pending`，已有 `task_id`。 | 继续用原 `jobPath` 做 `wait/query`，成功后 `download` 到原目录，或以完全相同计划恢复 `generate_image`。 |
| 查询异常，任务状态未获确认 | 网络、HTTP、代理、账号异常，或业务成功响应缺少有效任务状态。写入 `last_query_error` 并返回 `attention`，保留上次可信任务状态，进度标记 `stale`。 | 报告本次查询的具体原因并结束本轮。用户明确要求继续后，在原账号和环境对原任务重新查询。 |
| 查询业务拒绝 | HTTP 200，返回可解析的非 200 业务错误码，且错误来源未标为桌面代理。写入 `last_query_error.query_failed=true` 和 `error.phase=query`，返回 `failed`。 | 结束本轮并按查询错误报告。同一 `generate_image` 以终态返回。用户明确要求继续且有原任务 ID 时，在原账号和环境用同一个 `jobPath` 显式调用 `query` 或 `wait`。 |
| 远端生图失败 | 查询请求本身有效，且 `data.status=2`。写入 `state=failed`、`error.phase=generation`，清除旧查询错误。 | 报告失败并保留作业和已有文件。重进同一生成调用会返回终态。再执行生成须有用户明确的新决定。 |
| 提交被拒绝或状态不明 | 提交的 HTTP 4xx 记 `submission_rejected`。其余异常响应、传输异常或无效 ID 记 `submission_uncertain`，进程中断也可能仅留下 `submitting`。 | 保留原记录并说明原因。尚无可用任务 ID 时先核对原账号任务历史，确认原任务 ID 后可接管。若原 job 已保存任务 ID，按恢复流程查询该任务。 |
| 远端成功，交付失败 | 下载校验、结果 URL、工作区文件或导出失败。组合调用通常返回 `attention` 并注明 `download` 或 `export-image`。下载前刷新查询失败也可能返回查询业务失败。 | 保留原任务与已下载部分，报告本轮失败。用户明确要求恢复后，优先续同一下载或对原件重新转换。 |
| 成功取得图片，候选不合格 | 下载成功后实际看图发现方向、身份、姿态或必保特征不符。 | 保留成功任务和候选。在现有授权且尚有修订额度时，用新的 job 和输出路径执行定向修改。通用 Runtime 默认同一目标允许一次追加生图或编辑。选用 `head-reference` 时，同一问题允许两次定向修订，仍失败时由宿主交回用户选择。证据不足则保留候选待评审。 |

查询异常和远端失败可能都在工具层表现为失败，先看 `last_query_error` 和 `phase` 再决定分支。查询错误的提示来自 `hi3d_storage.py` 与 Skill，终止轮询的条件由 `wait_job` 执行。视觉修订上限是 Runtime 指令及领域评审规则，远端 job 继续保留真实任务状态。来源见 `hi3d/scripts/hi3d_jobs.py:256–355`、`hi3d/scripts/hi3d_generation_workflow.py:26–59`、`hi3d/scripts/hi3d_storage.py:13–21`、`head-reference/references/review.md:61–63`。 [随包调用与查询错误规则](../upstream/1.2.11/prebuilt-skills/hi3d/references/calling.md#查询错误)

只缺一面时可单独补该面。基准变化时随候选交付受影响的方向，这些方向需要参与整组复查。所选流程的放行及视角兼容要求见[整组视图验收与定稿](review-and-finalize-view-set.md)。

## Vet3D 的迁移边界

Vet3D 的 LLM、生图模型、3D 模型和 API 仍待选型。可以先把主图、补充参考、基准姿态、已观察的方向、待补方向和必保特征作为业务输入。前、后、左、右、顶的坐标语义与后端槽位分别记录。实拍优先作为方向证据，合成图通过单图检查后可填入候选空位，留待整组定稿。

例如同一只猫有正面和左侧实拍，生成背面与顶面时，可用正面锚定身份、左侧约束体型与花纹，并在计划里明确两个目标方向和顶视图的头部朝向。后端适配器负责把这些角色翻译成参考图、图像字段、相机条件或提示词，并在返回后确认方向映射。当前 Hi3D 桌面的具名多视图契约没有顶视图，未来选定的后端须验证它实际能接收或产出所需方向。

下面是 Vet3D 节点内部的计划示例。字段描述业务语义，适配器接到已选定的后端后再决定如何提交。`targets` 由本轮任务确定，右面虽为空位，本轮只要求背面和顶面。

```json
{
  "subject": "cat-01",
  "views": {
    "front": "photo-front-v1",
    "back": null,
    "left": "photo-left-v1",
    "right": null,
    "top": null
  },
  "anchor": { "image": "photo-front-v1", "role": "主体身份与姿态" },
  "references": [{ "image": "photo-left-v1", "role": "体型和可见花纹" }],
  "targets": ["back", "top"],
  "topOrientation": "头朝画面上方",
  "preserve": ["原姿态", "耳缘", "可见花纹", "身体比例"]
}
```

下面是 Vet3D 设计伪代码，用于暂存通过单图检查的候选。创建计划时，将上例 `anchor` 和 `references` 使用的图片解析为不可变版本或内容摘要，汇总为 `plan.reference_versions`。将单图检查绑定到候选、主体、生成计划和这些参考版本，并以一次持久化事务核对版本和候选槽位。并行补图或新实拍占用槽位时，仍保留候选供复查。

```python
def stage_candidate(store, plan, candidate, review):
    if not review.matches(plan, candidate) or not review.passed:
        return "保留候选，等待评审或修订"
    view = review.confirmed_view
    if view not in plan.targets:
        return "保留候选，方向超出本轮目标"
    with store.transaction_for(plan.subject) as tx:
        views = tx.read_candidate_views()
        if not tx.matches_reference_versions(plan.reference_versions):
            return "重新评审，参考图版本已变化"
        if views.get(view) is not None:
            return "保留候选，目标槽已有结果"
        tx.fill_empty_candidate_view(
            view,
            image_id=candidate.image_id,
            source="generated",
            review_id=review.id,
        )
    return "已暂存，待整组验收"
```

实现时事务需要覆盖参考版本和目标候选槽位，或用等价的条件更新。候选指针保留生成来源和单图检查引用，原始图片留作复查。整组批准仍以[定稿节点](review-and-finalize-view-set.md)检查的版本为准。

## 核查范围

基于本机安装包、先前保存的公开网页前端证据及离线合成数据。本次读取的安装更新事务备份为 `D:/install/Hi3DAgent.__hi3d-transaction`，其清单版本为 1.2.11，Runtime SHA-256 与先前核查的文件一致。离线测试验证了请求角色、原任务恢复与版本检查。云端内部使用的提示词模板、单次任务内的模型调用次数，以及真实动物的合成画质仍待验证。
