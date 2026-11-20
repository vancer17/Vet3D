# 桌面 hi3d-codex 参数契约

使用 Runtime `hi3d_api` dynamic tool；以下 CLI 示例仅说明字段映射，桌面 Agent 不直接运行这些联网命令。`--request` 对应工具的 `request` 对象，`--image-slots` 对应 `imageSlots`。

文生图和图生图不展示参数面板，默认模型与 AI 推荐比例遵循 [入口图片策略](../SKILL.md#图片生成与编辑)。图片 `settings.model` / `settings.aspect_ratio` 保留为可选兼容字段；其他参数面板使用的 `model_type` / `generation_type` 等显示 id 继续由工具包映射为下述 native 字段，desktop 不维护这些枚举。图片数不作为选择项，当前固定使用入口默认的 1 张；`model_type` 同时编码模型版本和子型号。参数齐全后可直接提交，不需要额外的计费授权字段。

## 路由与返回

| kind | 提交 | 查询参数 | 成功状态 |
| --- | --- | --- | --- |
| model / relief / split / multicolor | POST /model3d/submit | GET /model3d/result?jobId=… | data.status=1；0 等待/执行 |
| 3D 免费重试次数 | — | GET /model3d/result?jobId=… | data.retryCount 为服务端剩余次数；Runtime 归一化为 remaining，缺字段保持未知且不可重试 |
| 3D 免费重试 | POST /model3d/retry（仅本地代理，转正式账号接口 /aigc/api/generate/img2model3d-url），正文仅 `{"parentGenerateId":"<原任务根ID>"}` | GET /model3d/result?jobId=…（新任务） | 提交返回新 data.jobId；有有效 retryCount 时直接使用，否则从结果接口校准；随后与普通 3D 查询相同 |
| text-to-image / image-edit | POST /image-task/img-edit | GET /image-task/image-edit/result?taskId=… | data.status=1；0 执行；2 失败 |

检查 HTTP 和业务 code=200。提交分别返回 data.jobId、data.taskId。不能按旧 API 的 task_id/state/url 字段解析。价格、权限、模型配置由 generator 决定。身份、app_id=20010840、js_transfer 和计费由服务端管理。desktop 代理白名单、模型卡片和 `hi3d_api` action 见 [desktop 改动清单](desktop-free-retry.md)。

无文件时发送 application/json；有文件时 request 为 application/json part，images/mesh/viewImages 等为文件 part。图片 PNG/JPEG/WebP 单张 40 MiB，模型 GLB/OBJ/STL/FBX/PLY 单个 200 MiB，整次 multipart 512 MiB。优先自包含 GLB。

## 多视图与建模

```json
{"scene":"general","version":"v2.1","otherParam":{"generationType":"mesh","modelType":"fast","rmbg":1,"useGrayGeo":1,"privacyConfig":"{\"globalPrivacy\":1}"}}
```

```text
hi3d_api(action="generate_3d", images=["front.png", "back.png"], imageSlots=[0, 2], request=<上方对象>, jobPath="hi3d/mv.json", outputDir="exports/hi3d-model", dryRun=true)
```

与 C 端请求对齐时优先用 --image-slots 明确数字槽位；上述两张图发送 imageSlots=[0,2]，不压缩空槽。--views 兼容旧 CLI 的 front/back/left/right→0/1/2/3 映射，不与 --image-slots 同用；服务端 DTO 仅接收槽位数组，不在此推断每个素材方向。

未给 --request 时 model 默认 general/v3.0、both、standard、2048、GLB（前端 **quality／高质 + 几何+风格化贴图**，不是大师、不是纯几何）。前端档位名称与 Runtime 原生 `otherParam.modelType` 不同：`quality` → `standard`，`master` → `quality`。旧调用 `model=hi3dv3.0 resolution=2048quality request_type=3 format=glb` 仍兼容：Quality 的 `2048quality` 对应 `modelType=standard`，Master 的 `2048master` 对应 `modelType=quality`；request_type=1/2/3 分别为 mesh/texture/both。其他旧 model/resolution 组合明确报错，使用原生 scene/version/otherParam。生模弹窗目录与带钻项见 [网页 option 门禁](web-option-gates.md)。

Runtime v2.0 均衡档 `model_type=v2.0:1536` 显式传 `otherParam.modelType=balanced`，高质档 `model_type=v2.0:1536pro` 显式传 `otherParam.modelType=quality`，两档均传 `version=v2.0` 和 `voxelResolution=1536`；面板 id 与公共 API 的 resolution 代号保持不变。

Runtime v2.1 档位为 `fast` / `quality`：`model_type=v2.1:quality` 展开为 `version=v2.1`、`otherParam.modelType=quality`。旧面板值 `v2.1:pro` 不再接受；公共 API 的高质分辨率代号仍为 `1536pro`，不作为 Runtime 的 modelType。

原生 `request.otherParam.modelType` 或 `settings.modelType` 按后端值传入并保持原值，不再按前端档位二次转换。已有 job 按保存的请求和任务 ID 恢复；映射或默认值变化导致计划指纹不同仍拒绝覆盖，不换路径重提。

## 独立纹理

```json
{"scene":"texture","version":"v3.0","otherParam":{"generationType":"texture","modelType":"quality","pbr":1,"shadingIntensity":5,"voxelResolution":"2048"}}
```

使用 `submit model --request texture.json --mesh model.glb --image reference.png --job texture-job.json`。也可使用上述旧 request_type=2 转换方式。

## 浮雕、拆件、多色

```json
{"scene":"relief","version":"v2.0","otherParam":{"modelType":"pro","heightRelief":1.3,"reliefWidth":40,"rmbg":1}}
```

```json
{"scene":"split-to-print","version":"v2.1","otherParam":{"asyncInputParam":"{\"template\":1}","needRemesh":0}}
```

```json
{"scene":"multi-color-print","version":"v3.0","otherParam":{"asyncInputParam":"{}"}}
```

分别使用 submit relief/split/multicolor。浮雕用 --image；拆件、多色用 --mesh，拆件封面可附 --image。支持 imageUrl / meshUrl 传公开 HTTPS 地址；不接受明文 HTTP 或 TOS key。数值 format 以 generator 对应场景契约为准，不复用旧公共 API 浮雕枚举。split 可通过 generationType=mesh-2-parts 和 quality 使用原生拆件分支，默认沿用主站 mesh-2-fill-faces。asyncInputParam 是 JSON 字符串，其内部算法选项不得猜测。

## 文生图与图片编辑

`modelName` 使用当前环境配置中的精确名称。例如测试站为 `Nano-Banana 2`，不是算法代号 `nano-banana-2`。只有兼容图片 action 的 `imageModel` 由工具包 Python 自动映射；原生 `request.modelName` / `settings.modelName` 按原值发送。

```json
{"editTaskType":"TEXT_TO_IMAGE","modelName":"替换为当前环境配置的模型名","prompt":"一枚金色戒指，白色背景","imageCount":1,"aspectRatio":"1:1"}
```

```json
{"editTaskType":"EDIT","modelName":"替换为当前环境配置的模型名","prompt":"改成玫瑰金"}
```

使用 `submit text-to-image --request text.json --job text-job.json`；有参考图时 --image 均为 referenceImages。`submit image-edit --request edit.json --image base.png --image ref.png --job edit-job.json` 的第一张为 baseImage，其余为 referenceImages。

MULTI_VIEW_EDIT 使用 --image 和 --views 同序映射 viewImages/viewKeys；request 的 editedViewKeys、fullMultiViewInputs 使用 front_view/back_view/left_side_view/right_side_view，可同时保留未替换视角地址。模型名称、提示词、预设与场景选项需按实际任务提供。直接 generator 接入不包含主站 Controller 的提示词前置审核或 professions 文案转换。


## 随包脚本同步说明

`scripts/hi3d_api.py` 是唯一入口，包含 generate-image/generate-3d 单命令流程、模型别名和精简错误摘要。桌面适配保持原代理 Client、强制工作区限制、hi3d-codex-v1 backend 及账号/环境绑定，不分发独立测试 Cookie。默认参数从 `scripts/defaults.json` 加载。

Runtime 已暴露 `generate_image` / `generate_3d`，分别调用这两个 CLI 命令；兼容的 `text_to_image` / `image_to_image` 也使用 generate-image。generate-image 支持原生 request、settings、图片编辑和多图参考，结果继续转换为 PNG；多图返回原件列表。generate_3d 必填 jobPath、outputDir，kind 默认为 model；submit 的文件、槽位和原生请求参数均可使用。两个命令在同一 Python 进程中提交、等待和下载，通过 stderr JSONL 传回实时进度。

例如：`hi3d_api(action="generate_3d", images=["inputs/front.png"], jobPath="hi3d/model.json", outputDir="exports/hi3d-model", dryRun=true)`；校验后以同样参数正式生成。成功返回 result/task_id/job_file/files，Runtime 补充 jobPath；3D 仍需 workspace_commit_model 登记。pending/failed/attention 返回精简 job，包含提交 error、图像任务失败的脱敏 error（phase=generation）或查询 last_query_error；图片失败还返回 next_action 停止提示，不自动重提任务。账号接口任务的 adopt/query/wait/download 命令契约保持不变；全部生成动作仅通过桌面账号代理执行。
