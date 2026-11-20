---
name: rhino-build
description: 通过 rhino-control 在 Rhino 5–8 中完成建模与另存交付；自动定位安装或搜索用户提供的文件夹，验证运行版本后优先配置 MCP，回退原生 Python 或桌面操作。
---

# Rhino 建模工作流

通过 `$rhino-build` 将建模需求透传给独立 [rhino-control](../rhino-control/SKILL.md)。按目标环境优先 MCP，必要时使用原生 Python 或桌面操作完成建模。工作流只负责需求、环境准备、执行交接和交付，不另写探测器、安装器或 MCP 客户端。

## 输入、依赖与产物

输入为建模/修改目标、尺寸与单位、可选参考或已有 3DM、输出位置，以及可选 Rhino 安装文件夹、应用路径或指定版本。用户已给出的文件、对象范围和授权原样传递；缺少影响形体或尺寸的关键输入才询问，不把接口选择变成额外审批。

先按 [package.json](package.json) 提供完整分发包，读取依赖 tool 的完整入口；`RHINO_TOOL` 指实际 rhino-control 包，`RUN_DIR` 为包外任务目录。需已安装且获许可的 Rhino 5–8、外部 Python 3；MCP 与 Python 的具体依赖由 tool 按分支核对。本工作流不安装 Rhino 本体或处理许可。

交付新版本 `.3dm`、用户所需导出文件、实际执行的业务 `.py`（使用脚本时）、`environment.json`、`validation.json` 和阶段记录。仅请求环境配置或脚本编写时按该范围交付，不声称模型已完成。

## 执行与交接

先读 [检查点](pcg/routes.yaml) 与 [阶段和产物](pcg/architecture.yaml)。同一 agent 可以顺序执行全部阶段，不要求启动子 agent。

1. **locate：定位目标。** 先调用 tool 的 `scripts/rhino.py detect` 查常用安装位置；用户已给精确应用路径则用 `detect --app`，已给文件夹则用 `detect --root` 搜索。没有找到时才请用户输入安装文件夹，再自动搜索其中的应用/可执行文件。检查 `truncated` 和 `errors`，搜索未完成不能说未安装；缩小目录后继续。找到后复用本次路径，不反复问用户。多个版本沿用用户指定或当前文档所在版本；仍无法确定时询问目标。
2. **connect：验证并选择接口。** 完整遵循 rhino-control 的版本与路由规则，将安装候选、当前文档和输出目录交给它。应用元数据、`python_entries` 只用于选择探针：Python 运行入口是 Rhino 命令，不是目录中任意 `python.exe`。读取进程内版本/SR、Python 实现和文档标识后，才确认接口可用。先检查已有 MCP；受支持且缺插件时由 tool 自动安装、正常重启、启动桥接并验证。插件已可用就跳过安装；不把本包 Rhino 8 插件装入 5–7。无可用兼容 MCP 时直接按目标版本创建并运行原生 Python 探针；Python 确实不可用才交给通用 computer use。保存实际路径、安装/运行版本、入口、选择原因与探针证据到 `RUN_DIR/environment.json`。
3. **model：透传并执行。** 将原始目标、已确认尺寸/单位、来源路径、目标文档/对象 GUID、保留项及新输出路径一起交给 rhino-control。使用脚本前按其[两级版本索引](../rhino-control/references/versions.md)，以运行版本限定规则目录，并按目标平台/已核对快照分别选择 Python 分支与 XML 框架；已知 API ID 用 section --with-notes 批量读取契约与注意事项，未知名称/重载先 lookup --format text，复用已读行段；由 agent 创建业务脚本并在目标引擎完成只编译和只读预检，然后单次执行；`prepare` 的 probe/smoke20 不是业务脚本生成器。MCP 可直接调用满足需求的工具或传输同一脚本；有 Python 3 依赖时走已验证的 Rhino 8 CPython 入口。已有合格模型只验收时跳过建模；局部修订只改明确对象。结果不明先查原文档/记录，不能切换接口重放修改。
4. **verify：核验与交付。** 由 rhino-control 核对实际对象、几何有效性、所需闭合性、尺寸/单位及任务断言，建模结果另存新 3DM 并回读，仅检查已有模型时直接回读原文件；导出文件逐项核验，实际查看模型。将断言、文件路径、回读和视觉检查结果及未验证项记入 `RUN_DIR/validation.json`。说明真实版本、接口与交付文件；仅生成脚本、命令退出成功或保存成功都不等于建模验收通过。

已验证的 MCP/脚本入口只有在目标进程、文档与引擎仍匹配时才复用；重启、切换版本或文档后重新只读核对。原生脚本在新版通过不能当作旧版本体实测。未找到 Rhino 时可继续澄清需求或在用户已指定目标版本后准备脚本，但依赖应用的执行与验收保持未执行。

## 计时、恢复与计算范围

执行者按随包 [统一阶段记录契约](references/stage-records.md)，在 `RUN_DIR/stages.jsonl` 记录 locate、connect、model、verify 的实际开始/终态与跳过原因；交付 `RUN_DIR/timing.md` 的阶段摘要、总墙钟和缺失区间。记录由执行者完成，非脚本自动采集；token 无可靠来源则省略。

本入口默认编排小型交互建模，先明确本批对象与操作范围。潜在无界的复杂布尔、大规模重网格或离线渲染，必须先具备隔离进程，并按 [run-tools 预算契约](../.dependency-run-tools/references/budget-run.md) 用 `run_budgeted` 执行；中高档墙钟预算由任务规模明确后交宿主选择，不能以 MCP 超时充当内核中止。本包不提供该隔离执行器；没有隔离条件时停在脚本/方案准备，不把高负载任务送入用户当前进程，不强杀用户 Rhino。

失败后保留本次脚本、状态、对象与已有文件，按 tool 的恢复规则核对实际结果；回退检查点只改变后续编排，不撤销已发生的模型修改。输出另存新版本，不覆盖输入；需要覆盖或扩大修改范围时沿用宿主已有授权检查。

<!-- managed-by: sparc3d-runtime -->
