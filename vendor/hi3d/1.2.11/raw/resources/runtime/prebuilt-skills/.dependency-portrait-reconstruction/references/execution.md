# 执行与代码契约

`SKILL_DIR`、`RUN_DIR`、`HI3D_TOOL`、`MDF_TOOL`、`PYTHON` 和 `BLENDER` 都是调用者选定的绝对路径，不是环境凭据。Python 依赖安装到调用者自己的虚拟环境；Blender 使用自带 Python。运行前保留原模型和中间产物，每次形变使用新输出目录。

## 图像处理

文生图/图生图调用失败时停止该失败调用的自动重试并报告原因，保留原任务与已有产物；用户明确要求后才重试或恢复。调用成功但效果不佳时，按本流程和已有授权继续定向修图或重新生成，不因质量未通过新增逐轮确认或暂停整项任务；质量修订次数和最终验收门槛仍按原规则执行。正常 pending 继续查询原任务，不重提；不依赖失败结果的阶段可继续。

先读 [本阶段内置评审](image-review.md)。新参考图使用物化的 `scripts/reference_review.py` 及随包基础/头雕策略，prepare → 实际看图填完整 response → check → 真实人工确认 → 提交前重验，图像 approved 且满足下文服务视角契约才交给 quality。分数不代替硬项；H 单列 carved_flow，不能把过平的大体块判为雕刻发流合格。HTML 仅为可选静态报告，未接自动视觉服务或自动重试。评审指纹包含代码、策略、原图、所有实际输入/图片/prompt/例图及评审器版本，变化即失效，旧模型任务不随之重提。

参考图准备调用 [head-reference](../../head-reference/SKILL.md)：four-views 明确选择 aligned 转正四视图或 current 当前视角四视图。current 保留原图 yaw/pitch/roll，从自己的当前视角基准补相对视图；aligned 从自己的正面基准补标准视图。两种模式不串行，head/front 单图可独立调用。颈部范围、裁切、背景、头发造型与材料为共用参数；所有生成和修订均携带 [prompts](prompts.md) 的完整 H。只有明确复用合格图才续接并记录依赖；仅图像目标在此结束，原图保留作身份/来源依据，已验收的生成 front 留作默认纹理 condition。

接收图像版本及实际 prompt 绑定的 manifest：逐图必选头发质感检查，aligned 的转正 yaw/pitch/roll 或 current 对原图 yaw/pitch/roll 的分别保留依据，以及身份/范围/固定头姿与视角一致性。`generation_status` 与 `review_status` 分开；必需项存在 fail、uncertain 或 not_checked 时，不提交新的 quality 任务。同一问题连续两次针对性修订仍失败就交回用户选择。改图/换 prompt 后旧验收失效；恢复已有 job 时沿用原输入和任务 ID，不把修订图冒充其原始输入，历史产物可保留但必须注明来源未通过当前验收。

H 允许在图像生成/编辑中将过细发流和有发根连接的悬空刘海适度加粗，优先保留发型，不再强制删除刘海。manifest 继续使用 `unsupported_fringe` ID，按当前策略检查根部连接、细颈/薄片/尖端与各视图一致性；发梢悬空本身不判失败，真正脱离主体的碎片或仅遮住缺陷、薄膜桥接仍不通过。旧删除策略的评审不能替代新版检查，按当前策略重审但不自动重生成或重提任务。保留其余发长和主要发型，不在后续标签图中伪造这项几何改动，也不因本项选择而默认运行几何后处理。

four-views 的生成与修订另带 [配方 E](prompts.md#e-四视图耳朵位置与头发遮挡一致不要求露耳)，整组必查 `set/ear_hair_consistency`，适用 aligned/current 及所有材料。耳朵可以全部或部分被头发遮住，检查的是相对位置和遮挡关系一致，不是露耳率；不为检查拨开头发或挪动耳朵。该项须有四图证据，矛盾/漏项不能进入 quality；已遮挡且关系一致可以通过，不为露耳额外生图。

## 几何生成与服务交接

Hi3D 使用独立 hi3d-api 的 SKILL 与参数契约。当前适配器支持 `hi3dv3.0` / `2048quality`，`request_type=1` 仅几何；`request_type=2` 在现有 GLB 上生成纹理。先 dry-run，再按已有用户授权提交相同计划，后续查询/下载同一 job。面数以任务要求显式指定，不能把某个案例的面数当作默认。

视角交接是独立于图像 approved 的门槛。仓库当前公共适配器使用 front/back/left/right 语义标签，Runtime 路径也记录标准语义或槽位；本地契约尚未证明它支持带俯仰/侧倾的相对相机四视图。这不是断言线上服务绝对不支持。current 必须保留 view_0/90/180/270 与 view_frame，先交付参考图，确认服务契约并验证适配后才提交；不能仅改标签、用槽位绕开校验、静默转正或未经用户选择重生成 aligned。此维护不修改 API 客户端、不提交验证作业。

下面演示 **aligned 四视图** 的仅几何分支；用户确认的所选后处理需要纹理分析时，可按 hi3d-api 当前契约同时生成几何与分析用纹理，或复用合格同源渲染，不把灰模作为 pose 默认输入。无分析需求不必为旧默认链路生成分析纹理。最终纹理请求默认使用前面已生成并验收的 front 作为 condition，并绑定实际冻结的几何，不要求其必须经过修复或去噪。

```bash
"$PYTHON" "$HI3D_TOOL/scripts/hi3d_api.py" submit model \
  --image "$RUN_DIR/front.png" --image "$RUN_DIR/right.png" \
  --image "$RUN_DIR/back.png" --image "$RUN_DIR/left.png" \
  --views front,right,back,left --set model=hi3dv3.0 \
  --set resolution=2048quality --set request_type=1 \
  --job "$RUN_DIR/geometry-job.json" --dry-run
```

本 workflow 的 aligned 输入使用 `view_convention=screen-nose-direction-v1`，左右取鼻尖在画面中的朝向，不是相机侧别。四格与公共 API 上传对应如下：

| 四格位置 | 图片标签 / 文件 | 实际内容 | 公共 API 重排后位置（从 1 开始） |
| --- | --- | --- | --- |
| 左上 | front / front.png | 标准正面 | 1 |
| 右上 | right / right.png | 鼻尖朝画面右 | 4 |
| 左下 | back / back.png | 后脑 | 2 |
| 右下 | left / left.png | 鼻尖朝画面左 | 3 |

图片列表与 views 同序。公共工具按 front/back/left/right 重排，因此实际上传为左上→左下→右下→右上；它不识别图片内容，也不修正错误标签。提交前核对实际侧面、manifest 和 dry-run 文件顺序，不再手工反转一次。旧“相机左/右”文件不能凭旧文件名直接套用；先按 head-reference 迁移对应关系并重审，保留旧 job，不自动重新收费提交。此表不是 Runtime 数字槽位契约；账号路径的 imageSlots 另按其服务契约核对，不从公共上传序号推断。源图和四视图在提交前均须等比例 pad。

Sapiens2 请求使用本次**高模渲染**，不要把生成参考图的关键点直接当作高模坐标。当前消费的请求为 `image: {"$file": "front.png"}, tasks: ["pose", "seg"], detect_persons: false, visualize: true, offload_cpu: true`。用独立 mdf-call 按实际部署指定 `--service sapiens2 --endpoint ... --input request.json --run-dir service`；需要 NumPy。预期 `pose_data` 为 `keypoints[1,308,2]`、`scores[1,308]`，`seg_data.labels[1024,1024]`，皮肤 label=3。服务版本、标签定义或尺寸不同须适配，不假设兼容。

服务客户端负责保存/恢复 ID、脱敏与产物 manifest。无 ID 的超时不是失败重提许可。模板/本地脚本不读取任何凭据。安装依赖时提供整个工具包，而非仅拷贝一个 CLI。

## 几何后处理

这是可选操作组，不是必执行的修鼻→去噪链。**操作默认关闭，决策询问不可跳过**：凡路线进入 postprocess，宿主先询问“几何后处理默认不使用。请选择：不使用、仅修鼻、仅几何去噪、修鼻并去噪。”使用既有 waiting_choice 与本入口四个 option；默认项排在第一位不是自动提交。未收到明确答复时停在 postprocess，不启动相关分析/注册/修复/去噪，也不越过 freeze 继续纹理。超时、空答、仅说继续全流程均不是“不使用”的确认。

本任务同一输入已有明确的后处理答复时可直接沿用，记录实际答复及其绑定的输入路径/哈希、两项开关；明确要求“仅修鼻”或“仅去噪”本身就是选择，不再重复问同一问题。更换输入或选择不明确时重新询问；不能把上个任务的偏好、默认 false 或旧路线经过 denoise 当成答复。仅图像、仅几何交付与 split_only 不经过此门，不额外运行后处理。

用户确认不使用后直接引用原高模；确认仅一项时另一项记为用户选择跳过。只有选择去噪才准备权重并运行 `denoise_semantic_face.py`，不通过零轮导出代替跳过。仅去噪不需要 face-fit 或 donor。需要的输入缺失或操作失败时报告阻塞，不当作正常跳过。

routes 中 main/texture_only 经 postprocess 必答门；四个 option 分别进入 skip_postprocess、nose_postprocess、denoise_postprocess、selected_postprocess 子路线。宿主保留进入此门的父路线与所请求终点，子路线在 freeze 汇合后返回父路线继续，不能因选择后处理而把完整任务截成局部交付。已有合格前置可跳过；repair_only/donor_ready/denoise_only 仍用于明确的局部任务，验收后交付。路线是宿主编排说明，不是新增的一键脚本或自动确认器；没有 UI 的宿主直接提问并等待实际答复，不生成虚假的确认记录。

### 注册步骤（修鼻需要时）

调用独立 [face-fit](../../.dependency-face-fit/REFERENCE.md)，交接原 GLB 与本次 Sapiens2 分析目录，取回同源 donor、五官/鼻部指标及几何检查。详细参数、坐标变换、遮挡过滤和失败边界唯一维护于 [注册契约](../../.dependency-face-fit/references/guide.md)。物化后的 workflow 继续提供同名脚本兼容入口，不维护第二份算法。

### 鼻部移植（可选）

调用独立 [nose-repair](../../.dependency-nose-repair/REFERENCE.md)，交接上一阶段导出的同源 donor 与原高模，取回 repaired.glb、来源映射和局部审计。准备、运行及底层算子契约统一见 [修复操作](../../.dependency-nose-repair/references/guide.md)。本 workflow 的物化包保留同名 scripts 入口；调用前仍需确认 ROI，完成后仅在已选择时继续其他后处理，否则进入最终几何交接。

### 语义皱纹去噪（可选，选择后才运行）

先固定去噪实际输入：未做修复时是原高模，已做修复时是最新验收模型。移植改变顶点/面：**必须在最新版本上重新渲染与分割，或经过明确验证地转移权重**。禁止沿用旧顶点数组。`semantic_weights.project_weights(pixel_xy, visible, labels, protected, ...)` 是纯投影函数，输入实际相机投影与 raycast 可见性；对皮肤腐蚀、羽化并排除保护区域。它不会调用 Sapiens2、不会自动生成可见性。执行者复用采样适配器的相机/raycast 方法，按本次网格顶点生成权重；多视图融合后再次施加全局鼻部/眼唇/头发/饰品保护。只用二维投影而无深度检查会错误处理后脑。

准备 NPZ：`weights[N]`、`source_sha256`，N 等于目标 mesh 顶点数，权重有限且在 [0,1]，0 完全不动。nose transplant 内部及接缝过渡带权重均为 0，主要年龄褶皱按需要保护。

配置：`source`、`source_sha256`、`mask`、新 `output`，可选 `mesh_name`（多 geometry 必填）、`iterations:80`、`lambda:0.5`、`mu:-0.53`，以及**必填 `max_displacement`（模型本地坐标单位）**。80 是迭代轮数，不能独立解释为固定强度；效果也取决于权重、网格密度和位移上限。

```bash
"$PYTHON" "$SKILL_DIR/scripts/denoise_semantic_face.py" "$RUN_DIR/denoise.json"
```

`denoise(vertices, faces, weights, *, iterations, lambda_, mu, max_displacement)` 返回新顶点与数值指标，不改输入。三角邻接下正/负两步 Taubin，位移截断，退化方向保护；零权重固定、拓扑不变，零轮/全零权重为有效 no-op。`run(config)` 承担 GLB/NPZ I/O、源哈希约束、另存及 provenance。不能保证无自交；运行后需局部 Blender 检查和同步旋转观察。高频 Laplacian 能量下降不等于脸型/年龄自动合格。

### 最终几何交接

在任务记录中保留实际用户答复、每项选择、跳过原因、输入/输出版本和检查结论。freeze 必须核对已确认的决策，缺少答复返回 postprocess，不能将空选择当作全跳过。所有所选操作通过后，最终几何指向最后一个合格输出；明确不使用后处理则原样引用输入文件，不要求生成 repaired/denoised 文件。变更后处理选择需重新判定下游纹理/标签的版本对应，不能复用绑定旧几何的权重和贴图。未运行的子步骤记 skipped，而非成功耗时 0。

## 纹理生成

默认 condition 是**本任务前面图像处理阶段生成、实际验收且获人工确认的 front**：从当前已确认分支的 manifest/产物记录定位实际图片，不按文件名或修改时间猜测。aligned 四视图取其 front；独立 front 分支可直接复用。不是原始照片、整张四格图、高模分析渲染的 front.png 或黑白标签图。提交前按图像评审契约重验其对应 review_id，记录图片实际路径、SHA-256、所属分支/manifest 和评审版本，与冻结几何及纹理 job 一起绑定；不要求为这条默认规则重新生图。

没有合格 front 时暂停并询问选择现有合格 front、补做 front 或明确改用其它图片；补图或改用原图均需用户选择。current 只有 view_0/90/180/270 时没有标准 front，不能将 view_0 改名冒充 front、静默转正、自动补图或回退原照片。多个合格 front 无法由当前分支唯一确定时也先问。若 front 是灰模而目标明确要求彩色纹理，先说明材料冲突并询问补充彩色 front 或明确的替代图，不宣称灰图能提供原照片颜色。上述选择不放宽几何阶段的 current 服务视角门槛。

固定最终几何与上述实际图片后，使用独立 hi3d-api 的 `submit model --mesh FINAL.glb --image APPROVED_GENERATED_FRONT.png --set model=hi3dv3.0 --set resolution=2048quality --set request_type=2`，其中图片占位名须替换为已解析路径；用户明确选择替代图时记录覆盖默认的理由和来源。默认单张 front，可按已确认需求及工具契约追加对应多视图。独立纹理 job 先 dry-run 核对实际图片与几何，再按授权提交；失败按原 job 恢复，不自动退回 request_type=3 重新生成几何。

已有纹理只有几何版本、condition 图片哈希及有效验收/显式替代选择都匹配时才可作为当前结果复用。换 front 或改后处理选择时重新核对下游绑定，不沿用旧纹理/标签缓存；旧作业和输入快照保持原样，新的纹理请求另走授权，不自动重提或篡改历史 job。

检查下载产物 mesh/UV/material/texture、眼睛反光、鼻部颜色与接缝。服务可能重排顶点或调整结构，应用空间距离、轮廓和图像核对，不能只比较顶点数量。几何若有变化，明确报告并保留冻结的纯几何版本。

拆分需要黑白标签时按下一节的子工作流补齐或复用，标签纹理是语义数据，不作为最终材质。其渲染/标签图/贴图是辅助准备，归属图像与纹理能力，不是重新生成几何。统一冻结白模的双请求调度尚未接入，不因此重复提交已有作业。

## 几何拆分与交付

显式调用完整物化的 [head-hair-split](../../.dependency-head-hair-split/REFERENCE.md)，交接彩色 GLB 和已有标签图/模型，按其 [执行契约](../../.dependency-head-hair-split/references/execution.md) 补齐缺失阶段。已有标签直接运行 html，不默认运行 split。严格验证逐面对应，失败保留原件，不静默重网格。默认出口是内嵌代码/数据的交互 HTML 和 manifest，不执行最终 mincut。最终回复必须提供实际 HTML 链接并主动打开，然后等待用户自己调阈值、处理及下载带原漫反射贴图的双对象 FBX；不代点按钮、不補头皮或封口。仅用户明确要求代执行并确认阈值才调用 --confirmed-cut 的 split 获取 GLB 和报告；HTML 仍要交付。

展示页由执行者按任务目录生成：同步各个 Three.js viewer 的 OrbitControls，相同中心、尺度与朝向；保留原高模、实际后处理、纹理及实际拆分版本的下载。预览简化副本不覆盖主交付，页面无凭据或签名 URL。总览不能代替交互分割 HTML：提供“头发/头部分割”入口进入独立标签页，回复中也直接交付该 HTML。缓存复用不得漏交；打开失败说明原因并给文件，不退回自动切割。页面就绪时明确为待用户操作。

## 阶段统计

每次业务任务在 RUN_DIR 记录 `timings.jsonl`：stage、task_id、attempt_id、parent_id、status、带时区 start/end、seconds。进程内用 monotonic。随包 `timing.stage` 包裹本地主要 CLI，失败/中断记录错误类型；没有自动包裹的投影/导出/先验检查、外部服务、图生图和展示由执行者另行计时，不能宣称它们已自动统计。

按图像处理、几何生成、几何后处理、纹理生成、几何拆分汇总实际参与的阶段：pad、头部/转正图及外观配方、四视图、quality 提交/等待/下载、所选后处理的渲染/Sapiens2/投影/fit/鼻修复/去噪、最终纹理、标签准备、图割及展示。保留已有 CLI 阶段名，将其归入相应组，不假称新增自动采集。合并一次编辑的主体/姿态/外观不记为三次生成。复用标记 reused，未执行标记 skipped，注明原因；不要伪造计算时间为 0。重试追加新 attempt 并关联原 task，不覆盖旧记录。任务总墙钟按最早开始到最终结束，重叠和父子阶段不重复相加；服务计算耗时与本地等待分别标注。时间缺失明确范围及原因。

只有宿主或 API 实际返回 usage 才记录 token，注明来源/输入/输出/包含范围；不可由耗时、字符数或余额估算。不采集可省略，不为补统计重跑。运行报告放在任务目录，不写回 skill 包。

鼻部交接时将 face-fit 的 `fit/observed_face_settings.json` 作为 nose-repair 配置的 `landmark_settings`。准备脚本自动保护上唇并检查鼻翼/鼻小柱保留；冲突时停止并交给 agent 查看。常规计算与局部开放边/自交检查由代码执行，agent 保留输入方向确认、最终视觉验收和明确失败处理。展示 donor 时保留完整鼻部拓扑，不按观察到的 `fit_indices` 裁面，否则会误删鼻孔和鼻翼内部。
