# Hi3D Agent 的 LLM Tools

工具说明以 Windows x64 版 Hi3D Agent 1.2.11 的安装包快照为基准，本机复核使用 `D:/install/Hi3DAgent.__hi3d-transaction/resources/`。每份说明记录工具名称、模型可见描述、参数与结果、执行伪代码及核查依据。

| LLM Tool | 注册位置 | 职责 |
| --- | --- | --- |
| [`exec`](exec.md) | 随包 Codex 0.166.0 Code Mode | 在 JavaScript 中编排当前开放的工具。 |
| [`wait`](wait.md) | 随包 Codex 0.166.0 Code Mode | 按执行单元 ID 续查输出、读取终态或请求终止。 |
| [`exec_command`](exec-command.md) | 随包 Codex 0.166.0 shell 工具 | 在选定环境运行命令，Unified Exec 可返回可续接的进程 ID。 |
| [`write_stdin`](write-stdin.md) | 随包 Codex 0.166.0 Unified Exec | 按进程会话 ID 读取输出或发送输入。 |
| [`request_user_input`](request-user-input.md) | 随包 Codex 0.166.0 的独立函数工具 | 在 Plan 模式收集结构化答复，等待用户响应。 |
| [`request_user_input_async`](request-user-input-async.md) | 随包 Codex 0.166.0 的独立函数工具 | 提出问题后立即返回，用户答复按声明作为后续消息到达。 |
| [`hi3d_api`](hi3d-api.md) | Hi3D Runtime 动态工具 | 调用 Hi3D 图片及 3D 服务，管理已有异步任务。 |
| [`mdf_api`](mdf-api.md) | Hi3D Runtime 动态工具 | 同步调用桌面账号网格处理、自动绑定及图像分析服务。`invoke` 预检或提交，`download` 恢复已保存成功作业的下载。 |
| [`view_image`](view-image.md) | 随包 Codex 0.166.0 内置工具 | 将本地图片送入模型上下文。 |
| [`workflow_report`](workflow-report.md) | Hi3D Runtime 动态工具 | 读取或更新 Skill 工作流的计划、进度和产物归属。 |
| [`user_interaction`](user-interaction.md) | Hi3D Runtime 动态工具 | 通过宿主面板收集用户输入、偏好或授权。 |
| [`image_classification`](image-classification.md) | Hi3D Runtime 动态工具 | 记录建模任务的主体标签，供模型登记读取。 |
| [`workspace_commit_model`](workspace-commit-model.md) | Hi3D Runtime 动态工具 | 将指定的导出 GLB 登记为版本，返回新建或复用的版本身份。 |
| [`model_retry_prepare`](model-retry-prepare.md) | Hi3D Runtime 动态工具 | 为指定已登记版本创建或取回免费重试意图。 |
| [`skill_capture_suggest`](skill-capture-suggest.md) | Hi3D Runtime 动态工具 | 暂存可复用流程建议，由宿主在轮末评估是否发布。 |
| [`skill_draft_submit`](skill-draft-submit.md) | Hi3D Runtime 动态工具 | 校验并冻结当前工作区中的 Skill 草稿版本。 |
| [`studio_get_state`](studio-get-state.md) | Hi3D 桌面动态工具 | 读取 Studio 的加载身份和当前就绪状态快照。 |
| [`studio_load_revision`](studio-load-revision.md) | Hi3D 桌面动态工具 | 加载工作区内的版本并返回已确认的加载身份。 |
| [`studio_capture_view`](studio-capture-view.md) | Hi3D 桌面动态工具 | 截取当前 Studio 视口并登记截图产物。 |
| [`studio_arrange`](studio-arrange.md) | Hi3D 桌面动态工具 | 在 Studio 中执行摆盘并返回本次操作状态。 |
| [`studio_export_3mf`](studio-export-3mf.md) | Hi3D 桌面动态工具 | 打开 Studio 打印计划面板。 |

## 注册与可见性

Runtime 的 `Vg` 汇总九项动态工具，`tools/dynamicSpecs` RPC 返回这组定义。桌面 renderer 的 `S0e` 定义五项 Studio 动态工具。`thread/start` 先按名称读取桌面提交的定义，再合入 Runtime 定义，同名时以后者覆盖，将结果作为 `dynamicTools` 交给 Codex。此版本的 `thread/resume` 和 `thread/fork` 参数不包含 `dynamicTools`。已有线程实际可调用的工具以该线程的有效工具目录为准。Runtime 的定义汇总、目录 RPC 和线程合并分别位于 `runtime/dist/runtime.mjs` 零基 UTF-8 字节偏移 `2671153`、`2725778`、`3156636` 附近。 [Runtime 注册依据](mdf-api.md#核查依据) · [Studio 注册依据](studio-load-revision.md#核查依据)

动态工具可作为普通函数暴露，也可出现在 `exec` 的嵌套声明中，取决于本轮 Codex 工具路由。安装包定义、会话工具目录、模型可见声明和实际调用各有证据。留存 rollout 的 `session_meta.dynamic_tools` 记录线程目录，`additional_tools` 记录模型侧工具声明。具体工具是否被调用应读取结构化调用事件。 [本机 Code Mode 声明](exec.md#暴露给-llm-的描述) · [嵌套路由](exec.md#嵌套路由与结果交付)

Studio 动态工具以 `S0e` 内的五项定义为范围。通用编辑器随包带有内部检测 Worker、Smart Repair 和调用 `post-process-mesh` 的 Smart Decimate。1.2.11 的 `StudioHost` 挂载仅开放 `joint`、`arrange`，且未传入 `smartToolConfig`。可从 `app.asar` 的 `out/renderer/assets/index-CDPCug_K.js` 成员内零基字节 `1090971`、`3534907` 和 `4725587` 分别复核工具注册、Smart Decimate 请求和实际挂载。 [Studio 分派](studio-load-revision.md#执行与治理)

Codex 的 `request_user_input` 和 `request_user_input_async` 按 `DirectModelOnly` 暴露为顶层函数，由当前模式、模型能力及宿主支持决定可用性。它们的声明与调用入口独立于 `exec` 的嵌套目录。Runtime 的 `user_interaction` 使用宿主面板协议，参数和答复按原请求关联。桌面模型目录、外部另存等能力也有各自的 RPC 或 IPC。 [同步用户输入](request-user-input.md) · [异步用户输入](request-user-input-async.md) · [Code Mode 路由](exec.md#嵌套路由与结果交付) · [Runtime 交互](user-interaction.md)

## 动作、能力与执行入口

| 对象 | 可用条件与入口 |
| --- | --- |
| Hi3D 工具动作 | `generate_image`、`generate_3d`、`query` 和 `download` 等是 `hi3d_api` 的 `action` 值。其 `kind` 和 `settings` 按动作及输入组合校验。 [动作与参数](hi3d-api.md#参数与结果) |
| MDF 工具动作 | `invoke` 接受能力、输入文件和相应参数。`download` 按原账本恢复已保存的成功结果。两者共用 `mdf_api` 工具定义。 [参数与结果](mdf-api.md#参数与结果) |
| MDF 能力枚举 | `retopology`、`mesh-lod`、`auto-rig`、`watertight`、`check-printability` 等是 `invoke` 的 `capability` 值。`pose` 接收图片并输出人体二维关键点及可视化。以所选能力的输入、参数和结果契约为准。 [公开能力表](mdf-api.md#参数与结果) · [重拓扑请求与产物](mdf-api.md#retopology-的输入与产物) · [自动绑定请求与产物](mdf-api.md#auto-rig-的输入与产物) · [人体关键点](../upstream/1.2.11/prebuilt-skills/mdf-api/references/mesh-invoke-api.md#38-人体关键点pose) |
| Skill | `SKILL.md` 和随包参考给出选用条件、输入准备和执行约定，不注册同名 LLM Tool。`mdf-api` 提供公开网格服务契约，`rig-retarget` 提供绑定和动作适配的领域约定。工具可用性还取决于当前线程的工具目录。 [MDF Skill](../upstream/1.2.11/prebuilt-skills/mdf-api/SKILL.md) · [绑定 Skill](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) |
| Runtime 后端脚本 | `mdf_api.py` 是 `mdf_api` 的实现入口，由 Runtime 解析当前环境的已部署脚本后派发。 [MDF 派发](mdf-api.md#实现伪代码) |
| P0 已归档共享资源 | 提供工作区环境、可选 Blender 启动包装、本地进程预算、文件指纹和阶段记录。执行专项脚本时按调用方实际采用的入口查证。 [P0 索引](../resources/README.md) · [执行包装与计时](../resources/README.md#专项-blender-命令的执行包装) |
| P1 已归档共享资源 | 提供实际场景载入、局部或世界网格快照、预览、烘焙及权重和形变数值函数。通用回读由调用方选用，专项内部导入按发行映射和实际调用查证。 [P1 索引](../resources/p1/README.md) · [场景载入](../resources/p1/asset-scene.md) · [网格快照](../resources/p1/mesh-snapshot.md) · [权重数值函数](../resources/p1/skin-weights.md) |
| P1 选定对象导出函数 | `export_glb` 由 Blender Python 调用，接收明确对象和当前导出器选项；返回路径不验文件或质量，不登记版本。需要保留 skin／clip 的参数与静态 `service_rig export` 区分。 [参数、输出与失败](../resources/p1/glb-export.md) |
| P1 GLB 容器及尺寸函数 | `glb_clips.read_glb` 解析容器，显式同时模式可合并无冲突通道，不负责顺序拼片或动作语义。`glb_bounds.inspect` 计算受支持的静态节点／POSITION范围，不执行蒙皮；非空和最终世界范围有限性须另查。 [容器与合并](../resources/p1/glb-clips.md) · [静态尺寸及报告覆盖](../resources/p1/glb-bounds.md) |
| 随包 GLB 导入审计 CLI | `audit_models.py --input ... --output ...` 在 Blender 新场景逐件导入后写 `models[]`；它和路径辅助 `frame_runtime.py` 未列入 P0／P1 收据，不是 LLM Tool。报告无质量 `pass`，末尾覆盖写入且无输入／输出同址保护；动画只按其实际取样范围统计。 [参数、回读和失败](../resources/specialized-mesh-scripts.md#audit_modelspy-独立-glb-回读) |
| Studio 内部序列化与宿主保存 | 编辑器内部重新组包 GLB、`file:saveAs` 复制已有文件、`will-download` 回传磁盘终态均不是新增 LLM Tool，也不是 `studio_load_revision` 的工具动作。普通源文件无需登记版本；序列化、点击下载和复制完成有不同保证。 [参数、实现与待测范围](studio-load-revision.md#视窗导出与已有文件复制) |
| 随包几何脚本 | `rig-retarget/scripts/run.py` 分派 `prepare_mesh` 与 `service_rig` 等本地子命令。按命令契约读取实际工程和报告。需要单独检查几何时调用独立回读或测量入口。 [专项脚本索引](../resources/specialized-mesh-scripts.md) · [网格准备](../resources/specialized-mesh-scripts.md#prepare_mesh-网格准备) · [静态网格导出](../resources/specialized-mesh-scripts.md#rig-retarget-静态网格导出) · [独立 GLB 回读](../resources/specialized-mesh-scripts.md#audit_modelspy-独立-glb-回读) · [测量函数](../resources/specialized-mesh-scripts.md#mesh-audit-网格测量函数) |
| 随包骨架与权重脚本 | `make_profile` 写人形比例种子。`build_character` 导出初始权重 NPZ 或构建工程和 manifest；`weight_graph` 独立求解并写缓存和诊断。各名称由 `run.py` 本地分派。 [人形比例种子](../resources/specialized-mesh-scripts.md#make_profile-人形比例种子) · [构建与权重输入](../resources/specialized-mesh-scripts.md#build_character-权重输入接口) · [外部求解与回执](../resources/specialized-mesh-scripts.md#weight_graph-外部权重求解) |
| 随包单身体蒙皮 CLI | Blender 本地执行的 `service_rig inspect` 读取实际身体与 Armature，按指定帧段和网格局部高度写权重、绑定摘要及形变报告。部位语义与跨帧动作覆盖由调用方核对。 [参数、返回与失败](../resources/specialized-mesh-scripts.md#service_rig-inspect-单身体蒙皮检查) · [共享权重数值函数](../resources/p1/skin-weights.md) |
| 随包服务权重回迁 CLI | `service_rig bind` 检查实际服务骨架与目标身体的输入条件，随后迁移权重、保存新工程并报告姿势待验。调用需明确目标对象、空间与正的对齐容差。 [回迁参数与落盘](../resources/specialized-mesh-scripts.md#service_rig-bind-服务权重回迁) |
| 随包局部权重修订 CLI | `service_rig repair` 接收已绑定工程、实际身体及局部规则，校验网格、骨序和绑定矩阵后修订权重，保存新工程并原子替换单份 JSON；这不是工程／报告事务。报告只有改动统计、姿势待验与文件摘要，没有 `pass`，不自动重开或逐帧验收；规则不绑定旧权重、Action 或工程字节。 [参数、规则与落盘](../resources/specialized-mesh-scripts.md#service_rig-repair-局部权重修订) · [P1 数组函数](../resources/p1/skin-weights.md#repair_regions-局部数组修复) |
| 随包权重写回与保护函数 | `write_changed_weights` 只回写最终变化行，实际骨序及对象归属由调用方保证；`preserved_signature` 返回有限范围的属性签名。它们是同包函数，不是独立 LLM Tool，也不是单独的 `run.py` 命令。 [写回、签名及文件函数](../resources/specialized-mesh-scripts.md#service_rig-权重写回与保护函数) |
| 随包数值检查脚本 | `validate_blend` 打开已保存工程，按实际集合和帧范围写验收 JSON，报告可覆盖既有文件。 [工程数值检查](../resources/specialized-mesh-scripts.md#validate_blend-已保存工程的数值检查) · [P1 实际调用](../resources/p1/README.md#rig-retarget-的导入与调用) |
| 随包已有骨架 CLI | `rig_adapter` 由 Blender 本地执行。`inspect` 写骨架、休止矩阵和动作清单，要求新报告路径。蒙皮关联及变形按实际资产另验。`calibrate` 对符合门禁的 FK 骨架调整尾点和滚转并另存工程及报告。 [检查与调整](../resources/specialized-mesh-scripts.md#rig_adapter-已有骨架检查与调整) |
| 随包动作缓存 CLI | `run.py rig_adapter cache` 按输入 BLEND、确切 Armature、源帧区间和采样率求值，写新的 `rig-retarget-cache-v1` NPZ 与 JSON 报告。`run.py cache_bvh` 是依赖 Blender BVH 导入器的旧版缓存入口，结构和消费契约不同。这些名称是本地命令，不是动态 LLM Tool 或 MDF 能力枚举。 [求值缓存](../resources/specialized-mesh-scripts.md#rig_adapter-cache-求值动作缓存) · [BVH 兼容缓存](../resources/specialized-mesh-scripts.md#cache_bvh-bvh-兼容缓存) · [分派、摘要和计时](../resources/specialized-mesh-scripts.md#动作缓存的分派与共享函数) |
| 随包动作映射 CLI | `rig_adapter retarget` 接收匹配目标 rest 的配置与 v1 缓存，计算旋转和根位移，烘焙新 Action、另存并重开工程，再普通写 JSON 报告。`pose_qa_pending:true` 不是动作验收通过；缓存和配置身份、可选 IK 与失败落盘分别核对。 [参数、输出与失败](../resources/specialized-mesh-scripts.md#rig_adapter-retarget-动作映射与烘焙) |
| 随包映射与 Action 函数 | `retarget_math.retarget_samples` 返回内存四元数／根位移和诊断；`bake_action` 是会修改场景并返回 Blender Action 的内部函数。这些函数不是独立 LLM Tool，不能通过同名 `run.py` 子命令直接调用。 [计算与烘焙函数](../resources/specialized-mesh-scripts.md#retarget_math-与-action-烘焙函数) |
| 旧动作与 NLA 函数 | `motion.build_action` 消费旧 BVH 缓存及比例骨架配置，返回 Action；`sequence_actions` 先创建全部 Action 再组织 NLA。它们没有独立 CLI／报告，工程及 manifest 由外层 builder 保存，不具备通用 retarget 的完整门禁。 [配置、返回及保存边界](../resources/specialized-mesh-scripts.md#motionbuild_action-与-nla-编排) |
| 随包动作裁剪 CLI | `stage_ops clip` 经显式独立绑定包执行，只裁剪已有烘焙姿态并写新 Action／NLA，不做跨骨架重定向。候选须新路径，JSON 报告为覆盖写入，报告与输入／输出的隔离由调用方核对。 [参数、输出与覆盖](../resources/specialized-mesh-scripts.md#stage_ops-clip-已烘焙动作裁剪) |
| 随包场景盘点 CLI | 动画包的 `stage_ops inspect` 显式加载独立绑定包，按需列出场景与所选骨架朝向。报告可覆盖既有文件，调用方应先确定独立新路径并记录输入身份。 [参数、失败与复核](../resources/specialized-mesh-scripts.md#stage_ops-inspect-场景与朝向盘点) |
| 外部插件和 CLI | 以已安装版本的实际接口和平台支持为准。需要时从 `exec_command` 运行相应本地程序，长任务按调用方选用的预算资源执行。 [本地执行](exec-command.md) · [进程预算](../resources/process-run.md) |
| PCG 图与宿主状态 | `mdf.invoke`、`blender.write` 是 PCG 操作标签，`waiting_choice` 是宿主或会话状态。需要记录工作流时由 `workflow_report` 更新图。收集用户回答由 `user_interaction` 或已实现的宿主交互分支处理。 [工作流](workflow-report.md#参数与结果) · [交互](user-interaction.md#参数与结果) |

## 结果续接标识

| 标识 | 查询或恢复入口 |
| --- | --- |
| `call_id` | 关联一次模型工具调用及其回包。`wait` 的每次续查有自己的调用 ID。 [exec](exec.md#嵌套路由与结果交付) |
| `cell_id` | [`wait`](wait.md) 续查原 Code Mode 宿主中的执行单元。 |
| `session_id` | `exec_command` 返回此 ID 时，用 [`write_stdin`](write-stdin.md) 续读 Unified Exec 原进程。工程及报告等文件按实际产物核对。 [本地文件结果](exec-command.md#本地脚本的文件结果) |
| `requestId`（宿主交互） | [`user_interaction`](user-interaction.md#工具调用与宿主协议) 在当前 Runtime 内关联原调用和面板答复。沿原调用等待，跨进程恢复和交互终态须按实际记录核查。 |
| `jobPath`（Hi3D 生成） | [`hi3d_api`](hi3d-api.md) 的 `query`、`wait` 或 `download` 读取生成账本，依据其动作契约续查或下载。 |
| `jobPath` 和 `requestId`（MDF） | [`mdf_api`](mdf-api.md) 的 `download` 从原本地账本恢复已保存的成功响应。服务 `requestId` 用于对账。公开接口无网格作业轮询。 |
| `retryRequestId` | [`model_retry_prepare`](model-retry-prepare.md) 准备或取回免费重试意图，`hi3d_api.retry` 按该标识执行。 |
| `graphId`、`nodeId`（PCG） | [`workflow_report`](workflow-report.md) 返回图标识，更新阶段时接收当前图中的 `nodeId`。`resume` 按当前对话定位中断图，可提供 `skillName`，无需把 `graphId` 传回。 |

本地缓存的文件路径与摘要用于核对持久结果，不能代替 `cell_id` 或 `session_id` 查询运行状态。外层脚本完成、进程退出、缓存可解码、报告已落盘及产物通过验收分别取证。句柄失效或回执不明时先检查原进程和文件；重新启动命令不能视为对原进程的续接，文件级恢复能力以被调用程序的契约为准。`workflow_report` 可将 NPZ 与 JSON 作为 `file` 引用关联到当前图，但不校验其数组、动作或配对关系。 [本地文件结果](exec-command.md#本地脚本的文件结果) · [文件产物引用](workflow-report.md#参数与结果)

`.blend` 与配套 JSON 也可分别用 `kind:"file"` 引用；这不会登记 GLB 版本，也不冻结工程字节、解析 Action／NLA 或确认两份文件配对。通用 retarget 的新报告预检、普通 JSON 写入，旧 builder 的可覆盖 manifest，以及 clip 的默认 sidecar 都有不同契约。专项计时还可能在工程和报告完成后失败，不能仅看文件或单一状态推断整个执行成功。 [文件引用示例](workflow-report.md#调用示例) · [脚本写入边界](../resources/specialized-mesh-scripts.md#绑定脚本的文件与报告写入) · [专项计时](../resources/specialized-mesh-scripts.md#动作缓存的分派与共享函数)

`service_rig inspect` 要求新报告路径，完成数值检查但 `pass:false` 时仍先写报告再失败，前提错误则可能没有新报告。`service_rig repair` 要求新工程和新报告，工程先保存、报告随后原子替换；新路径预检不是并发锁，也不构成多文件事务。修订报告没有 `pass`，`pose_qa_pending` 固定为 `true`；可选专项计时还可能在工程与报告完成后追加失败。报告缺失或外层非零时先核查已有工程、报告及摘要，句柄失效后重新提交命令不能当作原进程续接。报告是否覆盖、是否有完整质量结论以及失败时保留哪些文件，均按具体脚本核对。 [单身体检查](../resources/specialized-mesh-scripts.md#service_rig-inspect-单身体蒙皮检查) · [局部权重修订](../resources/specialized-mesh-scripts.md#service_rig-repair-局部权重修订) · [报告及计时](../resources/specialized-mesh-scripts.md#绑定脚本的文件与报告写入) · [进程与文件结果](exec-command.md#本地脚本的文件结果)

两份本机 1.2.11 rollout 的 Code Mode 目录均包含 Codex 的 MCP 通用资源工具，同期能力记录为 `0 MCP tools`。Codex 在有 MCP server 或工具模式为 `CodeModeOnly` 时可提供资源查询入口。provider 工具则依据当前发现结果与工具可见性策略决定是否暴露。 [本机 Code Mode 声明](exec.md#暴露给-llm-的描述) · [Codex 注册条件](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/spec_plan.rs#L1276-L1292)
