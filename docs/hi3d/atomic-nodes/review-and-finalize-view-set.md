# 整组视图验收与定稿

Hi3D 实现以 Windows x64 版 Hi3D Agent 1.2.11 为核查基准。普通图生 3D 由 Agent 看图并选择提交文件。静态装配和人像头部各有专项验收脚本。Vet3D 的定稿记录及五视图流程属于本文的迁移设计。

## 节点契约

| 项目 | 契约 |
| --- | --- |
| 触发条件 | 多视图任务已收到一组可查阅的实拍或成功下载的候选图，需要确定可用于同一模型的版本。更换主体基准、候选字节、方向映射或必保约束时，重新核对受影响的证据。 |
| 上游与输入 | [主体确认](confirm-modeling-subject.md)交付目标个体、主体基准、目标姿态、参考图版本和必保特征。[生成新视角](generate-new-view.md)与[编辑已有视角](edit-existing-view.md)交付候选路径、具体版本、方向声明及来源。已有可用实拍时直接进入验收。 |
| 输出 | 整组验收结论、各方向所选的实际文件版本及用途、逐图和跨图证据、需修订或待确认项。Hi3D 普通路线可从实际入选路径与方向追溯定稿，安装包没有通用的独立定稿记录格式。 |
| 完成条件 | 本次任务要求的视图及必保项均已核对，跨图冲突已解决，入选文件与审查依据对应。领域 Skill 要求额外关卡时，完成相应关卡。 |
| 下游交接 | [多视图按位置配对](pair-multiview-inputs.md)读取定稿版本及用途，按后端能力映射文件与槽位。[生成前预检](preflight-generation.md)检查本次请求的路径、方向、选项和组包条件。仅交付参考图的任务在本节点结束。 |

## Skill 绑定

| 归档 Skill | 选用条件与规则 | SHA-256 |
| --- | --- | --- |
| [hi3d/SKILL.md](../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md) | 桌面普通图生 3D 及图片生成、编辑的通用入口。指定真实原图、方向、看图、分类以及图片作业恢复规则。普通多视图使用用户实际提供且标明方向的前、后、左、右图，并包含正面。其他方向可以缺省。 | `4c268ae14ece561234682d564cdfa6264c1f121a9ea118137c0388a9240c217d` |
| [image-to-assembly/SKILL.md](../upstream/1.2.11/prebuilt-skills/image-to-assembly/SKILL.md) | 选用静态逐部件重建与装配时，在阶段 C 审查每个部件的视图，并向阶段 D 交付方向清单。部件几何、加工预留、实际整组查看和粗模环绕均为该领域要求。 | `cf4ec08dec0decfd69560a940cc26ea18fecf559ea87852c269fd2682555705f` |
| [head-reference/SKILL.md](../upstream/1.2.11/prebuilt-skills/head-reference/SKILL.md) | 选用人像头部参考图流程时，执行所选姿态模式的基准检查、逐图和整组评审，以及与当前评审绑定的人工放行。 | `7e7fa5b0cd74928feac546a64edb0d71c77d66f6e5756bfef8c528523af95795` |

工作区内已有合格图片可直接使用。影响主要外观或装配的缺失信息交宿主澄清，其余合理假设按通用入口说明。领域流程的推断、人工放行和脚本清单按各自 Skill 的选用条件生效。 [工作区通用指令](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:33>) · [归档版本说明](../upstream/1.2.11/README.md)

## LLM Tools

| 工具 | 用途与调用条件 |
| --- | --- |
| [`view_image`](../tools/view-image.md) | Codex 本地图像工具。会话图像不足以确认实际文件，或候选只存在于工作区时读取该图。整组对照图可辅助定位问题，入选单图仍需核对。 |
| [`user_interaction`](../tools/user-interaction.md) | Runtime 动态工具。主体、姿态或方向存在会影响交付的歧义时，向用户收集信息。专项流程需要真实人工决定时，可通过可用的宿主交互提交选择，头部脚本还需核对当前 `review_id`。实际桌面对头部确认的自动接线未观察到。 |
| [`hi3d_api`](../tools/hi3d-api.md) | Runtime 动态工具。候选作业未结束时按原作业续查。已取到结果但需要修订时，由补图或修图节点调用 `generate_image`。整组定稿后由下游调用 `generate_3d` 预检和提交。 |
| [`image_classification`](../tools/image-classification.md) | Runtime 动态工具。进入建模且当前轮同主体分类未记录时，按通用 Skill 记录类别。回执用于分类交接，整组结论另行核对。 |
| [`workflow_report`](../tools/workflow-report.md) | Runtime 动态工具。当前轮使用 Skill 且有对应图节点时，可挂接审查证据、同步进度或报告完成。 |
| [`exec_command`](../tools/exec-command.md) | Codex 本地命令工具。选用领域 Skill 且需执行其 Python 清单或评审脚本时，使用当前路由可用的本地命令入口。 |

`generate_image`、`generate_3d`、`query`、`wait` 和 `download` 是 `hi3d_api` 动作。`MULTI_VIEW_EDIT` 是图片请求枚举。`view_contract.py`、`reviewed_submit.py`、`reference_review.py` 是随包本地脚本。工具注册、Skill 指导和实际调用分别核查。独立工具页维护原始描述、参数及通用实现。 [工具索引](../tools/README.md)

## Hi3D 实现

### 决策

1. **先定位看过的图与实际提交文件。** 用户照片可随消息以图像进入上下文。会话预览与原件路径分开时，需核对下游将使用哪份文件。生成或编辑作业从成功回包的 `files` 或 `images` 找到候选，再实际查看。原始主图提供身份和姿态依据，补充参考只参与其所支持的方向、结构或材质判断。 [附件如何进入上下文](../infrastructure/workspace/llm-context.md#组装本轮正文和附件) · [图片查看规则](../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md#3d-任务工作流)
2. **确认路线与方向。** 普通路线以用户标注、实图和目标主体为依据选图。只有一张时沿单图流程。普通多视图保留正面和已知的其他方向，缺失方向留空。需要制作新方向时，先确认用户目标和所选流程。静态装配允许在授权范围内推断不可见面，同时保留 `observed` 或 `inferred` 来源。人像头部先确定转正 `aligned` 或保留原姿态 `current`，再使用对应基准与方向约定。 [普通默认行为](../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md#默认行为) · [装配证据优先级](../upstream/1.2.11/prebuilt-skills/image-to-assembly/references/multiview.md#证据优先级) · [头部姿态与布局](../upstream/1.2.11/prebuilt-skills/head-reference/references/review.md)
3. **定位变化再修订。** 方向标签错误且看图确认像素适用时，修正映射并重审。实际缺少另一侧时，保留缺位或按授权生成缺失方向。补图用支持身份与姿态的操作主图，修图用待改方向的目标图。普通 `imageMode="edit"` 让操作主图占 `images[0]`，补充图在其后，目标相机方向、修改项与必保项写入 `prompt`。专项原生编辑的目标由相应视角字段传递。 [补图请求和图片角色](generate-new-view.md) · [已有视角和目标字段](edit-existing-view.md)

### 执行

**普通路线。** Agent 看图后确定入选文件及各自语义方向，按任务需要记录主体分类，再将入选结果交给下游。普通 3D 通过同序 `images` 与 `views` 传入入选的照片和目标槽位。主体基准、仅供核对的参考图及必保项在上游用于选择和验收。相应的普通多视图请求以入选图为输入，独立的主图和辅助参考字段属于图片编辑路线。普通客户端的结构校验可接受仅左、右两个合法方向，也可接受同一文件配给两个不同方向。普通 Skill 的正面和实拍规则由 Agent 执行。 [配对和本地组包](pair-multiview-inputs.md#执行) · [随包 Python 规划器](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_parameters.py:145>)

**根据本机已核实的普通交接重建的下游预检请求。** 路径为示例值。正面、背面和右侧各有一份选定原件。此例显式核对客户端计划，预期槽位为 `[0, 1, 3]`。正式组合调用也会先执行本地校验。 [组合调用与显式预检](preflight-generation.md#执行)

```json
{
  "action": "generate_3d",
  "kind": "model",
  "images": ["inputs/front.jpg", "inputs/back.jpg", "inputs/right.jpg"],
  "views": ["front", "back", "right"],
  "settings": {"model_type": "v3.0:quality", "generation_type": "both"},
  "jobPath": "hi3d/hi3d-view-set.json",
  "outputDir": "exports/hi3d-view-set",
  "dryRun": true
}
```

**静态装配路线。** 按每个唯一部件分别看独立视图和对照拼图，检查身份与范围、方向与相对尺度、共同结构地标、材质、非对称特征、隐藏面依据和加工预留。修订只针对最早造成冲突的图，并明确保护区域。改完查看整张图及关联方向。可环绕的粗模关卡验证结构和遮挡关系，保留隐藏面的来源标记。最终上传使用逐方向的独立无标签图，拼图用于对照。 [装配阶段出口](../upstream/1.2.11/prebuilt-skills/image-to-assembly/SKILL.md#主流程与阶段出口) · [实际审查与修复](../upstream/1.2.11/prebuilt-skills/image-to-assembly/references/multiview.md#审查与修复)

执行者将所选图写入 `hi3d-front-neg-y-z-up-v1` 清单。装配脚本读取清单，要求 2–4 个 API 槽且含正面，再按 `front/back/left/right` 排序。每项核对 `direction_reviewed`、非空证据、相机方向、上方向、画面前向、后缀、大小和当前 SHA-256。旋转对称且前向不可观察时，允许用 `rotation_symmetric=true` 配合 `not_observable`。桌面 `reviewed_handoff` 返回 `hi3d_api` 参数及独立的视图审计。审计中的审查哈希与工具参数并列，正式调用按当时的文件重新规划。脚本的独立公共接口分支另外检查待发的 multipart 顺序和字节。 [方向和清单约定](../upstream/1.2.11/prebuilt-skills/image-to-assembly/references/view-conventions.md#生成与放行) · [清单实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/image-to-assembly/scripts/view_contract.py:22>) · [桌面交接实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/image-to-assembly/scripts/reviewed_submit.py:78>) · [独立公共接口审计](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/image-to-assembly/scripts/reviewed_submit.py:44>)

**人像头部路线。** 先验收模式自己的基准。标准四向检查正面 yaw、pitch、roll，实际侧面与背面，以及整组身份、头发、造型、裁切和材质。相对四视图逐项对照 `source`，记录是否保持原始头姿，并用四图证据验证固定姿态。标准四向使用 `screen-nose-direction-v1`，其 `right` 表示鼻尖朝画面右。装配 API 清单里的 `right` 对应前向地标朝画面左。方向翻译需记录来源约定和实图依据。 [头部清单及约定](../upstream/1.2.11/prebuilt-skills/head-reference/references/review.md#输入与版本) · [装配方向表](../upstream/1.2.11/prebuilt-skills/image-to-assembly/references/view-conventions.md#唯一工作坐标与相机表)

`reference_review.py prepare` 绑定原图、候选、实际引用的生成输入、提示词、例图、规则、评审器版本和脚本指纹。`reference_anchor` 若只作为路径文字存在，须将实际使用的基准图纳入 `generation_inputs` 才能按图像证据哈希。审查者逐项填写 `pass`、`fail`、`uncertain` 或 `not_checked`，并记录观察和证据。`set` 项引用组内各图，相对模式的指定项还引用原图。`check` 重算指纹并校验矩阵。全部必查项通过后进入 `awaiting_confirmation`。使用对应 `review_id` 的真实人工决定后，批准进入 `approved`，拒绝进入 `human_rejected`。脚本检查决定字段与评审绑定，人的身份及决定来源由宿主确认。`check` 的退出码 0 表示已批准，2 表示评审有效但未放行，1 表示输入、版本或契约错误。 [执行和人工确认](../upstream/1.2.11/prebuilt-skills/head-reference/references/review.md#执行) · [文件指纹](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-reference/scripts/reference_review.py:26>) · [决策实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-reference/scripts/reference_review_core.py:132>)

**根据安装包重建的实现伪代码。** 前两路的视觉检查由执行者依据 Skill 完成。头部路线将已填写的视觉证据交给脚本核验。返回值使用说明性的名称，实际桌面字段见各分支。

```text
普通图生 3D
  看实图并核对用户标注 → 选择符合普通 Skill 的照片 → 交付文件及方向

静态装配
  逐件看独立图与拼图 → 检查跨图一致性和粗模环绕关卡
  → 填写方向清单 → 校验声明与字节摘要 → 返回工具参数和审计

人像头部
  验收基准 → prepare → 逐图及整组填写证据 → check
  → 缺证据则复核，有明确缺陷则定向修订
  → 全部必要项通过后获取真实人工决定 → 用当前 review_id 再 check
  → 获得 approved 后交付本模式的定稿文件
```

### 验收

分别确认**实图可用、选定版本一致、下游能消费这些方向**。普通路线可按入选图复核身份、姿态、方向和选择依据，提交证据来自实际文件路径及作业记录。装配另核对清单摘要和粗模关卡。人像头部只交付当前评审的 `approved` 版本，`current` 保留相对方向，继续 3D 前单独确认后端支持。 [头部交付边界](../upstream/1.2.11/prebuilt-skills/head-reference/references/review.md#人工放行与校准边界) · [装配阶段出口](../upstream/1.2.11/prebuilt-skills/image-to-assembly/SKILL.md#主流程与阶段出口)

`workflow_report` 的节点完成仅表示图状态被接受。Runtime 校验运行中的图和节点存在性，既有隔离复现中即使前置节点未完成且产物为空也可报告完成。图卡、分类回执、脚本退出码及下游 `dryRun` 均应按各自的证据范围解释。 [工作流状态更新](../infrastructure/workspace/workflow-graph-state.md#节点完成如何生效) · [预检验收](preflight-generation.md#验收)

## 完成与恢复

| 情形 | 操作和交接条件 |
| --- | --- |
| 生图返回 `pending` | 保留原 `jobPath`、已知任务 ID 和已有文件。沿同一任务查询或等待，成功后下载，再查看实际候选。 |
| 调用失败或受理不明 | 保留原任务、已有产物与诊断。按通用 Skill 停止自动重提，由用户明确要求后再沿原任务核对和恢复。 |
| 作业成功但图像质量不足 | 保留原成功作业、候选和明确失败项。按授权给修订使用新作业与输出目录，复查改动图及关联方向。通用宿主默认每个目标额外修订一次。头部模式同一问题可做两次定向修订，仍未达标时进入 `stop_for_user`。 |
| 证据不全或头部人工决定待处理 | 复看当前文件，补齐逐图与整组证据。头部 `needs_review` 与 `awaiting_confirmation` 各自恢复，批准只绑定当前 `review_id`。 |
| 文件、基准、方向或评审规则变化 | 修改候选字节后重新查阅该图，基准变化时复查依赖视图。方向修正后复查实际对应关系。装配重新校验清单。头部重新生成请求及决策，并按新 `review_id` 取得确认。保留旧版本及其历史作业。 |
| 可回填或交给下游 | 通过当前路线的验收后，按具体版本回填相应方向，记录实际用途，再交给配对。用户只要求参考图时交付定稿图片。服务已经提交时继续保留原提交与原输入，修订作为后续计划。 |

[普通图片作业规则](../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md#图片生成与编辑) · [头部执行与修订状态](../upstream/1.2.11/prebuilt-skills/head-reference/references/review.md#执行)

## Vet3D 迁移与核查范围

### 面向五视图的契约

业务层使用前、后、左、右、顶五个语义方向。先定义动物自身左右、观察方向和顶图的头部朝向。每张图保留主体 ID、姿态基准、实际资产版本、摘要、方向依据及用途。用途可区分参与重建和仅供验收。实际观察与合成推断各有来源记录，低置信或不可见部位保留待确认状态。检查身份、站姿、比例与轮廓、跨图地标及独有特征，例如耳缘缺口、肩背花纹或尾根位置。单图合格后还要核对这些特征在整组视图上的对应关系。

定稿记录要绑定完整的评审输入和输出，至少包括主体与姿态基准版本、入选五方向或本任务所要求的方向、文件版本及摘要、证据、用途和组级决定。可用宿主管理的不可变文件版本作为快照。若底层只提供可改写路径，则在消费时读取并核对同一份字节，再将该字节交给适配器。批准后换图或改变用途时形成新的定稿记录，旧记录继续指向历史作业。下游只把明确允许参与重建的方向转为后端参数。若任务要求五图都参与重建，四槽适配器返回能力不匹配。任务明确允许顶图仅供验收时，保留其参考用途并提交适配器支持的方向。

**Vet3D 实现伪代码。** 假定上游已有实际看图的证据，`requirements` 带任务要求的方向、用途及可选人工政策。下面只定义业务语义。

```python
def finalize_view_set(requirements, review, workspace):
    if not review.covers(requirements.required_views):
        return needs_evidence(review.missing_evidence())
    if review.has_failed_checks():
        return needs_revision(review.failed_checks())
    if review.has_unresolved_checks():
        return needs_evidence(review.unresolved_checks())
    if requirements.human_confirmation:
        decision = review.bound_human_decision()
        if decision is None:
            return awaiting_confirmation(review.revision)
        if decision == "reject":
            return rejected(review.revision)

    # 确认当前工作区引用仍对应本次实际审查的版本。
    versions = workspace.pin_reviewed_versions(review.bound_assets())
    if versions.changed:
        return needs_evidence(versions.changed_assets)
    return save_finalized_set(
        subject=review.subject_version,
        view_versions=versions.items,
        direction_convention=requirements.direction_convention,
        uses=requirements.view_uses,
        review_revision=review.revision,
    )
```

验收案例至少覆盖同一实拍文件误配两个方向、两张同侧图被当成相反侧、姿态在图间变化、非对称花纹位置冲突、基准被替换、审查后文件被修改，以及顶图仅用于验收与必须参与重建两种约束。核对修改过的图和它影响的方向。证据仍有效的未改方向可复用既有审查。

### 核查依据与缺口

| 证据类型 | 结论及可复核位置 |
| --- | --- |
| 版本固定 | 使用安装事务留存包。Runtime SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`。桌面 ASAR SHA-256 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`。三份归档 Skill 的字节与包内原件一致。 [安装清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) · [桌面 ASAR](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) |
| Runtime 静态与隔离核查 | `runtime.mjs` 原始零基字节偏移 `2581614` 起的 `_z` 含默认质量修订指令，`3072331` 为工作流 `reportNode`。可在隔离环境复核图状态更新和视觉验收的分离。 [原始 Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) |
| 随包离线测试 | 头部评审 15 项、装配桌面交接 4 项通过，覆盖版本失效、人工确认绑定、方向相反和字节改动。示例请求的等价 Python CLI 调用在临时工作区返回 3 个文件、槽位 `[0,1,3]` 和 `consent.result="ready"`。另用临时文件复现装配清单接受相同路径与相同字节配给两个方向，甚至可接受具备合法后缀与摘要的非图像字节。视觉结论仍需实图。 [头部测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-reference/tests/test_reference_review.py>) · [装配测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/image-to-assembly/scripts/test_runtime_handoff.py>) |
| 本机实际观察 | 普通多视图样本在用户消息内含三张图片，随后有主体分类、`references` 标为完成和 `front/back/right` 两次一致的参数调用。作业的三个原件摘要与本机文件一致，服务回传的非空槽位为 `[0,1,3]`。该样本覆盖选定与提交。 [普通多视图实测证据](pair-multiview-inputs.md#vet3d-迁移与核查范围) |
| 待实测 | 生产中逐图和整组判断的依据、实际补图后的跨视角质量、桌面人工决定如何写入头部评审、远端重建质量，以及 Vet3D 选用的模型和接口能否消费五视图。 |
