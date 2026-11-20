# 编辑已有视角

分析对象为本机 Hi3D Agent 1.2.11（Windows x64）。本次复核使用 `D:/install/Hi3DAgent.__hi3d-transaction` 保留的安装副本，Runtime 哈希与此前核对一致。随包 Skill、参考文档和工具包脚本的路径以 `resources/runtime/prebuilt-skills/` 为基准。补齐缺失方向见[生成新视角](generate-new-view.md)。

## 业务定义

编辑已有视角以**已存在且语义方向明确的图片**为目标。执行者识别具体问题，指定要修改的内容、修改后应看到的状态，以及必须保留的主体特征和相机条件。其他已有视角可以提供身份、比例、姿态、材质或共享地标的依据。节点交付目标视角的新候选、单图检查结果和受影响方向，并保留编辑前的图片和实际输入记录。候选通过[整组视图验收与定稿](review-and-finalize-view-set.md)后，才成为供下游使用的新版本。

这个节点有两种常见触发方式。一种是用户要求修某个方向，例如清理左侧照片的背景。另一种是生成结果已返回，但看图发现跨视角冲突，例如左视图的尾根位置与正、后视图不相容。`image-to-assembly` 要求定位最早造成矛盾的图，修订后同时复查整张目标图和受影响的其他方向。若经实际看图确认图像本身正确、只有方向标签错了，`head-reference` 允许另存并修正清单中的语义对应关系，再重新评审。来源为 `image-to-assembly/references/multiview.md:33–53`、`head-reference/references/prompts.md:51–55`。

## Skill 绑定

下表链接到仓库中保存的 `1.2.11` Skill 原文。链接文字是相对于安装目录下 `resources/runtime/prebuilt-skills/` 的路径，SHA-256 标识本次分析的文件。

| Skill 文档 | 在此节点中的角色 | SHA-256 |
| --- | --- | --- |
| [hi3d/SKILL.md](../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md) | 桌面通用图片编辑入口，定义主图与参考图的角色、提示词校验、异步任务及结果查看。 | `4c268ae14ece561234682d564cdfa6264c1f121a9ea118137c0388a9240c217d` |
| [head-reference/SKILL.md](../upstream/1.2.11/prebuilt-skills/head-reference/SKILL.md) | 选用头部参考图流程时，按失败项修订，保留已通过的基准，并对照当前姿态模式复评。 | `7e7fa5b0cd74928feac546a64edb0d71c77d66f6e5756bfef8c528523af95795` |
| [image-to-assembly/SKILL.md](../upstream/1.2.11/prebuilt-skills/image-to-assembly/SKILL.md) | 选用静态装配流程时，在阶段 C 对部件视图进行局部修复，并记录须复查的相关视图。适用范围包括动物。 | `cf4ec08dec0decfd69560a940cc26ea18fecf559ea87852c269fd2682555705f` |

当前安装包中未发现由 `MULTI_VIEW_EDIT` 自动加载领域 Skill 的绑定。头部参考图和装配部件的修订约束来自各自选用的 Skill。

## LLM Tools

| 工具 | 模型可见说明摘要 | 在本节点的调用时机 |
| --- | --- | --- |
| [`view_image`](../tools/view-image.md) | 查看磁盘上已有的本地图片。 | 查看目标图和其他方向，定位具体冲突。编辑后再查看候选及受影响的视角。 |
| [`hi3d_api`](../tools/hi3d-api.md) | 通过 Hi3D Runtime 生成、编辑图片或生成 3D，支持续查同一任务。 | 使用 Hi3D 执行多视图编辑时，调用 `generate_image`，用 `request.editTaskType=MULTI_VIEW_EDIT` 和 `editedViewKeys` 指定操作及目标。 |
| [`workflow_report`](../tools/workflow-report.md) | 在使用 Skill 的轮次上报工作流、节点进度和产物归属。 | 当修订属于已选 Skill 时，将修订版本归入实际阶段，例如 `image-to-assembly` 的 `C` 节点。 |
| [`user_interaction`](../tools/user-interaction.md) | 通过宿主面板收集输入、偏好或授权。 | 用户意图缺少必要范围，或已有授权无法覆盖本次修订时使用。 |

下例说明两个视觉检查点。第一次查看用于确定修改和保护范围，第二次查看用于判断候选是否兑现这些约束。若只发现方向标签错误，领域 Skill 可以修订视角清单并复评，仍可使用原始像素。完整工具描述与执行伪代码见[工具索引](../tools/README.md)。

```text
view_image(待改的左图及相关已验收视图)
→ hi3d_api(action="generate_image", MULTI_VIEW_EDIT 的目标为 left_side_view)
→ view_image(左图候选及受影响的相关视图)
→ 核对修改项、保护项、方向和参考图版本
→ workflow_report(operation="artifact", 执行 Skill 时登记修订产物)
→ 交接原图、新候选和须复查的视角
```

## Hi3D 的实现

### 通用工具和原生视角编辑

桌面 Agent 用 `hi3d_api` 的 `generate_image` 提交图片任务。普通 `imageMode=edit` 将首图作为待编辑主图，其余图片作为补充参考。要走结构化的视角编辑，调用方显式将 `request.editTaskType` 设为 `MULTI_VIEW_EDIT`，并把工作区图片和具名方向逐项配对。Python 将两者分别组包为 `viewImages` 和 `viewKeys`。待编辑方向另由 `editedViewKeys` 指定，已有视图的 URL 上下文可以放在 `fullMultiViewInputs`。因此，某张图可以为编辑提供依据，同时不在本次修改目标内。来源见安装目录内 `resources/runtime/dist/runtime.mjs` 的 `Kj`、`hi3d/SKILL.md:62–68`、`hi3d/references/desktop-parameters.md:76–85`、`hi3d/scripts/hi3d_parameters.py:143–171`。

下例根据桌面工具契约重建。`images` 和 `views` 通过数组位置绑定已有图片，`editedViewKeys` 只选左侧。两个路径代表调用方工作区中的输入。`dryRun: true` 仅作本地预检，输出路径预留给正式任务。

```json
{
  "action": "generate_image",
  "targetName": "猫",
  "images": ["inputs/cat-front.png", "inputs/cat-left.png"],
  "views": ["front", "left"],
  "imageMode": "edit",
  "imageModel": "gpt-image-2",
  "aspectRatio": "1:1",
  "prompt": "仅清理左视图背景。保留猫的轮廓、耳缘、花纹、尾巴姿态和左侧相机方向。正面图用于核对身份。",
  "request": {
    "editTaskType": "MULTI_VIEW_EDIT",
    "editedViewKeys": ["left_side_view"]
  },
  "outputPath": "exports/hi3d-cat-left-edit.png",
  "dryRun": true
}
```

组包的核心分支如下，摘自安装包 Python，省略外层任务类型判断和前置校验。校验过的 `labels` 先转换为服务方向键，再按原顺序读取文件。普通编辑使用主图和参考图字段，多视图编辑统一使用 `viewImages`。来源见 `hi3d/scripts/hi3d_parameters.py:149–168`。

```python
multi = body["editTaskType"] == "MULTI_VIEW_EDIT"
if multi and images:
    if not labels:
        raise ValueError("MULTI_VIEW_EDIT files require --views")
    parts["viewKeys"] = [VIEW_KEYS[VIEW_NAMES.index(v)] for v in labels]
elif labels:
    raise ValueError("--views for 2D requires MULTI_VIEW_EDIT")
for i, path in enumerate(images):
    field = "viewImages" if multi else ("baseImage" if kind == "image-edit" and i == 0 else "referenceImages")
    files.append(file_info(field, path, IMAGES, 40 * 1024**2))
```

上面的 JSON 在正式调用时形成如下 multipart 部件。这里省略边界串、默认字段和二进制内容，保留组包顺序与角色。`viewKeys` 表示每个文件是什么方向，`editedViewKeys` 表示本次要改哪个方向。来源见 `hi3d/scripts/hi3d_parameters.py:198–236`。

```text
request      application/json  {"editTaskType":"MULTI_VIEW_EDIT","editedViewKeys":["left_side_view"], …}
viewKeys     application/json  ["front_view","left_side_view"]
viewImages   image/png         input-0.png  ← cat-front.png
viewImages   image/png         input-1.png  ← cat-left.png
```

编辑和生成新视角共用提交、轮询、下载和原件留存。当前 Runtime 指令将本地参数校验纳入常规正式调用，独立 `dryRun` 可用于只检查请求。任务恢复沿用原任务 ID、计划指纹和作业路径。查询、远端生成、下载及导出错误分别按[图片任务状态与恢复规则](generate-new-view.md#图片任务状态与恢复)处理。

官网工作台通过界面选择已有图片的槽位，生成待编辑方向列表。它用前、后、右、左四个具名键构造已有视图 URL 对象，空槽以空字符串表达。返回时，前端按自己的位置映射重新组织视图；桌面执行层则主要交付图片文件列表。输入声明和网页回填代码能确认客户端的操作意图，未选视角是否由服务保留原始像素、指定方向是否按要求修改，要用实际输出核对。 [Hi3D 网页图片编辑器代码](https://hitem3dstatic.zaohaowu.net/website/nuxt-app/public/_nuxt/BuglGjIy6m903F7u.js)

下面是根据公开前端代码重建的网页请求片段。示例的后、右方向为空，已有的正面仍随请求传给服务，左侧是唯一编辑目标。URL 均为演示占位符。

```json
{
  "editTaskType": "MULTI_VIEW_EDIT",
  "fullMultiViewInputs": {
    "front_view": "https://example.invalid/cat-front.png",
    "back_view": "",
    "right_side_view": "",
    "left_side_view": "https://example.invalid/cat-left.png"
  },
  "editedViewKeys": ["left_side_view"],
  "prompt": "清理左视图背景，保留相机方向和主体轮廓。"
}
```

### 领域 Skill 如何组织一次修订

`image-to-assembly` 的模板把修订组织为可核对的指令。先指定唯一目标图的路径、方向和具体矛盾，再给出依据图及共享地标、允许改动的区域、可观察的完成状态、必须保护的轮廓与外观，以及用于对齐的其他视图版本。相机、尺度、外壳材质等保持条件随每次调用传入。同一部件的有依赖修订按版本串行，以免后续图引用过期的上一版；不同部件可以独立推进。记录本次真正发送的提示词、参考图路径和版本。来源为 `image-to-assembly/assets/view-prompts.md:20–30`、`image-to-assembly/references/multiview.md:33–53`。

下面将安装包的局部修订模板应用到猫的左视图，作为编排示例。编辑区域定义可变范围，保护项定义需要逐一复查的内容。其他视图的版本号说明这次修订实际依据的是哪一版。

```text
目标图  cat-left@v03，左侧正对视图。清理身体外轮廓周围的背景杂物。
依据图  cat-front@v02 确认耳缘和面部花纹，cat-top@v01 核对背部轮廓和尾根。
修改    只处理猫轮廓外的背景，完成后背景均匀，轮廓周围无残留杂物。
保护    保留耳尖、左右不对称花纹、尾巴曲线、身体比例、画幅和相机方向。
输出    完整左视图的独立图片，供全图复查及与已验收的正面、顶面比对。
```

`head-reference` 的修订围绕评审失败项展开。保留原始参考和上一版结果，复用当前姿态模式及必选造型约束；例如要求保留当前俯仰和侧倾时，修局部外观仍需延续这两项。基准图变更后，所有依赖该基准的视角都重新检查。对于只修正方向标签的情形，同步更新图片、实际提示词和实际生成输入在清单中的键与引用，保留旧记录，走新一轮评审。来源为 `head-reference/references/prompts.md:51–55`、`head-reference/references/prompts.md:65–84`。

两个领域 Skill 都可以使用宿主提供的图像工具，工作流依据是各自的提示词和验收规则。原生 `MULTI_VIEW_EDIT` 属于通用工具层，具体是否使用由任务和工具能力决定。来源为 `head-reference/SKILL.md:23–37`、`image-to-assembly/references/multiview.md:15–25`。

### 实际输入与评审版本绑定

一次编辑先确定待改的方向和旧图，再确定本次实际使用的基准与参考图。上例中 `cat-left@v03` 是待编辑版本。正面和顶面分别为身份与轮廓提供证据。假设新图为 `cat-left@v04`，视觉评审要同时检查背景是否清理干净、耳缘和花纹有无误改，以及相关方向的地标是否仍然对得上。调用记录要保存最终发送文本，包含修订项和保护项，便于追查 `v04` 的具体来源。

`head-reference` 由宿主建立分支评审清单。修订时更新对应方向的 `images[view]`、`prompts[view]` 和 `generation_inputs[view]`，分别记录新候选、本次实际提示词或完整调用记录和实际引用的图片。改动一张图或方向映射都会使旧的整组批准失效。历史作业和确认依旧可追溯，引用旧批准图的下游计划需按当前输入复核。分支视图键、评审指纹和复验步骤见[整组视图验收与定稿](review-and-finalize-view-set.md)。 [专项评审清单](../upstream/1.2.11/prebuilt-skills/head-reference/references/review.md#输入与版本)

**基准文件需要出现在实际文件证据里。** `reference_anchor` 的字段值参与清单指纹，脚本只对 `source`、`images`、`prompts`、`generation_inputs` 和 `examples` 中的文件计算内容哈希。离线复核表明，基准文件仅以路径写在 `reference_anchor` 时，原地替换该文件会保留旧 `request_id`。同一基准确实参与生成时，应同时列入相应方向的 `generation_inputs`。如果基准已经作为原图或候选登记，其对应文件角色也会参与哈希。 [基准字段与修订约定](../upstream/1.2.11/prebuilt-skills/head-reference/references/prompts.md#检查与恢复)

## 完成条件与恢复

| 状态 | 可核查的处理 |
| --- | --- |
| 编辑任务仍在处理 | 保留原任务路径和任务 ID，续查同一任务。 |
| 调用失败、提交状态不明、下载或导出失败 | 保留原任务和已有产物，报告原因，按[图片任务状态与恢复规则](generate-new-view.md#图片任务状态与恢复)处理。调用失败不计为质量修订。 |
| 图片到手 | 使用 `view_image` 查看整张目标图，核对修改项、保护项和方向。与受影响的参考方向对照并保留观察结果。通过单图检查的候选和相关方向交给整组复查。 |
| 成功出图但修改不达标 | 保留候选、原作业和失败依据。已有授权及次数允许时，另建作业和输出路径定向修订。 |

通用 Runtime 默认允许成功出图后针对每个目标额外修订一次。选用 `head-reference` 时，宿主累计同一视角、同一检查项得到新图的定向修订次数，用 `--retry-counts` 传入形如 `{"front/carved_flow": 2}` 的记录。初次生成、调用失败不计入，换文件名后沿用原计数。整组评审处理复查、两次修订后仍失败的用户交接，以及适用的人工确认。来源见安装目录内 `resources/runtime/dist/runtime.mjs:2`、`head-reference/scripts/reference_review_core.py:176–209`。 [评审与修订规则](../upstream/1.2.11/prebuilt-skills/head-reference/references/review.md#执行) · [整组恢复与定稿](review-and-finalize-view-set.md#完成与恢复)

## Vet3D 的迁移边界

以下为 Vet3D 的设计建议，适用于前、后、左、右、顶五视图。可先定义操作语义和可核查的记录，待图像模型与 3D 后端选型后再确定请求格式。

- **定义目标与参考。** 记录待改视角及其当前版本、参考图及其各自作用、要解决的缺陷、允许改动的范围、必须保留的主体与相机条件。原始照片、补充参考和合成图的来源随版本传递。只修标签时更新视角清单，并重新验证方向关联。
- **约束候选替换范围。** 例如清理猫的左视图背景时，左图是修改目标，正面和顶面可以辅助核对身份与轮廓。比较编辑前后耳缘、非对称花纹、尾巴姿态和画面朝向。左图新版本通过单图检查后进入待定稿集合，未编辑方向继续引用原版本。
- **按能力选用适配路径。** 后端支持按方向编辑时，可映射多视角上下文与目标方向。只有单图编辑能力时，可逐个处理目标并复查整组。若适配器无法可靠确定输出对应的方向，保留候选供复核。顶视图在业务层始终保留其语义和版本，是否进入当前图片或 3D 请求由后端能力决定。
- **分开记录执行结果和质量决定。** 关联原任务、实际提示词、输入版本、输出文件和验收证据。服务成功意味着取得候选；缺陷修订使用新的候选版本。基准或已审核的图像发生变化时，重新检查受影响的视图。

下面是 Vet3D 设计示例。`expectedVersion` 将编辑绑定到开始时的左视图版本。图像版本指向保存路径和哈希的不可变文件记录。`generation` 保存实际调用证据，`referenceVersions` 保存候选暂存时要核对的引用，`affectedViews` 指明定稿时需要复查的方向。示例中的 ID 为占位值。

```json
{
  "subjectId": "cat-01",
  "operation": "edit_existing_view",
  "targetView": "left",
  "expectedVersion": "cat-left@v03",
  "replacementVersion": "cat-left@v04",
  "affectedViews": ["left", "front", "top"],
  "referenceVersions": {
    "front": "cat-front@v02",
    "top": "cat-top@v01"
  },
  "generation": {
    "job": "jobs/cat-left-v04.json",
    "anchorVersion": "cat-front@v02",
    "inputs": [
      {"version": "cat-left@v03", "role": "待编辑主图"},
      {"version": "cat-front@v02", "role": "身份基准"},
      {"version": "cat-top@v01", "role": "背部和尾根参考"}
    ],
    "finalPrompt": "prompts/cat-left-v04.txt"
  },
  "candidateCheck": {
    "status": "pass",
    "evidence": "checks/cat-left-v04.initial.json"
  }
}
```

以下是 Vet3D 设计伪代码。暂存时在同一事务中读取当前清单，核对原目标图、参考图和本轮候选检查，再写入待定稿集合。若编辑期间原左图或参考图已更换，保留候选和检查证据供复查。

```python
def stage_edited_view(tx, record):
    current_views = tx.read_candidate_views()
    target = record["targetView"]
    if current_views.get(target) != record["expectedVersion"]:
        return "目标已变化，待复查"
    for direction, version in record["referenceVersions"].items():
        if current_views.get(direction) != version:
            return "参考图已变化，待复查"

    if not candidate_check_passes(record["candidateCheck"], record):
        return "候选待单图复查"
    tx.stage_candidate(target, record["replacementVersion"], record["affectedViews"])
    return "已暂存，待整组验收"
```

## 核查范围

依据为本机安装包的 Skill、参考文档与执行脚本，以及上文所引公开网页代码。离线测试验证了请求组包、同一任务恢复，以及只记录基准路径时的哈希边界。修订后的整组复验与人工确认的核查结果见[整组视图验收与定稿](review-and-finalize-view-set.md)。云端编辑效果和真实跨视角一致性仍需实图验证。
