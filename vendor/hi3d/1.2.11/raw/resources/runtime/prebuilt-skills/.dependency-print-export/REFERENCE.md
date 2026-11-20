---
name: print-export
description: "将已确认的网格写为毫米制 STL/3MF，并保持部件坐标和真实实体组织。"
---

# 打印文件导出

将已确认的网格写为毫米制 STL/3MF，并保持部件坐标和真实实体组织。

## 输入与完成结果

- 输入：显式三角网格或二进制 STL、目标路径和实例/部件关系。
- 输出：scripts/mesh_io.py 提供 STL/3MF 网格 I/O；scripts/stl_to_3mf.py 提供 STL → 3MF 打包。

## 调用与边界

NumPy、trimesh、manifold3d（按所用接口）。不做隐式减面或几何修复；3MF 中多实体组织按所用接口保留。回读检查尺寸、三角形/实体数量与装配坐标；几何合格与切片/实物合格分别报告。

源码入口与安装依赖见 [package.json](package.json)；调用脚本前按 [独立打包约定](../.dependency-package-tools/references/usage.md) 准备完整包。函数和资源导航见 [代码契约](references/code-contract.md)。

Blender 原始/求值三角形提取和二进制序列化见 [STL 原子契约](references/blender-stl.md)，摆盘与文件写入由调用方显式处理。

<!-- managed-by: sparc3d-runtime -->
