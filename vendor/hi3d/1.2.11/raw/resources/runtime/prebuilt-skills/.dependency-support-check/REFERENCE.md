---
name: support-check
description: 对闭合实体和明确密度或质量、接触点与重力方向计算静态重心及支承域裕量，输出几何稳定性报告；不证明实物抗推倒、摩擦或填充重量。
---

# 静态支承检查

接收已确认闭合且绕序一致的三角网格，或已知质量与重心；结合真实接触点完成一个静态几何判断。先读取 [计算与调用契约](references/contract.md)，明确单位、材料假设、接触对象和重力。网格闭合性需先由 [mesh-audit](../.dependency-mesh-audit/REFERENCE.md) 或等价实际检查确认，本核心不修网格。

按 [打包约定](../.dependency-package-tools/references/usage.md) 和 [清单](package.json) 提供独立目录，以 `$support-check` 或显式读取本文件调用。普通 Python 安装 `requirements.txt`；不需要 Blender。物化包内运行 `python scripts/check_support.py --input INPUT.json --output REPORT.json`，路径为任务目录的绝对路径。源 JSON 只读，报告拒绝覆盖；仅严格正裕量返回 0，边界或域外返回 1，非法输入抛错。

输出质量 g、重心 mm、垂直重力的平面坐标系、支承凸包和每条边的带符号距离 mm。不得把边界上的零裕量称为稳定通过。对象筛选、纸张是否计入和接触容差由调用方声明；不把某个品类阈值变为核心默认值。实体等效密度不能冒充实际填充、摩擦、固定、推力、疲劳或承载验证。

<!-- managed-by: sparc3d-runtime -->
