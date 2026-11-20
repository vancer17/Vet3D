# 独立依赖打包

输入为 --repo、--entry（可重复）或 --all 和全新的 --output。Python 3.9+ 标准库；不导入目标脚本、不调用外部进程/网络、不安装软件。输出为包含三类能力及必要文档的完整分发目录，各入口保留 SKILL.md 与其物化后的内部文件布局；跨包文档引用仍需保持有效，不能把单个子目录可执行等同于资料完整或宿主已安装。

package.json schema 1 的 files 为包内相对目标路径到仓库唯一源的映射，requires 为独立调用依赖名称。inventory 检查重名；dependency_order 检查未知名称和环；source_file/package_files 拒绝缺失资源、遍历、符号链接和本地文件覆盖。build 还纳入共享文件来源包和本地 Markdown 引用涉及的能力包，文档关联不使这些入口自动成为执行阶段；随后在外部临时目录准备，以排他创建声明全新输出，最后发布 bundle.json 完成标记；失败清理自身临时目录。复制的共享文件只属于生成物，不成为第二维护源。

[AI 入口](../.dependency-package-tools/REFERENCE.md)与 [独立安装](../.dependency-package-tools/references/usage.md)定义调用方式。

## 模块与接口

### scripts/bundle.py

[唯一实现](../.dependency-package-tools/scripts/bundle.py)。 Materialize explicitly declared skill dependencies into a new standalone distribution.

| 接口 | 参数 | 职责与失败边界 |
| --- | --- | --- |
| `safe_relative` | `value` | Validate one portable relative file path, rejecting traversal and absolute paths. |
| `source_file` | `repo, relative` | Resolve a regular, non-symlink repository file; reject every symlink component. |
| `inventory` | `repo` | Return global name → category/name, rejecting ambiguous discovery names. |
| `read_manifest` | `repo, owner` | Read explicit materializations and runtime dependencies; unknown schemas fail. |
| `package_files` | `repo, owner` | Return destination-relative → canonical source map; no shadowing local files. |
| `dependency_order` | `repo, names` | Topologically expand explicit dependencies; cycles and unknown entries fail. |
| `rewrite_links` | `text, source, destination, files` | Relocate local Markdown links in materialized docs, preferring local aliases. |
| `build` | `repo, names, output` | Write all selected entries and declared dependencies atomically to a NEW output.  Output must be outside the source repository. Existing output is never replaced. Canonical files remain unchanged; materialized copies are disposable build products. |
| `main` | `argv=None` | 按上述模块契约执行；显式输入，错误向调用方传播。 |

## 验收方法

仅在仓库外的独立包和合成输入上运行。校验参数错误、输出保护、正常结果及失败传播；记录工具不通过真实任务补统计，Blender 工具不在未保存的前台工程测试，依赖打包不修改已安装目录。验证记录保存到任务目录，不将一次测试当作全部业务/线上服务的验收。

## 离线测试接口

[tests/test_bundle.py](../.dependency-package-tools/tests/test_bundle.py) 覆盖独立物化后隐藏源树仍可调用；覆盖、越界、缺失/循环依赖、符号链接、凭据文件排除与文档链接重定位。测试只使用合成数据；通过物化包的 `python -m unittest discover -s tests -v` 运行。

`credential_path(parts)` 只检查文件名片段，排除 `.env`/`.env.*`、`.secrets` 与 `credentials.json`；不读取内容。隐式遍历跳过这些文件，显式物化此类路径则报错。

部分入口分发时，README 仅列实际打包的能力；`optional_doc_links(text, destination, directory)` 将 doc 镜像中未打包的可选来源链接转为明确的源仓库路径提示，避免伪造已安装入口。运行包内链接不使用此降级，缺失的实际依赖仍须修复。对应部分分发行为由 test_bundle 验证。

## 使用关系索引

[scripts/usage.py](../.dependency-package-tools/scripts/usage.py) 复用 `bundle.inventory/package_files/read_manifest/source_file`，为显式指定的源仓库生成 [能力使用关系](capability-usage.md)。Python 3.9+ 标准库；不导入被盘点的代码、不读取凭据、不联网、不执行 Blender 或业务阶段。不修改 `bundle.py` 的安装或依赖语义，也不将整个源仓库作为普通 skill 执行的隐式前提。

```bash
python3 "$PACKAGE_TOOLS/scripts/usage.py" --repo "$REPO" --write
python3 "$PACKAGE_TOOLS/scripts/usage.py" --repo "$REPO" --check
```

`--repo` 必填；`--write/--check` 必须二选一。目标是包含三层入口、各入口 `package.json` 及 `doc/capability-usage-declarations.json` 的源仓库，不能把部分分发包当作完整使用统计。调用脚本可位于独立物化包，数据始终从显式 `--repo` 读取。`--write` 重写 `doc/capability-usage.md`，并在 skills/workflows 缺少 `pcg/architecture.yaml` 时按 kind 补齐 linear/tree（不覆盖已有文件）；`--check` 不写文件，缺失或过期返回 1；成功返回 0 和入口/关系数量及 `pcg_entries`，不代表业务验证成功。文件错误、路径/符号链接错误、未知入口、无效声明、证据变化及 skills/workflows 缺少合法 `pcg/` 都失败，不生成“看似完整”的部分结果。tools 若出现 `pcg/` 也失败。

### Agent 循环衔接入库

[scripts/pcg_check.py](../.dependency-package-tools/scripts/pcg_check.py) 由 `usage.update` 调用，用 [pcg_yaml.py](../.dependency-package-tools/scripts/pcg_yaml.py) 解析 `pcg/routes.yaml`；skills 的 architecture 必须 `layout: linear` 且与检查点同序，workflows 必须 `layout: tree`。缺文件时 [pcg_architecture.py](../.dependency-package-tools/scripts/pcg_architecture.py) 按 kind 从 routes 生成（`hi3d.submit`→`hi3d-api`、`mdf.invoke`→`mdf-call`、`publish`→`game-deploy`），不覆盖已有文件。`usage.py --write` 与 `pcg_check.py --write-missing-architecture` 走这条补齐路径；`--check` 只校验。完整字段与不可逆枚举见 [pcg-loop](pcg-loop.md)。`check_repository(repo)` 返回已校验的 skill/workflow 数量；`main` 提供独立 `--repo` CLI。

生成器依据 routes 的检查点、路由、标签和不可逆标志构造初稿，不分析业务脚本，也不能推导真实产物格式与交接。默认生成的 `outputs` 标签及保留策略需要维护者核对；缺文件已补齐或 `--check` 通过不表示详细流程已完成。新增、迁入和流程修订的交付要求统一见[阶段架构与产物说明](repository-AGENTS.md#阶段架构与产物说明)。

### 数据与关系口径

| 类型 | 唯一来源 | 使用边界 |
| --- | --- | --- |
| Q 必需入口 | `package.json.requires` | 显式声明的独立调用依赖；不从文字引用自动加入 |
| C 代码物化 / F 资料物化 | `package.json.files` | 跨入口源文件到包内目的路径；`.py/.js/.mjs/.ts/.sh` 为代码，其余为资料/资产，包括测试资源。仅说明包复用，不证明实际调用整个 skill |
| R 文档引用 | 三层包内自有 Markdown 的相对链接 | 使用 bundler 的简单行内链接语法；物化别名解析回唯一源。保留指向的来源，不把比较链接当作运行依赖，不再次递归扫描物化副本 |
| A 条件调用 / K 契约使用 / H 下游交接 / I 间接交接 / X 非调用 | `doc/capability-usage-declarations.json` | 人工按原文判断；X 排除于反向使用表，其余保留类型和证据。示例、来源与“由某工作流调用本能力”不倒置为当前能力调用该工作流 |

声明 schema 1 的 `relations` 数组中，每项提供 `consumer`、`provider`（全局入口名称）、`kind`（`call/contract/handoff/indirect/context`）、`evidence`（使用方所属 Markdown 的仓库相对路径）、`quote`（该文件中原样保留且包含目标入口名的片段）。保留必要触发条件；同一 consumer/provider/kind 不允许重复，支持同一对入口有不同关系。文件物化和已有链接不在声明中重复手抄；真实独立调用即使同时有文档链接，仍可明确补充调用类型。新增独立调用的维护要求见 [根规则](repository-AGENTS.md#能力使用关系必须同步维护)。

`collect` 先检查入口布局：三层目录的能力子目录必须有 `SKILL.md`，入口不能直接放在层根，也不能作为自有或物化文件嵌套在另一个包内。缺少入口文件或放错层级直接失败，避免 `*/SKILL.md` 未发现的新增能力被静默遗漏；缓存和凭据目录名沿用 bundler 的排除规则，不读取其内容。

随后检查全部包内 Markdown 中出现的已知完整入口名均已有映射、链接或显式分类，避免入口以裸名称补充依赖后遗漏。检查器不理解自然语言，也不能发现没有名称/声明的动态调用或证明证据分类正确；需结合代码审阅。表不自动递归展开传递依赖：旧兼容层可能形成包级引用环，不能据此认定原子算法循环或所有阶段必须执行。

名称覆盖按 consumer/provider 这对入口聚合：已有一个映射、链接或声明即可覆盖该名称，不逐次判断每一处提及是否为新调用。C 边也只证明文件物化，不能证明包内每个脚本或旧配方都调用它，更不能证明没有残留手写实现。新增调用仍须按原文维护实际类型；复用是否完整按 [逐脚本和分支核对要求](repository-AGENTS.md#按第一性原理优先完善唯一维护源) 人工检查，不能以 `--check` 通过替代。

生成文档同时分类无 skill/workflow 使用记录、只有资料/契约/交接、以及仅 skill 使用而无 workflow 直接记录的入口。X 和仅由 tools 发起的边不解除第一类标记；孤立标记不阻止合法独立能力提交。C/Q/A 也不是执行成功证明，资料型能力需核对真实执行说明，不能为消除标记伪造调用。使用关系测试覆盖这些类别之间的变化。

### 模块与原子函数

| 接口 | 输入 → 输出及失败行为 |
| --- | --- |
| `named_entries(text, entries)` | 文本、当前完整名称集合 → 精确名称提及集合；仅用于覆盖，不推断调用 |
| `collect(repo)` | 显式仓库 → `(entries, edges)`；边按 consumer/provider/kind 合并并保留证据。检查完整的直接子目录入口、拒绝层根/嵌套入口，再校验全局名称/frontmatter、清单来源、别名链接和声明；自引用不计使用方；缺失、重复、过期或未分类即异常 |
| `cell(text)` | 来源文本 → 转义后的表格内容，防止证据中的 Markdown 链接被误解为文档相对路径 |
| `integration_status(entries, edges)` | 为每个 tool/skill 分类来自 skills/workflows 的使用方、C/Q/A 来源及 workflow 直接记录；排除 context 和仅工具使用，区分无使用记录与仅资料/契约/交接，不推断执行成功 |
| `render(entries, edges)` | 已校验数据 → 确定排序的 Markdown；为每个 tool/skill 生成反向行，为全部三层入口生成证据，零使用方不遗漏 |
| `update(repo, write=False)` | 收集与渲染结果 → 校验/更新固定文档和数量摘要，并校验 pcg sidecar；`--write` 还补齐缺失的 `architecture.yaml`。禁止符号链接输出，check 模式不写文件 |
| `architecture_from_routes(name, kind, routes)` | 入口名、kind、已解析 routes → 入库格式的 `pcg.architecture.v1`；skill 为 linear 链，workflow 为 tree；检查点 id 与根 id 冲突则失败 |
| `ensure_missing(repo)` | 为缺少 `architecture.yaml` 的 skills/workflows 按 kind 写入 linear 或 tree；已有文件跳过 |
| `main(argv=None)` | 显式 CLI → 退出码及 JSON 摘要；参数错误由 argparse 返回 2，输入/文档错误返回 1 |

### 仓库提交钩子

[hooks/pre-commit](../.dependency-package-tools/hooks/pre-commit) 是 POSIX shell/Python 3/Git 的本地维护入口。读取 Git 状态；若 tools/skills/workflows/doc、根 README/AGENTS 有未暂存修改或未跟踪文件则失败，避免用工作树中生成的记录掩盖不完整暂存快照。相关修改全部暂存后运行 `usage.py --repo . --check`（含 pcg 入库），失败阻断提交。它不自动暂存、提交、修改 Git 配置或执行能力；安装约束由 [AGENTS](repository-AGENTS.md#能力使用关系必须同步维护) 唯一维护。独立打包不会自动启用钩子。

Git 钩子不会随 clone 自动启用，也不是服务器分支保护。无既有自定义钩子时，在源仓库显式执行 `git config --local core.hooksPath tools/package-tools/hooks`；已有钩子应串联并保留。远端 CI 可复用相同 `--check`，是否强制由该仓库实际托管/保护设置决定。

### 验收

[tests/test_usage.py](../.dependency-package-tools/tests/test_usage.py) 使用临时合成仓库检查代码/资料/引用类型、全量与零使用方、新增能力/改依赖后的漂移、缺入口文件和层根/嵌套入口（含物化副本）、裸名称遗漏、过期/重复证据、删除/未知目标、别名、包级环、符号链接与提交快照；布局错误在写入前失败并保留旧索引，代码样例不会被导入。钩子测试在临时 Git 仓库验证拦截和检查转发，不产生真实提交。[tests/test_pcg_check.py](../.dependency-package-tools/tests/test_pcg_check.py) 覆盖 YAML 往返、tools 禁止 sidecar、不可逆确认、option 按钮、architecture 必填与缺文件按 routes 补齐。与 `test_bundle.py` 一起在物化后的 package-tools 包运行 `python3 -m unittest discover -s "$PACKAGE_TOOLS/tests" -v`；单次结果保存在仓库外。

## Desktop 平面分发与子模块

[host-bundle.mjs](../.dependency-package-tools/scripts/host-bundle.mjs) 以 Node 22+ 标准库执行，无 Python/npm 包、安装器或网络依赖。输入 --repo、全新外部 --output、--profile（默认 sparc3d）；[profile](../.dependency-package-tools/profiles/sparc3d.json) 只声明宿主展示入口和安装别名，物化依赖仍唯一来自各包 package.json。

schema 1 新增可选 profiles.<name>.files（目标路径→唯一源码；在这个显式模式允许覆盖通用映射）和 remove（仅该分发排除的目标路径）。普通 bundle.py 默认不选 profile，保留原三层分发及公共/内部行为。read_manifest 同时校验 profile 源，使用关系索引同时记录 profile 的跨包边。

safePath/source/files 校验便携相对路径、逐级非符号链接、凭据名排除和资源；buildHost 盘点当前三层全部入口，校验全局名称、依赖和覆盖，按 profile 物化。rewrite 依据实际文件来源和包内别名重定位 Markdown 链接；链接缺失直接失败。校验完成后直接写入最终输出，不使用暂存目录或 rename。默认排他创建新输出，失败清理本次创建的输出；已有目录须由宿主显式授权复用。


宿主安装可显式调用 `buildHost({ repo, output, profile, allowExisting: true, beforeWrite, entrySuffix })`。所有调用统一先在内存校验并渲染全部文件，再调用 `beforeWrite({ entries, files })`：entries 提供安装名 name 和唯一源 source，files 是预期相对文件列表，供宿主保留冲突内容、清理过期文件及使旧成功戳记失效。随后直接写入最终 output，不创建暂存目录、不调用 rename、不等待目录重命名重试。入口先写，entrySuffix 可追加宿主管理标记；全部成功后写 `.workflow-bundle.json`。现有输出路径中的符号链接被拒绝。写入失败保留部分文件，由宿主下次修复；调用方负责安装串行化、凭据保留、发现时机及最终安装戳记，不提供整体原子替换。默认 CLI 同样直接写入最终目录，但拒绝覆盖已有输出；allowExisting 仅控制覆盖许可，不切换安装算法。

`sparc3d` profile 的 `entries` 是宿主可发现入口白名单，实际名单以 profile 为准；其中 `head-reference` 公开为同名入口，供独立准备头部/转正/四视图，不要求先运行完整人像工作流。8 个媒体/软件工作流（`api-demo-service`、`app-prototype`、`asset-review-board`、`audio-prep`、`clip-edit`、`exhibition-tour`、`product-configurator`、`promo-layout`）同样公开。白名单内安装为 `<name>/SKILL.md`（有别名时使用别名），可由宿主 `skills/list` 发现并用 `$<name>` 选择；未列入的能力安装到隐藏的 `.dependency-*` 目录，入口命名 `REFERENCE.md`，仅供明确引用及文件依赖。`create-roblox-game`、`pub-roblox-game` 与 `roblox-api` 公开为独立入口，分别负责制作编排、发布与接口适配；业务依赖由各自 package/入口契约决定。`steam-mod`、`pub-steam-mod` 与 `steam-ugc` 同样公开为同名入口，分别负责创意工坊文件对齐、已对齐物品发布和 ISteamUGC 接口检查。`cad-file-verifier` 公开为同名入口，负责指定环境中的 CAD 打开、信息保留与继续编辑验收；不包含自动修复、格式转换或商业软件安装，ClassCAD 源端证据也不代替目标软件原生验收。`flex-motion` 公开为同名入口，负责在 Blender 中为已绑定角色的柔性部位烘焙惯性随动。`connected-faceted-lowpoly` 公开为同名入口，负责把已有角色、手办或雕塑高模做成真实连通的块面低模和有限纯色分区，交付对照工程与 GLB。`relief-lamp` 公开为同名入口，负责把文字、图片或已有浮雕做成可装配的透光浮雕灯，建模交付后再按同意配置整灯切片；同结构灯可修订连接配合与空白筒面。不与 `lamp-design` 的通用艺术灯具流程合并。`lithophane-lightbox` 公开为同名入口，负责按照片或已有浮雕制作发光浮雕相框，先选外框尺寸与混色/UV 工艺，复用 V5.1 参数化框体并配置、打开切片工程；不与 `frame-design` 的艺术相框或 `relief-lamp` 的筒形透光灯合并。`body-spring-connector` 公开为同名入口，负责把已有角色、动物或摆件的身体中段改为连续宽圆片弹簧和内藏 D 形桩槽；不并入 `print-joints` 的球窝人偶或 `twisty-fidget` 的互锁螺旋瓣。`image-to-print-forms` 公开为同名入口，负责把单张标志、线稿或剪影做成可选的分层标牌、落地桌摆、波浪围合或弧形竖片；不并入 `layered-laser-ornament` 的激光分层，也不把普通照片交给生模冒充这些构造。`lowpoly-quad-face-neck` 公开为同名入口，负责在对话里已有约两百万面高模时建立流形四边面；没有低模时先交接 `connected-faceted-lowpoly`，识别到脸时校准下巴与颈部并烘焙纹理，交付可编辑工程、OBJ 与 GLB。`quad-flow-plus` 公开为同名入口，负责按模型选择初始四边面重拓扑，并在已有基线上做保形减密或可靠边链预算重建；面颈基础交接 `lowpoly-quad-face-neck`，尺度分区交接 `scale-aware-quad-rings`，规则 4×4 的 16→15 交接 `closed-quad-transition`。`scale-aware-quad-rings` 公开为同名入口，负责对已有四边面按冻结尺度划分保护、缓曲和平缓区，并建立粗细环带。`closed-quad-transition` 公开为同名入口，负责保留外边链的局部 16→15 闭合过渡；不代替整模重拓扑。`unity-cozy-exploration-game` 公开为同名入口，负责把主题或已有 Unity 工程做成第三人称治愈系探索游戏，并说明 Windows/Mac 交付；裙发烘焙、绑定和生模仍交接已有入口。源码迁入时未安装 Unity，未把构建模板当作已通过的 Player 验收。`ue5-exploration-demo` 公开为同名入口，负责把文字或参考图做成可编辑的 UE5 展示场景；生图、生模和人物绑定交接已有入口，不在包内保存凭据。源码迁入时未安装虚幻引擎，未把环境说明当作编辑器或打包已通过。`stream-scene` 公开为同名入口，负责从参考编排可编辑溪流，并调用 `dcc-preset` 打开 UE 5.7 及以上水体插件、Houdini 海洋谱或 Blender 流体域；不代替 `water-feature` 的泵送水景或 `ue5-exploration-demo` 的通用展示场景。源码迁入时未把预制启用当成细波、白沫或网页已通过。`hex-terrain` 公开为同名入口，负责按 JSON 规则在 Blender 中做 lowpoly 正六边形地形并导出重导入检查过的 GLB；规则快照不含贴图和模型原件，不代替泵送水景或游戏寻路。`cinematic-camera-director-visual` 公开为同名入口，负责为已有 Blender 或 GLB 场景核对导演意图并生成连续相机动画。`rhino-control` 公开为同名入口，负责 Rhino 5–8 运行版本探测、MCP/Python/CUA 调用、Rhino 8 MCP 自动安装和分版本离线文档；几何验收与旧版脚本兼容测试由该工具提供。`rhino-build` 公开为同名工作流入口，将建模需求、安装文件夹与输出路径交给独立 `rhino-control`，负责环境准备、接口选择与模型交付；MCP 不可用时保留原生 Python/桌面回退，不重复维护控制脚本。`dcc-preset` 公开为同名入口，负责按版本检索 Blender、Houdini 与 UE 的水体类内置预制并执行对应的一项操作；UE 5.7 及以上只写入插件启用项，不创建水体，也不代替场景工作流。`exterior-surface` 保持隐藏。新增源码目录不会自动公开；需要桌面直接调用时须显式更新此白名单。物化出入口不代表正在运行的宿主会话已经安装或发现它。

`portrait-reconstruction` 不在 Hi3D Agent 的公开白名单中，安装为 `.dependency-portrait-reconstruction/REFERENCE.md`，不再提供 `$portrait-reconstruction`；客户端同时移除对应技能库卡片。源码及普通 `bundle.py --entry portrait-reconstruction` 的独立分发保留，Agent Internal 继续读取其原固定版本与物化包。Runtime 按新 profile 重装时清理旧的受管公开入口，用户自有技能仍由宿主原有冲突保护规则处理。

所有内容位于同一生成根，必须整体安装；.dependency-doc 保存完整文档镜像。每包 .runtime-profile.json 声明当前执行模式，.workflow-bundle.json 保存可复现的来源/内容摘要；不读取 Git 凭据或真实服务状态。验证公开入口时，除检查分发中的 `SKILL.md` 外，还须验证宿主安装后的 `skills/list`；消费端更新已推送的子模块指针并重启 Runtime 后重新安装，已发布客户端需要重新构建分发包。前端技能库卡片目录由消费端另行配置，不控制 `$` 发现列表。

```sh
node "$REPO/tools/package-tools/scripts/host-bundle.mjs" --repo "$REPO" --profile sparc3d --output "$NEW_BUNDLE"
```

消费仓库把本仓库作为 Git submodule，以 gitlink 固定已推送提交。开发、测试和构建先生成，生产包携带物化产物，不在用户机器上运行 Git 或依赖源仓库；升级须分别提交子模块源码和父仓库指针，生成目录不跟踪。

[host-bundle.test.mjs](../.dependency-package-tools/tests/host-bundle.test.mjs) 在合成仓库验证覆盖映射、共享源码变化、隐藏入口、稳定产物、不可覆盖、无效链接和凭据/符号链接路径保护。Node --test 直接执行，不导入能力实现。

### 游戏原子入口的分发范围

`sparc3d` profile 显式选择游戏规则、适配和验证入口；清单以 profile 的 entries 为唯一源，不在此复制名单。各入口保持自有 `.mjs` 示例、测试与契约，无隐式 Node 包安装。物化包的脚本调用需 Node 22+；浏览器检验另需调用方提供 Playwright Browser。新增白名单不代表正在运行的宿主会话已安装或发现这些入口。

`create-skill` 作为 `workflows/create-skill` 入口随 sparc3d 白名单分发；物化统一阶段记录契约，生成的草稿只能交由 Runtime `skill_draft_submit` 校验，不能经 shell 安装。
