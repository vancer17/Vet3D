# 本地烘焙核心契约

[scripts/texture_bake.py](../scripts/texture_bake.py) 在支持 Cycles 的 Blender Python 中运行，直接接收 bpy 对象，不导入文件或调用网络。

- `_device(scene,device,fallback_cpu)` 委托 [blender-tools 设备操作](../../.dependency-blender-tools/references/cycles-device.md) 并保持原 backend 字符串返回；显式 fallback_cpu 才在设备不可用时转 CPU。不写用户偏好文件。未知名称直接失败。
- `bake_context(sources,target,cage,ray,margin,use_clear,device='CPU',fallback_cpu=False)` 校验对象模式、独立源/目标、active UV 和目标节点材质。源与目标不得共享材质，避免临时烘焙节点反馈。配置 selected-to-active、单采样、无降噪、TANGENT +X/+Y/+Z、DIFFUSE 仅颜色。上下文退出恢复原 bake、Cycles、渲染引擎、计算设备选择、对象选择/可见性/active 状态。
- `bake_image(...,path,name,size,kind,colorspace,cage,ray,margin,use_clear,fill=None,normal_16=False,device='CPU',fallback_cpu=False,overwrite=False)` 为每个目标材质建立临时 active image node，执行单通道烘焙、保存并 pack，返回 image 和 path/kind/resolution/colorspace/device/cage/ray/margin/use_clear/seconds/normal_convention。目标原节点、选择及 active 节点恢复；失败清除本次图像与临时节点。
- `save_png(image,path,normal_16=False,pack=True)` 显式写 PNG；normal_16 用 float image 经 Raw、RGB、16-bit 保存，finally 恢复场景颜色配置。其他颜色图使用 image.save。成功文件保留，整组多通道不提供事务回滚；后续通道失败时已成功贴图仍可检查，工作流不可报告整组完成。

所有长度使用源/目标当前场景单位，无自动米/毫米转换；距离与 margin 非负，0 ray 保留 Blender 自身语义。use_clear=False 时 fill 为未观测 UV 的初值。目标必须可选择且位于当前 view layer；受排除集合或 hide_select 限制的对象先由调用方处理。

保留 profile：head-lowpoly 从完整高模按最大尺寸 cage=.009、ray=.04、margin=max(8,size//170)、clear=true、Metal 可回退 CPU；由其 PBR emission 适配所有源材质，相同常量 roughness/metallic 跳过。metahuman-fit 的临时外表皮 patch 保留每个四边形至少 3 个可烘焙点、眼口/耳颈保护，cage=.012、ray=.06、margin=8、clear=false，默认 CPU/显式 Metal 不自动回退；预填 albedo/flat normal，coverage 白色 emission 与 template 融合留在工作流。

验证需用可控几何实际烘焙 DIFFUSE/EMIT/NORMAL，读回尺寸/像素/16-bit 深度，核对 UV/几何、原着色和设置恢复，并检查失败清理。覆盖图只表示射线命中，不能代替完整 UV/接缝/身份视觉验收。远端 MDF 多视图 texture-bake 是不同契约，仍由 service-select/mdf-call 负责。

烘焙通过 cycles_device_context 恢复计算设备；枚举新增设备退出后禁用。工作流的阶段源码摘要必须包含随包 cycles_device.py，避免设备实现变化后误用缓存。
