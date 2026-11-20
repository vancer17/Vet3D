# rhino-control：Rhino 应用控制契约

[入口](../rhino-control/SKILL.md) 提供 Rhino 应用的通用控制能力，属于 tools；无 PCG sidecar，不编排具体品类工作流。唯一维护源为 `tools/rhino-control/`，无跨包运行依赖。分发由 package-tools 物化；宿主公开名称为 `rhino-control`。随包官方参考文档用于离线核对版本与 API，按任务渐进读取。

## 路由与输入输出

输入：目标 Rhino 安装/当前文档、建模或检查需求、显式包外输出路径。安装文件元数据只选择候选；进程内版本、Python 实现与文档序号决定真正目标。调用优先级为：版本一致且可用的 MCP → 经探针验证的原生 Python → 通用 computer use。当前固定 RhinoMCP 发行版支持 Rhino 8 Windows/macOS，不能安装到 Rhino 5–7；旧版另有已验证 MCP 时仍优先使用。Rhino 5–7 原生脚本使用 IronPython 2.7；Rhino 8 的 RunPythonScript 保留该路径，ScriptEditor 可使用 CPython。

输出：版本证据、协议结果、几何断言及按任务需要保存的 3DM/导出文件。普通编辑只操作任务 GUID、另存新文件；验收夹具只接受空模型。超时不证明命令未执行，不重发修改、不强杀用户应用。大型无界内核任务须由调用工作流另行用共享预算契约隔离执行，本工具的 socket timeout 仅为通信等待上限。

## 代码与 CLI

### scripts/rhino.py

[源码](../rhino-control/scripts/rhino.py) 只在外部 Python 3 中执行，不加载 Rhino 几何内核。

| 函数 / 子命令 | 参数与行为 | 输出 / 失败条件 |
| --- | --- | --- |
| `installation(path)` | 显式 `.app` 或 `Rhino.exe`；macOS 检查 McNeel 包身份和 CFBundleExecutable 对应的真实可执行文件，读取 Info.plist 或 Windows FileVersion | path、executable、platform、major、version、build、yak、preferred_transport、bundled_mcp_supported（仅本包插件）、python_entries（engine/command/documented_command 证据、runtime_verified=false）；runtime_version_verified=false。只接受 5–8，不按目录名推测版本 |
| `discover()` / `detect` | macOS 两个 Applications 目录；Windows 两种注册表视图和常见安装目录；`--app` 可指定 | 按大版本降序的候选列表，未安装返回空列表 |
| `search_installations(root, max_depth=6, max_entries=20000)` / `detect --root …` | 在显式目录内搜索名称含 Rhino/Rhinoceros 的 .app 及 Rhino.exe，改名的应用可直接通过 root/app 指定；不跟随子链接、不进入应用包内部、不启动程序。深度 0–20、条目 1–100000，包含文件计数；默认上限 6/20000 | root、installations、scanned_entries、max_depth/max_entries、truncated、errors；部分结果可用但不是完整未安装证明。缺目录/非法限制失败；候选不可读或元数据无效记录错误类型，安装器不算候选。Windows FileVersion 只调用 PowerShell 读取元数据 |
| `python_command(major, engine)` | 5–8 IronPython，8 另有 CPython | 文档规定的命令前缀；供探测与 macro 共用，不证明运行时可用 |
| `choose_transport(major, mcp_runtime_major=None, python_verified=False)` | MCP 运行版本须匹配；否则根据 Python 探针结果 | mcp/python/computer_use；未知大版本拒绝。该纯函数不代替探针 |
| `install_mcp(app, version='0.4.1.1')` / `install-mcp --app … [--version …]` | Rhino 8、自带 Yak、uv；固定数字版本；Yak 安装插件与 uv tool Python 3.11 环境分别限时 180/300 秒 | 两端成功才 installed=true，返回 server_command 和 restart/mcpstart 引导；包管理器失败直接报错，部分安装不回滚 |
| `python_macro(script, major, engine='ironpython')` / `macro` | 路径必须存在；`--engine cpython` 仅允许 8 | 带引号绝对路径的 RunPythonScript 或 ScriptEditor 宏；拒绝路径中的双引号/换行 |
| `prepare(kind, script, output, major, engine='ironpython')` / `prepare` | kind=probe/smoke20；major=5–8；engine=ironpython/cpython，后者仅允许 8 并加 `#! python 3`；新脚本和新输出均在包外；将唯一 runtime_compat 导入替换成内联源码，要求标记恰有一次 | 自包含兼容脚本、engine、对应 macro、compatibility_target；调用 run 前检查实际 Python 实现。已有路径拒绝，不隐式覆盖；不依赖包路径或导入缓存 |
| `main()` | argparse 解析上述子命令 | stdout JSON；依赖/权限/参数失败非零退出 |

安装不仅下载包：保存当前工作，正常重启 Rhino，执行 `mcpstart`，验证 loopback、插件能力与实际版本。无需修改宿主配置即可使用官方 SDK 客户端；安装 uv 的方式按官方文档与目标系统选择。完整引导见 [MCP](../rhino-control/references/mcp.md)。文件夹搜索、入口候选和 MCP/Python 实测交接由 [rhino-build 工作流](../rhino-build/SKILL.md) 编排；运行方式仍由本工具唯一维护。Windows 安装/启动路径需在该平台验收；macOS 的验证不能代替 Windows 实测。

### scripts/mcp_client.py

[源码](../rhino-control/scripts/mcp_client.py) 依赖 RhinoMCP 环境中的官方 `mcp` 2.x SDK。`request(server,calls,timeout=60,progress=None)` 通过 stdio 初始化、读取 tools/list；calls=None 返回目录，非空列表按序调用。所有请求的 name/arguments 和工具存在性在首个修改前检查。工具目录不代表 Rhino 已在线，必须另外调用 describe_capabilities 与进程内 probe。

`decoded(result)` 检查 MCP isError、文本 JSON 和 structuredContent.result 的 success=false/status=error。`error_messages(exc)` 保留 SDK 嵌套异步异常的实际叶错误。修改调用失败即终止后续项，无客户端自动重试。SDK/上游对只读连接探测可能有重连，不等于修改重放。

CLI：`--server` 默认 PATH 中 rhinomcp，`--request` 为 JSON 调用数组（省略则 tools/list），`--output` 为必须不存在的包外 JSON，`--timeout` 默认为 60 秒且范围 (0,600]。请求为 `{name:string, arguments:object}`。输出先排他写 started，发出前写 calling 与 active_call，收到后写 received 和已完成原始结果；最终 completed，异常 interrupted_or_failed 并保留进度/error。通信 timeout 另加 SDK 10 秒余量。状态文件用于避免未知结果下的盲目重发，不构成分布式事务或断电原子性。

环境限定 `RHINO_MCP_HOST=127.0.0.1`；Rhino 插件使用本机 1999 端口。一次只运行一个客户端，按实际能力表判断参数版本。RhinoMCP 的 Python 工具走内嵌 IronPython，不把 Rhino 8 的 CPython 支持混用到此工具。

### scripts/runtime_compat.py、probe.py 与 smoke20.py

[runtime_compat.py](../rhino-control/scripts/runtime_compat.py) 的 `runtime_info()` 是探针和验收夹具共同的只读版本实现，返回 rhino_major、rhino_service_release、rhino_build、python、implementation、document_serial、document_serial_source。`RhinoApp.Version` 从 5 SR9 提供；缺少时 build 为 null。文档 RuntimeSerialNumber 从 6 提供；5 使用 DocumentId 并标明来源。这些文档标识不跨进程持久化。不能从安装目录或 compatibility_target 伪造运行时证据。

[probe.py](../rhino-control/scripts/probe.py) 的 `probe()` 在上述元数据上增加对象数、单位和绝对容差；对象数沿用 AllObjects 默认排除项，不是完整空模型检查。`run(output)` 写一个新 JSON，拒绝覆盖。无第三方模块，须在 Rhino 内执行。实际提交用 prepare 内联共享模块后的自包含脚本；MCP 的代码字符串不能直接照搬带包内 import 的源文件。

[smoke20.py](../rhino-control/scripts/smoke20.py) 是跨 Rhino 5–8 的 20 项调用验收夹具，保留 IronPython 2.7 兼容语法，也可由 Rhino 8 CPython 执行。辅助函数 `require`、`near`、`rect`、`box`、`volume` 分别进行断言、数值容差判断、确定性基础几何及闭合实体体积验收；`runtime_info()` 复用共享模块；`document_is_empty()` 通过 Rhino 5 起支持的对象枚举设置检查普通/隐藏/锁定/参考对象、灯光和控制点，避免 AllObjects 默认排除项被误当空模型。`CASES` 包含 layers、point、line、polyline、circle、arc、nurbs、planar、solid_box、sphere、cylinder、extrusion、loft、revolve、sweep、union、difference、intersection、transforms、mesh，具体参数与后验条件见 [20 项表](../rhino-control/references/validation.md)。

`run(output, compatibility_target=None)` 只接受新输出目录和无对象的活动模型，设毫米和 0.001 容差并回读，逐项单次执行、验证 Geometry.IsValid、记录 GUID/结果/耗时；失败项保留并继续收集，其后整套失败，不自动重试。每项独立图层、组和标签，排成 5×4 格。正常后设置 Shaded、ZoomExtents，用 Rhino 5 起的 WriteFile 保存原生 `smoke20.3dm`，以 File3dm.Read 核对对象 GUID 集合、有效几何与毫米单位；无论回读断言成功与否都 Dispose 文件对象。finally 恢复原图层和 redraw 并写 report.json。异常留下本次测试对象，调用者检查后开新空模型重新验收，不清空用户文档。只在完整保存回读成功时 state=passed；20 项通过但收尾失败仍判整套失败。

报告字段：runtime、compatibility_target、cases（name/attempts/status/checks/object_ids/object_count/seconds，失败附 error/traceback）、passed/failed、automatic_retries、state、file_check。compatibility_target 是脚本兼容目标，不改变实际运行时或输出 3DM 文件版本。旧版脚本在 Rhino 8 的 IronPython 下通过，不等于 Rhino 5/6/7 本体实测。编写时的语言、单位/坐标、返回类型、SR 限制与保存前提统一维护于 [Python 清单](../rhino-control/references/python.md)。

### scripts/docs.py

[源码](../rhino-control/scripts/docs.py) 用标准库归档、检索官方资料。`Text` 提取 HTML 正文并跳过 script/style；`fetch(url)` 对 URL 空格编码，单次 45 秒，仅对网络/429/5xx 最多 3 次读取重试。`indexed_topics(base)` 读取连续 SearchUrl_Chunk0..29，处理旧版 JS 尾逗号，限定同一根 URL、去重主题；异常索引失败，不默默截断。

`mirror(base,destination,workers=8,allow_missing=False)` 限定官方 Rhino HTTPS 根，拒绝路径穿越，缓存原 HTML 到相邻 .cache，下载线程 CLI 1–16；默认缺任何页不发布 ZIP，保留 errors.json。显式 allow_missing 才发布带 missing.json 的可取得正文归档。ZIP 内含 html/text/index 和搜索索引，旁边 summary JSON 给出 indexed_topics/topics/missing_topics/complete_index_coverage/scope；归档内不包含网页媒体。临时 ZIP 完成后替换输出，维护者应使用包外新路径再审核资源更新。

`archive_rows` 优先读取 index.json；无索引的 MCP Markdown/RhinoCommon XML 归档则枚举真实 .md/.txt/.py/.xml 成员。`raw_text` 只读归档内真实文本成员，拒绝绝对路径、父目录穿越、非文本扩展、无效 UTF-8 和 NUL 二进制；不提取文件。旧 search/read 同时支持两种格式，lookup --sources 返回的原成员路径可直接 read。

`TopicMarkup` 提取 HTML meta-refresh 目标及保留缩进的 pre 代码块。`read_topic(archive,path)` 仅跟随本地已索引目标，兼容官方路径大小写/URL 转义，至多访问 32 页；缺目标、循环或超过上限时失败，不联网、不用跳转占位文字冒充正文。返回实际 path/url、redirect_chain、text、code_blocks；Python 源码归档没有 HTML 时直接读取原文本。

新增 `lookup --major 5|6|7|8 [--query …] [--kind rs|rc|mcp|guide] [--limit 12] [--sources] [--format json|text] [--rs-variant …] [--rc-variant …]` 与 `section --major … --id … [--id …] [--variant …] [--rs-variant …] [--rc-variant …] [--with-notes]` 使用下述目录模块；lookup 默认仅返回定位字段，--query 可重复以减少检索往返；单 query 保留对象返回，多 query 返回带 query 字段的结果数组。默认 JSON 输出兼容既有调用；text 每个命中项一行 `id | path:start-end | variants | summary`，每组保留版本、query、total/truncated；--sources 时另列来源行。文本供 agent 阅读，机器解析用 JSON。section 返回完整契约行段；--with-notes 附本版索引中按精确 API ID 关联的 guide 段，同组注意事项只输出一次。已知 ID 可直接读取，不要求先 lookup；只有当前大版本全部归档分支都有相同契约时可省略分支。--rs-variant/--rc-variant 分别选择当前大版本真实收录的 Python 分支/XML 框架，不影响 guide/MCP，支持混合批量；旧 --variant 仍用于单类读取，冲突拒绝。lookup/section 的 ValueError 以单行 error、退出码 1 和空 stdout 返回，Python API 仍抛异常；意外错误保留 traceback。旧 read 可加 `--start-line N --end-line M`（1 起点、两端含、须成对，不能与 code-blocks 同用）；越界拒绝。维护命令 `catalog-build --output 新.zip` 只写新路径，`catalog-check` 重建比较索引与正文。

CLI `mirror --base … --output … [--workers 8] [--allow-missing]`；`search archive query [--limit 20] [--full-text]` 默认按标题/路径不区分大小写检索，加 full-text 才读正文；`read archive path` 输出解析后的完整文本，`--code-blocks` 输出上述元数据及代码数组 JSON（省略 text）。普通提取文本不保留 Python 缩进，复制示例用代码模式或原始 .py 源码。官方归档与 PDF 来源、覆盖范围、失效项、SDK 包版本见 [文档索引](../rhino-control/references/documentation.md)。另存 5 Windows/Mac、6.0、7.0、8.0、8.30 官方 RhinoScriptSyntax 分支的完整 Python 源码/docstring 与许可说明，source.json 固定修订，按相同 index/text 协议检索；只作参考，不覆盖应用内置库。最新开发站含 Rhino 9 内容，须核对目标版能力。资源不是针对本机运行的诊断日志，运行测试证据均保存在包外。

### scripts/catalog.py

[源码](../rhino-control/scripts/catalog.py) 是 docs.py 的标准库离线目录模块，复用随包官方快照，不联网、不导入或执行 Rhino 源码。唯一运行入口仍为 docs.py，不新增 skill 或运行依赖。共用文档放在 catalog.zip 的 common/rs.md、common/rc.md；有差异的契约留在 5/、6/、7/、8/ 对应文件。四个版本各有 index.jsonl，具体路径、读取条件与 variant 选择见[两级索引](../rhino-control/references/versions.md)。原始 ZIP/PDF 不删除，许可、完整实现、示例和来源修订仍可定向回查。

| 函数 | 输入 → 输出与边界 |
| --- | --- |
| `compact` / `synopsis` | 文本 → 用于索引的空白规范化/首句（最多 180 字符，超长显式省略）；不将摘要当作完整调用契约 |
| `wrapper_tokens` / `prose_key` / `shared_python` | 函数源码/文档/候选集 → 比较表示/是否可共享；保留字面量、默认值、块缩进语义与显式类型差异，不执行源码。说明中引号/反引号字面量保留内部空白。纯类型标注补充之外的说明差异仅限 REVIEWED_RS 中已逐项核对且指纹匹配的来源；任何完整原函数/分支/抽取正文变化都会使人工例外失效，重新审阅后才可更新 |
| `review_fingerprint` | 候选记录 → 分支、完整函数 source_hash 与正文的确定性 SHA-256；绑定人工已审例外，不是运行验收证明，不放宽包装代码/显式类型比较 |
| `contract_text` | docstring → 省略 Example/Examples/See Also 章节的正文；识别同级或更高层大写开头的英文章节标题（可含版本号、括号及行内说明），保留后续 Notes/Returns/Raises 等约束，示例中的 if/else 不作标题 |
| `corrected_body` | 接口 ID、正文 → 按归档包装实现修正已确认的参数名/类型注释笔误，并附校正说明；不修改原始官方文件 |
| `python_contracts` / `rs_records` | Python 2/3 源文本/official 目录 → 公开顶层函数的签名、契约、摘要、实现比较表示及原文行号；tokenize 避开字符串内的假定义，保留原始缩进；紧邻函数的连续/多行装饰器纳入源码范围、指纹与包装比较，装饰函数保守拒绝共用并提示核对目标装饰器契约。无 docstring 时给出该函数实现和明确缺注释说明，不借新版注释冒充旧契约。完整示例按 source 行号回查 |
| `xml_records` | official 目录 → 每代每框架 XML member 的完整签名、summary/param/returns/remarks/since 等 XML、摘要及源行号；不凭旧版缺注释推断 API 不存在。嵌入代码保留缩进 |
| `mcp_records` | official 目录 → RhinoMCP README 工具表及所有 Markdown 章节的名称/用途、语义关键词与准确源行号；仅进入 Rhino 8 的 mcp.md，不将目的说明冒充完整入出参 schema，实际 tools/list 优先 |
| `guide_records` | 完整包根 → 共用与该版手工说明的章节位置、摘要及段内容校验值；5–7 不索引 Rhino 8 MCP/CPython 操作段。api-notes.md 各标题中的完整 rs.名称生成 apis 关联数组（精确匹配，不从正文提及推断依赖）；共同规则和 API 注意事项只维护原文一份，不复制进归档 |
| `assemble` / `build` | 契约记录/包根 → `{归档内路径: UTF-8文本}`；所有已归档版本和平台/框架都有接口且契约一致才归 common，缺版本/不同返回/不同默认值不得合并；Python 还比较可执行包装，不能只看同名签名。同一 major 下 docstring 相同而包装 tokens 不同的记录也独立分段，正文标 Wrapper difference 和所选原源码精确范围，避免输入/返回差异被文本去重掩盖。共用 Python 采用已核对的含类型说明；这不证明各 SR 内核或 CPython 转换相同。计算准确物理行号、确定性排序，不修改文件 |
| `write_catalog` | 文本映射、新 output → 排他写 ZIP，固定元数据使相同输入生成相同字节；输出已存在则拒绝。不隐式覆盖源资源 |
| `Catalog.__init__/__enter__/__exit__` | major、可选归档/包根/rs_variant/rc_variant → 单次调用的上下文管理读取器；打开 ZIP、只解析一次本版索引并建立精确 ID 映射与各 kind 的分支全集，验证所选标签属于当前大版本，正文按需每文件解压/分行一次。失败或退出关闭文件并释放快照；不在命令间缓存 |
| `Catalog.validate_variant` | kind、variant → 验证属于本版该类归档；未知/跨版本/跨类别标签报错并列实际可选值，不猜最近分支 |
| `index_rows` / `lookup` / `Catalog.lookup` | major、可选查询/kind/limit/catalog → 当前版本记录/匹配目录；major 仅 5–8，limit 1–100 默认 12，lookup 的可选 rs_variant/rc_variant 仅筛对应 kind；按查询词 AND 匹配 id/摘要及 MCP 章节中的工具关键词。精确接口名优先；同 id/行段的 variant 合并显示，输出 total/truncated，不加载 API 正文；sources=true 才返回原始来源路径与行号 |
| `section` / `Catalog.section` | major、精确 id、可选 variant/catalog/root → path/start/end/text 与适用 variants；可选 rs_variant/rc_variant 与旧 variant 冲突时拒绝；按精确 ID 映射定位，多份不同契约或未覆盖本版全部分支而未选择时拒绝。选择已归档分支但该 ID 缺项时说明快照缺证据，不宣称运行时不存在，不默认最新。只读取命中段，保留代码缩进；空结果、越界、越出包根的手写路径、手写段校验不符均失败。CLI 批量先全部解析再输出，避免部分成功掩盖缺项 |
| `Catalog.sections` | 精确 ID 序列、可选 variant/with_notes → 完整结果序列；默认等于逐个 section，附注模式按本版索引精确 apis 追加相关 guide，共同段去重、显式 guide 保持原位置；API variant 不过滤共用 guide。任一契约或附注失效均抛异常，CLI 在整批成功后才输出 |
| `check` | 包根与目录归档 → valid/documents；从当前原始快照和手写说明完整重建、逐文件比较，发现缺项、正文变化或行号过期即失败 |

维护者修改版本说明、接口资料或抽取规则后，先在包外生成新的 catalog.zip 并审阅，再替换源码归档；不手工修改二级索引或物化副本。`catalog-check` 是相关提交的必要检查。CLI 批量复用一个 Catalog；原单次 index_rows/lookup/section 函数保留参数和结果，通过独立上下文调用同一实现。workflow 本身无文档缓存实现；入口仅要求同一次任务中复用已读取且未变化的段，不能将它宣称为宿主 token 缓存。

## 元数据、分发与验收

`package.json` schema=1、files={}、requires=[]：源码资源自足，没有隐式邻包依赖。`agents/openai.yaml` 的显示名称为“Rhino 应用控制”，声明 `$rhino-control` 默认提示。references/versions.md 是第一级版本路由；catalog.zip 保存第二级接口索引与共用/差异 API 正文，versions/5–8.md 与 8-mcp.md 保存版本差异。Python 共用五项清单与 api-notes.md 接口经验分开索引；写脚本先查 guide:N:/guide:python:，其他接口路径按条件查目录。Python、CUA、20 项验收及官方来源仍按索引段读取，原始归档作为来源和完整实现回查。`sparc3d` profile 明确公开 rhino-control；入口文件存在不等于当前宿主会话已动态发现。

[边界测试](../rhino-control/tests/test_boundaries.py) 的 `fake_app` 仅创建不会启动的合成应用包；测试验证真实可执行文件/包身份、用户目录多版本搜索、符号链接跳过、深度/数量截断和无效安装、模拟 Windows FileVersion 与命令候选，以及安装元数据优先、运行版本路由、拒绝旧版强装 MCP、自包含脚本/输出保护、错误引擎在修改前拒绝、宏路径保护、缺页归档显式降级、跳转/代码缩进与缺目标/循环、MCP 业务失败、嵌套错误保留与修改超时不重放。生成脚本的元数据另以缺少新属性的 Rhino 5 SR0/SR12、6/7、Rhino 8 SR0/SR30 各两引擎模拟接口执行，禁止从包导入辅助模块，覆盖旧版属性缺失、非 ASCII 路径、probe/smoke20 错引擎前置拒绝和旧 compatibility_target 与真实 runtime major 的分离；该 mock 不验证几何内核。用装有 mcp 2.x 的 Python 3.11+ 执行 `python -m unittest discover -s "$SKILL_DIR/tests" -v`。

[目录回归测试](../rhino-control/tests/test_catalog.py) 覆盖全部 XML member 与 Python 函数的索引覆盖、全部段的边界、共用契约的版本完整性、不同实现/类型/默认值/说明字面量拒绝合并、人工例外变更失效（含装饰器）、示例后约束保留、批量只读取一次且跨调用刷新、紧凑输出字段完整、重载/平台歧义、过期手写行号拒绝、CLI 批量及原源码行段回查、API 注意事项的逐版本关联覆盖/精确选择/去重、简短失败输出与整批原子性、同正文不同包装拒绝猜测、Rhino 5 部分平台缺项拒绝默认、全部已归档分支/框架组合的混合读取与跨版本标签拒绝。文档读取量可与对应原模块/旧必读集合比较；字符或离线分词量不等同于宿主实际 token 账单或建模总耗时。

真实验收另在 Rhino 内完成：MCP 单次完整 20 项并在新模型重复，Rhino 5/6/7 兼容脚本分别原生 RunPythonScript，Rhino 8 分别执行 IronPython 与 CPython，核对报告、3DM 回读及视窗。业务脚本遵循目标引擎只编译/只读预检后再单次建模的顺序；语法通过不证明几何有效。边界 mock 和源码分析不代替该实测；无旧版安装时明确只验证旧脚本在现有运行时的兼容性。独立包还检查链接、资源、CLI、测试及宿主发现；缺目标宿主发现接口时记录未验证。文档和调用事实随代码同步，原始运行记录不入仓库。
