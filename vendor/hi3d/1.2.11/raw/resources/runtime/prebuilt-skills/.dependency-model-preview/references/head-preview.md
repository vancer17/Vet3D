# 头部检查场景

`scripts/head_preview.py` 在 Blender 内独立调用；先物化 model-preview，再通过 blender-tools 的 `execute.py --script` 运行自己的调用脚本。输入保留原场景单位，不归一化或修复几何。单头导入与额外头发保留由调用方使用 blender-tools 的 head_io 完成。

| 函数 | 输入、结果与边界 |
| --- | --- |
| `make_mesh(name, vertices, quads, uvs=None)` | 显式顶点/面与可选逐 loop UV → 当前场景中新建平滑网格；复用 scene_io 创建对象，不移动已有对象。UV 数量必须匹配 loops，错误向调用方传播。 |
| `material(name, color=(.42,.48,.53,1), roughness=.65)` | 线性 RGBA 与粗糙度 → 新 Principled 材质；复用 material_nodes，不自动做颜色空间转换。 |
| `aim(obj, target)` | 以本地 -Z 朝向目标、Y 为上，改变对象旋转；目标与对象位置必须不同。 |
| `studio(bounds, size=900)` | 两个有限三维边界、非零 span 和正分辨率 → `(camera, center, span)`；建立 EEVEE/AgX 正交场景、深色 world 与三盏面积灯。灯能量按 span²、灯尺寸按 span 缩放，正交尺度为 span×1.16；重复调用会新建展示资源。 |
| `render_view(camera, center, span, direction, path)` | 相机相对中心按 direction×span 定位 → 指定绝对路径 PNG；修改相机与 render.filepath，调用 Blender 实际渲染，异常传递。输出目录由调用方准备，已有同名图片可覆盖。 |

此 profile 保留头部正背侧与表情检查的参数语义；不替代通用多对象构图。复用者将 head_preview、preview_scene、scene_io、material_nodes 显式物化，并将使用它们的阶段源码纳入缓存。仅进行关键点投影或来源 IO 的阶段不需要展示模块。

验收时在空场景创建已知网格，检查 UV、平滑面和材质，调用 studio 与 render_view 输出实际 PNG；改变共享源码时验证相关阶段失效、无关阶段仍复用。
