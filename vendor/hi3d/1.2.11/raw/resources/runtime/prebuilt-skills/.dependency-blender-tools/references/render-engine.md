
# 渲染兼容

`render_engine.engine_identifier(requested, available)` 接受明确渲染器及可用标识集合；两个 EEVEE 名称等价，在 available 中优先 NEXT，否则旧 EEVEE，缺失直接报错。`set_engine(scene, requested)` 对 EEVEE 使用 Blender 当前 RNA 枚举，对 Cycles 等动态注册渲染器由 Blender 属性赋值校验，并返回实际标识；不根据版本号推测。`set_samples(scene, count)` 对 Cycles 或实际存在的 EEVEE taa_render_samples 属性设置正整数；不支持的属性返回 None，不能宣称采样数已生效。

render_scene 与已有产品、头部、相框、动捕预览共用此兼容层。分块帧恢复指纹包括本模块；同一输入下兼容层变化使相关渲染阶段失效，未用渲染的几何阶段保持原缓存。
