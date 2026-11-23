# 舞台与次级运动原子接口

本包保留舞台、布料、接触与预览实现；绑定、动作重定向及共享场景/摘要函数由显式提供的 rig-retarget 唯一维护，安装与导入契约见 [绑定依赖](rigging.md)。

## run

[scripts/run.py](../scripts/run.py) 的 `arguments(argv)` 解析 Blender 的 --；`dispatch(command, argv, rig_skill)` 只从显式 rig-retarget/scripts 路径加载共享模块，再从本包导入单个 character 命令。CLI 必须提供 `--rig-skill`；不搜索相邻目录，不自动运行绑定阶段。

## __init__

[character/__init__.py](../scripts/character/__init__.py) 为无副作用的本包模块入口。

## contact_check

代码：[contact_check.py](../scripts/character/contact_check.py)。按指定世界坐标网格对、整数/半帧和显式排除做三角面相交检查；不证明包含关系、自交或连续时间无碰撞。

| 函数 | 契约与副作用 |
| --- | --- |
| `sample_frames(expression)` | 逗号分隔的单帧或 start:end[:step] → 有限、排序去重浮点帧；Decimal 枚举避免半帧累积误差，范围包含可达末帧。 |
| `mesh_arrays(mesh)` | Mesh 数据 → float32 顶点与 int32 三角面数组；要求非空且全三角。 |
| `rest_surface(ob)` | Mesh 对象 → 静止顶点/面/摘要字典；要求非空三角网格，用于拓扑与排除校验。 |
| `evaluated_surface(ob, depsgraph, rest)` | 对象、depsgraph、静止表面 → 世界坐标顶点/BVH/包围盒；要求索引对应、有限且非奇异变换，并释放求值 mesh。 |
| `exclusion_mask(surface, rule)` | 静止表面、带原因/摘要/选择器的规则 → 面掩码；明确面号或全部三点位于静止 bounds，禁止整网格排除。 |
| `check(spec, frames, collect_faces=False)` | 对象对 spec、有限帧列表、可选收集面号 → 接触报告；实际采样世界表面，结束后恢复原帧，按剩余接触决定 passed。 |


## contact_sheet

代码：[contact_sheet.py](../scripts/character/contact_sheet.py)。从渲染 manifest 验证图像、哈希和分辨率，生成带时间/帧号的总览及可选 ZIP；Pillow 实现。

| 函数 | 契约与副作用 |
| --- | --- |
| `compose_sheet(manifest, output_path, archive_path=None, columns=3, cell_width=800, font=None)` | 渲染 manifest、新总览路径、可选 ZIP 与排版参数 → 图数/路径字典；核对图像摘要/分辨率/同目录约束再生成文件。 |


## embed_cloth

代码：[embed_cloth.py](../scripts/character/embed_cloth.py)。捕获已烘焙固定拓扑代理的求值局部坐标，内嵌 shape-key/NLA，并重开比较；保留对象身份以维持 Surface Deform 引用。

| 函数 | 契约与副作用 |
| --- | --- |
| `evaluate(ob, frame, rest)` | 代理对象、整数帧、静止表面 → 求值局部顶点与世界矩阵；检查拓扑/有限值，释放 mesh，改变当前帧。 |
| `capture(args)` | 含原工程/代理/起止帧/输出的选项 → 无返回值；要求单个有效 baked Cloth，保存 NPZ 与 JSON，拒绝覆盖。 |
| `embed(args)` | 含原工程/cache/候选输出/容差/帧范围的选项 → 无返回值；验证源/代理/fps，内嵌并重开比较，写误差报告，未通过抛错。 |


## render_samples

代码：[render_samples.py](../scripts/character/render_samples.py)。用户需要预览时按实际 fps 采样，记录工程/配置/图像摘要并支持严格匹配的恢复；不保存对输入工程的渲染设置修改。

| 函数 | 契约与副作用 |
| --- | --- |
| `sample_frames(start, end, fps, interval)` | 起止整帧、实际 fps、秒间隔 → 最近整帧采样列表；包含范围内可达端点，间隔不能小于一帧。 |
| `render_samples(input_path, out_dir, start=None, end=None, interval_seconds=1, camera=None, width=None, height=None, samples=None, resume=False)` | 源 blend、输出目录、帧/相机/渲染选项 → config/renders manifest；实际生成 PNG，恢复时核对源和图像，不保存输入工程。 |


## self_test

代码：[self_test.py](../scripts/character/self_test.py)。合成双角色的裁剪姿态、共享 Action 保留、逐人旋转中心、共享字体隔离与采样端点回归。


## stage_ops

代码：[stage_ops.py](../scripts/character/stage_ops.py)。已绑定场景的显式对象检查、无约束骨骼动作裁剪、整体朝向与 FONT 修改；不处理任意 IK 视觉烘焙。

| 函数 | 契约与副作用 |
| --- | --- |
| `selected_rigs(names)` | 唯一对象名列表 → Armature 对象列表；拒绝缺失、非骨架或重复选择。 |
| `inspect(args)` | 含 rigs/frames/head_bone/forward/report 的选项 → inventory/世界朝向；采样当前场景并写报告。 |
| `orient(args)` | 含 rigs/degrees 的选项 → 变换报告；验证无父级/约束/对象动画等边界，按每个 rig 站位绕世界 Z 转向并保持局部数据。 |
| `text_edit(args)` | 含 spec 路径的选项 → 编辑报告；精确 FONT 白名单、共享数据隔离、宽度约束，保留未选内容。 |
| `clip(args)` | 含源/目标帧、rigs、stage_actions、markers 的选项 → 裁剪报告；缓存所选骨骼姿态后创建新 Action/NLA，可重采样显式舞台曲线，保留未选引用。 |


## test_cloth_contacts

代码：[test_cloth_contacts.py](../scripts/character/test_cloth_contacts.py)。合成半帧碰撞、排除与拓扑保护，以及真实 Cloth bake/内嵌/Surface Deform/移走外部缓存后的播放回归。

| 函数 | 契约与副作用 |
| --- | --- |
| `require_error(function, fragment)` | 待调用函数、预期消息片段 → 无返回值；断言 ValueError，供无效操作回归。 |
| `mesh_object(name, vertices, faces)` | 名称、顶点与面 → 新测试 Mesh 对象，并链接当前场景。 |
| `contact_fixture()` | 无参数 → 接触保护测试报告；重置测试场景，覆盖半帧、世界变换、排除及拓扑。 |
| `cloth_fixture(root)` | 测试目录 → 内嵌回归报告；创建/烘焙真实小布料，验证跟随和外部缓存不可用时的播放。 |

网格读取与临时资源统一复用物化的 [blender-tools 快照](../../.dependency-blender-tools/references/mesh-snapshot.md)。原坐标、精度、三角面前提与领域拒绝条件由此入口保留。

图片画布、标签与缩放复用 [image-sheet](../../.dependency-image-sheet/references/contract.md)，本入口保留来源选择、字号、采样器、标签格式及业务验收/归档职责。
