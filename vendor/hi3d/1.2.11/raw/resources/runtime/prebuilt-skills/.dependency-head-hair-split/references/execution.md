# 执行、算法与恢复

变量均指实际绝对路径：WORKFLOW 为完整物化包中本入口，RUN 为包外任务目录，
SOURCE 为原带纹理 GLB，API 为独立物化的公共 Hi3D 工具包，BLENDER 为实际可执行文件。
安装 requirements 后查看 `python "$WORKFLOW/scripts/workflow.py" --help`。

## 渲染与图像交接

```sh
python "$WORKFLOW/scripts/workflow.py" prepare --mesh "$SOURCE" --run-dir "$RUN" --blender "$BLENDER"
```

输出 01_front_render/front.png、camera.json、prompt.txt。相机位于 Blender -Y（GLB +Z），
正交取景、三盏宽光；渲染 alpha 合成到白背景。必须先看实际渲染，不能靠模型文件名判断正面。
宿主读取 front.png 后用原生图像编辑及 label-prompt.txt，保存实际生成的标签 PNG。
不要重绘几何或给头发添加轮廓线；背景虽同为白色，但后续只采样表面 UV，不参与标签统计。

## 独立贴图

先读取独立 [Hi3D 调用与恢复](../../hi3d/references/calling.md)
和 [参数契约](../../hi3d/references/parameters.md)。
`request_type=2` 是现有 GLB 贴纹理，不是拆件服务；本流程不用 Hi3D 生成标签参考图。
以下配置为已跑通的起点，不保证所有发型最佳：

```sh
python "$WORKFLOW/scripts/workflow.py" plan --mesh "$SOURCE" --label-image "$LABEL_PNG" --run-dir "$RUN" --api-dir "$API" --job "$RUN/texture-job.json"
python "$WORKFLOW/scripts/workflow.py" submit --mesh "$SOURCE" --label-image "$LABEL_PNG" --run-dir "$RUN" --api-dir "$API" --job "$RUN/texture-job.json"
python "$WORKFLOW/scripts/workflow.py" wait --run-dir "$RUN" --api-dir "$API" --job "$RUN/texture-job.json"
python "$WORKFLOW/scripts/workflow.py" download --run-dir "$RUN" --api-dir "$API" --job "$RUN/texture-job.json" --output "$RUN/texture-result"
```

CLI 固定本分支 request_type=2、hi3dv3.0、pbr=0、shading=1、glb，可选 quality/master。
鉴权仅由已授权独立 API 进程内部消费 HI3D_AK/HI3D_SK；不读取其值或配置文件。
`submit` 与 plan 使用同一参数，去掉 `--dry-run`。dry-run 的 `consent.user_interaction` 交给宿主 preference 面板，参数齐后再提交。
pending 时继续原 job；attention/未知提交不能换目录重发。历史 job 可通过显式 --job 原样接管；
只有旧格式不兼容且已知完整 task ID 时，依照工具 adopt 创建恢复记录，保留原账本。
源码变动只使本地缓存失效，不表示远端需要再生成。
局部成功会生成包外 tool_result.json，采用 pcg.tool_result.v1 槽位短回写；
宿主据此登记新产物并投影，缓存复用只回写 skipped，不重复追加 traces。
API 命令保留独立工具的状态输出；宿主确认下载成功后登记 texture 槽，
不能把 pending 的退出 0 当作贴图完成。
账号 Runtime 用宿主已提供的接口完成相同贴图交接；本 CLI 不接收 Runtime 账本。

## 必交付的交互 HTML（默认出口）

```sh
python "$WORKFLOW/scripts/workflow.py" html --mesh "$SOURCE" --label-mesh "$LABEL_GLB" --run-dir "$RUN"
```

生成 `03_interactive/result/head-hair-split.html` 和 `manifest.json`。页面含模型、连续标签亮度、原漫反射图、双色 WebGL 预览、右侧头/发显隐、阈值滑块、Worker 图割及静态双对象 FBX 导出。`--threshold` 只设置初始预览值；默认 Otsu，不是用户确认。该命令不调用 maxflow，也不生成分件。`tool_result` 返回 html/manifest 槽位并停在 handoff。

**宿主必须给出 HTML 链接并主动打开，再结束本轮等待用户操作。** 有总览页时同时加“头发/头部分割”入口，点击进入独立标签页；最终回复仍直接提供 HTML，不让用户再追问。可用宿主文件/浏览器打开能力；打开失败仍给可下载文件并如实说明。用户自己调整滑块、点击“执行 mincut”和“下载带纹理 FBX”；agent 不为验收代点真实任务按钮，不自行决定最终阈值。缓存命中也要定位并交付同一个实际 HTML，不能因 skipped 漏掉交付。

`build_html.prepare` 复用 label_texture 的连续亮度、apply_labels 的一一面映射及 graphcut.prepare_graph 的邻接/凹边权/壳规则，不维护第二份 Python 图预处理。按源 mesh 的实际材质引用提取纹理与 UV，解析单实例父链变换，法线用逆转置，镜像变换修正显示/导出绕序。最终 GLB 源文件不改动。

浏览器 `cut.js` 保留独立运行环境的整数 Dinic，并用离线逐面 parity 验证与 Python 规则一致；`worker.js` 只在按钮点击后求解/导出。预览是双色、不显示标签纹理；源纹理只用于下载。改阈值会清除上次结果并禁用下载，取消/300 秒超时终止 Worker，无自动重试。`fbx.js` 只输出静态 Head/Hair、UV、法线及原 PNG/JPEG 漫反射/颜色因子；不包含完整 PBR，不封口、不补头皮。错误要报告，不回退为静默代切割。

## 明确代执行时的分割与无损回写

仅当用户明确要求 agent 代执行并指定/确认阈值才运行以下命令；“继续流程”、Otsu、滑块初始值或生成 HTML 成功均不构成授权。未确认时必须停在上面的 HTML 交付。`--confirmed-cut` 是执行者对已有真实答复的声明，不能自行添加以绕过等待。

```sh
python "$WORKFLOW/scripts/workflow.py" split --mesh "$SOURCE" --label-mesh "$LABEL_GLB" --run-dir "$RUN" --threshold 0.5 --confirmed-cut
```

阈值必须来自本次用户确认，示例 0.5 不是默认授权；可指定 `--tolerance 1e-6`（源包围盒对角线比例）。
输出 04_split/result 下 labels.npy、graphcut.json、parts/report.json、
parts/source_face_labels.npy 及 head_textured.glb、hair_textured.glb、head_hair_textured.glb。
白标签=1（头发）、黑标签=0（其他）；两类须非空，每个原面恰好归属一次。

- label_texture.sample：每三角面 7 个内部重心样本，双线性采样 base-color，按 RGB 亮度和
  baseColorFactor 求值；glTF UV 向下，不额外翻转 V。面积加权 Otsu 给初始二值标签。
  支持 repeat/clamp/mirrored repeat，不采样材质光照。拒绝无纹理、非有限 UV、退化面、单类标签。
- graphcut.solve：仅为邻接焊接完全重合位置；面作节点，以 6 轮平滑面法线的凹曲率和边长给
  对偶边权。白侧 .005、黑侧 .12 对角线的带宽之外是固定种子；带内弱数据项保留原分类。
  scipy Dinic 求整数容量 s-t cut，校验流量等于切割容量。主壳保留每类最大连通区域，
  小壳按可见性多数标签或隐藏时周边表面标签处理；48 射线检查有预算保护，始终不删除面。
  非流形焊接边拒绝。离散采样和连通整理不是精确语义证明，眉耳仍需看图。
- apply_labels.transfer_labels：先精确顶点/面索引，再同序三角角点，最后一一对应的面心检索
  加面积/法线/角点验证。几何变化超容差、面数改变、映射多对一时拒绝。
  不要求服务 UV 不变，因为最终使用原网格的 UV。
- partition：复用 glb-clips.read_glb 做容器校验；保留原 BIN 全字节，
  只追加两个面索引集合和子 mesh 节点。静态单实例限制保证不漏场景实例；
  原材质及图像数据保留，导出可能带未使用顶点和贴图区域，以无损为优先。
- apply_labels.run：独立重读最终三个文件，核对所有面集合、原始二进制前缀、材质及变换；
  只在全部通过后写 report.json，不以保存成功代替验收。

## 缓存、失败及预算

workflow.fingerprint 绑定各阶段实际输入、参数、业务及共享源码；complete.json 绑定产物哈希。
prepare 还绑定 Blender 可执行文件与提示词；html 绑定实际模板、全部 JS、Three.js/OrbitControls 和许可证。任一变化或缺文件就拒绝旧缓存，不覆盖修复。
同源缓存通过时记 skipped，图割新版可指定新 RUN 和已有 LABEL_GLB；不要求重新生成标签。
失败目录保留日志，未完成标记不复用。源素材可位于 RUN 的其他位置，但不能位于待写阶段目录。
API job/output 也不得指向包或输入文件；调用时使用独立任务路径。
只通过 workflow 启动实际重计算，worker/core 不单独提供预算。

默认单阶段 300 秒；中高档例如 `--max-seconds 900 --confirm-budget`，仅在真实用户选择后使用。
超时退出 3、计时 interrupted；不自动加时，未完成输出不纳入交付。
本地预算与心跳使用 [run-tools](../../.dependency-run-tools/references/budget-run.md)，
无新产物不能作为远端任务失败依据。硬退出可能只剩 running，恢复时依统一统计约定追加 interrupted，
保持未知起止为 null；不伪造耗时。

## 视觉交付与验证边界

默认先完成 HTML 可用性检查与交付，不要求 agent 预先求解切割。以下分件验收仅用于明确代执行或用户已经提交的处理结果：在同一世界尺度下渲染正、背、左右的原纹理组合及单独头/发，检查眉耳没有跑到发组、
发际线没有明显漏切、隐藏小壳未被误删。报告实际所看的视图；当前结果沿原三角边开口，
不补隐藏头皮也不封闭切口。修改阈值默认交由用户在页面处理；仅有新确认时才重跑本地 split。
测试使用合成静态 GLB 和模拟 API；已有真实输入可离线复用，但维护不加载密钥或重复收费。
本地包调用、线上服务、视觉验收、宿主自动发现为四个不同验证范围。
