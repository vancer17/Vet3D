
# Runtime 头部交接

先按 [账号生成](../../hi3d/SKILL.md) 获得 quality 彩色高模，然后以 high_glb 进入 image_pipeline。`execution_backend=runtime` 或 desktop 分发标记禁止 image/gray_views 触发公共 CLI；注册、局部修订、同一高模本地烘焙继续当前实现，默认不增加 UV 或远程贴色。

需要独立头发扩展时，`scripts/runtime_parts_generation.py CONFIG`（desktop 安装为 parts_generation.py）只生成 bald/hair 参数计划；必须确认灰图方向及头颈移除后遮挡头发已补全。500 万面是该扩展的既有配方值，可在交接计划中按任务调整，不是所有生成默认。每个部件的正式 `generate_3d` 先 dry-run，把 `consent.user_interaction` 交给宿主 [参数面板](../../hi3d/SKILL.md#参数面板)。

`texture_pipeline` 的 unwrap-uv 与 Hi3D texture 各自先 dry-run；Hi3D 把 `consent.user_interaction` 交给宿主参数面板后再正式调用。

`runtime_texture_pipeline.py CONFIG`（desktop 安装为 texture_pipeline.py）仅针对明确选择的分体扩展：无 UV 时先公开 unwrap-uv；将实际 uv.files.uv_mesh_glb 填入后续 texture.mesh，再调用 Hi3D texture。其他视图用于审查；该公开路线不是内部四视图投射，不提供 coverage，不据此执行 coverage 补洞。内部原 texture_pipeline 在普通分发继续保留。

pose 走 [公开 MDF](../../mdf-api/references/mesh-invoke-api.md)：NPZ 的 keypoints[N,308,2] 是原图像素，scores[N,308]、bboxes[N,4]，N=0 是可用检测结论。交给 [关键点投影](../../.dependency-landmark-project/REFERENCE.md) 前固定选中人物、同一渲染图、相机和输入哈希；保留既有 68 点眼唇、49 点耳部来源映射，不能把不同照片或图像大小直接投到当前头模。
