---
name: head-hair-split
description: 将带纹理人头与白发黑头标签模型制作成离线交互分割 HTML，必须交付并主动打开，由用户调阈值、点击 mincut 和下载带纹理 FBX；不默认代切割。支持标签准备和明确授权后的无损 GLB 分区，不补隐藏头皮。
---

# 头发与头部分割

输入已有带纹理静态人头 GLB，默认输出内嵌模型、标签亮度、代码和原漫反射贴图的交互 HTML，**必须给用户链接并主动打开，然后停止代操作**。用户在页面调阈值，点击 mincut 后下载带纹理的 Head/Hair 双对象 FBX。不能用已切好的模型、截图或普通成果页代替该 HTML；不能擅自点击页面的处理/下载按钮。

“继续整个流程”“完成头发分割”或默认阈值不是 agent 代切割授权。只有用户明确要求代执行并确认阈值，才走可选 CLI split，输出独立头发、其余头部及组合 GLB；HTML 仍须交付。只交付页面时应说明“待你在页面处理”，不能声称已完成最终 mincut/FBX 导出。
白色只指头顶头发；眉毛、睫毛、耳朵、胡须和饰品属于其余头部。
CLI GLB 分区保持原始三角面、UV、材质、纹理字节及节点变换；浏览器 FBX 的静态漫反射范围见下文。两者均不用标签贴图作为最终材质。

## 独立入口与依赖

按 [打包约定](../.dependency-package-tools/references/usage.md) 物化 [package.json](package.json)，
显式读取本文件或调用 `$head-hair-split`。运行目录必须在包外；Python 3.9+，
[requirements.txt](requirements.txt)、Blender（渲染时）及宿主图像编辑能力。
脚本不安装软件、不读取凭据文件、不复制 API 客户端。

先读 [执行和恢复](references/execution.md)、[检查点](pcg/routes.yaml)、
[实际阶段与产物](pcg/architecture.yaml)。宿主依照
[编排约定](../.dependency-pcg-view/references/host-orchestration.md) 维护会话和投影；
本包不实现 Agent 引擎，也不要求并行代理。

图像编辑优先沿用用户明确指定的宿主原生 imagegen；不因 Hi3D 能贴纹理就改用其生图。
没有图像工具时停在参考图交接；已有合格标签图或标签模型则跳过上游。
贴图阶段显式调用独立 [hi3d-api](../hi3d/SKILL.md)，传入原网格和标签参考图，
只执行贴纹理；使用实际工具目录及其鉴权、提交/恢复契约。本包 CLI 对接公共 API；
账号 Runtime 由宿主按对应工具契约交接，不混用账本，不自动切换后端。

## 阶段与出口

| 阶段 | 操作与出口证据 |
| --- | --- |
| input | 核对单 mesh/primitive、静态三角网格、嵌入贴图、真实正面和坐标；保留原件。已有标签模型直接 html，不直接 split。 |
| reference | `prepare` 用 Blender 渲染同源正面 PNG、相机 JSON 和提示词；检查正面、裁切及轮廓。 |
| label | 按 [标签提示词](references/label-prompt.txt) 编辑参考图：头发白、其余黑、背景白，保留体积光影。检查眉耳和轮廓后保存 PNG；不将阴影当真实类别。 |
| texture | `plan` 本地预检；在已有授权范围内 `submit` 一次，保存原 job，query/wait/download 恢复。出口为下载的黑白标签 GLB，而不是截图。 |
| html | `html` 严格验证逐面对应、采样连续亮度并准备图数据，生成离线交互 HTML 和来源 manifest；不运行 mincut，不生成最终分件。Otsu 仅初始化滑块，不代表用户确认。 |
| handoff | 必须在最终回复给 HTML 可点击链接并主动打开该页面，进入等待用户操作；打开失败交付文件并报告原因，不改为自动切割。用户自己调阈值、处理、下载；阈值改变会使旧结果失效。 |
| split（仅明确代执行） | 用户明确要求 agent 代切割并选定阈值后，才用 `split --threshold ... --confirmed-cut`；一一对应验证后回写原 GLB 面集合。出口为三个 GLB、标签 NPY 和报告。确认标志不是授权本身。 |
| review（按实际出口） | HTML 检查可加载、双色预览/右侧显隐/阈值控件正常即交付，不代点 mincut。明确代执行后再检查实际分件的正背左右、眉耳、发际线及漂浮壳；记录实际检查范围和阶段耗时。 |

多视图检查可显式交给 [model-preview](../.dependency-model-preview/REFERENCE.md)，
输入本轮三个原纹理 GLB 和同一坐标/相机范围，返回实际 PNG；不重新建模。
可另用 [asset-page](../.dependency-asset-page/REFERENCE.md) 汇总本轮模型、PNG 与报告，但不得代替必交付的交互 HTML，不隐含发布。

## 约束与完成条件

- 原始输入须为 Y-up、+Z 正面的 GLB；方向不符时先明确独立工作副本及映射，不能猜正面提交。
- 单个不带 skin、动画、morph、压缩扩展的索引三角 primitive；不静默合并多 mesh 或重网格。
  标签贴图要求嵌入 base-color、有效 UV、不透明，拒绝纹理坐标变换；支持正常 accessor stride。
- 阈值作用于贴图亮度，不作用于带灯光的渲染图。单正面不能证明后脑语义；背侧必须检查。
- 图割只重分配面，保留浮动/隐藏壳；不能通过删面让结果更干净。
  改变面数、坐标或无法建立一一对应时停止，不用近邻模糊转移冒充无损。
- 切口沿现有三角边；不封口、不补被头发遮住的头皮、不保证水密或可打印。
- HTML/浏览器 FBX 限单材质不透明静态网格、内嵌 PNG/JPEG 漫反射、repeat/clamp UV；完整 PBR、顶点色、透明材质、镜像重复纹理另验，遇到不支持输入应说明阻塞，不静默改材质或自动切割。GLB 分区仍保留原 BIN/材质，浏览器 FBX 不宣称无损保留全部 PBR。
- 页面要求桌面 WebGL2、Worker、Compression/DecompressionStream；所有资源内嵌，无网络请求。浏览器运算只在用户点击后启动，300 秒到点停止，可取消；不后台重试或自动加时。
- 本地 prepare/html/split 默认低档各 300 秒；复杂高模/多壳建议中档 900 秒、
  特大模型高档 1800 秒。中高档须先确认预算后 `--confirm-budget`；超时停止，
  仅在用户选择后以新目录和新预算继续，原收费任务不重提。
- CLI 自动记录其调用范围的 `timings.jsonl` 与本次 `timing_summary.json`；
  图像编辑、远端实际计算及人工视觉验收不在 CLI 耗时内。
  执行者按 [统一统计](../.dependency-run-tools/references/stage-records.md) 记录外部阶段及全任务墙钟，
  未知耗时留空，不估算 token。
- 原件与旧结果不覆盖。一个运行目录只由一个进程维护；崩溃/超时产物保留但不交付，
  未有 complete/report 不能当成功。复用以当前输入、参数、源码与输出哈希为准。

<!-- managed-by: sparc3d-runtime -->
