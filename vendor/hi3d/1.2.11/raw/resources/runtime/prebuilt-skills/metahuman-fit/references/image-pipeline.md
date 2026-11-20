# 图片 / 人头 GLB → 正面彩图 → MetaHuman 几何资产

默认先按 [正面无表情彩图](color-reference-prompt.md) 编辑输入，再用本页 `image` 入口生成 quality 几何与纹理并注册/bake。用户新传入人头 GLB 时先按下节渲染＋图生图，再走 `image` 入口；`high_glb` 仅用于本次 quality 产物恢复，或用户明确要求直接拟合现成高模时使用；quality 返回后直接对同一高模注册、微调，再在本地 Blender bake 颜色与法线；不额外调用 texture、bake、四视图上色或 UV 服务。默认不导出 DNA、不做绑定。独立头发仅在明确请求时使用 [双参考扩展](separated-pipeline.md)。

## 人头 GLB 的图像预处理

1. 在 Blender 导入用户 GLB，先检查真实正面方向、材质、头部对象和遮挡。保留源 GLB，使用任务目录中的场景副本；多部件头部可共同渲染，不把输入阶段强行当成单个皮肤对象。
2. 渲染一张清晰的正面参考图，保留原有颜色与可辨认的脸部结构，完整包含头、耳、下巴和颈部；适度留白，避免透视夸张。无贴图时用中性材质忠实展示几何，不捏造源贴图。必要时补侧面/斜面参考，执行者查看后再生图。
3. 使用宿主 imagegen，按 [彩色参考提示词](color-reference-prompt.md) 将渲染图转成光头、正面、无表情、带肤色纹理的头模图；去除头发/眼镜/胡须/假睫毛及肩胸，保持身份。缺失纹理的生成颜色注明推定。
4. 验收后将图片路径作为 `image_pipeline.py` 的 `image`，重新生成 Hi3D quality。此后 Sapiens2 反投影、注册和本地 bake 都绑定新 quality 高模，不复用输入 GLB 的顶点索引、相机或旧目标标注。

GLB 渲染和宿主 imagegen 由执行者编排；`image_pipeline.py` 自身不调用 imagegen。保存输入 GLB 哈希、渲染相机/图片及生图结果，分别记录 render/image 阶段耗时，恢复时复用已验收图片。不得直接把用户新传 GLB 填入 `high_glb` 来绕过此流程。

## 入口与依赖

`scripts/image_pipeline.py` 显式组合独立 `hi3d-api` 工具与本包注册器。调用方安装完整工具包，并提供其 `scripts/hi3d_api.py` 的绝对路径；协议、鉴权、任务恢复与下载只由该工具负责。工具不需要被宿主提前加载，也不能只复制入口脚本。Python/Blender/模板和可选 DNA 运行库见 [注册配置](inputs.md)。

用户请求按完整流程处理图片或人头 GLB 时，包含渲染/图生图和 quality 生成；维护/测试使用 dry-run 和模拟客户端，不调用收费接口。实际鉴权进程内部使用 `HI3D_AK`、`HI3D_SK`，不输出、读取排查或持久化真实值。不要把凭据或签名下载链接加入配置。

```json
{
  "image": "/assets/bald-neutral.png",
  "hi3d_api_script": "/tools/hi3d-api/scripts/hi3d_api.py",
  "output": "/work/image-head",
  "annotations": "/work/source-annotations.json",
  "sample_count": 100000,
  "surface_smooth_fraction": 0.006,
  "registration": {
    "hair_state": "bald",
    "target_parts": "skin",
    "blender": "/apps/blender",
    "texture_size": 2048
  }
}
```

```bash
python /skill/metahuman-fit/scripts/image_pipeline.py /work/pipeline.json --dry-run
python /skill/metahuman-fit/scripts/image_pipeline.py /work/pipeline.json
```

仅恢复已验收的 quality 高模或用户明确要求跳过预处理时，将 `image` 换成 `high_glb`，两者必须且只能提供一个；此时无需 `hi3d_api_script`。`source_object` 可指定导入后的皮肤对象名；多网格输入不能猜选。`registration` 复用注册配置的可选项，包括模板耳眼、牙齿贴图、DNA 和表情测试。`target/settings/source_scene/source_object/output` 由管线内部生成，不应作为外部中间件提供。

未提供模板时自动使用 [随包 Taro 资源](bundled-template.md)，显式模板和贴图优先。模板与 Blender 文件在提交前检查；生成后的模型仍必须人工或通过外部语义模块确认符合光头、皮肤和 neutral 声明。只有多对象分离已完成或源本身为单个皮肤对象时才能继续；语义分割网络没有内置。模板贴图应匹配 UV；需要口腔/耳/颈等模板回填时必须提供它。

## 固定生成配置

| API 字段 | 值 |
| --- | --- |
| `model` | `hi3dv3.0` |
| `resolution` | `2048quality` |
| `request_type` | `3`（几何与纹理） |
| `face` | `5000000` |
| `format` | `2`（GLB） |
| `pbr` | `1` |
| `shading` | `0.5` |

字段按官方 [API 概览](https://docs.hi3d.ai/zh/api/api-reference/overview)、[创建任务](https://docs.hi3d.ai/zh/api/api-reference/list/create-task) 与 [查询任务](https://docs.hi3d.ai/zh/api/api-reference/list/query-task) 的对应定义设置。quality 与 master 为不同档位；不能为增加面数改用 master。请求面数与实际生成面数分开报告，实际值在 `source/source_report.json`。

上表只作预选。正式提交前先 dry-run；把 `consent.user_interaction` 交给宿主 [参数面板](../../hi3d/SKILL.md#参数面板)。参数齐后再同样计划提交。可选 `hi3d_session` 只回写已选参数，不进入 job 指纹。

`hi3d_python` 可指定工具解释器，默认当前 Python。单次 `poll_seconds` 默认 45，允许 5–50；任务未完成时退出 3、`status=waiting_generation`，按原配置再次运行继续。生成可能长于一个轮询窗口；执行者按窗口继续调用直到成功、明确失败或需用户操作，不把一次 pending 当最终交付。`hi3d_job.json` 保存原任务 ID；工具在同一文件核对请求指纹并复用，禁止删文件后重提。提交结果不确定时由工具的恢复命令接管原任务。下载内容校验后缓存，多个 GLB 时必须设置 `artifact_name` 精确选择文件名。

## 高模准备与标注交接

按表面积确定性采样（`sample_count` 1000–1000000，默认 100000；`sample_seed` 默认 0），保存三角/源面/三顶点索引及重心坐标。导入后的对象变换应用到网格；`Source_High.blend` 是标注与烘焙的共同坐标依据。不要将 GLB 原始局部坐标直接当作 Blender 世界坐标。

拟合点云以法线相容的局部平面做一次有界投影，`surface_smooth_fraction` 为头部最大尺寸比例，默认 0.006、允许 0–0.03，0 关闭。不生成中间低模，不改变烘焙高模。此分支忽略 `target_smooth_iterations`（它仅适用于旧 quad 目标）。更细皱纹进入法线贴图；保留脸型仍依赖正确语义约束和视觉检查。

准备完成写 `annotation_request.json`，列出源文件/模板哈希、场景、采样目标与坐标契约。没有 `annotations` 文件时退出 3、`status=waiting_annotations`，不会运行无约束注册。外部模块生成 [源绑定注释](annotations.md) 后以相同配置继续；上游生成、导入和采样按哈希复用。当前不调用未定义的预测 endpoint。

## 交付与计时

下述是脚本通用契约，DNA 在 API 中可选且默认省略；按 [完整交付清单](head-workflow.md#交付验收) 补交原 Hi3D 高模及真实拓扑/布线图。

`source/` 保存完整高模场景、采样与实际面数；`registration/` 保存拟合、检查、bake、GLB 回读及可选 DNA/表情结果。通过几何检查后才复制到 `delivery/`；失败保留候选在 registration，返回 `geometry_failed`，不发布为成功。

交付 manifest 核对顶点数量、完整 quad 与 UV 数组，并记录模板/目标哈希、每个文件的 SHA-256、相对路径与纹理映射。以最新父级 summary 的成功状态和 manifest 文件列表为准；失败后的目录可能仍保留前次交付，停用的可选分支也不删除旧文件，但不加入新清单。OBJ 使用原 DNA 坐标，NPZ 同时提供目标坐标和变换；OBJ 的 UV 可配合交付贴图使用，查看完整材质装配用 GLB。配置模板皮肤时 `MetaHuman_Albedo_Fused.png` / `MetaHuman_Normal_Fused.png` 为最终头部贴图，否则使用无 `_Fused` 版本；normal 为 OpenGL +Y 切线法线。原始 bake 和辅助 mask 保留以便追查。提供 DNA 与附件 atlas 时，眼睛和牙齿贴图也另存 PNG。GLB 是静态检查资产，不能称为 UE auto-rig 成果。

可视化四列为原高模颜色、原高模几何、MetaHuman 几何、烘焙效果，各三视图。内部 `lowpoly_*` 帧名为旧入口兼容名；点云输入时实际渲染完整源高模，标题为 Source geometry。

父级 `timings.jsonl` 追加 generation、source、surface、annotations、registration、delivery 阶段的任务/尝试 ID、UTC 起止、单调耗时和状态，`workflow.json` 保存内容缓存。失败、中断、跳过的语义继承 [阶段统计](implementation.md)。`summary.json` 是本次调用墙钟；registration 包含子流程全部时间，不能再次相加。跨轮询的远端生成与标注等待可能跨多次调用，报告应单独说明外部等待，不能把单次本地处理时间称为图像端到端时间。token 未采集则省略。
