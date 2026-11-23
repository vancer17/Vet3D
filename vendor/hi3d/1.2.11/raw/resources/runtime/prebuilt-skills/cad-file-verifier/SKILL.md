---
name: cad-file-verifier
description: "当需要验证 CAD 文件在指定软件和版本中能否打开、保存并继续编辑，或校对编辑、导入导出、版本迁移前后的图层、结构与引用是否保留时使用。输出差异报告并追加实测记录；默认不修复、不转换、不覆盖原工程。"
---

# CAD 工程校对

检查 CAD 文件在指定环境中能否打开并继续编辑，核对图层、对象、参数、装配和外部引用是否保留，并给出有证据的差异报告。

## 输入与独立调用

Python 3.9+。先按 [打包约定](../.dependency-package-tools/references/usage.md) 物化 [package.json](package.json)，只执行安装包中的脚本。FreeCAD 由调用者显式提供可执行文件；本入口不下载、不安装软件。

输入为 `schema_version: 1` 的本地 JSON。字段、状态和结论边界见 [契约](references/contract.md)，工程类型检查项见 [检查配置](references/checks.md)，适配器能力见 [适配器](references/adapter.md)。示例见 [task.json](examples/task.json)。

```bash
"$PYTHON" "$SKILL_DIR/scripts/verify.py" --task "$RUN_DIR/task.json" --output "$RUN_DIR/new-result" --registry "$RUN_DIR/registry"
```

`--registry` 可省略。省略或写入失败时仍交付本地 `report.md` 与 `result.json`，并写明兼容记录未更新。命令退出 0 只表示报告已写出，业务结论看 `overall_status`。

## 执行与交付

1. 确认模式是 `inspect`、`compare` 或 `roundtrip`，以及目标软件、保留要求、预期变化和已有授权。只检查不隐含修改授权。没有基线时可以做当前健康检查，不能声称编辑前后的信息已保留。
2. 把输入复制到输出目录下的隔离副本。原文件和仍指向工作区外的依赖只读；符号链接不当作写入目标。
3. 用文件内容识别 STEP、DXF 和 FCStd。扩展名不能单独作为格式证据。提供了可执行的 FreeCAD 且已授权时，才在副本上做无头打开、保存和重新打开。本地内核先写预算再启动，墙钟到达即停止，不自动加时。
4. 按稳定对象标识比较。数量相同、外观相近或保存成功都不能单独通过。读不到的字段不能当成空值一致。授权修改单独核对，其余变化单独列出。
5. 每项为 `pass`、`fail`、`unknown`、`blocked` 或 `not_applicable`。必须项失败则整体失败；没有失败但有受阻则为受阻；没有失败或受阻但仍有未知则为部分验证。模拟适配器的通过不记入实测兼容。若调用方声明上游建模工具，原样记入 `upstream_build`。ClassCAD 只作为源端会话证据另列；它内部的特征、尺寸、体积或渲染通过，不能代替 SolidWorks、AutoCAD、Fusion 或其他目标软件里的图层、约束、特征和装配验收。本入口不连接 ClassCAD，也不把未实现的目标软件适配器记成可执行。
6. 交付中文 `report.md`、机读 `result.json`、快照和证据索引。修复、转换和编辑探针未实现时不改副本；超出授权的修复只写明需要确认，不执行。

先读 [阶段路线](pcg/routes.yaml) 与 [阶段及产物](pcg/architecture.yaml)。函数导航见 [代码契约](references/code-contract.md)。本入口只做验收，不创建模型，也不把某一次通过写成整个软件版本兼容。

<!-- managed-by: sparc3d-runtime -->
