# 基线几何检查

`check_geometry.py` 保留 NPZ/OBJ 文件适配和 neutral head 的报告范围；共享计算见 [mesh-audit 契约](../../.dependency-mesh-audit/references/geometry-comparison.md)。默认只读检查。仅传入 `registered` 时显式调用 surface-fit 的有界修复，并按原 linear/offset 逆变换回写；修复预算与排除条件不变。固定四边形三角化及原有输出文件名保持。非有限坐标或非法拓扑在比较前失败，不能作为通过报告。

注册顶点修复和逆变换统一调用 [surface-fit 注册几何核心](../../.dependency-surface-fit/references/registered-geometry.md)；本工作流仅组织归档、OBJ 文件名及报告写出。

耳部子流程已有保护点与局部验收时，主流程传 `--no-repair`，仅检查并导出已接受顶点，避免后续通用接触修复再次移动眼唇。Python 接口为 `check(path, output, registered=None, *, repair=True)`；默认行为不变，关闭修复仍重算 native 坐标并保留整头失败报告。
