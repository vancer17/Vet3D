---
name: mdf-api
description: 通过桌面登录态处理已有网格与图片，支持去背景、UV、水密、重拓扑、3MF、LOD、自动绑定、人体分析、中心线和可打印性检测。普通图生 3D、生成图片或模型贴纹理使用 hi3d。
---



# MDF API

使用 Runtime `mdf_api`，底层为当前桌面 test / pre / prod 环境的同步 `POST /v1/mesh/invoke`。Cookie 由 Electron 主进程附加；不要从 shell 运行联网脚本或读取代理密钥、Cookie、SDK/TOS 配置。共享传输与文件处理按 package.json 随本工具物化，不依赖相邻安装目录。

调用前读取 [接口契约](references/mesh-invoke-api.md) 对应能力的公开参数、文件限制和结果字段。仅支持文档的 14 项能力，不支持任意 worker 服务名、内部中控、SDK、TCP 或 BinaryFile。旧纹理渲染／多视图／烘焙服务未公开；需要模型贴纹理时用 `hi3d` 的 model 请求，或保留已有贴图进行本地处理，不能假装这些服务已迁移。

1. 选一个当前工作区本地文件：图片 PNG/JPEG/WebP ≤40 MiB；普通网格 GLB ≤200 MiB；auto-rig OBJ/FBX/GLB ≤256 MiB。需要材质时优先自包含 GLB。
2. 先离线校验，例如 `mdf_api(action="invoke", capability="auto-rig", file="exports/hi3d-body.glb", params={"use_transfer":true}, jobPath=".hi3d/mdf/rig.json", outputDir="exports/hi3d-rig", dryRun=true)`。
3. 正式调用只走宿主全局 `waiting_choice`。dryRun 后以同样参数移除 dryRun 调用；返回等待时由宿主弹出「仅本次 / 本次对话始终允许 / 取消」，Agent 不另做授权、不调用 `user_interaction`、不在聊天里提问。`mdf_api` 本身不拦截，未确认时由宿主硬门阻止。每个处理意图使用稳定且唯一的 jobPath。工具一次上传、同步等待、保存响应、下载文件；无需轮询。普通能力等待 2100 秒，LOD 7500 秒。sessionId/turnId 由 Runtime 提供真实对话关联，不用登录身份替代。同一上下文自动附加为 `X-Session-Id`、`X-Turn-Id` 请求头，无需 Agent 填写。
4. 仅 HTTP 200、`code=0`、`status=SUCCEEDED` 同时成立才算调用成功。`files` 是下载完成的字段名到本地路径映射；`response.data` 保留业务结果及 TOS key。LOD 的 `lods` 按目标面数降序解析动态字段指针，实际面数以元数据为准。
5. 下载文件名自动加 `hi3d-`。处理后的 GLB 检查用途相关质量后调用 `workspace_commit_model` 登记；沿用主体分类，工具要求分类时调用 `image_classification` 后用原文件重新登记。PNG 用 view_image 检查。auto-rig 不生成动画，后续交给 [rig-retarget](../rig-retarget/SKILL.md)。

`UNKNOWN`、断线或停止后保留原 jobPath 和 requestId，联系服务端核对；接口没有查询或幂等功能，不换 ID／路径重提。重复 invoke 会读取已有记录，不能重新执行算法。明确失败先处理原因，由新的明确重试意图使用新记录。

下载失败或 `downloadUnavailable` 不代表算法失败。使用 `mdf_api(action="download", jobPath="原路径", outputDir="原目录")` 只下载已保存响应的文件；CDN 不接收登录 Cookie，不拼接固定 CDN 域名。URL 缺失保留 key 并联系服务端。`recordingIncomplete` 不作废已得结果。

中心线和可打印性检测可以没有文件；读取 `response.data.result_json`。`topology_ok=false` 是检测不通过，不是调用失败；`topology_report` 可能是 JSON 字符串。人体法线／深度为相机坐标，不能直接当 GLB 世界坐标或切线空间贴图。

<!-- managed-by: sparc3d-runtime -->
