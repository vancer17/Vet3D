# API 原子能力

公开 Hi3D API 与内网 MDF 是不同的入口、鉴权和任务生命周期。MDF 的 service_name、BinaryFile、MDF 数组容器不能直接交给 Hi3D 创建接口；API 的 model/resolution/format 也不能原样当 MDF 参数。

## Hi3D：由独立 hi3d-api 调用

以下描述本仓库客户端支持的契约；完整兼容矩阵和参数校验以独立 `hi3d-api/references/parameters.md`、`defaults.json` 为准，调用命令见[调用说明](calling.md)。服务输出的真实文件由 query/download 获取，创建请求只返回 task ID。

| 原子 | 必要输入、关键参数 | 输出与效果 |
| --- | --- | --- |
| 单图几何 | submit model；一张 PNG/JPG/JPEG/WebP；request_type=1；model 与 resolution 兼容组合 | 由可见轮廓推断完整 3D，输出指定格式模型；隐藏面不是实测结构 |
| 多视图几何 | submit model；1–4 张图及唯一 views 标签，必须有 front；request_type=1 | 多视图共同约束模型；客户端重排 front/back/left/right，不能沿用 Geo 中控的列表顺序 |
| 独立贴纹理 | submit model；现有 GLB + 参考图；request_type=2，支持该模式的版本；可选 pbr/shading | 带纹理模型；已有几何是否完全不变仍需前后检查，不能仅按功能名承诺 |
| 几何与纹理串联 | submit model；参考图，request_type=3 | 一次异步任务交付带纹理模型；不能单独查看全部 MDF 中间阶段 |
| 图片浮雕 | submit relief；单图或 image_url；model_type=base/pro；height_relief、rmbg、width、sculpmode、format | 深度图或浮雕模型，适合平面图案起伏；不是完整背面重建 |
| 模型拆件 | submit split；GLB/STL/OBJ 或 mesh_url；model=character/general | 拆分后的模型产物；部件、切缝和连接结构需检查，不能据成功状态认定可装配 |
| 模型多色 | submit multicolor；带纹理 GLB；number_color=0..8，model=multicolor | 受限颜色表达；颜色数不等于独立对象数、零件数或打印材料数 |

图像每张 ≤20 MiB；拆件/多色 mesh ≤200 MiB。单图 URL 只在当前客户端对应模式允许时使用，不能把 URL 当多视图数组。输入来源、上传范围和收费任务沿用用户授权，生成前先本地 dry-run。

## 参数会怎样改变结果

- 建模 model/resolution 表示模型版本与服务档位，不是可随意填的像素尺寸；请求 face 是目标面数，不是精确最终面数。hi3dv3.0 支持 2048quality/2048master；其他版本须查独立工具矩阵，不按名称类推。
- 建模格式码为 obj=1、glb=2、stl=3、fbx=4、usdz=5、3mf=6。浮雕是另一张表：exr=1、png=2、stl=3、glb=4、3mf=5、bmp=6；优先传格式名称避免串用数字。
- 浮雕 width 为 20–600 mm；height_relief 为 0.1–50，当前文档没有确认其单位，不能直接标成毫米。rmbg=0 时可用 square/circle 底座及 thickness_base=0.1–20 mm；rmbg=1 改用 degree_rmbg=0..1。sculpmode=0 为凸雕、1 为阴雕。
- character 拆件采用 part=a..f 模板、joint=none/ball/dovetail/pin；有连接时 merge=yes/no，无连接时不传 merge。general 用 level=low/medium/high，不能混用角色模板参数。具体部位组合以服务示意为依据，不能从字母猜人体分区。
- 多色 0 是服务 max 模式，不能宣称固定为 8 或无限；支持 obj/glb/fbx/3mf，STL/USDZ 不是该客户端有效输出。

## 网络与恢复

客户端固定源为 `https://api.hitem3d.ai`。创建接口：`/open-api/v1/submit-task`、`/depth/create-task`、`/split/create-task`、`/muilticolor/create-task`（后三个同属 `/open-api/v1`；多色创建拼写是 muilticolor）。查询使用各自 query-task，多色查询路径拼写为 multicolor。JSON code=200 与有效 task_id 都需要检查。

AK/SK 只由已授权鉴权进程内部消费大写 `HI3D_AK`、`HI3D_SK`；AI 不读取值、不搜索凭据文件，不复制来源项目中的内嵌凭据或回退配置。鉴权 token 不落盘。完整 task ID 原样保留，job 重复执行复用原记录；创建结果不明先恢复原任务，不能自动重提。balance 是只读状态查询，返回 totalBalance/unit；不据此推算单任务价格。

官方契约：[建模创建](https://docs.hi3d.ai/zh/api/api-reference/list/create-task)、[任务查询](https://docs.hi3d.ai/zh/api/api-reference/list/query-task)、[浮雕](https://docs.hi3d.ai/zh/api/api-reference/list/depth-create-task)、[拆件](https://docs.hi3d.ai/zh/api/api-reference/list/split-create-task)、[多色](https://docs.hi3d.ai/zh/api/api-reference/list/multicolor-create-task)。官方页面与客户端允许范围不一致时先调整契约/预检，不通过重复收费提交试参数。

## Geo 项目中的其他图像 API

Geo 的 standard/full 灰模预处理还可使用外部图像 API；它们不是 MDF 服务，也不由 `hi3d-api` 客户端调用。以下为 Geo 提交 63dbc6cb 的调用形状，使用时需独立提供相应官方 SDK、当前账户授权和任务恢复能力；本包不复制原项目客户端或内嵌密钥。

| API | 源码中的输入与返回 | 用途与交接 |
| --- | --- | --- |
| fal `openai/gpt-image-2/edit` | 上传显式图片后，arguments 为 prompt、image_urls、image_size={width,height}、quality；返回 images[0].url 和提交时的 request_id | 以提示词重解释为灰模图，下载并检查后重新获取 alpha；不是灰度滤镜 |
| 腾讯 VOD OG | CreateAigcImageTask：SubAppId、ModelName=OG、ModelVersion=image2_low/medium/high、Prompt、FileInfos=[{FileId}]、EnhancePrompt=Disabled、OutputConfig={AspectRatio,Resolution}、InputRegion；源调用另传 ExtInfo 中 size；返回 TaskId/RequestId，查询同一任务取结果 | 同类灰图预处理；宽高需满足该模型要求，源适配器要求 16 的倍数并校验像素数 |

调用方 prompt 有实质差异：standard 可去除平面印刷纹样而保留实体结构，full 提示词会把文字/标记转为可读刻痕或浮雕；这会影响后续几何。应根据用户是否希望文字成为实体选择，而不是机械复用某分支提示词。源代码中的自动回退/日志策略不是本次用户授权；结果不明时先查原 request_id/TaskId，不直接换供应商生成第二份。
