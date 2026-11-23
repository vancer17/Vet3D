# 实现与资源契约

输入、输出和边界以 [入口](../REFERENCE.md) 为准。物化文件不另维护实现；原文件名到唯一源的映射见 [package.json](../package.json)。

| 维护文件 | 函数/类入口 |
| --- | --- |
| [scripts/product/__init__.py](../scripts/product/__init__.py) | 包命名空间/导入适配 |
| [scripts/product/media.py](../scripts/product/media.py) | `bounds`, `export_glb`, `export_section`, `setup_studio`, `render_views`, `author_lift_animation`, `check_framing`, `render_frames` |
| [scripts/product_scene.py](../scripts/product_scene.py) | `loadmesh`, `prep`, `setup`, `web_export`, `frames` |

参数默认值和返回字段见对应函数签名；argparse 入口可读 `--help`；位置参数适配脚本按入口中列出的格式调用。执行依赖按所选接口加载，不能在普通 Python 中导入含 `bpy` 的模块。运行产物写包外路径。

## 按职责维护的公共模块

- [product_preview](../scripts/product/product_preview.py)：`aim`、`studio`、`render`、`export`、`export_checked`。
- [planar_preview](../scripts/planar_preview.py)：`clean`、`export_glb`、`stage`、`camera`、`save`。
- [planar_render](../scripts/planar_render.py)：`render`。
- [brush_preview](../scripts/brush_preview.py)：`render`。
- [studio_preview](../scripts/studio_preview.py)：`stage`、`camera`、`render`、`export`、`save`、`animate_video`。

共享模块先按 package.json 物化。纯几何复用选择 `*_core`；各职责显式导入，路径与 profile 见 [组合契约](../../.dependency-shape-build/references/composition.md)。不同 profile 保留毫米/米、渲染策略和导出清理差异。

GLB 合并算法唯一源为 [glb-clips 契约](../../.dependency-glb-clips/references/contract.md)，通过 package.json 物化；本地函数保留原片段名称和返回字段适配。

[preview_scene / glb_export](preview-atoms.md) 维护可独立调用的构图、目标相机、面积灯和显式对象导出；原 product/planar/业务 profile 保留参数与结果格式。

## product 接口契约

| 模块/函数 | 输入 → 输出与副作用 | 失败及限制 |
|---|---|---|
| `product/media.export_glb / export_section` | 明确对象白名单、输出路径 → GLB 文件/包络摘要 | GLB 米制；section 是展示半切而非打印件；Draco 需要运行时插件/网页解码器，缺失明确失败，不默默减面。 |
| `media.setup_studio / render_views` | 对象白名单 → 中性工作室与实际视图 | 改当前场景镜头/灯光，渲染写指定目录；不等于真实家居使用场景。 |
| `media.author_lift_animation` | 对象、移动件、毫米位移、输出blend → 完整取出/返回源及逐帧包络检查 | 动作不能证明净空/力学；不自动隐藏干涉，不代替机构释放。 |
| `media.render_frames` | 显式blend、帧段、输出、分辨率/采样 → 真逐帧PNG及记录 | 打开场景会替换当前场景；不覆盖已有帧，不写回源，不编码MP4。 |

头部展示的 `make_mesh/material/aim/studio/render_view` 见 [头部预览契约](head-preview.md)，基础对象和材质创建复用 Blender 工具。

网页轻量副本与临时资源生命周期见 [网页派生契约](web-derivative.md)。
