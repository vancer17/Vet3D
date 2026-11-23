# 网页派生 GLB

`web_derivative.export_derivative(path, objects, derivatives, collection, polygon_budget, texture_limit, mesh_cache, exporter=None, **options)` 在 Blender 内接收显式导出对象白名单、需要减面的网格子集、当前场景集合、正整数预算和独立空字典缓存，写 GLB 并返回每对象的来源/预览面数和缓存命中。先按 package.json 物化，使用 blender-tools 的 execute 入口在独立后台进程调用；不依赖上游建模。

预算必须由调用方明确提供；当前产品 profile 为 300000 面和 2048 像素，其他用途不继承该默认。DECIMATE ratio 按原 polygon 数计算，结果面数以报告为准，不能保证精确预算。缩图保留比例且任一边至少 1 像素；相同贴图共享一个临时副本。只缩放白名单使用的直接图像节点，不递归处理节点组。

原网格、对象可见性和自定义 asset 属性不改；复制对象保留原父级、变换、材质关系与动作。只有副本网格参与减面，制造资产不受影响。`glb_export` 负责明确选集、帧/子帧恢复与导出状态检查。无论减面、缩图或导出哪步失败，都恢复节点与选择/active，清理本次对象、网格及图像。错误向调用方传播，目标文件可能不完整，调用方不能把文件存在视为成功。

缓存只限当前 Blender 进程，由调用方持有并用 `clear_mesh_cache(cache)` 释放；不持久化指针。key 绑定原网格身份、顶点/拓扑/已知属性、UV 与材质槽和减面预算。形态键、modifier、顶点组、自定义法线及无法完整读取的属性会跳过缓存；不以不完整摘要复用形变网格。成功导出后才保留新增缓存，失败不留下新增条目。不能把旧的业务私有缓存格式传给该函数。

product_scene 选择全部 art 网格，motion-base 选择明确角色；其余 asset 对象原样导出。`export_animations/current_frame/animation_mode/frame_range/force_sampling/materials/yup` 由调用方传递。同步片段合并继续使用 glb-clips，并保留各业务动画名称与 0/1 片段处理差异。

验收：静态与动画 GLB 回读；导出器可注入失败，检查原场景、节点和资源数量；改变原网格内容或预算后必须重新派生；最终调用方仍负责实际网页播放与视觉检查。现有两条产品 runner 不缓存建模阶段，网页网格缓存仅在进程内使用，不改变帧渲染的来源检查点。
