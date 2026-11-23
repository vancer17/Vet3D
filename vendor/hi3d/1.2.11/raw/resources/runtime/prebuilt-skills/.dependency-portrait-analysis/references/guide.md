# Sapiens2 人像分析契约

用于已有 GLB 的面部分割、关键点和预测法线。可独立运行；不要求先生成新模型。服务传输复用独立 mdf-call，不重复客户端。

## 输入图像怎么选

| 任务 | 本流程的输入要求 | 验收重点 |
| --- | --- | --- |
| pose：眼唇关键点 | **必须用带纹理的高模渲染**；不要用灰模关键点驱动 fitting | 眼角、眼睑与唇线是否落在实际结构上，置信度及人物数量 |
| seg：部位分割 | 可尝试灰模，也可与 pose 共用带纹理图 | 皮肤/头发边界、脸部/耳部、背景和漏分；不提供眼球细分 |
| normal：预测法线 | 可尝试灰模，保留柔和受光以表达体积 | 有限值、前景、方向、阴影造成的伪结构 |

“pose 必须带纹理”是本项目的人像注册使用约束，源于实际灰模定位失败；不是声称 Sapiens2 在所有灰图上都无法输出关键点。seg/normal 可用灰模是当前观察，不保证所有灰模都可靠，本 skill尚未做系统灰/纹理 normal 对照评测。不能因为服务成功就默认质量通过。

没有纹理时可以先做 seg/normal；关键点阶段应获取当前几何的可靠纹理渲染，或接收经验证的同源标注，不自动降置信阈值凑数，也不拿生成参考图上的点冒充 GLB 上的点。

## 从 GLB 准备渲染

配置 JSON 提供绝对路径 source、全新 output；可选 source_object（多对象时明确指定）、source_has_hair（需要头发遮挡检查时为 true）、sample_count（1000–1000000，默认 150000）。render_mode 支持 textured（默认）和 gray。脚本为既定正面相机适配器，输入须已确认朝向；任意角度需另行保存真实相机与同源投影数据。

```bash
"$BLENDER" --background --factory-startup --python-exit-code 1 \
  --python "$SKILL_DIR/scripts/prepare_sapiens_registration.py" -- "$RUN_DIR/render-config.json"
```

textured 模式保留导入材质的 base color，以低高光方式渲染，并在检测副本中断开 normal/bump 输入；不改原 GLB。它不会凭空生成缺失纹理：必须看 front.png，确认眼唇颜色与边缘实际存在。gray 模式使用统一灰色 Workbench 材质。

同一 GLB 的两种模式各用新 output。保持正交相机、分辨率、构图及 source_object 一致，检查两份 camera.json 的矩阵/ortho_scale。保存 source/image SHA、render_mode、surface_raw.npz 和可见性。姿态或裁切改变时必须重做对应投影，不只改图片路径。

## 请求

已裁好的人头，推荐一次带纹理请求 pose+seg：

```json
{"image":{"$file":"/absolute/render/front.png"},"tasks":["pose","seg"],"detect_persons":false,"offload_cpu":true,"visualize":true}
```

灰模 seg+normal 请求：

```json
{"image":{"$file":"/absolute/gray/front.png"},"tasks":["seg","normal"],"offload_cpu":true,"visualize":true}
```

task 和 tasks 互斥；只有包含 pose 时才传 detect_persons、bboxes 等 pose 专用字段。按需可用单项 task=seg 或 task=normal，避免默认 all。

```bash
"$PYTHON" "$MDF_TOOL/scripts/mdf_call.py" --service sapiens2 \
  --endpoint "$ENDPOINT" --input "$RUN_DIR/request.json" \
  --run-dir "$RUN_DIR/service" --environment test
```

ENDPOINT 来自当前部署；不硬编码 worker 地址。仅在现有授权范围内调用服务，超时先检查原任务。维护验证用离线文件，不为了验证文档重提服务。

## 输出与几何交接

- pose：keypoints[N,308,2]、scores[N,308]、bboxes[N,4]，坐标是输入编码栅格的 xy 像素。N=0 表示无检测，不能当成功定位。若需模板注册，使用 [landmark-project](../../.dependency-landmark-project/REFERENCE.md) 对应模板的映射，不把 308 索引直接当模板顶点。
- seg：labels[H,W]，按返回 metadata 的 class_names 核对标签；当前人体标签约定皮肤为 3。当前 29 类人体分割没有独立的眼球、瞳孔或虹膜标签；眼镜不是眼球。换成纹理图不可能增加标签类别，不能用脸部标签冒充全眼球 mask。以当前服务 metadata 和 [服务契约](../../.dependency-service-select/references/mdf/sapiens2.md) 为准。
- normal：normals[H,W,3]，为预测相机空间法线。不是切线 normal map，也不是当前 GLB 的精确几何法线；用于 3D 前须明确坐标变换，必要时重新单位化。预览颜色不作为法线数据。
- 原始 NPZ 用 allow_pickle=False 读取。H/W 对应输入栅格，预览 PNG 可能缩小，不用于坐标投影。服务不按 EXIF 自动旋转，事先规范图像方向。

请求前保存 service_binding.json 的 image_sha256，绑定实际输入。注册适配器按 [执行契约](../../.dependency-face-fit/references/guide.md#注册步骤) 核对模型、相机和服务结果，再 raycast 到源模型。3D 接口的 Blender 坐标为 Z-up/-Y-front，GLB 为 Y-up/+Z-front，禁止直接混用。

灰模分割与纹理关键点可以来自不同请求，但必须保持同一网格版本、相机与像素空间，分别保留各自图像绑定。**face-fit 的 prepare_sapiens_settings.py 默认消费同一次 pose+seg 结果**；若没有显式编写并验证合并适配器，优先直接使用纹理图的 pose+seg，不能替换文件、重写哈希伪装成同一次调用。

生成 3D mask/权重时需要深度可见性和遮挡检查；二维腐蚀/羽化不能替代 raycast，否则会选中后脑。修复鼻子改变拓扑后，旧顶点权重不可直接沿用，应重新投影/分割或验证转移。

## 完成与统计

交付输入渲染、相机/来源绑定、原始 NPZ、可视化叠图、质量判断；请求三维交接时另交付投射后的关键点或 mask。pose 不合格时暂停 fitting，seg 不合格时暂停依赖它的局部去噪；normal 不合格时不作为修复依据。

按 [阶段记录约定](../../.dependency-run-tools/references/stage-records.md) 保存渲染、请求/等待、保存检查、3D 投射与视觉验收的起止/状态/秒数。渲染器自动计时，服务调用和人工判断阶段由执行者记录；服务内部耗时与本地墙钟区分，不重复累加。token 无数据时不估算。图像选择和输出验收由 agent 判断，推理调用、投射与数组处理由代码完成。
