# 图片生成参考

图片生成与图生 3D 共用 Runtime dynamic tool `hi3d_api`，桌面模式下都经主进程代理使用当前环境和账号。Agent 不传服务地址或认证信息。

## 文生图

```json
{"action":"generate_image","prompt":"白色背景上的未来感头盔，产品概念图","imageModel":"gpt-image-2","aspectRatio":"1:1","outputPath":"exports/hi3d-helmet-concept.png","dryRun":true}
```

文生图和图生图均无需参数弹窗。按 [入口的图片策略](../SKILL.md#图片生成与编辑) 默认使用 `gpt-image-2`；未指定比例时由 Agent 根据内容、用途和参考图推荐，并显式传入 `aspectRatio`，上例的 `1:1` 仅示范方形产品图。dry-run 校验通过后保持同一计划，将 `dryRun` 改为 `false` 正式调用，无需提供面板答案。图片数量继续使用入口默认的 1 张。

## 图生图

```json
{"action":"generate_image","prompt":"保留主体轮廓，改为石雕材质","images":["inputs/front.webp"],"imageMode":"edit","imageModel":"gpt-image-2","aspectRatio":"3:4","outputPath":"exports/hi3d-helmet-stone.png","dryRun":true}
```

- `edit`：第一张图片是主图，其余图片作为补充参考。
- `reference`：所有图片都是参考图。
- 上例 `3:4` 示范竖构图；实际按主图构图、用途和用户明确要求选比例，预检后直接正式生成。
- 桌面输入 1–4 张静态 PNG、JPEG 或 WebP，每张不超过 40 MiB。Runtime 上传图片二进制并保留正确 MIME，例如 WebP 使用 `image/webp`。

## 可选参数

- `imageModel`：模型选择与默认值先读 [Hi3D 必读入口](../SKILL.md#图片生成与编辑)；兼容代号见下表。网页上除 Seedream V4.5 外带钻；Agent 生模/生图阶段仍可选用，见 [网页 option 门禁](web-option-gates.md)。
- `aspectRatio`：`1:1`、`16:9`、`9:16`、`4:3`、`3:4`；用户指定优先，否则由 Agent 推荐并显式传入，不询问用户。CLI 缺省的 `1:1` 仅作兼容回退，不代替 Agent 的比例判断。
- 桌面接口不兼容旧 `style` 预设；将风格要求写入 prompt。

`imageModel` 由 desktop 原样转发给工具包 Python，再转换为生成服务精确匹配的 `modelName`；未列出的字符串按原生名称传递，是否可用由目标服务决定：

| imageModel | modelName |
| --- | --- |
| nano-banana-2 | Nano-Banana 2 |
| nano-banana-pro | Nano-Banana-Pro |
| seedream-v4.5 | Seedream v4.5 |
| gpt-image-2 | GPT Image 2 |

这些名称已与测试站 `GET /aigc/api/image-task/client-config` 的模型列表核对。其他环境可用性仍由其配置决定；`request.modelName` 按原值覆盖映射，传入该环境的准确名称，例如 `{"modelName":"Nano-Banana 2"}`。不要把旧代号直接用于原生 `modelName`。

`prompt` 必填，按 [Hi3D 必读入口](../SKILL.md#图片生成与编辑) 在调用前执行 `check-image-prompt` Python 脚本计数；超长先等义精简、复查，再生成。检查最终 `request` / `settings` 覆盖且含追加修订的文本；desktop 不另设上限，工具包 Python 对 dry-run 与正式提交共用最终请求校验，超长报错而不静默截断。长 workflow 的完整编排/验收说明不要全部拼进请求，改成保持关键约束的短版并记录实际发送文本。

`outputPath` 使用工作区内新的 `.png` 文件，文件名必须以小写 `hi3d-` 开头，建议位于 `exports/`。桌面 `generate_image` 和兼容的 `text_to_image` / `image_to_image` 入口都调用 generate-image，在同一 Python 命令内完成异步提交、等待和原件下载，随后转换为 PNG；原件保留于 `<outputPath>.originals`。相同输出路径和参数复用同一 job，不同 action 名称也可恢复同一个任务。先 dryRun 校验，再正式生成。

默认等待 1800 秒，每 30 秒查询，并把进度发送到客户端状态卡。Agent 不在对话中逐次转述普通等待或百分比变化。`pending` 返回 jobPath，可用 wait/query 继续原任务，成功后下载；取消本地等待不会取消远端生成。调用失败或提交不确定时遵从 [入口的停止规则](../SKILL.md#图片生成与编辑)：报告脱敏原因，保留原任务并停止，不换参数、模型、路径或工具重新提交；用户明确要求后才恢复。generate_image 可用 request/settings 覆盖原生参数，request.imageCount 指定多图输出时返回 files/images。需要单独控制生命周期时用 `submit` + `request` + 稳定 `jobPath`，见 [桌面参数](desktop-parameters.md)。实际模型可用性由当前环境配置决定。调用成功且取得图片后，效果不佳、视角错误或质量验收不通过属于质量迭代，可按已有授权和调用方原有次数限制继续修图或重新生成，无需逐轮重新确认，不因此暂停整项任务。质量新版本使用新的 job/输出目录，保留成功任务及产物；这不允许绕过调用失败或提交不确定的原 job。质量验收状态不得写成服务任务的 failed；最终验收门槛照常执行。

旧固定地址同步生图服务已经移除。所有图片生成都必须使用桌面账号代理，当前最多接收 4 张输入图片。
