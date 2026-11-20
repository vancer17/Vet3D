# Hi3D 1.2.11 P0 资源归档

归档包含 14 个原件，路径按安装包 `resources/` 下的相对布局保存。归档收据绑定发行锁和优先级清单，记录每个原件的字节数、SHA-256 及 16 个证据引用。原件位于版本归档目录。 [归档收据](../upstream/1.2.11/archived-p0/archive.lock.json) · [P0 精确文件表](../upstream/1.2.11/extraction/priority.md) · [发行索引](../upstream/1.2.11/inventory/inventory.jsonl)

P1 的建模、预览与验收原件及其独立说明见 [P1 资源归档](p1/README.md)。

## 原件与独立说明

| 资源 | 用途 |
| --- | --- |
| [`AGENTS.md`](workspace-agents-template.md) | 工作区指令模板。 |
| [`config.toml`](codex-config-template.md) | Runtime 渲染的 Codex 配置模板。 |
| [`config_runtime.py`](config-runtime.md) | 参数、现有文件与写入根预检。 |
| [`path_safety.py`](path-safety.md) | 声明写入根与受保护路径的重叠检查。 |
| [`process_run.py`](process-run.md) | 子进程、日志、墙钟预算和心跳。 |
| [`checkpoints.py`](checkpoints.md) | 本地文件指纹和缓存产物检查。 |
| [`hi3d-edit-job.py`](hi3d-edit-job.md) | 本地编辑任务的执行及已完成结果复用。 |
| [`stage_cli.py`](stage-cli.md) | 阶段命令参数与退出信号。 |
| [`stage_events.py`](stage-events.md) | 阶段开始与结束事件。 |
| [`timing.py`](stage-timing.md) | 按尝试记录耗时、事件与摘要。 |
| [`session_schema.py`](session-schema.md) | 独立任务会话的结构和产物操作。 |
| [`artifact_refs.py`](artifact-refs.md) | 本地产物别名和引用解析。 |
| [`tool_result.py`](tool-result.md) | 短工具结果的构造和校验。 |
| [`execute.py`](blender-execute.md) | 后台 Blender 脚本或模块执行包装器。 |

每页链接到确切原件，并说明发现入口、模型可见性、参数、结果、副作用、权限和核查范围。原始模板和脚本按安装字节保留，说明页中的中性示例单独标注。

## 依赖闭包和隔离验证

本批直接本地依赖只有下列四条文件边。其余 Python 导入已核对为标准库。Blender 包装器的运行环境及目标脚本由调用方提供，目标自身的依赖随实际选用入口核验。宿主模板的渲染变量、Codex 和 Runtime 接口见对应说明页。 [声明的依赖闭包](../upstream/1.2.11/extraction/priority.json)

| 实际调用文件 | 同目录依赖 |
| --- | --- |
| [`config_runtime.py`](config-runtime.md) | [`path_safety.py`](path-safety.md) |
| [`hi3d-edit-job.py`](hi3d-edit-job.md) | [`process_run.py`](process-run.md)、[`path_safety.py`](path-safety.md) |
| [`artifact_refs.py`](artifact-refs.md) | [`session_schema.py`](session-schema.md) |

已用归档副本在 Windows 临时目录验证路径拒绝、文件指纹、直接子进程成功与非零退出、预算超时、编辑任务成功复用及修改产物后拒绝复用。还验证了阶段事件、阶段参数、耗时摘要、短工具结果交给会话和引用的解析与改写。归档 `config.toml` 已用标准 TOML 解析器读取。Blender 4.5.16 LTS 在后台以 `--factory-startup` 和 `--disable-autoexec` 运行归档包装器，目标夹具成功导入 `bpy` 并收到指定参数。完整宿主渲染、权限、跨轮注入和实际领域产物仍按说明页的边界验证。

## 专项发行中的调用证据

以下入口使用专项发行目录里的本地副本。其 SHA-256 与 P0 收据对应原件相同。通过各入口的导入和调用位置可以核对具体使用的函数。 [P0 归档收据](../upstream/1.2.11/archived-p0/archive.lock.json)

| 安装包入口 | 实际依赖与用途 |
| --- | --- |
| `head-lowpoly/scripts/run.py` | 使用 `process_run.run_process` 启动本地阶段。用 `checkpoints.digest` 计算摘要，只有阶段指纹与 `artifacts_match` 均通过时才复用已有结果。 [进程调用](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/run.py:14>) · [缓存判定](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/run.py:224>) · [进程与断点资源](process-run.md) · [摘要校验](checkpoints.md) |
| `.dependency-mesh-audit/scripts/fresh_review.py` | 通过 `stage_cli` 读取阶段参数及交付退出状态，通过 `checkpoints.digest` 将重开的实际文件与报告关联。选用该脚本时使用这些依赖。 [导入与回读](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/fresh_review.py:12>) · [阶段命令](stage-cli.md) · [文件摘要](checkpoints.md) |

四边通 Plus、基础四边面与面颈、尺度感知四边环、闭合四边过渡等 Skill 在长时间后台处理时指导调用 `process_run.run_budgeted`，用于墙钟预算、日志与心跳。确认与续接取决于相应 Skill 及宿主的有效交互。需要通用 Blender 启动包装器时可选用 `execute.py`。 [进程预算](process-run.md) · [Blender 包装器](blender-execute.md) · [四边通 Plus](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/quad-flow-plus/SKILL.md:192>) · [基础四边面与面颈](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/lowpoly-quad-face-neck/SKILL.md:67>) · [尺度感知四边环](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/scale-aware-quad-rings/SKILL.md:46>) · [闭合四边过渡](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/closed-quad-transition/SKILL.md:101>)

### 专项 Blender 命令的执行包装

`rig-retarget` 的随包调用示例由 Blender 直接加载 `scripts/run.py`，入口按子命令加载对应的 `rigging` 模块。`service_rig export` 通过 `bpy`、NumPy 和同包 `surface()` 读基础网格，直接调用 Blender glTF 算子，通过 `io_utils.file_digest()` 与 `atomic_json()` 写出文件摘要和报告。`io_utils.py` 来自 Skin Weights 资源，按发行映射物化到专项包，P0／P1 收据均未收录该文件。 [随包调用示例](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/runtime-service-rig.md#身体输入与服务交接) · [分派代码](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/run.py:31>) · [导出代码](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:127>) · [文件摘要与落盘](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/io_utils.py:10>) · [物化映射](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/package.json:3>)

`prepare_mesh` 直接使用 Blender `bpy`、`mathutils.Matrix`、NumPy 和标准库，先保存工作 `.blend`，再用 `Path.write_text()` 写 `.mesh.json`。准备分支的直接依赖限于这些模块，报告中的计数和归一化参数由其自身生成。P0 包装器、预算控制和摘要核对可由调用方显式接入。 [专项导入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/prepare_mesh.py:3>) · [准备报告落盘](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/prepare_mesh.py:118>) · [Blender 包装器](blender-execute.md)

`service_rig inspect/repair` 也可直接由 Blender 运行，实际数值使用 P1 `skin_weights`，路径、指纹、候选和报告由专项脚本处理。`repair` 先保存工程后用同包 `io_utils.atomic_json` 写报告；helper 可替换已有目标，CLI 的新路径预检不等于并发锁。P0 包装不提供额外场景回滚、旧权重版本绑定或动作验收，不能将其进程成功视为修订质量通过。 [检查参数](specialized-mesh-scripts.md#service_rig-inspect-单身体蒙皮检查) · [修订与失败](specialized-mesh-scripts.md#service_rig-repair-局部权重修订) · [写回及文件函数](specialized-mesh-scripts.md#service_rig-权重写回与保护函数) · [P1 数值入口](p1/skin-weights.md#repair_regions-局部数组修复)

| 资源 | 适用范围 |
| --- | --- |
| `AGENTS.md`、`config.toml` | 工作区和宿主上下文。模板提供 Blender 绝对路径和通用 `export_extras=True` 的单位标记约定。专项 `export` 的 glTF 调用未传 `export_extras`，单位和变换取证应读取实际文件及调用方记录。 [工作区模板](workspace-agents-template.md) · [Codex 配置模板](codex-config-template.md) · [专项算子调用](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:155>) |
| `execute.py`、`process_run.py`、`checkpoints.py` | 由外层按需选用，分别负责启动包装、子进程预算和缓存产物检查。`run.py` 不自动接入这三项资源。`make_profile` 可用标准库 Python 直接运行；`build_character`、`rig_adapter`、`cache_bvh` 和 `service_rig` 可由 Blender 直接启动，各自处理文件。单身体检查按所选对象及帧范围取证，回迁命令会写入权重并保存新工程。动作缓存不带采样断点或自动续写。 [Blender 包装器](blender-execute.md) · [进程预算](process-run.md) · [文件摘要与断点](checkpoints.md) · [本地构建](specialized-mesh-scripts.md#build_character-权重输入接口) · [已有骨架](specialized-mesh-scripts.md#rig_adapter-已有骨架检查与调整) · [求值缓存](specialized-mesh-scripts.md#rig_adapter-cache-求值动作缓存) · [BVH 缓存](specialized-mesh-scripts.md#cache_bvh-bvh-兼容缓存) · [单身体检查](specialized-mesh-scripts.md#service_rig-inspect-单身体蒙皮检查) · [服务权重回迁](specialized-mesh-scripts.md#service_rig-bind-服务权重回迁) |
| `timing.py` 与专项计时 | P0 `timing.py` 提供通用阶段记录。`rig-retarget/scripts/run.py` 仅在显式传入 `--timing-log` 时加载同包 `rigging/timing.py`，调用 `record_stage()` 追加 JSONL，由 `profiles/rig_timing.py` 物化。该专项文件与 P0 原件摘要不同，未列入 P0／P1 收据。日志只记录执行时间和完成／异常状态；追加失败可在产物已落盘后使命令报错，不提供产物摘要或验收。原脚本未检查日志与输入／缓存／输出／报告的重叠，调用方应使用独立日志路径，避免晚期追加破坏文件。 [通用计时](stage-timing.md) · [专项计时与分派契约](specialized-mesh-scripts.md#动作缓存的分派与共享函数) · [专项计时分支](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/run.py:38>) · [专项计时原件](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-run-tools/scripts/profiles/rig_timing.py:11>) |

Blender 4.5.16 LTS 隔离试验用 `run.py` 直接启动和 P0 `execute.py --script` 包装启动。`service_rig export` 的合成 GLB 字节一致，`prepare_mesh` 的合成 `.mesh.json` 内容一致。后者显式计时成功写出 `complete`，已存在输出路径时写出 `failed_or_interrupted`。这些验证覆盖本地命令、报告和计时。实际宿主轮次的有效工具权限、长耗时进程管理及生产资产表现仍待实测。 [静态导出合成回归](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_service_rig.py:14>) · [准备命令及计时](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/run.py:38>) · [P1 导入和回读资源](p1/README.md#rig-retarget-的导入与调用)

`rig_adapter cache` 用专项 `io_utils.file_digest()` 记录源文件和缓存 SHA-256，用 `retarget_math.rigid_matrices()` 校验求值矩阵。这两个文件均未进入 P0／P1 归档；其发行映射、安装原件摘要和调用契约见专项说明，不能用 P0 `checkpoints` 的契约代替。缓存 NPZ 先于 JSON 报告写入，报告采用同包 `blend_common.write_json()` 的普通写入，未调用 `io_utils.atomic_json()`。缺少报告或外层计时失败时，应保留已有文件并按摘要和可读性核查，不能据此推定脚本没有执行。 [分派与共享函数](specialized-mesh-scripts.md#动作缓存的分派与共享函数) · [缓存输出与失败边界](specialized-mesh-scripts.md#rig_adapter-cache-求值动作缓存) · [发行映射](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/package.json:3>)

`rig_adapter calibrate/retarget` 同样由 Blender 直接执行，外层 P0 包装和预算仍是可选。它们使用专项的载入、保护、映射计算和普通报告写入；目标工程摘要与源动作缓存摘要各自追溯，配置需另保。`retarget_math.py`、`blend_common.py`、`io_utils.py` 与专项 `rig_timing.py` 均未进入 P0／P1 收据，不能套用 P0 `checkpoints` 的缓存身份或原子报告保证。新路径预检不等于并发锁或完整工作区治理，保存工程、重开复验与写报告也不是多文件事务。 [动作映射契约](specialized-mesh-scripts.md#rig_adapter-retarget-动作映射与烘焙) · [计算与烘焙函数](specialized-mesh-scripts.md#retarget_math-与-action-烘焙函数) · [共享载入与文件函数](specialized-mesh-scripts.md#动作缓存的分派与共享函数)

`motion.build_action`、`build_character.sequence_actions` 是原比例骨架路线的本地函数，分别生成 Action 和组织 NLA；它们不是独立 LLM Tool，也没有通用 P0 执行账本。动画包的 `stage_ops clip` 是显式提供独立绑定包后运行的本地命令，复用 `blend_common` 载入、保存重开和普通报告写入。外层包装只能提供自身的进程或预算结果，不能改变这些接口的报告覆盖、已保存工程及内存修改边界。旧动作、NLA 与裁剪的参数和待实测项见各自说明。 [旧动作与 NLA](specialized-mesh-scripts.md#motionbuild_action-与-nla-编排) · [已烘焙动作裁剪](specialized-mesh-scripts.md#stage_ops-clip-已烘焙动作裁剪) · [显式绑定依赖](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d-model-gpt-animation/scripts/run.py:27>)

## 16 项证据引用

已复验下表每项安装包文件的字节数与 SHA-256。引用路径指向锁定发行或安装副本，收据中的 `evidence_references` 保存其相对路径。

| 证据 | 已核实 | 待实测或适用范围 |
| --- | --- | --- |
| [`app.asar`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) | 匹配发行锚点。桌面主进程和 renderer 的成员位置由发行索引记录。 | 真实桌面启动、图形界面和端到端交付。 |
| [`codex-package.json`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/codex/vendor/x86_64-pc-windows-msvc/codex-package.json>) | 记录 Windows x64 Codex 0.166.0 和发行入口。 | 当前轮的生效工具、权限和 Hook 以实际 app-server 和轮次记录核查。 |
| [`runtime.mjs`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) | 匹配发行锚点。已定位模板渲染、受管资源安装、Hook 配置和工作区交接分支。 | 完整宿主的启动故障、权限、刷新和恢复。 |
| [`runtime/manifest.json`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) | 锁定 Runtime 版本与发行身份。 | 实际运行实例的配置和已解析资源位置。 |
| [Blender 工具 `REFERENCE.md`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-blender-tools/REFERENCE.md>) | 记录后台 Blender 启动与 `execute.py` 的显式选包方式，脚本调用已做隔离复现。 | 其他 Blender 版本和选定业务脚本的文件及场景副作用。 |
| [Run Tools `REFERENCE.md`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-run-tools/REFERENCE.md>) | 依据上游索引核对阶段记录、运行预算和会话辅助入口。 | 具体 Skill 是否读取或调用某个入口。 |
| [`artifact-refs.md`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-run-tools/references/artifact-refs.md>) | 记录别名、槽位和会话文件语义，已验证合成会话中的解析和改写。 | 跨轮实际注入与目标宿主的真实路径约束。 |
| [`budget-run.md`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-run-tools/references/budget-run.md>) | 记录预算及心跳语义，已验证 Windows 直接子进程超时。 | 真实宿主弹窗、跨平台进程树取消和后续恢复。 |
| [`desktop-runtime.md`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-run-tools/references/desktop-runtime.md>) | 记录宿主可用时的动态工具、版本登记和产物交接约定。 | 目标轮次是否实际暴露及采用对应入口。 |
| [`hi3d-edit-job.md`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-run-tools/references/hi3d-edit-job.md>) | 记录探测、预算和复用，已验证合成任务复用与输出修改后的拒绝。 | 真实外部编辑器的取消、并发以及领域产物验收。 |
| [`local-runtime.md`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-run-tools/references/local-runtime.md>) | 接口与本地依赖已对照归档源码，路径与进程基本分支已隔离验证。 | 有效宿主沙箱、并发文件变更和调用方的输出约束。 |
| [`stage-records.md`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-run-tools/references/stage-records.md>) | 记录阶段和尝试身份的落盘格式，已验证合成尝试的事件及摘要。 | 硬中断、真实消费者及恢复关联。 |
| [`.workflow-bundle.json`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.workflow-bundle.json>) | 发行锚点，记录 `sparc3d` profile 的实际路径、源码映射和摘要。 | 其他 profile 或上游完整源码树的重建。 |
| [`prebuilt.json`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/prebuilt.json>) | 发行锚点，Runtime 以其校验和物化预置 Skill。 | 宿主对损坏文件、安装戳失配和增量更新的实际处理。 |
| [`pcg_yaml.py`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/support/pcg_yaml.py>) | 已定位 packaged Runtime 的存在性检查和预置 Skill 架构读取。 | 真实宿主的工作流可见性、解析失败及回退。 |
| [`skill-credit.cjs`](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/hooks/skill-credit.cjs>) | 已核对宿主信任和 loopback 分派。原 Hook 有同版模拟端点验证。 [执行 Tool 的权限证据](../tools/exec-command.md#核查依据) | 实际轮次的用户确认、授权撤销和逐工具触发。 |

## 复核或重建归档

从仓库根目录运行。命令重建并核对优先级输入，只读检查安装原件与证据，然后发布完整归档。目标已存在时逐项复核原件和收据，发现多余文件或字节差异即失败。 [命令入口](../../../scripts/hi3d/archive-p0.py)

输出目录须与版本下的 `inventory/` 和 `extraction/` 互不包含。示例使用两者的同级目录。

```powershell
$release = 'docs/hi3d/upstream/1.2.11'
python -B scripts/hi3d/archive-p0.py `
    --release-dir $release `
    --resources-root 'D:/install/Hi3DAgent.__hi3d-transaction/resources' `
    --output-dir "$release/archived-p0"
```
