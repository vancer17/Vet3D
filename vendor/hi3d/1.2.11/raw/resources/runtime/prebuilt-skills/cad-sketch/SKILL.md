---
name: cad-sketch
description: 创建全约束矩形/圆草图、拉伸和直孔口袋，修改命名尺寸，另存 FCStd 和 STEP 并回读体积；单位毫米。
---

# FreeCAD 约束草图

创建全约束矩形/圆草图、拉伸和直孔口袋，修改命名尺寸，另存 FCStd 和 STEP 并回读体积；单位毫米。

## 输入与独立调用

Python 3.10+、FreeCAD 1.x 命令行运行时。先按 [打包约定](../.dependency-package-tools/references/usage.md) 物化 [package.json](package.json)，只执行安装包中的脚本。调用者显式提供软件路径，不在技能内下载/安装软件。

输入为 `schemaVersion: 1` 的本地 JSON；示例见 [hi3d-spec.json](examples/hi3d-spec.json)，字段与函数见 [契约](references/hi3d-contract.md)。相对素材路径以 JSON 所在目录解析，输出目录必须全新或是同指纹的已完成任务。使用 `$cad-sketch` 或显式读取入口，不把文件存在当成宿主发现。

```bash
"$PYTHON" "$SKILL_DIR/scripts/hi3d-cad-sketch.py" --spec "$RUN_DIR/hi3d-spec.json" --output "$RUN_DIR/new-result" --freecad "$FREECAD_CMD"
```

## 执行与交付

1. 校验字段、软件及素材，声明实际单位/帧率/字体。已有合法产物可只核对；不重复执行上游。
2. 执行本能力；需要外部长进程时复用 [运行预算](../.dependency-run-tools/references/budget-run.md)。`budgetSeconds` 为每个子进程墙钟上限（默认按代码），不自动续跑/加时；大型任务需先确认预算。
3. 检查 `hi3d-project.FCStd、hi3d-solid.step、hi3d-review.json` 和 `hi3d-result.json`。成功复用同时验证输入、实现及产物哈希；失败/中断保留记录并选新输出目录，不覆盖输入。源工程保留即本轮回退点，不承诺操作前台应用的撤销栈。
4. 交付真实文件与验证范围；原生工程须重开，渲染结果须查看/播放。单次日志只写输出目录。

先读 [阶段路线](pcg/routes.yaml) 与 [阶段及产物](pcg/architecture.yaml)。本入口只承担上述原子能力，不启动其他软件适配或付费生成。

<!-- managed-by: sparc3d-runtime -->
