# 彩色拆分 → 灰模建模 → 高模上色 → 最终拓扑烘焙

历史独立头发扩展：其中远端 texture/四视图/UV 分支不适用于当前 quality 头部流程。当前流程直接使用 quality 带纹理高模并本地 bake，禁止因补色缺陷自动进入本页服务分支；只有用户另行明确要求此历史扩展时才采用。

**仅在用户明确要求独立头发时读取本扩展。** 默认正面无表情彩色光头流程见 [head-workflow.md](head-workflow.md)，不执行本页的毛发保留分支。

本流程由执行 skill 的 AI 编排图像编辑、独立工具调用、本包注册与 Blender 装配；不是一个自动完成图像判断和绑定的黑盒脚本。`parts_generation.py` 自动负责两个几何任务的提交/恢复，`texture_pipeline.py` 自动负责单部件四视图及高模 RGB 投射。注册和皮肤烘焙复用 `image_pipeline.py` / `run.py`，头发拓扑与装配在 Blender 完成。每个阶段允许接收已验收的现成产物。

## 1. 先彩色拆分，再转灰

使用可用的 GPT 图像编辑工具；本地图片先查看，分别编辑，保存实际提示词、来源关系与版本。普通图像编辑优先宿主 imagegen，不偷偷换模型/服务。不把同一次图片编辑当作几何精确对应。

- **彩色光头**：保持人物辨识度、年龄、五官、自然不对称、表情和原 pose。只移除头皮头发与装饰品，补全合理的头皮；保留自然肤色、眼睛、原眉毛与胡须。去掉假睫毛及独立细长睫毛，头颈仅到肩颈交接，不留肩、衣服、底座。不可用模板脸替换人物脸。
- **彩色纯头发**：不仅是分割可见像素。移除人头、耳朵、颈部及全部皮肤后，**补全原先被它们遮挡的头发**：后脑内表面、耳后连接、后颈长度与内侧发束，形成完整、可装配的独立发套。原脸部开口应能看见深处的后方头发，不能挖成整块白洞；也不能用前方平面发帘填满。明确内腔深度与前后层次，保留原分缝、发际线、外轮廓、体积、长度和不对称；不生成布质假发帽、头皮或模特头。额外后视图可辅助约束，但不替代这一遮挡补全。
- **灰模副本**：分别从上述两份彩图编辑，读取 [完整灰模提示词](gray-reference-prompt.md)，先附光头/纯头发分支约束，再附通用正文。头发雕塑化必须覆盖内侧和原遮挡部分。彩图保留作最终颜色依据，不把灰图再染色来替代原彩图。

检查眼球是否仍有圆形虹膜/高光痕迹、眉须是否过厚、头发是否只是照片去色、是否有独立细丝、内腔是否缺失。失败只修相应图，不提交错误参考。原照片看不见的结构属于推定，需明确说明；不能保证真实背面完全一致。

图片阶段记录 `bald_color_front`、`hair_color_complete` 及各自 gray 对应；附加后视图按同一发套命名。每张单图独立保存，拼图仅供审核，不能整张送单图生成。灰模转换允许合并细丝，但不能改变外轮廓与发量。无头发人物跳过 hair 分支；极短发茬近乎贴合头皮，不硬造可拆发套。

## 2. 两路 quality 几何

显式安装完整 `hi3d-api` 工具并提供 `hi3d_api_script`；AI 不读凭据，授权的 API 进程内部消费 `HI3D_AK`/`HI3D_SK`。已有高模直接继续下游，不为测试或文档维护提交收费任务。

```json
{
  "output": "/task/quality",
  "hi3d_api_script": "/tools/hi3d-api/scripts/hi3d_api.py",
  "parts": {
    "bald": {"gray_views": {"front": "/task/images/bald_gray_front.png"}},
    "hair": {
      "occluded_hair_completed": true,
      "gray_views": {"front": "/task/images/hair_gray_complete.png"}
    }
  }
}
```

`occluded_hair_completed` 是执行者实际查看确认的前提，不是脚本进行了遮挡预测。若已有同一发套的独立后视灰图，加入 `gray_views.back`，不把另一发型或镜像正面放进去。`parts_generation.py` 保留 front/right/back/left 真实标签，用 Hi3D 多图入口传递，不丢后视参考。

```bash
python "$SKILL_DIR/scripts/parts_generation.py" /task/parts.json --check
# 正式执行；waiting_choice 交给宿主全局弹窗：
python "$SKILL_DIR/scripts/parts_generation.py" /task/parts.json
```

固定 quality / `hi3dv3.0` / `2048quality` / 500 万面请求，灰模路线为 `request_type=1` 只生成几何，避免先生成无用的灰材质贴图。旧 `image_pipeline.py` 单图入口保持原几何+纹理行为。新 CLI 每次有界轮询，pending 复用同一任务 ID，两个独立任务可并行，不能换目录重复提交未知状态任务。记录实际面数，不能把请求值写成测量值。

## 3. 拓扑准备与高模上色可并行

**人头**：分离眼球、牙齿/口腔，选择外部皮肤目标，使用本包 [原有高模入口](image-pipeline.md) 直接表面采样、接入本来源关键点与 mask、注册 MetaHuman。保留模板耳眼口腔、下巴腮部身份特征。只在拟合副本抑制细褶皱，原高模留作 normal 源。不能复用另一高模的顶点索引标注。

**颈部**：裁掉源高模多出的肩膀/衣服/底座，裁切线在肩颈交接的非身份区域，保护下巴和下颌。不能破坏性删除最终 MetaHuman 顶点而声称仍是原拓扑；需裁短展示时用独立展示副本/非破坏隐藏，保留完整可驱动的规范网格，并清楚区分。

**头发**：仅对独立头发制作低模。Blender 导出工作三角网格，显式提供 Instant Meshes，`-d -r 4 -p 4 -f <目标面数> -S 2 -o <quads.obj> <working.obj>`；导入后检查实际四边形、内腔、连接和发尾，展开头发自身 UV。不要套用人头眼口环线算法。工作减密副本可提速，烘焙始终用原始高模。自动四边化不等于手工顺发流布线。

两路高模独立归一化，不能直接原点重叠装配。保存每路源到共同坐标的变换，以头顶、太阳穴、耳侧与后颈对应校准。对齐/必要的局部变形同时作用于头发高低模，然后再做最终 normal bake；不得只挪低模而忘记烘焙源。

## 4. 彩图 + 对应几何 → 四视图 → 高模颜色

显式提供完整 `service-select` 的服务契约和 `mdf-call` 的 `scripts/mdf_call.py` 路径；前者给当前参数与约定，后者唯一承担网络/协议/审计。本包不复制客户端。依次调用：

1. 高模缺 UV 时 `texture-uv-unwrap-v3-0`，`need_repair=False`；UV 过程仍可能拆点，回查几何/轴向/尺度，不能用于最终 MetaHuman UV。
2. `texture-render-v3-0` 在同一高模渲染 normal/CCM/mask 和 front/right/back/left 相机。
3. `multiview-service` 用本部件**彩色参考**加上述几何控制图生成四视图。保留缺失参考的 None 槽；后视参考存在就放 back 槽。纹理路线使用 renderer 原始控制图，不套用 Geo2 bridge 的 CCM 通道变换。已具几何时不调用 pass3 重建几何。
4. `texture-bake-v3-0` 将四张彩图投射到同一高模 UV，保留 coverage/mask。这一步生成颜色，不生成几何 normal，也不能用 compose 分支冒充多视图投影。

```json
{
  "part": "hair",
  "occluded_hair_completed": true,
  "high_glb": "/task/hair_high.glb",
  "has_uv": false,
  "color_views": {"front": "/task/images/hair_color_complete.png"},
  "resolution": 2048,
  "texture_size": 4096,
  "mdf_call_script": "/tools/mdf-call/scripts/mdf_call.py",
  "output": "/task/hair_texture"
}
```

```bash
python "$SKILL_DIR/scripts/texture_pipeline.py" /task/hair_texture.json
```

光头同理 `part=bald`。`has_uv=true` 只在实际检查全部目标 primitive 的 UV 后使用。脚本输出 `texture_result.json`，状态为 `needs_visual_review`，不把服务成功当完成验收。缓存以输入内容/参数指纹区分，已有调用的歧义状态禁止自动重发。API/服务阶段日志在任务目录，不能加入 skill 包。

头发内腔若四视图看不到，检查 coverage 并补一张能看进内腔的视图，再局部投射；不要把仅外表面四视图视为完整覆盖。补视图属于显式扩展阶段，当前四视图脚本不自动执行。彩图含原照明时先按服务契约去光照或检查并修正，不能把深阴影当 albedo 黑斑。检查几何控制是否保住雕塑发束，避免颜色阶段重新画出大量细碎毛丝。

## 5. 高模 → 最终 UV，最后装配

- **皮肤**：把已上色的同一高模作为新 `source_scene`，复用注册结果，仅重跑本包 `run.py` 的受影响 bake/appearance 阶段。若 UV 服务重排高模索引，重新绑定源对象与排除区；注册的语义目标与上色的源几何需验证一致，不能沿用失配索引。`review.py:bake_skin` 将高模 DIFFUSE color-only 与几何 tangent normal 分别烘到规范 MetaHuman UV，保留模板耳、眼球、内唇和口腔，必要时做肤色匹配与泊松融合。
- **头发**：Blender selected-to-active 从上色高模向低模 UV 分别烘 Albedo 与 Normal；只选该部件，按实际尺寸确定 cage/ray distance，检查内外表面串投。DIFFUSE 仅 color、不烘直接/间接灯光；Normal 为 OpenGL +Y tangent、Non-Color，交付 16-bit PNG。使用高模表面几何法线，不把四视图控制 normal 贴在 UV 上。
- **装配**：在共同坐标装配独立头发，保留人头规范顶点顺序、四边形、UV、morph 和眼口材质。不能为了塞头发扩大腮部或缩掉下巴。修发际线/内腔交叉、耳侧与后颈缝隙；头发跟随 head joint，不能把脸部表情位移全量套到头发。

只交付通过检查的版本：原图同相机渲染、真实四边形灰模、至少两个表情、后侧/内腔视图、albedo 与 normal。GLB 导出后回读贴图和形态键；Blender 保留可编辑四边形。正面姿态不匹配、眼皮穿球、口腔丢材质、背面缺发/内侧空洞均不能标记视觉通过。

## 耗时与恢复

每个任务交付阶段记录：彩色拆分/遮挡补全、灰模转换、两路 quality、头部注册、头发 lowpoly/UV、各路高模四视图及投射、最终 albedo/normal bake、装配与可视化。用本包 `Journal` 记录脚本阶段到任务 `timings.jsonl`；GPT 编辑及手动 Blender 阶段由执行者记录任务/尝试、带时区起止、单调耗时及状态。未执行标为 skipped，中断时间未知用 null 和原因，不伪造 0。失败/修订追加记录。

总墙钟按任务首尾区间，不能相加重叠阶段；远端计算时间与本地等待区分，父 stage 已包含子调用。只改彩图时复用 quality 与拓扑；只改 UV/分辨率时复用参考图、几何和未失效四视图；最终形状变化才重做相关几何控制和 bake。token 无实际 usage 可省略。图片、高模和运行统计留在任务目录。

已确认 Hi3D task_id 后，查询网络错误通过原 job 的 wait/query 恢复；先比对请求指纹，不再进入提交入口。提交结果不确定或请求指纹不同必须保留断点并检查，不能重新发起生成。


## 装配与投射空洞的局部修订

两个独立 quality 模型分别归一化，不能按相同包围盒或顶点中心直接装配。先固定已注册人头和原图相机，选择分缝、发际线、两侧翻卷、外轮廓和发尾的语义点，只求头发的相似变换，再看侧面、背面和头皮间隙。保存配准点、变换与像素残差；低像素误差不证明三维无穿插。相似配准后若后侧头腔仍与头皮相交，优先保持参考图的外轮廓、发量和前方刘海；局部变形必须受轮廓约束，不能靠整体撑大后脑或加宽头发消除穿出。不能把内外两层同时硬投影到同一头皮曲面，否则会压塌厚度并产生重叠。高低模应用同一变形场，再重烘受影响的法线；保留原 UV 和颜色。展示资产允许显式采用发下头皮遮挡时，可在展示网格中省略完全被头发覆盖的头皮面，必须另存完整 canonical 头模、被省略的面索引及顶点映射，并检查正侧背面与表情；不能将该展示子集宣称为完整模板或内部无穿插的实体拟合。要求完整头皮连续或严格实体装配时，此遮挡方案不满足要求。此时不重新生成模型，也不移动脸部来迁就头发。

四视图可能无法观察深发缝、内腔和 UV 边界。高模 RGB 投射后先检查 coverage mask 与渲染，不把黑色未覆盖像素烘到最终低模。小空洞或颜色连续区域可显式运行：

```bash
python "$SKILL_DIR/scripts/fill_projection.py" /task/high_texture.jpg /task/coverage_mask.png /task/high_texture_filled.png --edge-pixels 1
```

此原子脚本依赖 NumPy/OpenCV，按最近的有效 UV 像素传播颜色，保留有效颜色；边缘收缩用于去除 JPEG 黑边。输出新 PNG 与同名 JSON 计时说明，拒绝覆盖服务原始产物。将新图链接到对应高模材质，再重烘低模 albedo。填补色是推定，不能当成新增观测；UV 空白区域也参与填补，报告中的 atlas 占比不是表面覆盖率。跨岛或大面积未见区域可能颜色错误，应补充有几何约束的视角或采用已审核材质，不依赖最近邻恢复新细节。

交付前将所有新增 shape key 显式设为零，分别渲染 neutral 与单个表情；创建 shape key 后不能依赖隐式初值。颈部显示裁剪保留完整 canonical 模型、UV 和顶点映射，裁剪边界可单独整平；不能将裁剪后的子集声称为完整固定顶点数的 MetaHuman 模板。
