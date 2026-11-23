---
name: hi3d
description: 通过 Runtime 的统一 Hi3D 能力入口进行文生图、单图或多图参考编辑、图生 3D、模型贴纹理、图片转浮雕、模型拆件、多色处理、余额查询，以及按原 3D 任务查询免费重试次数并提交一次免费重试。用户要求生成图片或从图片生成普通 3D 模型时使用；明确要求参数化建模、CAD 或可编辑工程参数时不要用 Hi3D 生成 3D。
---



# Hi3D

默认通过 Runtime 的 `hi3d_api` dynamic tool。桌面端的图片和 3D 生成都使用当前 test / pre / prod 环境和登录账号，由 Electron 主进程自动附加 Cookie。不要直接运行 Python 联网，不要读取 Cookie 文件、AK/SK、Token 或环境变量；普通 Agent shell 不提供生成代理密钥。

工具统一使用账号异步生成接口；`defaults` 返回对应默认值，完整参数见 [桌面参数契约](references/desktop-parameters.md)。旧公共 API 与固定地址生图客户端已经移除，不能绕过桌面登录。原有公共 API job 与账号接口不兼容，不能把旧任务 ID 当作新接口任务重新提交。

宿主自动为生成、查询和轮询请求附加 `X-Session-Id`、`X-Turn-Id`，关联当前调用所属的对话和用户轮次；Agent 无需填写。恢复任务时使用本次调用的轮次，两个请求头不进入生成参数或 job 指纹。

以当前对话工具定义的 action 枚举为准。若旧对话尚无 generate_image / generate_3d，图片沿用 text_to_image / image_to_image，3D 沿用 submit → wait → download → workspace_commit_model，不调用未暴露的动作。

## 默认行为

默认参数以 `hi3d_api(action="defaults")` 返回值为准，配置来自 `scripts/defaults.json`，用户本次明确指定的参数优先：

- 普通图生 3D 默认使用本 skill。只有用户明确要求参数化建模、CAD 或可编辑工程参数时改用其他建模流程，因为 Hi3D 不生成参数化/CAD 模型。
- 文生图、修改现有图片或基于参考图生成，默认使用 `generate_image`；有参考图时传 `images` 和 `imageMode`。生成结果必须保存到工作区内新的 `.png` 路径。`text_to_image` / `image_to_image` 名称继续兼容。
- 图生 3D：`hi3dv3.0` + `2048quality`（前端 `quality`／高质，Runtime `otherParam.modelType=standard`；前端 `master`／大师对应 `2048master`、Runtime `modelType=quality`），几何与纹理，PBR 开启，去光影 0.5，目标 200 万面，GLB。弹窗带钻项见 [网页 option 门禁](references/web-option-gates.md)。
- 一张图用单图模式；多视图只使用用户真实提供并标明的前、后、左、右图，且必须包含正面。不要复制、镜像或臆造缺失视图。
- 用户明确要纯几何或灰模时设置 `request_type=1`；参数面板里对应 `generation_type=mesh`。
- 用户只要为已有 GLB 贴纹理时，面板选 `generation_type=texture`（等价 `request_type=2`，Runtime 自动改 `scene=texture`），同时提供参考图和 `mesh`；只有 v3.0 档位可用，缺 GLB 或选 v2.0/v2.1 会在提交前被拒绝。
- 浮雕使用 relief/v2.0；具体参数读取 defaults，不套用旧公共 API 的格式枚举。
- 拆件、多色使用新接口的原生参数；不要沿用旧公共 API 的拆件数、颜色数、连接件和格式默认值。

skill 被加载不代表运行全部付费能力。仅在用户要求生成或处理时提交相应任务；只问能力、默认值或价格时不提交。查询已有任务不创建新任务；桌面 balance 提示从账号菜单查看积分，不调用旧公共 API 余额。已有注册模型的免费重试次数用 `retry_quota` 和准确 `fileName` 查询；用户明确要求（含卡片「重试」）后，使用卡片注入的 `retryRequestId` 调用 `retry`。只有文件引用时先调用 `model_retry_prepare(fileName)` 取回已有或新建意图。不要根据套餐名自行推断次数，也不要把同参数 `generate_3d` 当成免费重试。

## 参数面板

每个需要新建远端任务的 action 都先 dry-run。文生图和图生图不展示参数面板，按下节默认模型与 AI 推荐比例预检后直接生成。其他 action 的 dry-run 返回 `consent.user_interaction` 时，必须将该合法 payload 交给宿主 `user_interaction` 展示面板，不能把问题只写在普通聊天里，也不能自行改成另一种 kind。

- 参数面板使用 `kind="preference"`、匹配 option label 的 `defaultAnswer` 和 `timeoutSeconds=60`。超时采用面板里的推荐参数。3D 模型在同一个面板中询问扁平的 6 项 `model_type` 与 3 项 `generation_type`（`both` / `mesh` / `texture`），不先询问版本；浮雕询问 `rmbg`，拆件询问 `scene` 与 `template`。用户取消参数面板时停止。
- 将参数面板的 `answers` 合并进正式调用的 `settings`。用户已明确要求生成或处理时，参数齐全后直接提交，不再显示额外的计费授权面板。

模型正式调用示例中的 settings 形状为 `{"model_type":"v3.0:quality","generation_type":"both"}`。必须复用参数 dry-run 的其余输入、jobPath 与输出路径，不悄悄更换计划。

## 图片生成与编辑

**生成前必读：图片模型与 prompt 策略由本工具包维护，desktop 只转发参数。**

- 用户没有指定模型时，Agent 使用 `imageModel="gpt-image-2"`，服务原生名称为 `GPT Image 2`。显式指定的其他模型优先；工具包 Python 负责默认填充与兼容代号转换，desktop 不维护默认值、模型枚举或映射。
- 文生图和图生图均不弹窗询问模型、比例或图片数量。用户未指定比例时，Agent 根据画面内容、用途与参考图构图，从 `1:1`、`16:9`、`9:16`、`4:3`、`3:4` 中推荐合适比例，并显式传入 `aspectRatio`；保留构图的图生图优先选择接近主图的比例。用户明确指定的模型和比例优先。图片数量继续使用入口默认的 1 张，显式多图请求按下文处理。
- 文生图、图生图最终 `prompt` 最多 **4000 个字符**。必须先使用下方 Python 命令计数，再调用生图工具；不能靠目测估算。按 Python `len(str)` 计数，一个中文字、英文字母或非 BMP 码点各算 1 个字符，空格、换行和标点也计入；不按 token、UTF-8 字节或 UTF-16 单元计算。检查的是 `settings.prompt` → `request.prompt` → 顶层 `prompt` 优先级选出的最终文本。
- 超过 4000 时，Agent 先合并重复措辞、等义精简到 4000 字符以下，保留主体、姿态、风格和所有必选约束，再运行 Python 复查；只将通过检查的同一文本发送。不能机械截断、删掉必选约束或同时叠加长版与短版。每次追加修订或覆盖 prompt 后重新检查。本地超长检查发生在提交前，可直接精简复查，不属于失败 API 的重试；已有失败/不确定 job 仍按停止规则处理。工具包 Python 对 dry-run 和正式提交统一校验最终请求，desktop 不另设上限。
- 文生图或图生图调用失败后立即停止当前图像生成流程，报告脱敏原因并保留 task ID、job 和已有产物；不更换参数、模型、路径或工具自动重提。只有用户明确要求重试或恢复时才继续；正常 pending 可继续查询同一任务。本规则同样适用于兼容图片 action、手动 submit、下载和 PNG 转换失败；本地失败不等于远端未创建任务。
- 调用成功且取得图片后，效果不佳、视角错误或质量验收不通过属于质量迭代，可按已有授权和调用方原有次数限制继续修图或重新生成，无需逐轮重新确认，不因此暂停整项任务。质量新版本使用新的 job/输出目录，保留成功任务及产物；这不允许绕过调用失败或提交不确定的原 job。质量验收状态不得写成服务任务的 failed；最终验收门槛照常执行。
- 优先级为工具包默认值 → 显式 `imageModel`/`prompt` 等参数 → 原生 `request` → `settings`。`generate_image` 的部分 `request` 由工具包补齐；手动 `submit` 的原生请求仍由调用方完整提供。

将最终实际发送文本保存为任务目录的 UTF-8 文件（示例 `hi3d-image-prompt.txt`），定位本安装包的实际 `SKILL_DIR` 后执行：

```bash
python3 "$SKILL_DIR/scripts/hi3d_api.py" check-image-prompt --prompt-file "$RUN_DIR/hi3d-image-prompt.txt"
```

返回 `characters`、`max_characters=4000` 和 `valid`；`valid=true` 退出 0，超长退出 1。此命令只读文本、不联网、不读取认证信息、不创建 job，可在普通 Agent shell 中执行；生成仍必须走 Runtime。保存的文本包含实际追加要求，不把未发送的完整 workflow 文档当作 prompt，也不漏算末尾换行。

桌面图片生成也是异步任务。`generate_image` 及兼容图片入口会自动完成提交、等待、下载、转 PNG：

1. 用户明确要求生成或编辑图片时，先按上述 Python 命令检查最终 prompt 并完成必要精简，再调用 `hi3d_api(action="generate_image", prompt="...", imageModel="gpt-image-2", aspectRatio=<本次推荐或用户指定的比例>, outputPath="exports/hi3d-concept.png", dryRun=true)` 校验计划；通过后以同样输入将 `dryRun` 改为 `false` 正式生成，无需参数弹窗或面板答案。输出使用新的 PNG 路径。工作区内所有新生成文件的文件名必须以小写 `hi3d-` 开头；用户原始输入、Runtime 隐藏状态文件和归档内部依赖保持原名。
2. 图生图同样调用 `generate_image` 并传 `images`，桌面接口最多 4 张工作区图片，`imageMode="edit"`（默认）时第一张为主图，其余为参考图；`reference` 时均为参考图。按本节必读策略选择模型；兼容代号由工具包 Python 转换。原生 `request.modelName` 优先，必须使用当前环境的精确模型名称，不能直接填旧算法代号。完整映射见 [图片生成参考](references/image-generation.md)。不要使用旧 `style` 预设，将风格要求写入 prompt。
3. 输出路径对应稳定的本地 job。若返回 pending 或被中断，使用返回的 jobPath 执行 wait/query；同样参数和输出路径重入会复用同一任务，不重复 POST。提交不确定时先核对已有任务。
4. 工具返回路径后用 `view_image` 检查。若该图将用于生成 3D，检查后必须调用 `image_classification` 提交主角的 `{"tag4": ...}`，再进入 3D 生成；文字生成参考图也必须分类，不以用户消息是否附图为条件。同轮次已完成主角分类且主体未变时不重复调用。API 原件保存在输出文件名加 `.originals` 的目录内，拒绝覆盖不同内容。
5. 多图输出可通过 `request.imageCount` 指定，工具返回 `files` / `images` 供选择。`request` 和 `settings` 可覆盖原生场景参数。只有需要单独控制生命周期时，才使用 `submit` 的 kind=`text-to-image` / `image-edit`，随后 wait/download。

## 3D 任务工作流

1. 用 `hi3d_api(action="defaults")` 查看当前默认值。准备生成时先调用 `action="generate_3d", dryRun=true` 校验输入与参数，同时提供 `jobPath`、`outputDir`；kind 默认为 model。新接口价格由服务端决定，dry run 不鉴权、不联网、不收费。
2. 按“参数面板”执行；参数齐全后直接调用 `generate_3d` / `submit`。每个生成意图使用稳定、唯一的 `jobPath`，例如 `hi3d/model.json`；`outputDir` 使用 `exports/` 下的新目录，例如 `exports/hi3d-model`。同一 job 可防止误重复提交。
3. 工具默认在 Python 内等待 1800 秒、每 30 秒查询一次，最长 3600 秒，Agent 等待同一调用完成，不逐轮查询。Runtime 进度由客户端状态卡展示，不需要在对话中转述。普通排队、生成中或百分比变化时保持安静；只在工具结束、失败、需要用户处理或出现会改变后续决策的状态时说明。若宿主有更高优先级的定期沟通要求，只使用其允许的最长间隔和一句最短状态，不重复参数、历史或相同进度。API 没有提供可靠百分比时使用不定进度，不要编造数值。
4. 返回 `result="success"` 表示已完成下载；若已有 `registeredModel`，直接使用该登记结果，不重复登记。否则从 `files` 中找到 GLB 后调用 `workspace_commit_model`，`exportPath` 指向该 GLB 的工作区路径，使其成为工作区的新模型版本。新模型必须已通过 `image_classification` 提交分类；无匹配类别使用 `{"tag4":null}`，同主体后续修改可继承原分类。如果登记返回 `classificationRequired`，补调分类工具，再用原 `name` 和 `exportPath` 重试登记，不重新生图或生成 3D。最后按工作区规范报告 `产物：<实际 GLB 文件名>`。
5. `pending` 只是本次等待预算结束，不是失败。使用返回的 jobPath 执行 `wait`；成功后 `download` 到原 outputDir，再登记模型。也可用完全相同的生成参数恢复同一 job；不要换路径重提。`submit` / `adopt` / `query` / `wait` / `download` 继续用于手动分阶段控制和已有账号任务恢复。
6. 免费重试：卡片提供 `retryRequestId` 时调用 `{"action":"retry","retryRequestId":"<请求ID>"}`；只有准确注册文件名或自然语言请求时，先调用 `model_retry_prepare(fileName)`。次数查询为 `{"action":"retry_quota","fileName":"hi3d-model_1.glb"}`。以当前对话工具定义为准，未暴露工具时不调用。Runtime 校验账号、环境和次数，分配原任务根 ID、新 job/输出目录与登记字段；次数从提交或结果中的有效 retryCount 直接使用，缺失或异常时才校准，Agent 无需重复查询；Agent 不填写 parentTaskId、jobPath、outputDir、kind 或计费参数。工具返回 registeredModel 后不重复登记，继续原任务中受影响的场景替换与交付。失败、不确定或已取消的请求保留原意图，不更换路径、不自动再消耗次数、不转为付费生成。桌面接入见 [desktop 清单](references/desktop-free-retry.md)。

点击停止只会取消本地执行和等待，远端已接受的生成可能继续，保留原 job 查询。登录失效时重新登录原账号；环境或账号不匹配时切回原环境/账号再恢复。

`submission_uncertain` 或没有 task id 时不要盲目重提；保留 job 并报告需要核对平台任务历史。文生图/图生图失败后报告原因并结束当前图像生成流程；用户明确要求重试或恢复后才继续。所有生成任务查询报错后，说明具体原因并结束当前轮次；不得自动继续 query/wait、下载或重提，用户明确要求后才恢复。

区分“查询失败”和“任务失败”：查询失败时只报告本次无法确认任务结果，不把旧状态当作新结果；用户要求继续后，查询同一任务。工具明确返回任务失败时，说明具体原因；成功时按上述流程处理产物。错误原因直接使用工具提供的说明，默认不展示数字错误码；没有具体原因时明确说明未知，不自行推断。结果字段与恢复调用见 [查询错误](references/calling.md#查询错误)。

## 参数与结果

图片 action 使用 `prompt`、`images`、`imageMode`、`imageModel`、`aspectRatio`和 `outputPath`。3D `generate_3d` / `submit` 的 `kind`：`model`、`relief`、`split`、`multicolor`。本地 `images`、`mesh`、`jobPath`、`outputDir`、`outputPath` 都必须位于当前工作区；URL 必须是无嵌入凭据的公开 HTTPS 地址。

多视图的 `images` 与 `views` 一一对应，视角值为 `front/back/left/right`。参数覆盖放在 `settings`，只传确有需要的字段。桌面调用的原生参数见 [桌面参数契约](references/desktop-parameters.md)。`request` 可传原生 JSON，`settings` 在其上覆盖；身份、计费、回调参数由服务端管理。

API `success` 只说明服务完成，不保证模型适合打印。保留 API 原件；用户要求质量检查时，再检查文件能否载入、外形、材质/UV、部件关系和明显网格问题。不要只凭封面判断几何质量。


## 低 token 消耗与脚本版本

只加载当前任务需要的参数章节，不搜索后端源码或反复读取完整 job。正式图片生成使用一次 generate_image；新模型使用 view_image → image_classification → generate_3d → workspace_commit_model。轮询和下载在同一个 Python 生成命令中完成，Agent 不逐轮 query，也不把客户端进度通知复述成 commentary。保留桌面模型登记与分类步骤，普通生成不自动添加 Blender 渲染、审计或报告。

Runtime 的 `generate_image` / `generate_3d` 已分别接入 `scripts/hi3d_api.py` 的 generate-image / generate-3d，兼容图片 action 复用 generate-image。保留模型别名、精简错误摘要及实时进度。桌面客户端仍使用原代理和原 backend 标记，已有账号任务可恢复；不要绕过 Runtime 从 shell 获取代理凭据。

<!-- managed-by: sparc3d-runtime -->
