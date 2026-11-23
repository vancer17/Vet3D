# 工具实现与服务契约导航

本目录详细记录 [`tools/`](repository-README.md#tools) 中的全部代码和功能，并导航到原子能力的服务契约及部署工作流。三层能力目录见 [仓库 README](repository-README.md)，维护流程见 [AGENTS.md](repository-AGENTS.md)。原子能力的单点契约在 `skills/`，端到端编排在 `workflows/`，本目录不重复维护其正文。

## 能力架构与使用关系

- [原子能力整合决策](capability-design.md)：三层构成、已采用的公共内核与保持独立的特异性实现；列出具体源码、目标契约和实际接入范围。只融合高度可复用部分，包级复用记录不能代替逐脚本/分支核对；新增候选与已采纳决策分别维护。
- [能力使用关系](capability-usage.md)：为每个 tool 和 skill 记录使用它的 skills/workflows，标出无使用记录及仅资料/交接的入口，同时记录 tools 间的关系和所有入口的来源证据。由工具生成，不能手工改表；检查器会拒绝缺入口或放错层级的能力目录，避免新增能力漏记。
- [Agent 循环衔接](pcg-loop.md)：skills/workflows 的检查点、load、不可逆权限、前端 option 与必填 architecture 执行拆解；新增/迁入时的详细阶段与产物要求由[根规则](repository-AGENTS.md#阶段架构与产物说明)维护。每轮 loop、compact 与流中断重投影画板；会话是任务目录里的进度索引（叶子路径须再探测），不是跨会话记忆库；`load` 按 `injected` 去重，`stream.incomplete` 可续跑。`waiting_choice` 弹窗由 [宿主编排注入](../.dependency-pcg-view/references/host-orchestration.md) 统一触发，心跳分类见 [run-tools 预算契约](../.dependency-run-tools/references/budget-run.md)。画板与决策图见 [pcg-view](pcg-view.md)。
- [显式交接声明](capability-usage-declarations.json)：补充文件物化无法表达的条件调用、契约与交接，以及需要排除的非调用说明。不是第二份安装依赖清单。

完整维护约束唯一存于 [AGENTS 的使用关系规则](repository-AGENTS.md#能力使用关系必须同步维护)。新增、修改、拆分、改名和删除三层能力时，同次更新来源、生成记录并通过检查；生成器与提交钩子的接口见 [package-tools](package-tools.md#使用关系索引)。本索引不把资料引用当作实际运行证明。

## 工具索引

| 工具或模块 | 代码 | 能力 | 详细文档 |
| --- | --- | --- | --- |
| blender-tools | [入口与实现](../.dependency-blender-tools/REFERENCE.md) | 后台 Blender、Cycles 设备选择/恢复、显式对象导入/保留、完整资产载入、原生依赖与分块帧渲染（产品 studio 归 model-preview） | [接口契约](blender-tools.md) |
| hi3d-api | [入口与实现](../hi3d/SKILL.md) | Hi3D API、账号请求关联头（X-Session-Id/X-Turn-Id）、工具包维护的 3D 参数面板、v2.0 原生档位 balanced/quality、v2.1 原生档位 fast/quality 与 v3.0 前端 quality/master 到原生 standard/quality 的映射、图片免弹窗及默认模型/AI 推荐比例/4000字符预算、生成前 Python 计数与超长精简、最终请求校验、单次提交、3D 免费重试次数查询与按原任务提交、图像调用失败不自动重试、成功后的质量迭代与脱敏原因摘要、任务恢复、调用方错误处理契约与内部错误码映射、失败状态同步、下载校验与共享网格检查适配 | [接口契约](hi3d-api.md) |
| mdf-call | [入口与实现](../mdf-api/SKILL.md) | MDF HTTP/SDK 调用、运行时与产物校验 | [接口契约](mdf-call.md) |
| package-tools | [入口与实现](../.dependency-package-tools/REFERENCE.md) | 显式依赖、独立安装包物化、使用关系生成/检查、pcg 入库（含缺 architecture 按 routes 补齐）与提交钩子 | [接口契约](package-tools.md) |
| pcg-view | [入口与实现](../.dependency-pcg-view/REFERENCE.md) | skill 线形回退进程、workflow 编排树、G6 流程图投影、产物目录、语义 cache 清理、routes 决策图（含宿主决策弹窗）与宿主编排注入提示 | [接口契约](pcg-view.md) |
| rhino-control | [入口与实现](../rhino-control/SKILL.md) | Rhino 5–8 安装/文件夹搜索、命令入口候选与应用控制、MCP 安装/调用、Python/桌面操作、跨版本脚本编写与预检、共用/差异正文及两级行号索引、紧凑批量检索、接口注意事项联读、平台分支/框架隔离与混合批量、几何验收 | [接口契约](rhino-control.md) |
| run-tools | [入口与实现](../.dependency-run-tools/REFERENCE.md) | 多输入路径保护、CLI、显式环境、阶段记录、内容校验、子进程恢复、包外会话产物留痕、对话 `@name` 引用、短工具回写、load 注入去重、流中断续跑、本地预算心跳杀进程与心跳弹窗分类 | [接口契约](run-tools.md) |

索引只列实际存在的工具或模块，按名称字母顺序排列；没有工具时保留表头。每项链接到 `tools/` 中对应代码和本目录中的详细文档。每个代码文件都必须归属一个有文档的条目，不遗漏内部辅助模块；同一模块内的函数可集中记录，无需每个函数单独建文件。

## 详细记录要求

按实际复杂度组织说明，覆盖该工具的全部代码文件、模块、原子函数与功能：

- **职责与原理**：说明解决的问题、适用范围、代码文件与职责的对应关系，以及从目标、不变量到实现的关键推导；只记录实际存在的机制。
- **函数与接口契约**：记录各原子函数和功能入口的位置、用途、参数、类型、默认值、单位或坐标约定、返回值与输出格式，以及必要前提和不变量。
- **依赖与组合**：说明运行环境、安装或导入方式、配置来源、模块调用关系及 skills/workflows 如何独立接入。工具实现由 `tools/` 唯一维护，共享资源按显式清单物化；调用方不另存维护副本，也不依赖作者的工作目录。
- **副作用与失败边界**：说明涉及的文件、网络、进程或应用状态变更，以及错误表现、资源清理、覆盖、幂等和重试规则；不适用的机制不必展开。
- **调用与验收**：给出最小可运行示例、预期结果、关键边界的验证方式及已验证环境；有局限或未验证项时明确记录。
- **迁移来源与调用方**：迁入或提取工具时记录可核实的来源版本或协议快照、保留的必要能力、重要排除项及受影响 skills/workflows 的交接契约。区分离线模拟与真实服务验证；不复制源凭据、账户记录或历史执行日志。原子实现与业务编排分别链接到所属 skill/workflow，不移入本目录重复维护。

详细是覆盖完整且足以正确复用，不是复制源码、堆积逐行注释或执行历史。共用约定只维护一份并相互链接；业务端到端流程留在 `workflows/`，原子能力实现与说明留在 `skills/`；工具操作说明留在 `tools/<tool-name>/references/`，完整工具代码契约在本目录。工具入口若引用 doc，分发时必须提供对应文档并保留有效路径，不能把缺少文档的单目录复制称为完整安装。

## 同步规则

所有提交（包括纯文档、配置和资源）都须先按 [前置比较与关联维护](repository-AGENTS.md#先理解再修改) 核对当前约束、三层标准和已有实现，确认正确目录与唯一维护源后再整合，按该规则同步共享实现的阶段缓存/源码指纹；本节是文档方面的具体同步要求。

每次新增、修改、重命名或删除工具代码及功能，都同步本索引、对应文档和代码链接，并复核受影响的 skills、workflows 及根 README 能力描述。代码与文档进入同一 commit；提交与推送按 AGENTS 及用户明确例外执行。提交前逐个核对 `tools/` 中的代码文件和功能均有准确记录，示例与实际接口一致，索引无遗漏、重复、过时条目或失效链接。

根 README 的 Tools 表与本索引分别维护：前者按 `tools/*/SKILL.md` 列出可调用的通用工具入口，后者覆盖这些工具包内的全部代码，包括不单独设入口的辅助模块。不得将原子 Skills 或端到端 Workflows 列表合并进工具索引，或以此索引替代根 README 的三类能力表。

根 README 开头的 Doc 表是文档阅读入口：创建或迁入任何三类入口前，按 [开发前必读规则](repository-AGENTS.md#先理解再修改) 完整阅读当前 [hi3d-api.md](hi3d-api.md)，并按 [新增前阅读、复用与经验保留](repository-AGENTS.md#新增前阅读复用与经验保留) 完成能力入口全文阅读：新 skill 先读全部 tools，新 workflow 先读全部 tools 和 skills。相关实现与参考资料再按需深入读取；每次文档变化同步摘要、链接和排序。

完善已有能力时，遵循上述唯一规则源中的第一性原理与经验保留要求；允许补充、整合、描述重组，不能靠大量删除已有 tools/skills 经验完成去重。全文改写也需保留有效的适用条件、参数、失败修复、兼容性和验收细节，并同步所有受影响文本与引用。

外部服务的完整契约默认由 `skills/service-select/references/mdf/` 维护；mesh-watertight 的调用与完整契约由 `tools/mdf-call/references/mesh-watertight.md` 唯一维护，service-select 通过 package.json 物化同一文件。`doc/mdf/` 保留导航，共用约定链接到唯一能力包，服务名称、功能及输入输出速查在 `mdf_list.md`；不凭服务文档新增工具索引行。固定来源版本，分清调用方参数与服务端完整输入输出，保留影响调用的边界。

能力目录与速查面向直接使用：每个服务都写明能做什么、传什么、返回什么；只补充必要参数分支和详情链接。单次诊断报告、具体请求 trace ID、参数校验过程、抽样方法、探测日志、证据哈希及执行历史保存在仓库外的任务目录，不写入任何仓库文件或 commit 正文；精简时保留全部服务与必要参数，并同步移除失效引用。记录要求中的验收方法指可复用的使用契约，不要求保存每次维护的检查过程。

`.gitkeep` 仅用于保存空目录，不属于工具代码，不加入索引。

Desktop 子模块、公开入口白名单与隐藏依赖分发见 [package-tools](package-tools.md#desktop-平面分发与子模块)；账号图像/3D、公开 mesh/invoke 与受管状态分别见 [Hi3D](hi3d-api.md#账号-runtime-backend)、[MDF](mdf-call.md#账号公开-meshinvoke) 与 [运行约定](run-tools.md#受管-desktop-执行)。

Roblox 领域文档在其唯一能力源维护：[制作流程](../create-roblox-game/SKILL.md)、[发布](../pub-roblox-game/SKILL.md)、[接口与官方资料](../roblox-api/SKILL.md)。三入口纳入 desktop profile；实际宿主安装/发现需另验，不把物化成功当作线上发布。

Steam 创意工坊文档在其唯一能力源维护：[文件对齐](../steam-mod/SKILL.md)、[发布](../pub-steam-mod/SKILL.md)、[ISteamUGC](../steam-ugc/SKILL.md)。三入口纳入 desktop profile；正在运行的宿主要重启 Runtime 后才会按新白名单重装。
