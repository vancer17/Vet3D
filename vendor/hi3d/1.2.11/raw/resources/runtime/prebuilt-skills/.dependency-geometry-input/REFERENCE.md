---
name: geometry-input
description: "将图像或已有 Geo bridge 产物规范为几何服务的对齐图像和 prep.zip，提供纯本地输入组装。"
---

# 几何输入组装

将图像或已有 Geo bridge 产物规范为几何服务的对齐图像和 prep.zip，提供纯本地输入组装。

## 输入与完成结果

- 输入：RGBA 图像，或 bridge 清单及有序 GrayColor 图像；路径与视图顺序显式传入。
- 输出：scripts/geometry_inputs.py 的 prepare_image、read_bridge、build_prep_zip 输出；保留图像对齐、alpha、成员顺序与已有中间产物。

## 调用与边界

Python 3.9+、Pillow。先看 --help 与函数契约；只构造文件，不提交服务。目标服务的视图/数组协议由 service-select 的相应契约规定。

源码入口与安装依赖见 [package.json](package.json)；调用脚本前按 [独立打包约定](../.dependency-package-tools/references/usage.md) 准备完整包。函数和资源导航见 [代码契约](references/code-contract.md)。

详细输入字段和副作用见 [几何输入契约](references/geometry-contract.md)。

详细输入字段和副作用见 [几何输入契约](references/geometry-contract.md)。

<!-- managed-by: sparc3d-runtime -->
