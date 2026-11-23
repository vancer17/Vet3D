# 本地实现契约

本包不含服务客户端、完整面具生成器或自动化舒适认证。图像处理、Hi3D、局部建模修复、渲染和网页由执行者按工作流组合；这里提供可独立调用的确定性辅助能力。各 CLI 仅解析参数、组合适配器和呈现状态，不依赖仓库 cwd 或相邻目录。文件命令不覆盖已有正式输出；同一目标路径只由一个进程操作。

## default_head.py

- `slopes/profile/bump/point` 与向量辅助函数：纯数值计算，固定原创夹具轮廓和光滑局部形态；无肖像输入。分段单调 Hermite 插值在轮廓节点连续，避免每个节点斜率归零形成台阶。固定夹具不声称人体均值或个体精度。
- `build_head()` → 毫米顶点与外向三角面；`obj_text(vertices, faces)` → 确定性 OBJ 字符串。均无文件副作用。
- `head_metadata(vertices, faces, obj_digest)` → 来源、尺度、合成标志点和基本拓扑。拒绝非闭合、非正体积或退化三角面；非通用全局自交检测器。
- `save_head(dest, text, metadata)` → 新 OBJ/JSON 路径，排他写入；已有文件拒绝，写入中断保留部分文件供检查。`main` 组合生成、审计、序列化和写出。

## calibrate.py

- `positive` 验证正有限实数；`calibrate(data)` 从同名定义的直线测量拟合 `mm/model_unit`，输出残差与状态，不修改头模。方差权重来自输入，不代表照片重建误差已知。
- `calibrate_file(source, destination)` 负责 JSON I/O，保持输入与旧报告；字段错误、非直线、重复标识抛 ValueError，路径冲突抛 FileExistsError。CLI 输出实际状态；数据冲突返回 2，单尺寸保留限制。阈值是内部复核规则，非适配认证。

## mask_geometry.py

Blender 场景对象是显式输入，场景单位与依赖图从当前 Blender 上下文取得；函数在 Blender 主线程内执行，不支持并发操作一个场景。

- `mesh_mm(obj)` 返回评估修改器/世界变换后、物理毫米坐标的临时 mesh；调用者负责释放。`topology/tree/samples/stats/audit_meshes` 分别做局部拓扑、同一三角化 BVH、面积加权采样、分位统计及组合审计，无文件写入。`audit` 是场景适配器，创建副本并在异常时释放；需同时提供 head/inner，拒绝非法采样数和壁厚目标。
- `make_object/active/apply/mm_scene` 是明确的 Blender 状态操作；`extruded_mesh` 纯计算二维多边形的挤出顶点/面，`extruded` 创建相应对象。`liner` 输入已平滑的单连通开口曲面、正 gap/wall、可选平滑避让组，生成 `Mask_Inner/Mask_Shell`。它不自动平滑、倒圆、修复自交或添加艺术外观，失败后检查当前场景而不沿用半成品。
- `build_coupon` 只在空场景生成固定布局平板、布尔贯穿圆孔/圆角槽及入口倒圆，尺寸超范围拒绝；`audit_coupon` 检查真实孔道、孔周实体和中面尺寸。样件不证明实际面具锚点根部强度。`coupon` 组合构建、审计及导出；不先删除用户场景。
- `stl_mm/glb_metres` 分别输出数值为毫米的二进制 STL 与归一到米的 GLB；临时网格在结束/异常时释放，GLB 导出恢复场景单位。`write_json` 排他写报告；`require_new_paths` 在修改前检查目标是否已存在。CLI `coupon` 运行在一次性空场景；`run_liner/run_audit` 加载指定源，写新版本/报告，不覆盖源。导出中断保留部分文件，不能继续声称整套输出已完成。
- 审计退出成功仅代表报告产生；`topology_repair_required` 不是通过。自交、全域碰撞、压力、切片、根部强度和本人试戴必须另行检查。射线薄壁/近邻距离的抽样范围和局限见 [验证](render-and-validation.md)。

## validate_delivery.py

- `manifest_errors` 纯检查 JSON 类型、必需分类（基础 image/description/model，video_requested=true 才加 video）、去重、源版本和摘要格式；`file_errors` 纯比较文件观测与清单，以及基本 GLB/MP4 标记。
- `delivery_path` 仅允许根目录中的相对文件，包括解析符号链接后仍在根内；`inspect_file` 分块读取大小、SHA-256、头部，关闭文件句柄。`validate` 组合读取/检查并返回 passed/failed，不修改资产。
- `save_report` 排他写新报告，路径已存在拒绝。CLI 无效清单返回 1，参数/报告写入失败返回 2；不证明视频解码、可播放、模型形状或浏览器交互。

测试方法与运行命令见 [工具验证](tooling.md#离线验证)。默认头型等生成资产只进入业务/测试输出目录；代码与空模板随技能提供，私人头模、渲染和每次运行记录不进入技能包。

网格拓扑测量通过物化的 [mesh-audit 测量核心](../../.dependency-mesh-audit/references/mesh-measure.md) 执行；本工作流保留旧字段、单位、面积阈值与通过条件。
