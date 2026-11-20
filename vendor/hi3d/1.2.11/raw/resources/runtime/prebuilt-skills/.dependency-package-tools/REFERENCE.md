---
name: package-tools
description: "将显式 package.json 依赖物化为仓库外的独立能力包，验证来源、冲突与依赖；也可为明确的能力仓库生成和检查使用关系。"
---

# 依赖打包工具

将显式 package.json 依赖物化为仓库外的独立能力包，验证来源、冲突与依赖，供任意 skill 或 workflow 安装调用。

## 输入与完成结果

- 输入：明确的仓库根目录、全局 entry 名称和不存在的输出目录。
- 输出：scripts/bundle.py 生成独立分发目录；references/usage.md 定义源包与安装包的区别、CLI 和依赖契约。

## 调用与边界

Python 3.9+ 标准库；不导入目标代码、不联网、不读取凭据、不修改已安装目录。打包模式不覆盖已有输出，拒绝越界路径/符号链接/资源冲突。

源码入口与安装依赖见 [package.json](package.json)；调用脚本前按 [独立打包约定](references/usage.md) 准备完整包。函数和资源导航见 [代码契约](references/code-contract.md)。

需要维护能力仓库的使用索引时，显式提供目标仓库 `--repo`，运行 `scripts/usage.py --check` 或 `--write`。前者只读校验，后者更新 `doc/capability-usage.md`，并在 skills/workflows 缺少 `pcg/architecture.yaml` 时按 kind 生成 linear（skill）或 tree（workflow）入库格式（不覆盖已有手调）。`--check`/`--write` 均会校验 `pcg/routes.yaml`、`ops.lock.json` 与 `architecture.yaml`（tools 除外）。skill 缺 linear 架构或与检查点不一致则入库失败。依据目标入口、物化清单、资料链接与人工交接声明，不运行能力或推断实际执行。索引标出无 skill/workflow 使用记录的入口，并将仅资料/交接与代码/调用来源分开，不能把无 Python 导入的规则型能力直接判为孤立。数据格式及错误边界见 [使用关系索引](../.dependency-doc/package-tools.md#使用关系索引) 与 [Agent 循环衔接](../.dependency-doc/pcg-loop.md)。普通打包不要求先运行此检查。

宿主需要平面 skills 时使用 [Desktop profile 分发](references/usage.md#desktop-profile)，保留唯一源、安装别名和完整引用；普通三层包保持原行为。

<!-- managed-by: sparc3d-runtime -->
