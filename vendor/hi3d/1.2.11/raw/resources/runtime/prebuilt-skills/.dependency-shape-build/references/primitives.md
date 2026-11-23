# 独立轮廓与基础形体

[primitive_core.py](../scripts/primitive_core.py) 仅依赖 Python math，不创建 Blender 数据；输入和输出使用同一单位，由调用方显式换算。

| 函数 | 契约 |
| --- | --- |
| `rounded_rectangle(width,depth,radius,segments=10)` | 圆角矩形 CCW 点列表；每角含两端点，共 4×(segments+1)，半径必须小于短边一半；保留角部采样，不替换另一种等弧长重采样轮廓 |
| `extrude_polygon(outline,start,end,axis='Z',center=(0,0,0),orient_y=True)` | 有序二维轮廓、递增区间 → 顶点和多边形面；axis 将输入二维分量映射到另两轴，CCW 轮廓默认 Y 绕序翻转；旧调用方可显式 orient_y=False 后按原流程重算法线 |
| `cylinder_mesh(center,radius,length,axis='X',segments=64)` | 正尺寸、XYZ 轴 → 两端环、端盖和四边形侧面；明确 Y 绕序，保留首点相位及顶点编号；不修改输入 |

[blender_primitives.py](../scripts/blender_primitives.py) 接收场景单位：`cylinder_object(name,center,radius,depth,collection,axis='Z',segments=64)` 保留 Blender operator 的三角/多边形相位及未应用旋转；仅链接显式集合，但会改变当前选择/active，品类适配继续负责材质、倒角及是否应用变换。不能把它与按数组创建的圆柱静默互换。

`curve_tube(name,points,radius,collection,material=None,spline='BEZIER',resolution=12,bevel_resolution=3,fill_caps=True)` 创建可编辑 BEZIER/POLY 管道，不转换网格。Bezier 使用 AUTO handles；POLY 保留逐点顺序。成功返回对象，创建失败清理新数据。灯具保留无端盖/4级截面，直线多部件保留 POLY/1级路径/2级截面，产品米制接口保留 BEZIER/12级路径/3级截面。产品材质、粉体、遮罩、标签与装配行为归调用方。

网格对象创建交 [blender-tools scene IO](../../.dependency-blender-tools/references/scene-io.md)，调用方明确集合、坐标换算、smooth 与是否重算法线。新形体可独立由纯坐标核心创建，再交工具链接；不需要预览或打印能力。测试见 [纯原语](../tests/test_primitive_core.py)。

studio 的毫米 POLY 管道仍在业务适配中转为网格并执行 smooth/tag；原始曲线核心不代替这一步。产品和 studio 的原生圆柱也复用 cylinder_object，分别保留 96 段和既有倒角/旋转应用参数。
