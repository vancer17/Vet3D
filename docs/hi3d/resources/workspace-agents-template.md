# 工作区 `AGENTS.md` 模板

## 资源名称、来源与模型可见性

`runtime/templates/AGENTS.md` 是 Hi3D Agent 1.2.11（Windows x64）随包发布的工作区指令模板。Runtime 的 `Uj` 读取并渲染模板，工作区注册表在创建目录时写入工作区根的 `AGENTS.md`。Runtime 启动时在 Codex app-server 启动前尝试刷新已登记工作区。随包 Codex 0.166.0 根据项目指令发现、目录可信状态、读取权限和字节预算，将渲染后的内容纳入模型上下文。该资源的模型可见正文见归档原件，含运行时占位符。正文作为项目指令进入上下文，没有独立的 Tool 注册名或 Tool `description`。 [归档原件](../upstream/1.2.11/archived-p0/resources/runtime/templates/AGENTS.md) · [Codex 项目指令实现](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/agents_md.rs#L51-L87)

## 输入、结果与副作用

| 模板变量 | 上游输入及渲染结果 |
| --- | --- |
| `ASSET_NAME` | 当前登记的工作区显示名。 |
| `BLENDER_BIN` / `PYTHON_BIN` | 宿主探测到的 Blender 与独立 Python 路径。各自缺失时替换为提示文字。Blender 运行自己的 Python 解释器。 |
| `PORTABLE_PATH_NOTE` | Windows 分支提示使用可迁移的相对路径。其他平台替换为空。 |
| `MACOS_EXTERNAL_APP_SANDBOX_NOTE` | macOS 分支补充 Blender 和 BambuStudio 的启动权限说明。其他平台替换为空。 |

渲染结果为 UTF-8 文本，指导目录与命名、建模选择、程序调用、模型版本登记、本地文件和网页交付。Windows Store 条件分支由宿主生成专用 Python 入口，存在该入口时还替换 Python 调用说明。普通 Windows 分支在此处使用探测得到的 Python 路径。模板提及的工具仍须由当轮宿主注册。 [本地执行](../tools/exec-command.md) · [模型版本登记](../tools/workspace-commit-model.md) · [Studio 状态](../tools/studio-get-state.md)

新建写入使用 `wx`，已有目标会使该写入失败。启动刷新逐项检查受管路径，拒绝符号链接，内容相同则跳过。需要更新时写同目录临时文件，再重命名替换并清理临时文件。刷新错误记录在宿主启动日志，其余工作区可继续处理。模板文件缺失或读取失败会使该次渲染失败。

## 权限、沙箱与前置 Hook

创建和刷新由 Runtime 使用宿主进程的文件权限完成。项目指令可以指导模型选择命令和请求权限。执行时的审批、沙箱、前置 Hook 仍由应用到该命令的 Codex 策略决定。是否实际进入特定轮次，需对照该轮输入和有效上下文。 [本地执行权限与 Hook](../tools/exec-command.md#权限沙箱与前置-hook)

## 中性示例与核查依据

**模板渲染示例。** 假设普通 Windows 宿主解析出以下值。创建时，Runtime 将 `AGENTS.md` 写入该工作区根目录。随后 Codex 从对应项目目录发现指令。

```text
ASSET_NAME = Demo Asset
BLENDER_BIN = C:/Tools/Blender/blender.exe
PYTHON_BIN = C:/Tools/Python/python.exe
```

已静态核对 Runtime `Uj`（原始文件零基字节偏移 `2473266`）、`refreshAgentsFilesAsync`（`2688340`）和启动刷新调用（`3111564`）。同版桌面日志记录了 `Workspace AGENTS.md` 启动阶段。刷新后的文件内容是否进入指定轮次、路径探测发生变化以及单项刷新失败时的实机表现仍需结合对应文件与轮次记录核对。 [安装包 Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) · [启动日志](<D:/download/.sparc3d-runtime/environments/prod/logs/desktop-20261115T032556Z-30688.log:19>) · [发行锁](../upstream/1.2.11/inventory/inventory.lock.json)
