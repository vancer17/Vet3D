# 几何核心与兼容调用

`product_core` 以米为输入；`planar_core`、frame/box_core 和 `studio_core` 保留毫米 profile。这些核心只构造/修改形体及执行所需 bpy 操作，不依赖预览、打印输出、审查或来源规范化模块。

工作流按职责显式导入核心和领域函数。旧 product/planar/frame/box/brush_geometry 与 studio 聚合入口已移除；重新物化后使用下表模块，不依赖星号导入顺便提供的第三方包、打印或来源函数。几何包只物化所需通用 Blender 操作，不能反向打包预览、打印、审查或来源能力。

- [model-preview](../../.dependency-model-preview/REFERENCE.md)：`product_preview`、`planar_preview`、`planar_render`、`brush_preview`、`studio_preview` 保留灯光、相机、渲染/跳过策略和可视 GLB。frame/box 的相同 render 共用 planar_render；brush 保留原忽略 engine 的策略。
- [print-export](../../.dependency-print-export/REFERENCE.md)：`product_print` 保留在临时副本上明确进行的焊点/三角化/退化清理，原生几何保持；`frame_print` 保留 float32 毫米量化后仅去掉精确零面积三角形和移除计数；`planar_print` 与 `studio_print` 保留不做修复的序列化 profile。profile 的数值清理不能当作闭合/强度验收。
- [mesh-audit](../../.dependency-mesh-audit/REFERENCE.md)：`product_audit`、`planar_audit`、`brush_audit`、`studio_audit` 保留各自体积单位和包围盒求值范围。product topo 对 curve 采用临时求值网格，保留指标而不再把输入对象转换成 mesh。
- [source-prepare](../../.dependency-source-prepare/REFERENCE.md)：`product_source` 保留高度/宽度二选一、旋转、保留原副本及显式减面；`studio_source` 保留标签来源与毫米放置。不会以合并整场景的 prepare_source 替换单头导入。

按 package.json 物化后导入；支持 scripts 根目录和已有 product/teapot_model 等包内相对导入。调用对应唯一模块；不同职责允许单向复用，不能通过聚合入口形成相互依赖。标准库及 NumPy/Blender 类型显式导入，不作为几何 API 的附带输出。

frame/planar/studio 三种 STL profile 共用 print-export 的 `evaluated_triangles` 与 `stl_bytes`；只在 frame 适配中显式调用精确零面积量化过滤。头部字节、坐标尺度和记录字段保留，求值副本在失败时也释放。

常见迁移：`geometry.import_source` → `product_source.import_source`；几何函数 → `product_core`；相框/收纳盒的通用轮廓 → `planar_core`，特有布尔/孔操作 → `frame_core`/`box_core`；边界 → `planar_audit`/`brush_audit`；预览 → `planar_preview` + `planar_render`（笔刷用 `brush_preview`）；STL → `frame_print` 或 `planar_print.export_stl_legacy`。原函数签名、单位和品类选择保留。`media.export_parts` 改由 `product_print.export_parts` 提供，预览包不再提供制造导出。
