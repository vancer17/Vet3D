---
name: connector-select
description: "根据自由度、载荷、制造与释放条件选择打印连接构型，输出有依据的接口设计简报。"
---

# 连接选型

根据自由度、载荷、制造与释放条件选择打印连接构型，输出有依据的接口设计简报。

## 输入与完成结果

- 输入：用途、材料、制造方式、固定/运动关系、装卸空间以及已有研究。
- 输出：连接简报、候选比较、公差链、配对接口图和试片需求。按 references/connector-research.md 执行，补充页只在对应条件适用时读取。

## 调用与边界

本能力不建完整产品；已充分研究且条件未变时复用研究。原理、推算与实物数据分别标注，不把案例间隙变成通用默认值。

源码入口与安装依赖见 [package.json](package.json)；调用脚本前按 [独立打包约定](../.dependency-package-tools/references/usage.md) 准备完整包。函数和资源导航见 [代码契约](references/code-contract.md)。

<!-- managed-by: sparc3d-runtime -->
