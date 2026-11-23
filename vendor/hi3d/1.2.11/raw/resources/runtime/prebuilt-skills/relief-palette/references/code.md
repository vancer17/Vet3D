# 原子函数与副作用

全部实现随包位于 `scripts/`。模块只依赖同目录代码、标准库和明确的 Blender 运行时；CLI 不包含核心算法。复用脚本时将本包 `scripts/` 的已解析路径加入 Python 搜索路径，再显式导入所需模块。

| 模块 / 函数 | 输入、输出与边界 |
| --- | --- |
| `spec.number/vector/validate_spec` | 纯配置验证，返回数值/原配置；拒绝非有限数、重复标识/颜色、无效开角和尺寸关系。不会核实图片语义或粉盘间空间关系 |
| `spec.read_spec` | 从明确 JSON 路径读取，解析声明的文件路径并检查存在、非空、扩展名及 Python 语法；无 Blender/网络，返回已解析配置 |
| `geometry.linear_rgb/shader/material` | sRGB 转线性、按节点 `type` 查找 Principled BSDF、创建材质。节点查找不依赖本地化名称；插槽按 Blender 5.x API 使用 |
| `geometry.powder_material` | 创建具有毫米颗粒尺度和凹凸的粉体材质；默认起点 grain=.09 mm、bump=.035 mm、metallic=.35、roughness=.5，可按产品修改；不是真实光谱或粒子模拟 |
| `geometry.rounded_points` | 纯二维圆角矩形轮廓；尺寸与半径需正且有效 |
| `geometry.mesh/plate/ring/cylinder/ellipsoid` | 接收显式 collection 和毫米尺寸，只创建并返回对应对象；内部按 `MM=.001` 转为米。ring 外内轮廓还需调用方保证相互嵌套；形状不自动校准参考图 |
| `geometry.bevel` | 给指定对象追加边缘及加权法线修改器，返回对象；宽度毫米，不负值 |
| `geometry.difference` | 显式目标/切割体；复制被共享的目标 mesh，应用当前修改器、三角化后执行差集，保留 cutter 供调用者清理。修改目标具有破坏性，先在候选工程操作 |
| `geometry.parent_keep_world` | 更新依赖图后保留对象世界矩阵并设置父对象；不保留独立运动层级语义 |
| `geometry.applicator` | 指定整体尺寸、两个端头种类和材质字典，返回可取出空对象根与实际几何列表；刷头是包络，无毛发模拟 |
| `geometry.aim/fit_camera` | 朝向毫米目标；对指定几何的 evaluated 包围盒投影取景，修改正交相机位置和尺度；每个姿态重新计算，不用固定俯视尺寸估计翻盖高度 |
| `relief.fit_vertices` | NumPy 坐标数组、源轴排列/深度符号、目标 XY 尺寸/高度/基线，返回米制顶点和映射元数据；只做等比 XY 与独立 Z 归一化，无 IO |
| `relief.import_relief` | 导入一份明确 STL，适配几何、重新计算法线、与粉饼共用材质并返回对象/数据；不改源文件。恢复选择和 active 对象，异常只清除本次新建对象 |
| `assembly.hinge_control` | 闭合状态 moving 对象、轴心/轴/符号、关键帧，返回 `open_angle` 空对象控制器；驱动轴向旋转并插入角度关键帧 |
| `assembly.world_mesh/overlaps/tree` | 读取 evaluated 三角网格并立即释放临时 mesh；计算世界范围、AABB 相交和 BVH，用于表面检测 |
| `assembly.store_roles` | 检查本场景几何角色、contents 子集及特定接触对，将实际对象名称与运动契约写入 scene 自定义属性 |
| `assembly.validate_scene` | 当前激活场景，返回通过与否、运动/碰撞/间隙/材质报告；采样过程恢复帧。具体覆盖范围见 [验证](validation.md) |
| `pipeline.import_builder` | 从明确 Python 文件载入 `build`；执行模块顶层代码，调用方必须先审阅，不能当作不可信插件隔离器 |
| `pipeline.configure_render/render_shot` | 配置 Cycles/AgX；按镜头姿态取景和写 PNG，恢复原帧、相机、构图变换及输出路径，避免共用相机最后闭盖取景裁掉开盖默认视图 |
| `pipeline.run` | 组合预检、独立场景、builder、粉体、铰链、验证、保存与渲染；拒绝已有目录、记录失败并恢复原场景。失败候选留在内存及已产生的输出中供定位，不擅自删掉用户工程 |
| `timing.Recorder/write_json` | 在明确的外部目录追加阶段事件并原子替换汇总 JSON；单写入者，不跨进程共享同一日志。详见 [统计](timing.md) |
| `run.main` | 仅参数解析、分派和结果/退出码呈现，按模式延迟导入 Blender 模块 |

需要不同粉盘轮廓、源格式、曲面映射、复杂机构或透视相机时显式扩展相关原子函数，并验证新的输入范围；不能只改入口描述扩大实际支持范围。

姿态/求值公共能力按 [motion-check 契约](../../.dependency-motion-check/references/scene-samples.md) 物化；本工作流保留对象角色、采样计划和原碰撞后端/阈值。

基础形体复用物化的 [shape-build 原语](../../.dependency-shape-build/references/primitives.md)，网格链接委托 [blender-tools](../../.dependency-blender-tools/references/scene-io.md)。保留本入口毫米/场景单位换算、集合、曲线/网格类型、材质、倒角与法线 profile；品类形状仍由此工作流编排。

构图/相机或 GLB 输出复用 [model-preview 展示原子](../../.dependency-model-preview/references/preview-atoms.md)。保留本工作流画幅、边界 profile、材质与动画选项；临时导出对象和采样/选择状态在异常时也恢复。
