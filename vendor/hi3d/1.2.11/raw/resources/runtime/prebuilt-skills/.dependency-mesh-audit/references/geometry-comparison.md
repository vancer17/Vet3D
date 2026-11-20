# 同拓扑基线比较

`from geometry_compare import compare_geometry, triangulate_faces`，在完整物化包的 scripts 搜索路径下由 Blender Python 调用。依赖 NumPy 和 mathutils BVH，无文件或场景副作用。

`compare_geometry(rest, current, faces)` 接收同形状、同坐标/单位的有限 N×3 顶点及整数三角形/四边形。`triangulate_faces` 对四边形固定使用 012、023，并保持先全部 012 再全部 023 的顺序，保留旧报告的面编号。

返回有限值、退化面数、最小两倍三角面积、基线/当前/新增穿越数、新增面索引对和接触中心、geometry_passed。只将当前严格穿越减去 rest 穿越后的差集判为新增；退化也不能通过。形状不匹配、越界、负/非整数索引、空拓扑和非有限坐标抛 ValueError。既有 crossing_pairs 的共面、相切、共享顶点及完整包含排除范围不变；没有运动或附件间隙保证。

修复属于 surface-fit，调用方显式传入基线集合、预算后再用本能力复查；本能力从不修改输入。neutral head 的眼睑/附件限制及 NPZ/OBJ 命名由人头工作流保留。验收使用既有基线相交、新引入相交、零面积、非法索引和输入不变案例。
