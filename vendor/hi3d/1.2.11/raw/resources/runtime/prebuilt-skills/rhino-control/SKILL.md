---
name: rhino-control
description: 控制 Rhino 5–8 创建、修改、检查和保存模型，按实际版本选择 MCP、原生 Python 或桌面操作；适用于 Rhino 自动化、脚本执行与结果验收。
---

# Rhino 应用控制

输入：目标安装/文档、模型操作、新输出目录。输出：实际运行版本、操作结果、3DM/所需导出及验收。`SKILL_DIR` 是完整安装包，`RUN_DIR` 是包外任务目录；外部 Python 负责准备/传输，几何在 Rhino 内执行。

## 版本与最小资料读取

仅准备脚本且目标版本已明确时，直接按该版查资料；进程探测与执行验收留待运行前，交付标记为未执行。

1. 运行 `python3 "$SKILL_DIR/scripts/rhino.py" detect`；明确应用用 `--app`，用户文件夹用 `--root` 有界搜索。核对真实 executable，安装器不算已安装；truncated/errors 时缩小搜索范围。名称匹配 Rhino/Rhinoceros 的 .app 或 Rhino.exe，改名应用直接传路径。多版本沿用指定目标或当前文档版本。
2. 按[两级版本索引](references/versions.md)限定本版与所选接口路径的规则目录，批量读取需要的行段。创建脚本读本版运行约束及共用“创建与提交”“一次提交的编写清单”“提交前检查顺序”；保存时加保存段。已知精确 API ID 用 `section --with-notes` 直读契约与对应注意事项；未知名称或 RhinoCommon 重载先 `lookup --format text`。Python 分支与 XML 框架分别用 --rs-variant / --rc-variant；正文或包装不同、分支缺项均须明确选择目标，不能换平台绕过缺项；已读且未变化的段复用。不要默认读取整份 Python 模块、XML、全部版本索引或重复 MCP 文档。
3. 安装版本和 python_entries 只用于选择探针，不是系统 python.exe 入口，也不是运行证据。用共用“创建与提交”段的 prepare probe，核对进程内主版本/SR、build（可缺）、Python 实现、文档标识；缺失旧 API 由随包探针适配。官方来源、跳转/代码块和缺项仅在索引不足时按[来源导航](references/documentation.md)定向查询。

## 接口与执行

- 先查现有 MCP 的 tools/list、describe_capabilities，再运行只读探针。只有运行主版本与目标一致且能力满足才使用；目录/端口开放不证明连接成功。已有经验证适配旧版的桥接仍优先。
- Rhino 8 缺桥接时按本版索引的[安装与 MCP](references/versions/8-mcp.md)段自动安装、保存工作后正常重启、mcpstart 并验证。固定 jingcheng-chen/rhinomcp 仅声明支持 Rhino 8 Windows/macOS，不能强装到 5–7。
- MCP 不支持所需能力/引擎或存在已确认阻碍时，运行原生 Python 探针；成功才建模。5–8 的 RunPythonScript 用 IronPython 2.7；8 的 CPython 另查本版引擎/ScriptEditor 段。本包 MCP 的 Python 工具不能替代 CPython 验证。
- Python 确实不可用才按索引读 [computer use](references/computer-use.md)。用 UI 启动 mcpstart 或提交脚本只是引导，不必退为逐对象点选。

固定输入 GUID、文档、单位/容差和新输出路径；显式参数批量调用，核对返回类型和失败值。业务脚本自包含，在目标引擎只 compile/只读预检后单次执行，再做几何和文件回读验收。脚本夹具 prepare 不是业务脚本生成器；20 项测试只在新空模型按[验收索引段](references/validation.md)执行。代码保留缩进并移除示例隐含交互；New in 9 的内容不是 Rhino 8 契约。

只操作本任务 GUID，编辑另存新文件；不覆盖未保存工作。MCP 超时不等于未执行：保留状态，先查文档/结果，不重放、不切换接口重复修改，不杀用户进程；插件的异常撤销声明不能代替状态检查。

本工具只提供交互控制与小型确定性验收。大规模重网格、复杂布尔或离线渲染由调用工作流安排隔离进程与可中断预算；socket timeout 不会停止 Rhino 内核。

交付说明安装版本、进程内版本、实际接口、业务断言及产物回读。新版 IronPython 通过不能当作旧版本体实测，也不承诺任意拓扑一次成功。

<!-- managed-by: sparc3d-runtime -->
