# 确认建模主体

分析对象为本机 Hi3D Agent 1.2.11（Windows x64），安装包实物位于 `D:/install/Hi3DAgent.__hi3d-transaction`。本文以已有多视图参考图的建模任务为主。Hi3D 的实际行为和 Vet3D 的拟议节点契约分别标明。

## 业务定义

本节定义 Vet3D 拟实现的节点契约。用户要求根据照片或视频抽帧建立、补充或修订一个动物模型时，先确认要还原的个体、作为基准的姿态，以及每张图可以提供的证据。用户变更建模对象、基准姿态或相关参考图时，复核受影响的判断。

| 项目 | 节点契约 |
| --- | --- |
| 上游与输入 | 接收用户的建模要求、指定的对象或图片、既有主体记录，以及导入后的原图和预览引用。用户提供的视角、拍摄状态和画面区域随图传入，来源未知的字段可留空。 |
| 主体输出 | 记录目标个体、基准图、目标姿态、可区分个体的特征与未决项。物种或品种可选。Hi3D 自带的 `tag4` 仅保存类别，完整主体记录是 Vet3D 的设计。 |
| 逐图输出 | 记录每张图的主体归属、姿态是否相容、可见证据和允许用途。用途可以是基准、同姿态视图、局部外观参考或排除。证据不足的图片保留待核查状态。 |
| 完成条件 | 目标个体和任务所需的基准姿态已经明确。相关照片均有处置，任何可能改变建模对象或基准姿态的冲突均已解决。品种未知或缺少某个方向可以作为已知缺口交接。 |
| 下游交接 | 已有可用原图时交给[整组视图验收与定稿](review-and-finalize-view-set.md)。需要补图时交给[生成新视角](generate-new-view.md)，需要修订已有图时交给[编辑已有视角](edit-existing-view.md)。交接携带主体依据、基准姿态、各图角色和版本。 |

主体基准图用于确认要还原的个体。一次生图调用的主图用于指定从哪张图片出发。两者可以是同一张图，也可以随目标视角改变。是否凑齐前、后、左、右、顶，以及哪些方向能交给生成器，由视图准备和后端适配阶段处理。

## Skill 绑定

下表链接到仓库内归档的 [Hi3D Agent 1.2.11 原文快照](../upstream/1.2.11/README.md)。

| Skill 文档 | 作用与选用条件 | SHA-256 |
| --- | --- | --- |
| [`hi3d/SKILL.md`](../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md) | **通用入口。** 普通图生 3D 根据建模参考图判断主体，复用合格原图。多视图使用用户提供并标明的前、后、左、右图，包含正面，允许缺少其他方向。只有一张图时走单图路径。参考图生成、检查与类别登记也由此入口指导。 | `4c268ae14ece561234682d564cdfa6264c1f121a9ea118137c0388a9240c217d` |
| [`image-to-assembly/SKILL.md`](../upstream/1.2.11/prebuilt-skills/image-to-assembly/SKILL.md) | **静态装配领域 Skill。** 当任务需要部件建模、配准和装配时使用，适用对象包含动物。选用后执行整组证据盘点、同版本与同状态区分、主图优先、观察与推断标注，以及后续部件视图和环绕审查。 | `cf4ec08dec0decfd69560a940cc26ea18fecf559ea87852c269fd2682555705f` |
| [`head-reference/SKILL.md`](../upstream/1.2.11/prebuilt-skills/head-reference/SKILL.md) | **人像头部参考图领域 Skill。** 头部任务明确需要转正或保留原姿态的参考图时使用。选用后先验收该模式自己的基准图，再依次复用共用身份、造型和外观约束，按该 Skill 的评审契约交付。 | `7e7fa5b0cd74928feac546a64edb0d71c77d66f6e5756bfef8c528523af95795` |

普通整件多视图使用通用入口的规则。主图冲突裁决、粗模环绕和头部评审分别来自被选中的领域 Skill。用户只要求根据实拍还原整只动物时，按普通入口准备建模输入。

## LLM Tools

工具定义、模型可见描述原文和通用实现维护在[工具索引](../tools/README.md)下的独立页面。本表记录工具在本节点的调用条件。

| LLM Tool | 用途摘要 | 本节点调用时机与条件 |
| --- | --- | --- |
| [`view_image`](../tools/view-image.md) | 将本地图片送入模型上下文。 | 查看工作区已有图、补查原图细节，或逐张查看生成返回的候选。聊天附件本身可作为视觉输入。 |
| [`image_classification`](../tools/image-classification.md) | 保存模型登记所需的一个 `tag4` 类别。 | 通用 Skill 指导：普通新建模型实际查看建模参考图（含生成图）后、发起生成前调用；同一轮同一主体的多张参考图只记录一次。同主体后续修订可沿用分类；登记报缺时补录。Runtime 另支持显式分类或家族分类回退。 |
| [`user_interaction`](../tools/user-interaction.md) | 用宿主面板收集必要信息。 | 目标对象、姿态等重大歧义靠已有信息无法解决时，可用 `kind="input"` 请用户指定具体图片或对象。主体识别路径中未见固定弹窗步骤。 |
| [`workflow_report`](../tools/workflow-report.md) | 上报 Skill 工作流、进度及产物归属。 | 本轮实际执行已选 Skill 时，按该 Skill 架构使用 `inspect`、`plan` 等操作。中断后续接同一 Skill 时先按工具契约 `resume`。只有对应阶段实际完成或实际产生文件后，才上报完成或归属。 |
| [`hi3d_api`](../tools/hi3d-api.md) | 执行图片或 3D 任务，管理已有远端作业。 | 合格实拍直接用于判断。本节点只有在已选择的路线需要额外生成参考图时，才交给图片动作 `generate_image`。`query`、`wait`、`download` 用于已有作业。`generate_3d` 属于下游。 |

`view_image` 由随包 Codex 提供。其余表内工具是 Hi3D Runtime 的动态工具。工具注册表示宿主具备该能力，Skill 规定使用时机，某次会话是否调用仍需该轮工具轨迹验证。`generate_image` 是 `hi3d_api` 的动作，`EDIT` 等是原生图片请求枚举。领域 Skill 的评审或交接 Python 脚本是本地程序。本文中的离线测试只执行随包脚本或规划函数。

## Hi3D 的实现

### 决策

#### 原图与预览的关联

常规导入先把原文件写入工作区 `inputs/`。图片达到 512 KiB 时，renderer 尝试生成最长边不超过 1536 px、质量参数为 0.85 的 JPEG。只有预览比原件小时才采用。前端在同一条附件记录中用 `path` 指向预览、用 `fullResolution.path` 保存原件路径。未采用预览时，`path` 直接指向原件。来源见 `app.asar` 内 renderer 的 `A2`、`GS`、`Wa` 和 `QI`。 [工作区输入组装](../infrastructure/workspace/llm-context.md#组装本轮正文和附件)

**根据已核实行为重建的数据流。** 下例省略其他消息字段，路径用占位名表示。

```text
前端附件：{id: 附件UUID, name: "cat.png", path: 预览路径,
          fullResolution: {name: "cat.png", path: 原图路径}}
发送：    localImage(name="cat.png", path=预览路径)
          mention(name="cat.png", path=原图路径)
无预览：  localImage(name="cat.png", path=原图路径)
```

`localImage` 提供模型所看的图像。`mention` 还会进入消息的附件文字说明，供 Agent 用 `view_image` 补看原图。`O3` 将编辑框中的 UUID 引用展开为显示名，发送的类型化附件也没有该 UUID。同名附件仍保留各自的路径和顺序，但正文中的名字不足以唯一定位照片。后续 3D 上传读取 `images[]` 指定的路径，选中预览时就发送预览字节。来源见 renderer 的 `O3`、`cS` 和 `Yce`。 [会话输入实例](../infrastructure/workspace/llm-context.md#组装本轮正文和附件) · [3D 文件组包](../tools/hi3d-api.md#3d-本地文件组包)

#### 谁作判断，怎样处理证据冲突

**普通入口。** 对话模型结合用户所指对象、实际看过的图和 Skill 规则判断建模主体，并决定哪些照片用于建模或仅供参考。`view_image` 提供图像，`image_classification` 保存当前主体的类别。通用 Skill 指导按用户标明的实际方向选图，采用多视图时包含正面。普通 Python 客户端校验文件和视角参数的结构，离线模拟提交中仅使用左、右两图仍可组包，同一文件也可以配给两个不同的合法方向。静态装配由清单脚本强制包含 `front`。当前核查范围内未发现优先以正面确认个体、按像素验证各图是否为同一个体或同一姿态、自动分配逐图用途的固定程序。工作区模板要求对影响主要形象或装配的缺失信息用 `user_interaction` 收集，其余合理假设可说明后继续。若 Agent 为主体或姿态发起 `kind="input"` 澄清，回答返回原工具调用，由 Agent 继续判断。 [通用入口](../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md#默认行为) · [配对异常矩阵](pair-multiview-inputs.md#验收) · [工作区模板](</D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md>) · [澄清工具](../tools/user-interaction.md#工具调用与宿主协议)

**装配专项。** 选用 `image-to-assembly` 时，Agent 先看整组图，分别记录版本、涂装和姿态。出现冲突时，用户指定主图决定主体和姿态，其他图仅补充有依据的局部结构。准备新视图时可用证据最强的一面作为生成基准。遮挡、低清和不可见面保留不确定性，用户允许的局部推断可以继续，保留 `inferred` 标记。身份仍无法确定或目标互相冲突时请用户澄清。身份错误、方向矛盾和严重缺失须在付费高模提交前处理。 [装配主体判断规则](../upstream/1.2.11/prebuilt-skills/image-to-assembly/references/proxy-segmentation.md) · [装配多视图规则](../upstream/1.2.11/prebuilt-skills/image-to-assembly/references/multiview.md)

**人像头部专项。** `head-reference` 的转正模式使用已验收正面，保留原姿态模式使用已验收的初始观察方向。该 Skill 的逐项视觉评审及人工确认适用于其头部参考图。 [头部提示词与基准](../upstream/1.2.11/prebuilt-skills/head-reference/references/prompts.md) · [头部评审契约](../upstream/1.2.11/prebuilt-skills/head-reference/references/review.md)

### 执行

**通用 Skill 的默认顺序。** 归档 `hi3d/SKILL.md` 为普通新建模给出的顺序是 `view_image → image_classification → generate_3d → workspace_commit_model`。有其他任务生成的图被用于本次 3D 时，也先查看再分类。同一轮针对同一个主体复用已确认的类别。视觉判断负责确认是哪个个体及哪些图片能代表它；`tag4` 只记录模型登记所需的粗类别。 [图片输入规则](../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md#图片生成与编辑) · [默认调用顺序](../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md#低-token-消耗与脚本版本)

**Runtime 的登记入口。** `workspace_commit_model` 可接受显式 `tag4`（包括 `null`）。省略时才依次查同线程同轮分类、规范化后同名家族最新版本的分类。都缺失则返回 `classificationRequired`。`generate_3d` 也有独立的可选自动登记入口，需要同时提供 `registerName` 和显式 `tag4`，并满足其 GLB 交接条件。生成入口的本地门禁负责核对文件和参数，`image_classification` 的生成前调用时机由通用 Skill 指导。 [版本登记规则](../tools/workspace-commit-model.md#参数与结果) · [组合工具动作](../tools/hi3d-api.md#参数与结果)

**根据已核实行为重建的请求示例。** 假定 Agent 已确认目标为用户指定的猫，并判断 Hi3D 的类别枚举没有合适选项。按通用 Skill，向 `image_classification` 提交以下参数。`null` 表示已完成类别判断但无适用枚举。 [工具参数与实现](../tools/image-classification.md)

```json
{
  "tag4": null
}
```

Runtime 从调用上下文取得工作区、`threadId` 和 `turnId`，把 `{tag4}` 写入 `<Runtime 存储根>/environments/<环境>/workspaces/registry.json` 的 `imageClassifications[threadId][turnId]`。同轮再次调用会覆盖该记录，并更新当前工作区内同一线程、同一轮次的已登记版本 `modelMetadata[assetId][fileName].tags`，可能涉及不同模型家族。写盘成功后，Runtime 回复工具结果并通知桌面。图片、姿态和逐图用途留在对话及后续业务计划中。 [分类写入实现](../tools/image-classification.md#实现伪代码) · [Runtime 实现，`recordImageClassification`](</D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>)

下游 [`workspace_commit_model`](../tools/workspace-commit-model.md#参数与结果) 登记 GLB 时，依次读取显式标签、当前轮标签和同名家族最新版本的标签。显式 `{ "tag4": null }` 是有效记录。都缺失时返回 `classificationRequired`，补分类后用原 `name` 和 `exportPath` 登记同一文件。正式 `generate_3d` 也可携带 `registerName + tag4`，下载到唯一有效 GLB 后直接登记。标准 3D 上传请求不会自动携带这个顶层标签。Studio 从已登记版本的 `tags` 读取分类，可据此选择表面处理或 3MF 打印预设。 [自动登记参数](../tools/hi3d-api.md#共用字段与条件) · [桌面应用包，`StudioHost` 与 3MF 预设](</D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>)

**根据已验证行为重建的可选图片请求示例。** 假定主体已经确认，任务另需从正面实拍生成一张背面候选。选择 Hi3D 作为本次图片工具时，向 `hi3d_api` 提交如下参数。主图放在 `images` 首位，左图作为补充，仅用于约束体型和可见毛纹。目标方向和必保特征写入 `prompt`。这里使用普通编辑枚举 `EDIT`，目标方向由文字提出。`dryRun` 只检查客户端计划。 [图片任务契约](../upstream/1.2.11/prebuilt-skills/hi3d/references/image-generation.md) · [工具调用说明](../tools/hi3d-api.md)

```json
{
  "action": "generate_image",
  "targetName": "猫",
  "imageMode": "edit",
  "images": ["inputs/cat-front.png", "inputs/cat-left.png"],
  "request": { "editTaskType": "EDIT" },
  "prompt": "以第一张为同一只猫的身份和站姿基准。第二张只补充躯干比例和可见侧面毛纹。生成正对背部的独立图片，只改变观察方向，保持体型、耳缘、尾部姿态和已有花纹。未见背部细节为推断。",
  "aspectRatio": "1:1",
  "jobPath": "hi3d/cat-back-candidate.json",
  "outputPath": "exports/hi3d-cat-back-candidate.png",
  "dryRun": true
}
```

这个本地图示例由 Python 组为 JSON `request`、首图文件字段 `baseImage`、其余文件字段 `referenceImages`。采用显式原生 URL 请求的图生图分支也可保留 `baseImageUrl` 和 `referenceImageUrls`。这些字段表达本次生图的角色。具名视图编辑另用 `MULTI_VIEW_EDIT` 及对应的 `viewImages`、`viewKeys`。本节点完成主体判断后才交接补图，合成候选的来源仍是推断。 [桌面参数契约](../upstream/1.2.11/prebuilt-skills/hi3d/references/desktop-parameters.md) · [生成新视角的组包示例](generate-new-view.md)

### 验收

主体确认以目标个体、基准姿态和各图的允许用途为验收结果。普通入口看过建模参考图后记录主体类别，`image_classification` 的回执用于核对标签已保存。候选组成整组后的身份、方向、比例与非对称特征一致性，以及领域脚本的定稿条件，由下游单独核对。 [整组验收条件](review-and-finalize-view-set.md#验收)

## 完成条件与恢复

类别保存由本机 Runtime 完成。对话模型看图判断主体时无需创建独立的 Hi3D 图片作业。下表中的 `pending`、提交不明和候选修订对应可选的生图交接分支。

| 情形 | 处理与交接 |
| --- | --- |
| 主体明确，原图可用 | 普通路线复用合格原图，并按用户标注准备视图输入。缺少非必需方向时，可以留空。 |
| 缺失信息影响主要形象或装配 | 按工作区指引用 `user_interaction` 收集必要信息。面板答案交回 Agent，用于决定选图或继续建模。 |
| 图片作业返回 `pending` | 保存原 `jobPath` 和已知任务 ID，用同一作业执行 `wait`，需要检查状态时使用 `query`。成功后下载或取得已下载的候选，再实际看图。 |
| 提交状态不明 | 保留原计划、`jobPath`、已有任务 ID 及已取得文件。先按服务任务记录核对，找到原任务后恢复原作业。确认任务状态前保持原提交记录，避免以新路径重复提交。 |
| 查询失败或生成明确失败 | 查询失败时保留最后一次已知状态，报告具体原因并结束当前轮。生成明确失败时保留原任务与产物，停止该生图流程。用户明确要求恢复后，再按原任务状态续查或决定如何重试。 |
| 作业成功，候选未通过视觉验收 | 保留原任务成功状态、候选版本和失败依据。按已选流程及修订范围，定位最早出现冲突的视图，针对方向或局部差异修订。质量修订产生新版本和独立作业，复查修改图及依赖它的其他方向。 |
| 候选通过视觉验收 | 只有已核对主体、目标方向、姿态和必保特征的候选才能回填相应视角。回填保留生成来源、图片版本和审核依据。交给 3D 前再检查该后端能消费的方向及所选 Skill 的额外交接条件。 |
| 已有 GLB，登记提示缺分类 | 按 Skill 补记类别后，用同一模型名和原导出文件重新登记；Runtime 也允许直接为此次登记显式传入已判断的类别。原生成无需重跑。 |

[生成、等待与恢复规则](../upstream/1.2.11/prebuilt-skills/hi3d/references/image-generation.md) · [模型登记与重入规则](../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md) · [专项候选修订规则](../upstream/1.2.11/prebuilt-skills/image-to-assembly/references/multiview.md)

## Vet3D 的迁移边界

Vet3D 的 LLM、生图模型、3D 模型及 API 均待选型。先定义业务记录，工具适配器再把这些语义映射到具体供应商。

- **主体记录。** 用稳定的主体与资产标识关联个体、基准图、姿态和逐图依据。每张图以同一个资产标识关联原件、预览及版本，正文引用也保留该标识。建模上传显式选定原件或经审查的派生图。同一轮可保存多个主体，后续任务显式引用其中一个。物种、品种及资产分类可以独立于身份判断维护。
- **视图与角色。** 保留 `front`、`back`、`left`、`right`、`top` 的语义标注及来源，明确左右以动物自身为准，并记录顶视图的头部朝向。生图计划独立描述身份基准、本次操作主图、辅助图的局部用途、目标方向和必保特征。语义方向由各后端适配器映射为自己的字段或槽位。
- **视觉判断与持久化。** 视觉模型根据实图给出同主体、姿态和证据判断。宿主校验资产归属和版本，记录观察或推断，并将审核结果绑定到输入与候选的版本。回填前在同一次写入中复核当前记录，避免用旧审查覆盖后补实拍。后端只有四槽时，保留顶视图及其实际用途，例如只参与验收。

**Vet3D 设计示例。** 对每张图分别记录个体归属、姿态相容性、允许用途和判断依据。同一个体但姿态不同的照片，可提供耳缘、毛色等局部外观证据。疑似另一只动物或证据不足的照片保留原件和判断状态，暂缓用作建模视图。只有歧义可能改变目标个体、基准姿态，或让必要输入无法选定时才询问用户。续接时同时读取上次保存的评审和用户回答，复核受影响的判断，并将选中的视图与各图用途一并交接。下例是拟议控制流，函数名表示业务职责。

```python
def confirm_subject(task, previous_review=None, clarification=None):
    if clarification is None:
        review = assess_reference_photos(task.intent, task.assets)
    else:
        review = reassess_affected_evidence(previous_review, clarification, task.assets)

    # 分别记录个体归属、姿态相容性、依据和允许用途。
    view_choices = assign_reference_uses(review)
    save_subject_review(review, view_choices)

    blocking_issue = find_issue_affecting_target_pose_or_required_input(review, view_choices)
    if blocking_issue is not None:
        return request_clarification(blocking_issue)

    return handoff_subject_and_references(review, view_choices)
```

| 建议的 Vet3D 验收案例 | 预期行为 |
| --- | --- |
| 同一只动物的五视图顺序打乱 | 用户所指对象和逐图证据一致时，结论不随附件顺序改变。 |
| 同一只猫的正面站姿和侧面坐姿混合，用户已选站姿 | 可以确认个体并继续。正面图确立站姿，侧面图只用于可见毛纹、耳缘等局部外观，侧面站姿仍是缺口。 |
| 两只外观相似的动物混在一组图中 | 能定位明确指定的目标时记录冲突图。目标仍有歧义时，记录待澄清项。 |
| 主体和姿态明确，缺顶视图或品种未知 | 主体节点可完成，缺口随记录交给下游。 |
| 云端成功返回背面候选，但毛纹或方向明显错误 | 保存远端成功和视觉未通过两个状态，候选留作修订，目标槽继续等待合格结果。 |

## 核查范围

- **实际运行观测。** 2026-11-11 的生产 rollout 第 13 行记录了三张附件以 `input_image` 进入模型侧输入。第 35→39 行可配对实际调用 `image_classification({tag4:null})` 及对应标签回包。第 145→148 行显式以 `tag4:null` 登记选定 GLB，返回版本记录中的 `tags.tag4` 也是 `null`。该样本可追溯附件、标签调用和登记字段。 [附件输入](</D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:13>) · [分类调用](</D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:35>) · [版本登记](</D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:145>)
- **安装包静态核查。** 版本为 1.2.11。查看了附件输入、Runtime 工具注册与分派、`tag4` 的本地保存及登记读取、图片角色组包。
- **离线核查。** 用安装包里的前端函数复现了预览回退和同名附件在正文中失去 UUID 指代的行为。用合成输入验证 3D 组包按选中路径上传对应字节，同一文件可配给不同合法方向。本文的 `EDIT` 示例使用两张合成 PNG 通过随包 Python 的 dry-run，并核对了主辅图的组包顺序和字节。`image-to-assembly/scripts/test_runtime_handoff.py` 的四项交接测试均通过。测试中没有发起远端生成。
- **Skill 指导。** 通用多视图规则及领域 Skill 的验收要求按该轮所选流程适用。三份 `SKILL.md` 的归档字节与本机安装包核对一致。 [Skill 绑定](#skill-绑定)
- **待验证。** 上述登记显式传入了标签，分类缓存回退仍需一条省略显式标签的轨迹核实。对话模型如何在真实动物照片中区分相似个体、判定姿态，云端如何加权主图与辅助图，以及目标方向和五视图的保真度，仍需用对应会话和结果验证。拟议的 Vet3D 契约需在选型后用代表性输入验收。
