# 来源检查视图

[source_views.py](../scripts/source_views.py) 的 `render_source_views(obj,out,height_mm,*,extent_factor,light_energy,light_size,light_distance,camera_distance,world_name,replace_world=False)` 接收已规范化的米制 Blender mesh 与已存在输出目录，修改隔离场景并输出 front/back/left/right/top/hero 六张 PNG。height_mm 只用于把目标点设为 (0,0,height_mm/2000)，不修改几何。

调用方明确给出尺度因子、面积灯功率/尺寸/位置距离和相机距离；距离均为米。三个灯方向为 (-1,-2,2)、(2,-1,1)、(0,2,2)，复用 [area_light](preview-atoms.md)，保留 SQUARE 形状。正交比例为 max(obj.dimensions)*extent_factor；渲染为 600×600、Cycles CPU、12 samples、去噪和 2 线程、AgX。replace_world 为真时创建新世界，否则保留现有世界并更新颜色；均不保存用户偏好。

本函数增加灯和相机并留下最后视图的场景状态，不声称恢复整个工程；先由调用方保存不含预览设备的 source.blend。源规范化使用 [source-prepare](../../.dependency-source-prepare/REFERENCE.md)。通用来源 CLI 保留 1.65/15/.2/.12/.5 的取景与灯光参数；护甲适配器保留 1.2/110/.45/.45/1.2 及新世界策略。跳过条件由各自 CLI 决定，不把业务品类名写入公共函数。
