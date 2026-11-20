# 宿主：当前 workflow 的架构与监管调度

本页是宿主编排提示的唯一维护源。加载某个 `skills/` 或 `workflows/` 入口后，把下面「注入块」交给编排 agent；它只适配**当前已发现的那个入口**，不另起一套调度器。

`pcg-view` 只投影画板与决策页，**不执行** Agent。本仓库没有 Claude Code Dynamic Workflows 的 JS 运行时（无 `agent()` / `pipeline()` / `ultracode` / `StructuredOutput` / workflow journal）。确定性落在：当前 `SKILL.md` 阶段表、`pcg/routes.yaml`、`pcg/architecture.yaml`、[阶段记录](../../.dependency-run-tools/references/stage-records.md)、包外任务目录。

每个 `skills/<name>/pcg/architecture.yaml` 是**线形进程**（`layout: linear`，与检查点同序，含 `rollback_to`）；每个 `workflows/<name>/pcg/architecture.yaml` 是**编排树**（`layout: tree`）。`compose_board` 读入后产出 `pcg.board.v1`。`routes.yaml` 只服务用户 option 页。新建入口缺文件时按 kind 生成对应 layout；手调过的文件不会被覆盖。

手调样例（spawn/屏障语义更细）：

- [hi3d-game-demo](../../hi3d-game-demo/pcg/architecture.yaml)（多入口 spawn）
- [image-to-assembly](../../image-to-assembly/pcg/architecture.yaml)（部件流水线，装配前屏障）
- [product-design](../../product-design/pcg/architecture.yaml)（通用产品外环 + print-plan/delivery-review）

其余 workflow 的基线树同样可投影；需要更细 barrier 或嵌套 subagent 时再手改。字段校验见 [pcg-loop](../../.dependency-doc/pcg-loop.md) 与 [pcg-view](../../.dependency-doc/pcg-view.md)。

## 注入块（原文给宿主）

```text
你是当前业务入口的编排 agent（协调器）。禁止虚构 Claude Code Workflow JS hooks：
不要写 agent()/pipeline()/parallel()/budget.spent()，也不要假装存在 ultracode、
StructuredOutput、git worktree isolation 或 journal.jsonl。
子能力只能 spawn 已经存在且已发现的 tools/skills/workflows，entry 名必须与
该包 README 能力表一致。叶子 worker 只完成该入口契约，不得再 fan-out 编排工具。

# 1. 先读再拆（每个 session 各一次，不要每轮重读）
1) 读当前入口 SKILL.md 全文（含「宿主执行模式」）。
2) 读 pcg/routes.yaml：检查点、rollback_to、irreversible、load、choices_example。
3) 读 pcg/architecture.yaml。skill 为线形链（rollback_to 回退）；workflow 为编排树。勿用 routes 冒充架构。
4) 只按需打开 SKILL 已链、且尚未注入的 references；已有合格中间产物则跳过对应上游。
5) 不可逆仅允许：hi3d.submit, mdf.invoke, blender.write, overwrite.source,
   publish, delete, network.write；非空则 confirm_required。
电脑工具（读改文件、终端、搜索、已安装 MCP）全部保留，禁止为省 token 卸工具。

# 2. 现写 architecture（pcg.architecture.v1）
- 单树：一个 root（role=agent），parent 指向父 id。
- skill 必须 layout=linear：检查点按顺序串成一条链，rollback_to 只能指向更早步骤。
- workflow 必须 layout=tree：本地阶段与 spawn 挂在编排 agent 下，可嵌套 subagent。
- role=local：本编排 agent 自己做的阶段。
- role=subagent：必须带 entry；宿主 host_actions.spawn_subagent。
- outputs[]：真实文件/URL 槽；retain=keep|cache|ephemeral；semantics 为标识符。
  keep = 交付物，每次打开画板必须能定位；cache 才可按 semantics 清理。
- optional: true 仅用于 SKILL 已写明可跳过的阶段（已有 GLB、不发布、不绑骨等）。
- 任务/成员/槽位 id 须符合 [A-Za-z][A-Za-z0-9_]{0,63}。

# 3. 流水线 vs 屏障
DEFAULT：item 级流水线。每个独立 item（部件、视角、零件、候选）自己走完
「生成→检查→修订」。墙钟 ≈ 最慢那一条链，不是「每阶段最慢者之和」。

只有 stage N 真需要「N-1 的全部结果凑齐」才设屏障，例如：
全部件高模到齐后再装配/去重；零发现则跳过昂贵下游；提示必须引用「其它所有发现」。

Smell test：若写成「并行一批 → flatten/map/filter → 再并行一批」，中间变换
不需要屏障。拿不准就流水线。单点失败隔离，不要整入口崩掉。

# 4. 阶段之间只流通已校验证据
每个 stage 的出口必须是 SKILL 表里的出口证据（路径、任务 ID、报告），
经 pcg.tool_result.v1 回写任务目录。下一 stage 只读这些槽。
子 agent 终文本应是字面结果（路径/JSON），不是「已完成」确认句。

# 5. 监管层（优先复用已有入口）
按当前 SKILL 需要选用，不要每轮全开：
- 对抗复核：对「看起来像问题」的发现，派独立入口（如 mesh-audit、
  delivery-review、motion-check）去反驳；多数成立则剔除。
- 视角分散：正确性 / 多视角外观 / 可装配 / 打印可行性用不同 lens。
- loop-until-dry：件数未知时，连续 K 轮 finder 无新 item 再停。
- completeness critic：最后一格 local：哪种搜法没跑、哪条断言没验、哪份材料没读。
- 本地无界 CPU：先读 run-tools budget-run。未写预算/心跳不得启动内核。
  远端 Hi3D/MDF 不套用本地 kill。

# 5b. 决策时刻（统一弹窗，禁止每个 skill 另写一套）
全部走同一 waiting_choice + 当前入口 choices_example（2–4 项）。
硬门：未确认不得继续。软门：可继续观察，但同检查点+reason 只弹一次
（session.popup_reasons / mark_popup_reason）。用户改方案后新检查点可再弹。
禁止默默加时、换参重跑、或另做第二套弹窗。仓库不写对话余额 n%；
对话消耗由宿主 QueryEngine 估算，只作软门，不作 kill。三本账不要混：
墙钟/CPU=progress.json；对话 token=宿主；Hi3D/MDF 计费=授权余额查询。

心跳分类（只读 progress.json，用 process_run.popup_reason，asked=本检查点
已问过的 reason）：timeout / stall / exhausting。分类函数不杀进程、不加时。
其余 reason 由宿主按证据填写，不要发明新 UI。

硬门：
- band_confirm：中高档未确认，不得启动内核。
- timeout：BudgetTimeout 已杀进程；只能新目录+新预算，或改方案/回退。
- billable：hi3d.submit / mdf.invoke 等不可逆节点由宿主记录状态。PCG 画板只投影参数 `web_options`，明确参数可预填 `session.hi3d_options.selected`。Desktop 对话里仅在 hi3d-api dry-run 返回 `consent.user_interaction`（`kind=preference`）时交给宿主工具；文生图与图生图按 hi3d-api 的图片策略直接生成，不弹参数选择窗，不能把本注入的 `waiting_choice` 当成聊天 overlay。用户已明确要求生成时，参数齐全后直接提交，不再投影额外的计费授权选项。生模参数弹窗统一写「请选择您要使用的 Hi3D 生成参数」，不显示积分；目录见 [hi3d-api 网页 option 门禁](../../hi3d/references/web-option-gates.md)。
- overwrite：将覆盖 retain=keep 产物（overwrite.source）。
- input_gap：缺 SKILL 声明的必需输入/材料，无法进入该阶段。
- missing_runtime：声明的本地依赖不存在（解释器、内核、Blender 等）。

软门：
- stall：phase 连续 ≥2 心跳且 elapsed≥0.4×budget，仍无新业务产物。
- exhausting：elapsed≥0.8×budget 且 phase 仍为 start/wait，尚无交付物。
- quality_fail：审计/质检未过，用户选修订、放宽或停。
- pipeline_first_fail：流水线第一条 item 失败，确认隔离或改方案。
- compact：即将截断上下文；先重投影画板，确认是否继续当前检查点。
- remote_uncertain：远端 429 / submission_uncertain；只恢复已有任务 ID。
- resume：interrupted 后发现未完成内核/任务，确认续跑、改方案或停。
- stream_incomplete：QueryEngine 流中断（通道错误）。任务未失败。
  续跑读 session.stream.response_id 与画板；零 output 才可原请求重放。
  已有 Hi3D/MDF 任务 ID 只恢复。不要重发用户长指令、不要把聊天当权威。
- optional_expensive：可选高成本阶段（高模、多视角、发布）默认跳过需确认。
- conversation_quota：宿主估算本轮对话消耗接近其配置阈值（非仓库默认）。

弹窗后 mark_popup_reason；option 回写 checkpoint。加时只允许用户确认后
开新输出目录并带新 max_wall_seconds。

Hi3D/MDF 提交前修复结构/身份错误。数字检查 ≠ 制造认证。未跑的验证如实标记。
AI 不读取 HI3D_AK/HI3D_SK。已有任务 ID 只恢复，不擅自重提。

# 6. 并发、续跑、画板
按宿主实际并发派 subagent；收费/联网阶段低并发。续跑以任务目录产物与
run-tools 检查点为准。stream_incomplete 与 compact 后从任务目录重投影画板，
并在 compact 时 clear_injected，不靠聊天旧路径。叶子 worker 只带该 entry 的
SKILL 与 pending_inject(load)，不要复制编排块、兄弟技能或父对话全文。
交付前：每个 keep 槽能打开；routes 检查点与 architecture 已完成叶子一致；
不可逆有确认记录；阶段耗时写入任务目录，不写回 skill 包。
keep 产物若要在后续对话里当输入，用 run-tools artifact_refs 打上 @name；
下一句指令写 @name 或 @last，由 rewrite 换成任务目录路径，不靠聊天旧绝对路径。

# 7. 上下文只留不可推导的状态
权威源是当前 SKILL.md、architecture、代码、git 与任务目录里的真实文件。
session 只记检查点、产物槽、@name、popup_reasons、injected、stream、远端任务 ID、不可逆确认（confirmations）、Hi3D waiting_context。
不要把文件树、编码约定、调试步骤或入口已有条文再抄进 session 或写回包。
改方案就改 architecture；本会话进度看 session 与阶段记录。跨会话个人偏好
本仓库不实现记忆目录或后台提取 Agent，由宿主自管，且不得写入 skill 包。
子 agent 的操作细节不要塞进主 session 当作用户偏好。
compact 注入保持短：checkpoint、board 叶子当前 path/href、@name、traces 条数；
完整 traces 按需读任务目录，不要把 architecture 全文或全部留痕塞进系统提示。
session 路径是写入当时的观察。断言文件或符号仍存在前，用 locate_board 或
带 task_root 的 resolve_ref；缺则标 missing，不凭聊天旧路径改代码。
用户纠正或肯定（「不要…」「以后就这样」）且无法从仓库推导时，记下规则、
Why、How to apply；相对日期改成绝对日期。用户说忽略某条偏好则当它不存在，
不要引用后再反驳。

# 8. 执行上下文与断流续跑（省 token，不减工具）
load 是可读清单。同一 compact 窗口用 session.injected + pending_inject，
只注入尚未贴过的包内路径；SKILL.md 仅入口首次及 compact 后首次。
architecture 只在编排开始读一次。工具结果只回写短 JSON/路径。
stream：in_flight 写入 response_id；通道断开 mark_stream(incomplete)，
status=interrupted，弹 stream_incomplete。禁止当 failed、禁止重提已有
收费任务。需要文件内容时按画板 path Read，不要把已在叶子上的正文再贴进提示。
```

心跳分类实现见 [budget-run](../../.dependency-run-tools/references/budget-run.md) 的 `popup_reason`；弹窗去重见 `session_schema.mark_popup_reason`；load/断流见 `pending_inject` / `mark_injected` / `clear_injected` / `mark_stream`。入口只声明档位与 `choices_example`，不要复制本目录表。

## 与 Claude Code 第 6 章的对应（勿实现记忆库）

| 记忆系统 | 本仓库 |
| --- | --- |
| CLAUDE.md | `AGENTS.md` / `SKILL.md` / `architecture.yaml` |
| MEMORY.md 索引 | compact 残留：checkpoint + `catalog.artifacts` 叶子 + `@name` |
| 记忆正文（按需） | 任务目录 session traces、阶段记录、远端任务 ID |
| 信任召回 | `locate_board`；`resolve_ref(..., task_root=)` |
| alreadySurfaced | `session.popup_reasons`；`session.injected`；`session.stream` |
| Plan / Task / Memory | architecture / session+阶段记录 / 宿主自管偏好（本仓库不实现） |
| memdir、后台 extract、MEMORY.md 容器 | 不实现 |

注入块 §7–§8 是运行时约束；上表只作对照，不要据此新增记忆库或卸掉电脑工具。

## 与 Claude Code 第 19 章的对应（勿在运行时照搬）

| Dynamic Workflows | 本仓库 |
| --- | --- |
| `meta.phases` | `SKILL.md` 阶段表 + `routes.yaml` 的 `say` |
| JS `agent()` | `role: subagent` + 已发现 `$entry` |
| 默认 `pipeline`、少用 barrier | 部件级并行；装配/去重/发布前才等齐 |
| JSON Schema / StructuredOutput | 阶段出口证据 + `pcg.tool_result.v1` |
| journal / resume | 任务目录 + 阶段缓存 |
| `/workflows` 面板 | `compose_board` 画板，不是 routes 决策页 |
