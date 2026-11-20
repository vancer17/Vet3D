# 纹理原子如何连接

已有合格网格即可进入纹理链，无需重新生成几何。基本交接为：合格参考图去背景 → UV 网格 → 渲染 normal/CCM/mask 和相机 → 多视图图像 → 烘焙 GLB；已有 RGB/MR/normal 材质可按合成分支装入 GLB。多视图、渲染和烘焙服务的露出状态待确认，见 [目录](catalog.md)。

## 图像与材质

- 已有材质图须核对通道打包约定，不因图片有颜色就当作 albedo，也不能未经确认交换通道。
- 图像 multiview 的几何用途和纹理用途共享服务名，参考图、prompt、控制强度与通道用途不同。生成图片列表需保持与 camera_azims/camera_elevs/view_weights 对齐；缺失参考槽用 None，不能删除中间槽导致方位串位。

## UV、渲染与烘焙

`texture-uv-unwrap-v3-0` 生成可烘焙 UV，need_repair=True 可能改变几何；水密模型是否需要再次修复由实际检查决定。Geo 当前融合层 DEFAULT_UV_TEXTURE_SIZE=8192，fast 的 multiview 图像分辨率默认 1024，但 UV/bake 仍可为 8192；这两个参数不等价。

`texture-render-v3-0` 输出条件图与相机列表，通常不改变 mesh；显式相机或 num_views 二选一。补绘分支 `op=inpaint_select` 需要已有 visible_texture、coverage_mask 和 existing_camera_*，用来选择缺失区域视图，不能当作普通条件渲染调用。

`texture-bake-v3-0` 的烘焙分支需要带 UV 的同一网格、有序 view_images、同序相机与权重。RGB/MR 同时烘焙时 mr_view_images 与视图逐位对齐，允许的空槽按部署契约处理。`bake_channels=compose` 则将已有 texture_image 及可选 MR/normal 图装入 GLB，不会执行多视图投影，也不会修补 UV 或生成法线。

coverage/coverage_mask 衡量覆盖情况，不能代替接缝、细节和颜色一致性检查。只在任务需要补绘且已有可验证的缺失区域时使用补绘分支；保存首轮产物以比较变化。

## 模型后处理

重拓扑改变顶点/面组织，旧 UV/逐顶点数据不自动可复用。LOD 服务会为多个面数档减面并重烘纹理/法线，需逐档检查 actual_faces、材质、法线方向和外观。格式转换只负责表示转换；导出 STL 后不能期待贴图仍在，导出 3MF 也不等于已验证打印装配。

最终用可加载 GLB 的查看器或 Blender 检查：材质和图片是否真实绑定、底色与 MR 是否误接、法线空间是否正确、接缝与背面是否缺失；换光照后再判断高光是否来自材质或被画进 albedo。源图中的武器纹样、眼睛、文字和小部件应单独对照。
