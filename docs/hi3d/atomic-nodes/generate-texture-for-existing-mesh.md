# 依据参考图为已有网格生成纹理

以 Hi3D Agent 1.2.11（Windows x64）为核查基准。桌面通过 `hi3d_api` 的 `generate_3d` 模型入口，把确切的已有网格与参考图组为贴纹理任务。仅贴纹理意图对应原生请求的 `scene` 与 `generationType` 均为 `texture`。任务受理、候选下载、几何与纹理验收及版本登记分别记录。 [版本归档](../upstream/1.2.11/README.md)

## 业务定义

| 项目 | 契约 |
| --- | --- |
| 触发 | 用户要求为已有网格生成新的表面外观，且已有可用参考图。用户只要求保留或迁移可用的旧贴图时，按已有材质和目标 UV 进入迁移或烘焙。 [贴图迁移与烘焙](migrate-textures-and-bake-details.md) |
| 上游与输入 | 固定目标模型的确切版本、实际文件和摘要。确认需保留的几何、部件、姿态和已有属性。固定使用的参考图文件、方向、来源和用途。已确定目标 UV 的任务记录布局身份，只有需要准备或验证 UV 时进入相应上游。 [目标 UV](establish-and-review-target-uv.md) · [整组视图验收](review-and-finalize-view-set.md) |
| 图片与网格角色 | `mesh` 是要贴纹理的已有 GLB。`images` 是实际送入生成的条件图，`views` 或 `imageSlots` 按位置与其逐项对应。单张省略方向时使用首槽。仅用于审查的图片留在业务记录中。目标是纹理候选，几何保留项及审查方向在业务侧另行验证。 |
| 输出与完成条件 | 持久化原任务和下载文件。选择并回读实际带纹理的候选，确认约定范围内的几何、UV、材质和参考图一致性。完成后提供恰当的 GLB、实际候选摘要与验收记录。 |
| 下游 | 将选定候选、源网格和参考图的版本对应、已通过与未覆盖的范围交给登记、展示或后续处理。需要把新纹理转到另一版最终可编辑网格时，将实际候选作为迁移源并按最终目标 UV 复验。 [工作区登记](../infrastructure/workspace/import-or-register-model-version.md) · [纹理迁移](migrate-textures-and-bake-details.md) |

## Skill 绑定

**通用入口。** 工作区规则指导核对确切版本、使用工作副本并按实际任务交付。选用已有模型贴纹理时，`hi3d` 指导提供 GLB 和参考图并显式选择 `texture`。普通多视图要求使用确认方向的图并含正面。该要求来自 Skill，通用 Python 槽位校验没有强制前槽非空。以下人像、分体与语义标签规则随所选专项生效。 [工作区模板](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:25>) · [通用 Skill](../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md#默认行为)

| 归档入口 | 选用条件与作用 |
| --- | --- |
| [`hi3d/SKILL.md`](../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md) | 桌面生成入口。定义已有 GLB 贴纹理、模型档位、参数面板与 3D 作业续查。 [参数门禁](../upstream/1.2.11/prebuilt-skills/hi3d/references/web-option-gates.md) |
| [`portrait-reconstruction` 依赖入口](../upstream/1.2.11/prebuilt-skills/.dependency-portrait-reconstruction/REFERENCE.md) | 人像专项进入纹理阶段时，核对已冻结几何及当前分支已验收的生成正面图，保留评审和作业依据。 [纹理交接](../upstream/1.2.11/prebuilt-skills/.dependency-portrait-reconstruction/references/execution.md#纹理生成) |
| [`metahuman-fit`](../upstream/1.2.11/prebuilt-skills/metahuman-fit/SKILL.md) | 默认用原 quality 高模做本地烘焙。明确选用桌面分体扩展时才通过规划脚本交接可选 UV 与单张正面条件图。 [Runtime 交接](../upstream/1.2.11/prebuilt-skills/metahuman-fit/references/runtime-handoff.md) |
| [`head-hair-split` 依赖入口](../upstream/1.2.11/prebuilt-skills/.dependency-head-hair-split/REFERENCE.md) | 已选头发分件且缺适用标签模型时，可用黑白标签图为原头部生成标签 GLB。该图用于下游逐面分类。 |
| [`mdf-api`](../upstream/1.2.11/prebuilt-skills/mdf-api/SKILL.md) | 仅在选定流程需要且目标缺可用 UV 时，提供公开 `unwrap-uv`。UV 候选实际回读后才进入贴纹理。 |

## LLM Tools

| 独立工具说明 | 调用时机与条件 | 核查状态 |
| --- | --- | --- |
| [`hi3d_api`](../tools/hi3d-api.md) | 目标与条件图固定后用 `generate_3d`、`kind: "model"`、`generation_type: "texture"`。只检查计划时用 `dryRun`。得到 `parameters_selected` 时按 `next_call` 续调。需要分阶段控制时按原账本查询、等待或下载。 | Runtime 已注册通用生成入口。贴纹理是模型模式，使用共用作业链。 |
| [`studio_get_state`](../tools/studio-get-state.md) | 用户指代当前视窗模型且文件未明确时，用工作区、`ready` 和 `fileName` 找到确切网格。 | 状态用于确认版本指代。UV 和真实文件由本地证据确定。 |
| [`user_interaction`](../tools/user-interaction.md) | 参考图、目标版本或专项替代方案无法确定时，用于业务澄清。 | 内置生成参数面板由 Runtime 发起，工具应答按 `next_call` 处理。 |
| [`mdf_api`](../tools/mdf-api.md) | 已选择 UV 准备分支时，按原独立 MDF 作业取得通过验收的 UV GLB。 | `unwrap-uv` 是 `invoke` 的能力枚举。它与纹理生成使用不同作业。 |
| [`exec`](../tools/exec.md) · [`exec_command`](../tools/exec-command.md) · [`view_image`](../tools/view-image.md) | 按需核对原图与网格的摘要，实际回读候选，或渲染并查看对照。 | 数值与视觉证据分别核对。`exec_command` 是本地执行入口，图像和 3D 生成由 `hi3d_api` 承接。 |
| [`wait`](../tools/wait.md) · [`write_stdin`](../tools/write-stdin.md) | 已得到 Code Mode `cell_id` 或命令 `session_id` 时，分别续读原执行。 | 服务任务沿原 `jobPath` 和任务 ID 查询。 |
| [`workspace_commit_model`](../tools/workspace-commit-model.md) · [`image_classification`](../tools/image-classification.md) | 已选候选通过业务验收且需要独立登记时，登记实际导出。缺分类时补分类后用原文件重试登记。 | 登记、分类与验收各有结果。已有 `registeredModel` 时核对该版本身份。 |
| [`workflow_report`](../tools/workflow-report.md) | 选用有工作流图的专项且实际执行时，按原节点记录阶段与产物归属。 | PCG 路线与阶段回填体现在编排，任务状态以实际回包及文件为依据。 |

`texture` 是 `settings.generation_type` 的选项，`scene` 与 `generationType` 是规划出的请求字段。`waiting_choice` 是参数等待状态。`texture_pipeline.py` 是本地规划脚本，独立公共 CLI 和桌面 Runtime 分别管理各自账本。 [注册与可见性](../tools/README.md#注册与可见性)

## Hi3D 实现

### 决策

1. **先锁定模型指代。** 已有确切路径时直接检查文件。指代 Studio 当前模型时先确认已加载版本，再解析工作区文件。若需要保形或保留原 UV，记录冻结基线、允许变化的区域与后续比较依据。通用纹理预检的网格文件检查覆盖路径、后缀、字节数与 SHA-256。UV 内容和几何可用性由实际读回确认。 [工作区状态](../infrastructure/workspace/read-studio-state.md) · [输入文件验证](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_parameters.py:40>)
2. **挑选实际条件图。** 按已确认用途与方向建立逐张对应，核对主体、朝向和可见区域。只供审查的照片保留独立角色。按任务需要与所选流程追加方向或补做图。通用桌面入口只接受四个槽位。 [视图交接与配对](pair-multiview-inputs.md#从方向标签追踪到上传字节)
3. **固定生成模式和计划。** 目前公开桌面路径使用 `v3.0:quality` 或 `v3.0:master`，模式显式为 `texture`。为同一处理意图选定稳定的 `jobPath` 和 `outputDir`。如需先业务验收，正式调用可省略自动登记的双参数，保留可选择的下载候选。 [桌面参数](../upstream/1.2.11/prebuilt-skills/hi3d/references/desktop-parameters.md) · [下载与登记](../tools/hi3d-api.md#已下载-3d-产物与登记)

### 执行

#### 通用桌面请求

**根据已验证行为重建的预检请求。** 示例将左视图和正面图交给已定稿的目标网格。路径以工作区为基准。

```json
{
  "action": "generate_3d",
  "kind": "model",
  "targetName": "动物模型",
  "mesh": "inputs/target.glb",
  "images": ["inputs/left.png", "inputs/front.png"],
  "views": ["left", "front"],
  "settings": {
    "model_type": "v3.0:quality",
    "generation_type": "texture"
  },
  "jobPath": ".hi3d/texture.json",
  "outputDir": "exports/texture",
  "dryRun": true
}
```

本例原生计划为 `scene: "texture"`、`version: "v3.0"`、`otherParam.generationType: "texture"`、`otherParam.modelType: "standard"`，`image_slots: [2, 0]`。`v3.0:master` 对应原生 `modelType: "quality"`。选项层拒绝 v2.0/v2.1 的 `texture` 组合。通用原生默认值仍可能包含面数、PBR 和格式字段，具体是否保留原拓扑、UV 和材质需从生产候选验证。 [模型选项映射](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/web_option_gates.py:485>) · [预检结果](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_api.py:177>)

本地图片最多四张，支持 PNG、JPEG、WebP，每张至多 40 MiB。通用本地网格文件上限 200 MiB，贴纹理规程使用 GLB。单图缺方向时使用槽 `0`。多图使用与文件等长、唯一的具名方向或数字槽位，二者互斥。`front/back/left/right` 对应 `0/1/2/3`。图片不会为填槽重排，缺槽可省略。`top` 和第五张图在该路径会被客户端拒绝。 [输入与方向规则](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_parameters.py:139>)

#### 参数面板及旧参数冲突

参数未齐全时，正式调用顶层可返回 `waiting_choice`。显式预检把等待状态放到 `consent`。Runtime 识别两者，通过宿主偏好面板只询问缺项。60 秒默认来自面板配置，用户可选或取消。有效答复返回 `parameters_selected` 与 `next_call`，保留原文件路径、视图、作业、输出目录和 `dryRun`。续调重新读取文件和规划。若文件内容已变化，业务侧先复核定稿版本。取消时没有续调。 [Runtime 参数面板](preflight-generation.md#执行) · [面板构造](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/web_option_gates.py:547>)

| 已核实的输入组合 | 面板或原生预检结果 |
| --- | --- |
| 两个现代选项均明确，`generation_type: "texture"` | 有效 v3.0 档位时可 `ready`，`scene` 与 `generationType` 都为 `texture`。 |
| 只明确现代 `generation_type: "texture"` | 面板只问 `model_type`，默认 `v3.0:quality`。后续重新校验是否是支持的 v3.0 档位。 |
| 只传旧 `request_type: 2`，或只提供原生 `scene: "texture"` | 原生请求可含纹理意图。现代选择仍待补，缺少的 `generation_type` 问题默认 `both`。 |
| 同时保留旧 `request_type: 2` 和现代 `generation_type: "both"`，且已有现代模型选项 | 本轮离线可得到 `ready`，原生请求却是 `scene: "texture"` 与 `generationType: "both"`。 |

规划器先应用旧兼容字段，再叠加现代覆盖值。现代 `both` 只覆盖 `generationType`，不会重置兼容分支已写入的 `scene`。业务预检同时核对两个原生字段，发现冲突时在提交前按明确的仅贴纹理意图整理参数。生产服务如何处理混合值仍待测。 [兼容覆盖顺序](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_parameters.py:88>) · [现代选项转换](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/web_option_gates.py:485>)

#### 组包到候选下载

**根据已核实行为重建的执行伪代码。** 省略本地登记与错误包装。图和网格都为本地文件时，`imageSlots` 与重复的 `images` 字段保持同序，`mesh` 是单独的文件部分。

```python
def generate_texture(original_inputs, settings, job_path, output_dir, *, dry_run):
    gate, overrides = resolve_display_options(settings)
    plan = build_plan(kind="model", inputs=original_inputs, overrides=overrides)
    if dry_run:
        return preview(plan, consent=gate)
    if gate.result == "waiting_choice":
        return gate  # Runtime 处理面板答复并返回 next_call

    job = submit_or_reuse(plan, job_path)
    observed = wait_same_task(job, seconds=1800, interval=30)
    if observed.result != "success":
        return observed
    return download_same_task(job, output_dir)
```

1. **准备传输。** Runtime 把本地 `images` 逐项交给 Python，`views` 或 `imageSlots` 保持原序。multipart 先写 `request` 与 `imageSlots` JSON，再写图字节与目标网格。组包重新核验规划时的文件长度和 SHA-256。顶层输入的 URL 兼容分支分别把 `meshUrl` 写入 `otherParam.meshUrl`，把 `imageUrl` 写入 `multiViewSourceImageList` 首槽。无本地文件时发 JSON。`imageUrl` 的公开工具说明面向浮雕，贴纹理 URL 组合的结论限于共用规划器的离线构造。 [本地 3D 组包](../tools/hi3d-api.md#3d-本地文件组包) · [传输分派](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_jobs.py:183>)
2. **提交并持久化。** 同路径同指纹时复用原作业。新作业在 `POST /v1/model3d/submit` 前独占写入 `submitting` 账本。收到有效 `jobId` 先保存为 `task_id`，再更新等待状态。新的候选规划、确认面板、账户代理和任务受理各有自己的证据。 [提交实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_jobs.py:192>) · [组合入口](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_generation_workflow.py:11>)
3. **沿同一任务观察与下载。** `/v1/model3d/result` 按原 `jobId` 查询。整数 `data.status=0` 为处理中，`1` 为成功。`percentage: 100` 可以仍为处理中。组合调用默认等 1800 秒、每 30 秒查询。无完整下载缓存时，下载分支刷新同一任务结果并取得实际 HTTPS 候选，记录路径和摘要。回包可包含多个 GLB、预览与附件，按实际产物选择。 [查询状态](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_jobs.py:269>) · [原候选下载](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_artifacts.py:175>) · [等待调度](schedule-wait-and-handoff.md)

#### 专项交接

| 分支 | 条件、实际行为与交接 |
| --- | --- |
| 人像重建 `texture_only` | 冻结最后一个通过的几何版本。从当前分支 manifest 定位已经验收并获人工确认的生成 front，绑定 `review_id`、图像摘要与冻结网格。只有相对方向且无标准 front、或存在多个适用 front 时，按专项规程明确选图。默认传一张，可按已确认意图追加具名方向。PCG 路线声明阶段顺序。归档中的独立 CLI 参数属于非 Runtime 模式，桌面走 Runtime 工具。 [专项执行](../upstream/1.2.11/prebuilt-skills/.dependency-portrait-reconstruction/references/execution.md#纹理生成) · [PCG 路线](../upstream/1.2.11/prebuilt-skills/.dependency-portrait-reconstruction/pcg/routes.yaml) |
| MetaHuman 桌面分体 | 显式选定 `bald` 或 `hair` 才使用此交接。`texture_pipeline.py` 读取调用方 `has_uv`，缺 UV 时生成 `texture_size: 4096`、`need_repair: false` 的可选 MDF 计划。验收实际 `uv.files.uv_mesh_glb` 后填入 `mesh`。`front` 是唯一上传条件图，其余记在 `reviewViews`。脚本返回 `plan_only` 与 `geometry_preservation_verified: false`，其中旧 `request_type: 2` 仍需按桌面选项规程处理。 [桌面交接](../upstream/1.2.11/prebuilt-skills/metahuman-fit/references/runtime-handoff.md) · [规划实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/metahuman-fit/scripts/texture_pipeline.py:9>) |
| 头发分件的标签纹理 | 缺合格标签时，从实际原头部及对应正面生成白发黑头图，作为贴纹理条件。独立 CLI 包装参数含 `request_type=2`、`pbr=0`、`shading=1.0`。收到的是按 UV 采样的语义标签候选，分件需要验证逐面对应，最终材质来源仍是原彩色模型。独立 CLI 采用其真实的认证、组包与账本。 [标签流程](../upstream/1.2.11/prebuilt-skills/.dependency-head-hair-split/REFERENCE.md) · [独立包装](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-head-hair-split/scripts/workflow.py:142>) |

随包另存内部纹理服务调用方资料。其投射分支接受同一目标几何、UV、有序相机、图像和权重，`compose` 用于装配已有通道。桌面公开 MDF 枚举未开放这些旧能力。桌面分体规划没有 Coverage 输出，覆盖和局部质量从实际产物另行验证。 [内部投射与合成契约](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-service-select/references/mdf/texture-bake-v3-0.md:5>) · [公开边界](../upstream/1.2.11/prebuilt-skills/mdf-api/SKILL.md)

### 验收

| 检查 | 通过条件与边界 |
| --- | --- |
| 计划与来源 | 实际送出的 `mesh`、图与槽位对应冻结输入。原生 `scene` 和 `generationType` 均为 `texture`。保存任务 ID、作业记录和实际候选摘要。 |
| 几何与保留项 | 回读选定 GLB，对照源网格的实际对象、部件、变换、尺度和轮廓。保形任务按实际空间距离和约定范围验证。索引变化、UV 缝拆点与实际几何差异分别记录。 |
| UV、材质与外观 | 核对贴图可读与实际引用、需上图区域、使用 UV 层及参考方向的一致性。审查接缝、串位、遮挡和背面，并记录参考可证实的区域及推定区域。 |
| 交付身份 | 通用下载器校验容器与下载身份。自动登记依据合格工作区 `.glb` 数量；恰好一项才登记。返回 `registeredModel` 时仍核对业务验收对应的实际文件。 [通用下载](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_artifacts.py:175>) · [登记边界](../tools/hi3d-api.md#已下载-3d-产物与登记) |

人像专项进一步明确对照眼睛反光、鼻色、接缝和保形；服务可能调整几何或索引，发现改动时保留冻结原件与对照证据。通用候选核对沿用工作区实际文件和视觉证据。 [人像验收](../upstream/1.2.11/prebuilt-skills/.dependency-portrait-reconstruction/references/execution.md#纹理生成) · [候选适用性](check-model-candidate-suitability.md)

## 完成与恢复

| 状态 | 恢复与交接 |
| --- | --- |
| 参数未齐或已答复 | 用宿主实际 `next_call` 续调，复核定稿文件及原生两个模式字段。取消则保留已准备输入，结束本次待选。 |
| 原任务仍在运行或等待预算结束 | 有 `task_id` 时只沿原 `jobPath` 续 `wait` 或核对同一任务。可用同一合格计划重入 `generate_3d`。当前工作单元仍在运行时用实际 `cell_id` 续等。 |
| 提交不明且缺任务 ID | 保留原账本、指纹、输入及已知回执。不能因本地中断另建路径重发。仅从可靠证据取得原任务 ID 后，按同一账号与环境的恢复契约续查。 [作业资格](locate-job-and-qualify-resume.md) · [作业恢复](../tools/hi3d-api.md#作业持久化与恢复) |
| 查询或等待返回错误 | 保留已持久化的任务与诊断，区分服务明确拒绝和本次查询不可用。按 Tool 约定报告具体原因，用户明确要求恢复后，沿原记录继续核对。 [查询诊断](../tools/hi3d-api.md#查询与等待诊断) |
| 任务已完成但下载中断 | 沿原 `jobPath` 与绑定目录恢复。独立 `download` 命中完整缓存时校验路径、字节数和摘要后可直接交付。缓存不完整时按同一任务获取新鲜成功及下载来源。 [下载与恢复](confirm-download-source-and-recovery.md) |
| 已有候选，质量未通过 | 保存该作业、候选及实测依据。根据失败项选择修订参考图、回到目标 UV 或选择局部迁移。目标与参考变更属于新的处理意图，原任务及其资料保持可追溯。 [目标 UV](establish-and-review-target-uv.md) · [局部迁移](migrate-textures-and-bake-details.md) |
| 候选通过，登记失败或有多个 GLB | 保留下载文件与原任务。`attention/register-model` 只描述登记结果。核对各实际 GLB 的用途，再用独立工具补登记选定文件。若缺分类，沿用原导出补分类后再登记。 [独立登记](../tools/workspace-commit-model.md#失败与重入) |

**完成交接。** 确认源网格和条件图版本、实际已选候选、保留项及质量记录一致，再交给下游。作业 `success` 和版本登记各有回执。若用户明确要求免费重试，按可信已登记来源和实际额度使用专用意图。其重试请求通过 `parentGenerateId` 引用根任务，调整参考图或目标网格需另外规划。生产贴纹理任务的资格及服务行为待验证。 [免费重试准备](../tools/model-retry-prepare.md) · [重试实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_jobs.py:108>)

## Vet3D 迁移与核查范围

### 供应商无关的交接契约

业务层固定目标网格及参考图的版本、方向、来源、作用区域与保留项。适配层负责把仅生成纹理的业务意图映射到后端支持的模式和视角。Vet3D 可在业务层保存前、后、左、右、顶五向语义。要求顶图参与而后端仅支持四槽时，记录能力不匹配；任务明确允许时才将顶图用于复验。执行层分别记录实际发送图与仅审查图、原任务标识、产物摘要和验收状态。

**Vet3D 设计示例。** `provider` 的模型和 API 字段留在适配层，下面示意业务输入的身份和用途。

```json
{
  "intent": "texture_existing_mesh",
  "targetMesh": {
    "revision": "target-03",
    "file": "work/target.glb",
    "sha256": "6fe817dcf0d7d55a5e44777943a5d2464393ae39f07b32dcd500bdbc28e10b92"
  },
  "references": [
    {"direction": "front", "file": "refs/front.png", "use": "condition"},
    {"direction": "top", "file": "refs/top.png", "use": "review"}
  ],
  "preserve": ["geometry", "part_boundaries", "scale"],
  "review": {"status": "pending", "evidenceFiles": []}
}
```

这个例子将顶视图标为审查用途，实际任务仍要绑定每张图的版本与摘要。用作业指纹保护任务受理，用候选摘要绑定验收。模型供应商仍可独立选型。

### 下游接收检查

Vet3D 交接时，将用户批准的网格及参考角色与实际提交的网格、条件图顺序、原作业对应记录，在候选上保存最终通过的几何、UV、纹理检查范围。如需把新纹理用于另一网格，将该候选作为迁移源，使用另一网格验收通过的目标 UV 建立新的迁移记录。 [迁移交接](migrate-textures-and-bake-details.md#供应商无关的交接契约) · [主模型交接](select-primary-model-and-confirm-handoff.md)

### 安装包证据、样例与缺口

- **安装包证据。** 使用 `D:/install/Hi3DAgent.__hi3d-transaction/resources/` 的 Windows x64 1.2.11 快照。`runtime.mjs` 中 `dz[0]` 定义在零基字节 `2522079`，`Kj` 分派在 `2503566` 附近，参数答复构造 `next_call` 在 `3205416`。`app.asar` 的 `out/main/index.js` 成员零基字节 `212899` 为 `/v1/model3d/submit` 路由字符串。桌面版与独立开放 API CLI 的入口和账本分别归属。 [版本清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) · [Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) · [桌面 ASAR](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>)
- **离线核查。** 本页请求复跑得到 `ready`、`texture/texture` 和槽位 `[2,0]`，未创建作业或输出目录。已复核 multipart 顺序、`top` 拒绝、旧参数冲突、URL 构造及规划后文件变更导致的组包哈希冲突。模拟传输覆盖同一任务 pending 续接、多候选下载和缓存复用。只含合法资产头、没有网格与 UV 的 GLB 也能通过下载器，说明候选要另做业务验收。随包账户与恢复测试共 49 项通过。 [账户测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/tests/runtime/test_account.py>) · [恢复测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/tests/runtime/test_recovery.py>)
- **样例覆盖。** 留存猫模型作业采用 `scene: "general"`、`generationType: "both"`、`imageSlots: [0,1,3]`。留存会话记录普通生成的面板续调、下载和登记。三个 GLB 与该会话提供普通生成及后续模型交付的样例证据。 [留存作业](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/hi3d/hi3d-cat-multiview.json>) · [该次实际续调](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:68>)
- **待实测。** 生产贴纹理的实际条件图利用和槽位解释、URL 组合、指定网格的几何与 UV 保留、不同档位的产物与免费重试资格，以及真实四足资产的纹理质量和遮挡一致性。离线组包能核实客户端如何传递输入，云端行为需用实际结果验证。
