# sapiens2

单图调用 Sapiens2 的 pose、seg、normal、pointmap、matting 五项能力；支持单项、组合或全部执行。默认注册名 `sapiens2`，实际名称可由部署覆盖。模型实例缓存复用，默认每项结束后卸回 CPU。

契约依据 Hi3Dreamer 服务仓库 [sapiens2-service 的固定版本](http://172.31.0.3:8099/hi3dreamer/sapiens2-service/-/tree/d5c8f6f0acbf4705043b73fc3897940b4611cb88)，包含 [请求校验](http://172.31.0.3:8099/hi3dreamer/sapiens2-service/-/blob/d5c8f6f0acbf4705043b73fc3897940b4611cb88/sapiens_service/contract.py)、[模型与任务执行](http://172.31.0.3:8099/hi3dreamer/sapiens2-service/-/blob/d5c8f6f0acbf4705043b73fc3897940b4611cb88/sapiens_service/engine.py)、[官方输出适配](http://172.31.0.3:8099/hi3dreamer/sapiens2-service/-/blob/d5c8f6f0acbf4705043b73fc3897940b4611cb88/sapiens_service/predict.py)和 [MDF3 包装](http://172.31.0.3:8099/hi3dreamer/sapiens2-service/-/blob/d5c8f6f0acbf4705043b73fc3897940b4611cb88/sapiens_service/worker.py)。算法固定 [官方 Sapiens2 源码](https://github.com/facebookresearch/sapiens2/tree/7e5bae88456ac418ff0e58e74106c9fe192055d4)，使用其配置、预处理、模型和解码器。

**覆盖范围：源码契约，部署待验证。** 本地适配器测试与分割模型直接推理不能证明五项模型的 CUDA 推理、CPU offload 显存行为或 center 注册成功。调用前确认目标实例完成这些验收；本页不提供未经验证的 relay33 端口。

## 输入

输入必须是对象，`image` 为持有真实图片字节的 MDF3 BinaryFile；客户端路径不会自动上传。图片须为 Pillow 可解码单帧栅格，至少 2×2，最多 1600 万像素、32,000,000 字节。不按 EXIF 旋转，原图坐标均指编码栅格。

| 字段 | 默认值 | 含义 |
| --- | --- | --- |
| `task` / `tasks` | `"all"` / 无 | 单个任务名或任务名列表，两字段互斥；支持 pose、seg、normal、pointmap、matting，重复/未知项拒绝。 |
| `offload_cpu` | true | 每项完成卸回 CPU，释放 CUDA 缓存；false 仅允许 standalone 模式保留最后模型，切换任务时仍先卸载前一个；managed 模式拒绝 false。 |
| `visualize` | true | 额外返回 PNG 预览，原始 NPZ 始终返回。 |
| `bboxes` | 无 | pose 的原图 xyxy 像素框，1–32 个有限、正面积、位于图内的框；有框跳过 DETR。 |
| `detect_persons` | true | pose 无框时调用本地 DETR；false 明确使用全图框，适合裁好的人头。 |
| `bbox_threshold` / `nms_threshold` | 各 0.3 | pose 检测阈值，有限数值 [0,1]。 |
| `flip_test` | 官方 pose 配置 | bool；false 关闭翻转测试。 |
| `pointmap_smooth` | true | pointmap 放大时使用官方平滑步骤。 |

布尔值必须是真实 bool，False 和 0 不被默认值覆盖。pose 控制只在请求包含 pose 时接受，pointmap_smooth 同理。检测不到人物返回 N=0，不自动用全图冒充检测结果；如需全图推理显式传 `detect_persons=false`。超过 32 个检测人物失败，调用方可传选定框。

## 调用

传输复用独立 [mdf-call](../calling.md)，不另复制客户端。其业务 CLI 的 JSON 文件引用示例：

```json
{
  "image": {"$file": "/work/head.png"},
  "tasks": ["pose", "seg", "normal"],
  "detect_persons": false,
  "offload_cpu": true,
  "visualize": true
}
```

`$file` 是客户端展开语法，最终传输的是 BinaryFile。下游服务名是 `sapiens2`；由 mdf-call 经 TaskQueue 按服务名调度，不写死 worker IP。单独法线调用将控制换成 `{"task":"normal"}` 并保留 image；不要携带 pose 专用字段。

也可在 Hi3Dreamer 服务仓库安装实际 MDF3 SDK 后使用其 [单次调用客户端](http://172.31.0.3:8099/hi3dreamer/sapiens2-service/-/blob/d5c8f6f0acbf4705043b73fc3897940b4611cb88/sapiens_service/client.py)。超时不自动重试，先用已记录 trace 确认原任务状态。

## 输出与交接

成功包含 `success=true,status="success",trace_id`。`results.<task>` 包含 `data:BinaryFile(<task>.npz)`、`metadata`，以及可选 `visualization:BinaryFile(<task>.png)`。先保存真实字节，再用 `numpy.load(...,allow_pickle=False)` 读取 NPZ；它不是 data-io .zst 容器。

| 任务 | 数组 | 语义 |
| --- | --- | --- |
| pose | keypoints[N,308,2] float32、scores[N,308] float32、bboxes[N,4] float32 | 原图 xy 像素；metadata 提供官方关键点名称与 bbox_source，N 可为 0。 |
| seg | labels[H,W] uint8 | 29 类人体部位，0 为背景；metadata 提供 class_names 与 palette。 |
| normal | normals[H,W,3] float32 | 官方相机坐标法线，先归一化后插值；插值结果模长可略偏离 1。 |
| pointmap | pointmap[H,W,3]、depth[H,W]、scale[1,1] float32 | 相机坐标预测除以官方 scale 得到米制估计，depth 为 Z 分量。 |
| matting | alpha[H,W]、foreground_premultiplied[H,W,3] float32 | alpha 与预乘 RGB 在 [0,1]；合成时不要再次乘 alpha。 |

H/W 为原始栅格尺寸；normal/pointmap 先去预处理 padding 再恢复尺寸，seg/matting 按各自官方 resize 恢复。预览最长边 1024，只用于查看，不作为数组坐标基准。normal/pointmap 不依赖 seg/matting；需要前景筛除时由调用方按同尺寸 labels/alpha 组合。

相机法线不是烘焙的切线 normalmap；pointmap 也不是已注册 GLB 世界点。用于人头注册时须建立相机、尺度和关键点对应，不能直接把 308 点当 MetaHuman 顶点索引。人体分割不保证区分所有人脸精细区域，应检查眼皮、耳朵、口腔等目标区域的实际 mask。

全局字段另有 `image_size=[W,H],tasks,offload_cpu,upstream_commit,started_at,ended_at,seconds,timings,memory`。逐项计时包含检测、模型搬运、推理和打包；模型 preload 不在请求计时内。CUDA memory 包含当前 allocated/reserved 及请求峰值；CPU/MPS 不返回虚构 CUDA 数值。

失败返回 `success=false,status="failed",error_type,error_message,error_info,trace_id,seconds`；两错误文本一致，不把部分任务产物当整次成功。推理或打包失败会卸载当前模型；致命 CUDA 错误继续抛给框架。输入输出使用内存字节，不依赖服务端临时路径。

## 部署与验收

部署完整步骤见 Hi3Dreamer 服务仓库 [README](http://172.31.0.3:8099/hi3dreamer/sapiens2-service/-/blob/d5c8f6f0acbf4705043b73fc3897940b4611cb88/README.md) 与 [启动入口](http://172.31.0.3:8099/hi3dreamer/sapiens2-service/-/blob/d5c8f6f0acbf4705043b73fc3897940b4611cb88/sapiens_service/serve.py)。默认采用 AlgoWorker + ManagedServiceBase，按 --device 登记单张 GPU，由 GpuArbiter 分配请求。模型在 CPU 初始化，业务调用结束或失败先卸载再向框架返回，防止释放使用权后仍占用显存；保留 --mode standalone 的普通 ServiceBase 专用设备路线。启动参数兼容 --env、--service_name、--port/--tcp_port，新增 --arbiter-host（127.0.0.1）与 --arbiter-port（19600）。

Python ≥3.12，PyTorch ≥2.7，MDF3 SDK 3.2.4。模型路径和 MDF 环境配置由部署提供；默认五项 1B、CPU preload、float32，检测器本地加载。pose/seg/normal/pointmap 可配置 0.4b/0.8b/1b/5b，matting 仅 1b；业务请求不更换尺寸、不下载模型。权重使用官方原始 task safetensors，严格匹配，并在下载时记录 revision/SHA-256。

先检查 GPU 与主机 RAM 容量：五项模型缓存于 CPU，并不因显存卸载而释放全部 RAM。默认 offload 以模型搬运开销换取空闲显存；standalone 模式下同模型连续请求可显式关闭，切换时仍保持最多一个模型在 GPU。失败通知默认关闭。容器另默认关闭 MDF3 指标上传。

验收必须包括：五项单独和组合请求、重复请求复用、原图尺寸/有限数组/关键点投影/视觉结果、False 和 0、空检测及错误路径，以及真实 BinaryFile/center 往返。offload 应核对参数所在设备与运行前、峰值、结束后的 CUDA allocated/reserved；只调用 empty_cache 不算显存验收。部署注册与首次完整中心返回通过后，才可声明服务可用。

## 自动构建

Hi3Dreamer 服务仓库提供 [.gitlab-ci.yml](http://172.31.0.3:8099/hi3dreamer/sapiens2-service/-/blob/d5c8f6f0acbf4705043b73fc3897940b4611cb88/.gitlab-ci.yml)、[Dockerfile](http://172.31.0.3:8099/hi3dreamer/sapiens2-service/-/blob/d5c8f6f0acbf4705043b73fc3897940b4611cb88/Dockerfile) 和 [docker_run.sh](http://172.31.0.3:8099/hi3dreamer/sapiens2-service/-/blob/d5c8f6f0acbf4705043b73fc3897940b4611cb88/docker_run.sh)。使用 inference-service-rf runner 和区域镜像仓库；先构建 test target 执行单元测试、真实 SDK 构造签名/二进制往返、配置打包检查，再推送 runtime target 的完整 commit SHA 标签。MR 验证不发布。新建项目须绑定可用的对应 runner；流水线排队、测试通过、镜像发布与 GPU 服务上线分别验收。

Docker 使用 Python 3.12、Torch 2.7.1 / torchvision 0.22.1 CUDA 12.8 wheels；SDK 从固定 3.2.4 gitlink 打包，提取官方打包元数据和运行模块，不执行 SDK 上传入口。构建不加载业务权重，也不包含环境 YAML 或凭据。容器运行时挂载模型配置、MDF 配置和权重目录，只开放选定 GPU，使用 host 网络连接 arbiter。完整环境变量和构建命令见 Hi3Dreamer 服务仓库 README。
