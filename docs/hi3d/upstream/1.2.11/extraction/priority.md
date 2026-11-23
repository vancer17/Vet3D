# Hi3D 1.2.11 资源优先级与 P0 核查表

本表由[核查范围](priority.scope.json)、[抽离清单](extraction.json)和[发行锁](../inventory/inventory.lock.json)生成。完整交付路径、字节数、SHA-256 和源码映射见[机器可读清单](priority.json)。

P0 共 30 个交付路径，含 14 个原件候选和 16 个证据引用。所有路径相对 `resources/`。

## P0 能力入口

| 能力 | 原件入口 | 外部前提与宿主边界 |
| --- | --- | --- |
| 工作区启动与执行环境 | `runtime/templates/AGENTS.md`<br>`runtime/templates/config.toml` | Hi3D Runtime 宿主提供模板变量、工作区和确认服务<br>随包 Codex 0.166.0 读取生成后的指令和配置，宿主在启动时配置信任的 Hook |
| 受管资源安装与定位 | 由宿主承载 | Hi3D Runtime 读取预置清单并物化资源，完整宿主启动还检查 runtime/support/pcg_yaml.py 存在<br>工作流图解析需要实际入口的架构数据和调用环境，按选用条件另行复核 |
| 本地进程、写入边界与恢复 | `runtime/prebuilt-skills/.dependency-run-tools/scripts/config_runtime.py`<br>`runtime/prebuilt-skills/.dependency-run-tools/scripts/process_run.py`<br>`runtime/prebuilt-skills/.dependency-run-tools/scripts/checkpoints.py`<br>`runtime/prebuilt-skills/.dependency-run-tools/scripts/hi3d-edit-job.py` | Python 标准库<br>外部程序由调用方显式指定<br>进程组清理依赖 POSIX，Windows 默认处理直接子进程 |
| 阶段命令与执行记录 | `runtime/prebuilt-skills/.dependency-run-tools/scripts/stage_events.py`<br>`runtime/prebuilt-skills/.dependency-run-tools/scripts/timing.py`<br>`runtime/prebuilt-skills/.dependency-run-tools/scripts/stage_cli.py` | Python 标准库<br>调用方提供任务标识、输出目录和阶段回调 |
| 会话产物引用与短工具结果 | `runtime/prebuilt-skills/.dependency-run-tools/scripts/artifact_refs.py`<br>`runtime/prebuilt-skills/.dependency-run-tools/scripts/tool_result.py` | Python 标准库<br>调用方读写 PCG 会话并决定何时向模型注入内容 |
| Blender 脚本执行入口 | `runtime/prebuilt-skills/.dependency-blender-tools/scripts/execute.py` | 独立 Blender 提供 Python 与 bpy。调用方给出可信目标、导入路径和参数 |

## P0 精确文件表

直接本地依赖列给出静态核实的文件边。解释器、调用方传入的文件和宿主接口见能力入口表。

| 交付路径 | 用途 | 直接本地依赖 | 纳入依据 | 待验证或适用范围 |
| --- | --- | --- | --- | --- |
| `app.asar` | 证据引用 | — | 桌面发行归档锚点。可沿发行索引定位具体宿主实现和协议成员的字节及摘要。 | 需按具体行为定位和验证相关成员。整包只作为证据，实际调用范围依赖宿主。 |
| `runtime/codex/vendor/x86_64-pc-windows-msvc/codex-package.json` | 证据引用 | — | Windows x64 随包 Codex 的版本和入口记录，声明 0.166.0 及 bin/codex.exe，用于定位模板和 Hook 的实际宿主。 | 真实启用的工具与 Hook 以 app-server 启动参数、当前轮上下文和调用结果为准。 |
| `runtime/dist/runtime.mjs` | 证据引用 | — | 打包后 Runtime 主模块。分派预置资源检查与安装的 Ij 位于零基字节偏移 2448254。工作区和会话恢复、工具注册、登记等宿主行为由完整 Runtime 承载。 | 这项用于静态追溯。跨环境启动、安装刷新及失败恢复需要实际运行验证。 |
| `runtime/manifest.json` | 证据引用 | — | 随包 Runtime 版本与交付元数据，供关联安装副本、模板和主模块。 | 清单只提供发布身份，当前运行实例的有效配置和资源位置仍须由宿主确认。 |
| `runtime/prebuilt-skills/.dependency-blender-tools/REFERENCE.md` | 证据引用 | — | 上游 Blender 辅助能力的用法和范围，供定位包装器与隔离的实际执行入口。 | 渲染、网格和材质能力各自按被选入口与依赖验证。 |
| `runtime/prebuilt-skills/.dependency-blender-tools/scripts/execute.py` | 原件候选 | — | 第 2 至 5 行只导入 Python 标准库。设置指定脚本或模块的导入路径及参数后调用 runpy。业务目标的闭包以实际选用路径展开。 | 随包包装器已作为 Blender 离线检查入口使用。抽离后按选定 Blender 和目标脚本复测参数与退出码。 |
| `runtime/prebuilt-skills/.dependency-run-tools/REFERENCE.md` | 证据引用 | — | 上游 run-tools 能力入口，说明本地执行、阶段记录和会话脚本的选用场景。 | 入口列出的各 profile 和资料链接按需要逐项复核。 |
| `runtime/prebuilt-skills/.dependency-run-tools/references/artifact-refs.md` | 证据引用 | — | 上游对话产物别名契约，规定 @last、引用标记、会话文件和解析时对本地路径的核对。 | 需要 session fixture 验证缺失文件、非法路径和跨轮解析，并单独验证模型侧上下文。 |
| `runtime/prebuilt-skills/.dependency-run-tools/references/budget-run.md` | 证据引用 | — | 上游本地预算和心跳契约，区分脚本超时、宿主用户决策、计时和远端任务恢复。 | 心跳如何对应宿主选择界面属于宿主集成验证。 |
| `runtime/prebuilt-skills/.dependency-run-tools/references/desktop-runtime.md` | 证据引用 | — | 宿主实际提供相应动态工具时由 Skill 读取的桌面执行约定，说明工具路由、已存在文件复用、路径、确认和登记边界。 | 文档中的工具建议需要以实际 Runtime 注册和会话轨迹验证，宿主同步与授权行为另行复测。 |
| `runtime/prebuilt-skills/.dependency-run-tools/references/hi3d-edit-job.md` | 证据引用 | — | 上游编辑任务契约，记录路径写入边界、程序探测、完成复用、进程预算和中断。 | 调用方使用的外部程序、领域检查和运行方式需要按具体任务验证。 |
| `runtime/prebuilt-skills/.dependency-run-tools/references/local-runtime.md` | 证据引用 | — | 上游本地进程、检查点、阶段记录、显式配置及写入根接口说明，区分共享机制和调用方约定。 | 写入保护、日志、取消和缓存需随真实调用方的具体环境复测。 |
| `runtime/prebuilt-skills/.dependency-run-tools/references/stage-records.md` | 证据引用 | — | 上游阶段身份、尝试、耗时、事件和恢复的记录约定，明确区分实际执行时间和恢复等待。 | 仍须核对具体入口实际使用的记录类型及消费者。 |
| `runtime/prebuilt-skills/.dependency-run-tools/scripts/artifact_refs.py` | 原件候选 | `runtime/prebuilt-skills/.dependency-run-tools/scripts/session_schema.py` | 显式标记、查询和解析 PCG 会话的本地 @name 产物引用。第 10 行导入 session_schema.validate_session。 | 需要验证目标宿主在会话恢复后重新解析、检查确切文件并注入上下文。 |
| `runtime/prebuilt-skills/.dependency-run-tools/scripts/checkpoints.py` | 原件候选 | — | 分块计算 SHA-256，并按预期文件名及摘要只读核对本地缓存。 | 调用方仍须验证运行参数、输入指纹和缓存策略。远端任务续查使用服务自己的任务身份。 |
| `runtime/prebuilt-skills/.dependency-run-tools/scripts/config_runtime.py` | 原件候选 | `runtime/prebuilt-skills/.dependency-run-tools/scripts/path_safety.py` | 读取显式文件输入和配置，解析写入根。resolve_file_request 在第 49 行导入 path_safety.validate_write_roots。 | 需要按调用方真实输入、输出策略和平台验证。写入根预检之后的并发变化及事务处理由调用方负责。 |
| `runtime/prebuilt-skills/.dependency-run-tools/scripts/hi3d-edit-job.py` | 原件候选 | `runtime/prebuilt-skills/.dependency-run-tools/scripts/process_run.py`<br>`runtime/prebuilt-skills/.dependency-run-tools/scripts/path_safety.py` | 负责显式本地编辑任务的程序探测、写入根预检、指纹、预算、产物记录和完成复用。第 10 至 11 行导入 process_run 与 path_safety。 | 用实际外部程序验证主线程信号、跨平台取消和完成目录复用。领域产物质量由调用方验收。 |
| `runtime/prebuilt-skills/.dependency-run-tools/scripts/path_safety.py` | 原件候选 | — | 解析写入根，并通过只读检查拒绝与资源包或受保护输入重叠的路径。 | 并发变更、硬链接和具体派生文件约束仍需由执行层按选用场景验证。 |
| `runtime/prebuilt-skills/.dependency-run-tools/scripts/process_run.py` | 原件候选 | — | 执行本地子进程，支持合并日志、显式环境、墙钟预算和心跳。默认中断或超时回收直接子进程。 | Windows 多进程取消和具体工具行为尚待复测。POSIX 进程组路径由调用方显式启用。 |
| `runtime/prebuilt-skills/.dependency-run-tools/scripts/session_schema.py` | 原件候选 | — | 为产物引用提供 PCG 会话校验。另有产物槽、load 注入差集、缓存清理和 Hi3D 专有确认字段，均保留为上游实现证据。 | 脚本只提供上游会话数据操作。LLM 实际看到的内容、宿主会话和 Runtime 恢复须从宿主实现及真实会话验证。 |
| `runtime/prebuilt-skills/.dependency-run-tools/scripts/stage_cli.py` | 原件候选 | — | 本地阶段入口辅助模块，解析脚本参数并携带阶段结束退出码。 | 参数分隔和进程退出语义须结合选用的普通 Python 或 Blender 入口验证。 |
| `runtime/prebuilt-skills/.dependency-run-tools/scripts/stage_events.py` | 原件候选 | — | 输出 running 与终态的基础事件，使用单调时钟测量耗时，通过回调交由调用方关联并存放记录。 | 用真实调用方核对事件投递及取消、预算超时到其状态的映射。 |
| `runtime/prebuilt-skills/.dependency-run-tools/scripts/timing.py` | 原件候选 | — | StageRecorder 和 record_external_stage 维护有任务及尝试标识的包外阶段记录，对外部记录做结构校验。 | 采用时先固定实际消费者及复用记录的规则，并验证写盘中断和恢复。 |
| `runtime/prebuilt-skills/.dependency-run-tools/scripts/tool_result.py` | 原件候选 | — | 独立构造或校验短 pcg.tool_result.v1 字典，产物字段可交给 session_schema.apply_tool_result 消费。 | 调用方是否会采用这套结果协议及如何回写宿主会话尚待核对。 |
| `runtime/prebuilt-skills/.workflow-bundle.json` | 证据引用 | — | sparc3d profile 的物化路径、源码相对路径与部署 SHA-256 映射，供追溯来源和区分别名版本。 | 来源映射用于证据对账。资源闭包仍需核对具体入口的导入、配置和数据读取。 |
| `runtime/prebuilt-skills/prebuilt.json` | 证据引用 | — | 随包内置入口和文件 SHA-256 清单，供 Runtime 检查并安装对应资源。 | 安装戳复用、内容损坏和增量刷新行为需按真实宿主场景复测。 |
| `runtime/support/pcg_yaml.py` | 证据引用 | — | Runtime packaged 入口在安装预置 Skill 前用 gg 同时检查此文件和 prebuilt.json。Uge 调用随包 Python 解析预置 Skill 的架构 YAML。两处分别见 runtime.mjs 零基字节偏移 2444606 与 3044474。 | 此项只为还原完整 Hi3D 宿主的启动和解析要求。目标宿主是否采用 PCG 及实际模型可见性待验证。 |
| `runtime/templates/AGENTS.md` | 原件候选 | — | Runtime 的 Uj 渲染初建及启动刷新用的工作区指令，记录文件命名、建模路由、资源入口和外部程序位置。见 runtime.mjs 零基字节偏移 2473266。 | 需在目标宿主核对模板变量的供给、刷新时机和实际进入模型上下文的文字。 |
| `runtime/templates/config.toml` | 原件候选 | — | Runtime 的 Ya 渲染 CODEX_HOME 配置，包含模型服务、审批和沙箱基线、Skill 下发及 shell 环境过滤。见 runtime.mjs 零基字节偏移 2471192。 | 模型服务、变量注入、用户设置合并和实际生效的 sandbox 权限须在目标宿主分别验证。 |
| `runtime/templates/hooks/skill-credit.cjs` | 证据引用 | — | Codex PreToolUse Hook 使用 Node 的 node:http 向 Runtime 确认。显式处理拒绝、异常和超时。启动配置及信任检查见 runtime.mjs 零基字节偏移 3095138 与 3098083。 | 独立执行依赖宿主传入的内部 URL、授权参数与确认服务。后续如选用，再核实注入和撤销行为。 |

## P1 试点

以下文件从既有抽离试点顺延至建模与验收批次。

- `runtime/prebuilt-skills/.dependency-blender-tools/scripts/material_nodes.py`
- `runtime/prebuilt-skills/.dependency-texture-bake/scripts/cycles_device.py`
- `runtime/prebuilt-skills/.dependency-texture-bake/scripts/texture_bake.py`

## P2 延期候选

其余 2730 个候选等待能力选取或环境触发后再展开依赖。以下是已明确的延期入口。

- `runtime/templates/store-python.ps1` — Windows Microsoft Store Python 可执行入口，需宿主提供安装路径变量并定位 AppxManifest。
- `runtime/prebuilt-skills/.dependency-pcg-view/scripts/view_cli.py` — 画板与视图投影按产品需求另行选择，并展开目标架构数据和其本地脚本。
- `runtime/prompts/skill-install-review.md` — 仅在选用宿主的 Skill 安装审查流程时复核。
- `runtime/prebuilt-skills/.dependency-package-tools/scripts/bundle.py` — 源码工作树的独立能力包物化工具，待选定发布路径后复核。
- `runtime/prebuilt-skills/.dependency-package-tools/scripts/host-bundle.mjs` — 读取源码仓库 profile 与入口清单的桌面构建工具，待选定发布路径后复核。
- `runtime/prebuilt-skills/.dependency-run-tools/scripts/cli_schemas.py` — 仅在所选领域入口引用对应阶段 CLI 结构时展开对 stage_cli.py 的依赖。
- `runtime/prebuilt-skills/.dependency-run-tools/scripts/build_stage.py` — 按采用该构建阶段的消费者纳入，届时展开对 request_inputs.py 的依赖。
- `runtime/prebuilt-skills/.dependency-run-tools/scripts/frame_runtime.py` — 与 config_runtime.py 同源同摘要的物化别名，按选定调用方读取的确切路径纳入。
- `runtime/prebuilt-skills/.dependency-run-tools/scripts/profiles/print_kit_timing.py` — 专用于打印套件工作流的记录格式。
- `runtime/prebuilt-skills/.dependency-run-tools/scripts/profiles/portrait_reconstruction_timing.py` — 专用于人像重建工作流的记录格式。
- `runtime/prebuilt-skills/rig-retarget/SKILL.md` — 人形 T/A-Pose 绑骨和重定向，仅作流程参考，动物骨架与动作效果仍待验证。
- `runtime/prebuilt-skills/hi3d-model-gpt-animation/SKILL.md` — 人形模型动画交付编排，按所选动画和动物骨架路径另外复核。
- `runtime/prebuilt-skills/image-to-assembly/SKILL.md` — 整件拆件、人工装配和制造路线，按明确需求选择。
- `runtime/prebuilt-skills/motion-base/SKILL.md` — 机械底座、关节支架和打印造型，按对应交付需求选择。
- `runtime/prebuilt-skills/lamp-design/SKILL.md` — 灯具设计按专项目标启用，相关查看器、素材及设计脚本随实际需要审查。
