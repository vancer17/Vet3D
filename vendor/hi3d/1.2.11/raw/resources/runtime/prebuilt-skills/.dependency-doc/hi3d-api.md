# hi3d-api：通用 API 与产物工具

[独立 AI 入口](../hi3d/SKILL.md)负责 Hi3D 单图/多视图建模、GLB 贴纹理、浮雕、拆件、多色、余额、3D 免费重试次数/提交、任务恢复和产物下载；可选 Blender 原始数据检查。它不生成骨架或动画；业务工作流 [hi3d-model-gpt-animation](../hi3d-model-gpt-animation/SKILL.md)显式调用它并接收原始 GLB。

## 来源与迁移边界

人形原始 GLB 需要新身体绑定时，推荐交给独立 [rig-retarget](../rig-retarget/SKILL.md) 组合 mdf-call 的 HTTP auto-rig，再回迁和修复蒙皮。此交接不改变本工具的生成请求、恢复语义或客户端实现；已有合格绑定直接复用。

来源为用户提供的 `hi3d-share/` 分享包，协议说明标记日期为 2026-09-07。分析范围为明确列出的非敏感脚本、参数及说明；未打开源凭据文件，未运行源安装器，源目录保持不变。迁移不包含 `.secrets/`、凭据、会复制凭据的安装器、历史案例图片、个人偏好和账户记录。未核实的历史价格不固化为费用估算器，余额数值的单位保持未确认。

全部 Hi3D 密钥只允许 `HI3D_AK`、`HI3D_SK`，规则见 [README](repository-README.md)及 [AGENTS](repository-AGENTS.md)。AI 不查看实际值，不加载 shell 配置或凭据文件；实际授权鉴权进程内部消费环境变量，模拟测试替换模块的环境读取边界，绝不复制真实环境用于测试。API 与下载器禁用隐式代理配置，避免读取代理环境或携带代理凭据；需要代理的环境目前没有专用 CLI 配置。

旧动画客户端、对应 HTTP 测试及 `requests` 依赖已删除；旧 state 通过已知 task ID adopt，不能重用为新版 job 或触发重提。交接与独立依赖安装方式唯一维护于业务工作流的 [模型生成说明](../hi3d-model-gpt-animation/references/model-generation.md)。

## 设计与组成

不可重复的远端提交、可恢复的本地记录和原始产物完整性是核心不变量。先按本地输入形成指纹并验证上传字节，再鉴权、独占写 intent、单次 POST；有效 task ID 先独立持久化，再更新状态；任何提交歧义保留记录。查询结果只保存受限状态，不把服务端自由文本带入报告。下载使用无鉴权连接，原件与派生文件都记录哈希，不覆盖未知内容。

模块依赖：CLI → jobs/artifacts/client/parameters；artifacts → jobs/parameters/storage；jobs → client/parameters/storage；client 和 parameters → storage。Blender review 组合物化的 mesh-audit 三角数组核心，只需要 Blender/NumPy/storage，不加载 API 客户端。默认值与参数校验分别集中，CLI 只负责解析、编排和脱敏呈现。

固定源为 `https://api.hitem3d.ai`，以下路径均以 `/open-api/v1/` 开头；auth/token 使用 POST，balance 使用 GET。路由来自分享包快照，`muilticolor` 是源创建接口的拼写，不应自行改为查询接口的拼写。

| kind | 创建 POST 路径后缀 | 查询 GET 路径后缀 |
| --- | --- | --- |
| model | submit-task | query-task |
| relief | depth/create-task | depth/query-task |
| split | split/create-task | split/query-task |
| multicolor | muilticolor/create-task | multicolor/query-task |

完整文件映射：

| 文件 | 职责 |
| --- | --- |
| [hi3d_api.py](../hi3d/scripts/hi3d_api.py) | CLI 和可注入客户端的编排 |
| [hi3d_client.py](../hi3d/scripts/hi3d_client.py) | 固定源 HTTPS、内存鉴权、单次请求与余额 |
| [hi3d_parameters.py](../hi3d/scripts/hi3d_parameters.py) | 模式契约、参数规范化、输入指纹、流式 multipart |
| [web_option_gates.py](../hi3d/scripts/web_option_gates.py) | 网页带钻 option 目录；3D `model_type` 的 `label` 为提交 id、`description` 为网页短文案；生模/浮雕/拆件生成符合宿主契约的 60 秒参数 preference；`generation_type` 含 both/mesh/texture，texture 映射 `request_type=2`（Runtime 另加 `scene=texture`），并经 `validate_generation_selection(selected, has_mesh)` 在上传前拒绝无 GLB 或 v2.0/v2.1 的组合；图片无需弹窗即 ready，可选图片 settings 与弹窗 id 换成公共或 Runtime `--set`；其他任务参数齐全后允许 POST；Agent 可选用、网页锁定；积分不能解锁 |
| [hi3d_jobs.py](../hi3d/scripts/hi3d_jobs.py) | 独占 intent、提交、接管、查询和有限轮询 |
| [hi3d_artifacts.py](../hi3d/scripts/hi3d_artifacts.py) | 下载、GLB 头校验、ZIP 解压、文件 manifest 与缓存校验 |
| [hi3d_storage.py](../hi3d/scripts/hi3d_storage.py) | JSON、SHA-256、原子保存、报告脱敏 |
| [blender_review.py](../.dependency-hi3d-api-source/scripts/blender_review.py) | 原始网格检查适配、导入、独立顶点色显示副本 |
| [triangle_arrays.py（物化来源）](../.dependency-mesh-audit/scripts/triangle_arrays.py) | 数值核心由 mesh-audit 唯一维护，见其 [测量契约](../.dependency-mesh-audit/references/mesh-measure.md#三角索引数组) |
| [test_api.py](../.dependency-hi3d-api-source/tests/test_api.py) | 无网络、无真实密钥的行为回归 |
| [test_blender.py](../.dependency-hi3d-api-source/tests/test_blender.py) | 合成 UV/顶点色 GLB、显示副本与覆盖保护回归 |
| [test_web_option_gates.py](../.dependency-hi3d-api-source/tests/test_web_option_gates.py) | 网页/Agent option、图片免弹窗与兼容参数映射、texture 选项的公共/原生映射与无 GLB、v2.x 拒绝、其他任务的合法宿主交互 payload 与参数完整性回归 |
| [test_account.py](../hi3d/tests/runtime/test_account.py) / [test_recovery.py](../hi3d/tests/runtime/test_recovery.py) | 账号 Runtime 传输、参数/授权桥接、下载与中断恢复回归 |
| [defaults.json](../.dependency-hi3d-api-source/defaults.json) | 可覆盖起始参数、协议快照日期；不保存价格或账户信息 |
| [openai.yaml](../hi3d/agents/openai.yaml) / [.gitignore](../.dependency-hi3d-api-source/.gitignore) | 直接调用元数据、缓存及凭据路径排除 |

## 原子函数契约

以下路径均由调用者显式传入，`path` 可为字符串或 Path。运行依赖、CLI 示例、参数枚举和状态恢复规则按需读 [calling](../hi3d/references/calling.md)、[parameters](../hi3d/references/parameters.md)、[review](../.dependency-hi3d-api-source/references/review.md)，此处不复制操作正文。

### 本地存储与参数

| 函数 | 输入 → 输出与边界 |
| --- | --- |
| `now()` | 无输入 → UTC ISO 时间字符串。 |
| `load(path)` | JSON 文件 → 对象；I/O/JSON 错误传播。调用者不得指向密钥文件。 |
| `digest(path)` | 文件 → SHA-256；按 1 MiB 块只读。 |
| `save(path, value, exclusive=False)` | JSON 对象 → 无返回值；拒绝 NaN，创建父目录，mode 0600，flush/fsync；首次独占创建或同目录临时文件原子替换，清理临时文件。 |
| `public_record(value)` | 字典/列表/标量 → 新脱敏视图；敏感字段不读取值，HTTP(S) URL 隐藏用户信息、query、fragment；不是任意自由文本的密钥发现器，因此不接收 API 原始错误正文。 |
| `load_defaults()` | 无输入 → 从脚本自身位置读取 defaults.json，不依赖 cwd。 |
| `enum(p, k, values)` / `number(p, k, lo, hi, step=None)` | 参数字典与约束 → 无返回值；枚举或 Decimal 有限范围/步长不符抛 ValueError；不修改 p。 |
| `file_info(field, path, exts, max_bytes=None)` | 文件字段、路径、扩展集合和可选字节上限 → field/path/bytes/sha256；必须非空，不解码图像/模型。 |
| `secure_url(url)` | 字符串 → 原 URL；要求绝对 HTTPS 且无内嵌用户名/密码，不主动探测 URL。 |
| `normalize_parameters(kind, overrides, defaults)` | 模式、key=value 列表、显式配置或 None → 新参数字典与覆盖字典；标准化整数/格式，检查白名单及回调 URL，不修改默认字典。None 时加载包内配置。 |
| `model_inputs(p, changes, images, views, image_url, mesh, mesh_url)` | 已规范化参数与候选输入 → files、允许 mesh 扩展名、上限；校验建模/贴纹理兼容性，重排多视图；**修改传入的 p**，补 mask、去除不适用字段；只读本地输入。 |
| `relief_inputs(p, images, views, image_url, mesh, mesh_url)` | 参数与候选输入 → 同上三元组；校验单图/URL 二选一、背景和底座参数；修改 p，必要时读取图像。 |
| `mesh_inputs(kind, p, images, views, image_url, mesh, mesh_url)` | split/multicolor 参数与候选输入 → files（此阶段为空）、mesh 扩展名和 200 MiB 上限；规范化模式相关字段，修改 p。 |
| `build_plan(kind, *, images=(), views=None, image_url=None, mesh=None, mesh_url=None, overrides=(), defaults=None)` | 显式输入 → kind/parameters/files/fingerprint；编排模式校验并补 mesh 元数据，以完整 JSON 计算计划指纹，无网络/鉴权/写盘。返回的原计划可能有输入 URL 签名，只能经 public_record 呈现。 |
| `multipart(parameters, files)` | build_plan 结果的参数、文件列表 → 上下文内临时二进制流、Content-Type、字节长度；重算上传字节哈希，变化立即停止；匿名上传文件名，退出关闭临时文件。 |

### 传输与任务

| 函数或方法 | 输入 → 输出与边界 |
| --- | --- |
| `environment_credentials()` | 无参数 → 内部鉴权所需值对；**只允许真实已授权鉴权调用或模拟测试**，只消费 HI3D_AK/HI3D_SK，缺失抛固定错误，无文件/别名回退，不打印返回值。 |
| `NoRedirect.redirect_request(...)` | urllib 重定向回调 → None，阻止 API 鉴权重定向。 |
| `Client(opener=None)` | 可注入 opener → 惰性客户端；默认固定 HTTPS、禁用代理自动配置，不鉴权。 |
| `Client._http(path, method, data, content_type, authorization, length=None, timeout=90)` | 固定 API 路由、正文/流与内存鉴权 → HTTP status 和临时 JSON 字典；无重试，不记录请求/响应，非对象响应抛 TypeError。内部接口，调用者禁止输出 authorization/返回正文。 |
| `Client.auth()` | 无参数 → 无返回值，内存保存 token；固定源 Basic 认证 POST，HTTP/API code 均需 200，token 为非空字符串。错误正文不外传。 |
| `Client.request(..., timeout=90)` | 路由及请求参数 → 临时 status/body；无 token 时认证；仅 GET 显式 401 可刷新一次；POST 永不自动重复。 |
| `Client.balance()` | 无参数 → checked_at/totalBalance/unit；数值须有限且非布尔值，单位不臆测。 |
| `task_identifier(value)` | 字符串 → 验证后的 ID；限 1–200 个 ASCII 字母/数字/点号/连字符/下划线，原样返回，不拆分或重构。 |
| `response_error(status, body)` | 临时响应 → HTTP 状态与最多 12 位纯数字 code 或 None；不复制 msg。 |
| `adopt_job(kind, task_id, path)` | 已知 task → 新独占 job；无网络/鉴权，不覆盖旧 state。 |
| `submit_job(client, path, planned)` | 客户端、job 路径、完整计划 → reused/job；同指纹仅复用，不同指纹拒绝。上传字节先验证，鉴权后独占写 intent，再单次 POST；成功响应中的有效 ID 先单独原子保存再更新 queueing；异常/不完整成功响应保留 submission_uncertain，异常阶段以固定 error.phase 标识，不记录原响应；仅明确 HTTP 4xx 标记 rejected。 |
| `query_job(client, path, timeout=90)` | 有 ID 的 job → 更新后的 job 和仅供下载用的临时 data；更新受限状态/查询时间或 last_query_error，正文/签名 URL 不写盘；旧 success 遇新查询错误不能触发下载。 |
| `job_outcome(job)` | job → result/退出码；success 或 pending=0，failed/rejected=1，未决/查询错误=2；先检查查询错误。 |
| `wait_job(client, path, seconds=50, interval=20, clock=monotonic, sleep=time.sleep)` | job 与有限调度窗口 → result/job 与退出码；时钟可注入，遇终态/查询错误立即返回；网络超时与调度窗口分离，详见 calling。 |

job 与磁盘写入失败向外传播；若提交后写盘失败，原 intent 仍阻止同路径再次提交。ID 检查点已保存时可从 submitting 直接 query 恢复；保存完全失败时仍需控制台找回，具体流程见 [提交后本地失败的恢复](../hi3d/references/calling.md#提交后本地失败的恢复)。独占创建约束仅覆盖同一路径，不能阻止调用者故意更换 job 重提；这一边界同时写入 skill。并发查询/下载没有事务合并，一个 job 由单进程维护。

### 下载与 Blender

| 函数或方法 | 输入 → 输出与边界 |
| --- | --- |
| `HttpsRedirect.redirect_request(...)` | 下载重定向 → 仅允许 HTTPS 且无内嵌凭据；不添加 API 认证头。 |
| `validate_glb(path)` | 文件 → 无返回值；检查 magic、version=2、声明长度与最小长度，不解析完整 glTF。 |
| `fetch(url, target, opener=None)` | HTTPS URL、新目标路径 → Path；临时流式下载、非空检查、适用时 GLB 头校验，硬链接独占发布，finally 清理临时文件；禁止覆盖，不携带 API 认证。 |
| `unpack(path, destination)` | 原始文件、新解压目录 → 文件 Path 列表；非 ZIP 返回原件；ZIP 先校验路径、重复成员、符号链接与声明总大小，再独占创建目录/文件；解压 GLB 校验头，保留原 ZIP。中断时保留不完整目录供检查。 |
| `file_record(path)` | 文件 → 绝对路径、bytes、sha256。 |
| `verify_artifact(artifact, output)` | manifest 和输出根目录 → 无返回值；核对原件、每个派生文件及已有封面的归属/大小/哈希，不修复或重写。 |
| `download_job(client, path, output, fetcher=fetch)` | 已知 job、新产物目录或完整缓存 → cached/artifact；有 manifest 时只验证缓存，否则需要新成功查询；识别误标后缀的 ZIP，可选封面失败只记录错误类型；保存完整 manifest。 |
| `edge_counts(triangles)` | 保留公开导入名，直接复用 [mesh-audit 数组契约](../.dependency-mesh-audit/references/mesh-measure.md#三角索引数组)，无本地算法副本。 |
| `inspect(obj, weld)` | Blender Mesh 对象、虚拟焊接开关 → 原始数据指标；读取局部顶点/三角索引，由共享 measure_indexed 检查有限值与面积；weld 使用精确坐标去重，不修改网格或变换。 |
| `import_asset(path)` | 模型或 BLEND → 无返回值；重置/打开 Blender 场景并导入；BLEND 禁止脚本自动执行。 |
| `bind_vertex_colors(objects)` | Mesh 对象列表 → 绑定记录；按颜色属性建材质并替换材质槽，只供新显示副本，非几何修改。 |
| `review_asset(source, metrics, *, weld=False, vertex_colors=False, display=None)` | 源资产、新报告、可选新显示副本 → 报告字典；导入、检查、可选打包保存，核对源文件哈希不变；拒绝覆盖、路径碰撞、无 mesh 或无副本的顶点色操作。 |

Blender 指标的单位、面积阈值、UV 拆点解释和人工验收限制见 [review](../.dependency-hi3d-api-source/references/review.md)。解压不是沙箱执行，不加载模型中脚本；几何检查不能证明模型可打印或无自交。

### 入口与测试代码

`hi3d_api.parser()` 构建子命令；`execute(args, client_factory=Client)` 返回对象与退出码，可独立注入客户端，离线命令不创建客户端；`main(argv=None)` 解析、执行并仅输出脱敏 JSON，异常只报告类型和固定指引。`blender_review.main(argv=None)` 解析 Blender `--` 后参数或显式 argv，调用 review_asset，不处理任何认证。

`test_api.py` 的 `reply`、`glb_bytes` 构造固定响应/最小 GLB；`Response` 为内存响应流；`Opener.__init__/open` 记录请求并提供固定内存响应；`FakeClient.__init__/auth/request` 计数并消费模拟响应；`Tests.setUp/plan` 创建可自动清理的临时输入并调用真实计划函数。`test_*` 方法按可观察行为覆盖：离线命令零鉴权、全大写环境变量映射、惰性认证和固定源、POST 不重试、GET 刷新上限、余额类型、各模式参数及输入、字节变化阻断、multipart 内容、同 job 复用、歧义留存、认证失败无 intent、adopt 全路由、过期成功阻断、有限轮询、脱敏、无认证下载/覆盖拒绝、无效 GLB、危险 ZIP、缓存篡改和 JSON 文件权限。补充的模拟回归覆盖含点号的官方形状 ID 从提交到查询下载、离线接管、ID 检查点中断后恢复、非法 ID 的固定阶段诊断与不重提。所有认证值都是明确标记的合成值，不读取实际环境。

`test_blender.mesh_snapshot()` 返回当前 mesh 顶点/面/世界变换；`run_review_test(root)` 创建新目录及有 UV 接缝/顶点色的 GLB，检查指标、另存重开一致和覆盖拒绝，写测试报告；`main()` 解析新工作目录并调用。测试会重置 Blender 测试场景，不能在用户未保存的前台工程运行。

## 验证方式与实际范围

```bash
"$PYTHON" -m unittest discover -s "$SKILL_DIR/tests" -p test_api.py -v
"$BLENDER" --background --factory-startup --python-exit-code 1 --python "$SKILL_DIR/tests/test_blender.py" -- --work "$RUN_DIR/new-review-test"
```

2026-09-08 已在 macOS 的 Python 3.9.6 运行 24 项离线测试通过；Blender 5.2.0 LTS 合成 GLB 检查通过：索引顶点 6、精确坐标诊断顶点 4，三角面 2，边界边从索引视图 6 到诊断视图 4，另存副本重开后几何与变换一致，原件哈希保持。动画工作流 在仓库外副本通过 5 项权重测试及完整合成 GLB→准备→BVH→权重→绑定动画→重开验收，检查 5 帧。

官方在线契约、真实鉴权、收费提交、账户额度/扣费、真实大模型和生产角色视觉质量均未验证；未查看真实密钥。每个实际任务仍需按当前服务契约与用户授权执行。

仓库外独立包在 Python 3.9.6 与 3.13.13 均通过 24 项 API 回归。独立 AI 上下文仅收到复制出的 skill 和两张合成图，完成 Master/500 万面/front+left 的本地预检及已有 task ID 的 adopt，13 项产物断言通过；审计保护记录网络、凭据读取和外部进程尝试均为 0。夹具只验证视图标签与顺序，不证明真实多视角对应。该验证为显式提供路径后的直接调用，未安装到用户技能目录，未验证宿主自动发现。

最终包通过 skill-creator frontmatter 校验与 Ruff 检查；全仓库本地链接、9 个 API Python 文件及 22 个动画 Python 文件的文档映射、README 三个 skill 的一一对应/字母排序与密钥规则扫描通过。仓库外 API 副本再次通过 Blender 检查；动画副本的 16 个 CLI 均可独立导入并查看帮助。

[参数面板测试](../.dependency-hi3d-api-source/tests/test_web_option_gates.py) 验证 v2.1 的 fast/quality 原生映射，并拒绝旧的 v2.1:pro 面板值。

## 账号 Runtime backend

请求关联由宿主按本次工具调用注入：`SPARC3D_TOOL_SESSION_ID`、`SPARC3D_TOOL_TURN_ID` 分别映射为 `X-Session-Id`、`X-Turn-Id`。Client 初始化时保存各自值，限 1–128 个 ASCII 字母、数字及 `_.:-`，非法非空值在联网前抛 ValueError，缺失时省略对应请求头。`_send` 对生成、查询及共享 MDF 调用统一加头；恢复调用使用新的用户轮次，新增请求头不改变既有业务请求体、job 或计划指纹。账号/环境校验和单次提交语义不变；产物下载器不附加关联头。

公共 AK/SK 模式继续保留。账号模式唯一源位于 [scripts/runtime](../hi3d/scripts/hi3d_api.py)，网络任务由 desktop 受管 Python 进程调用；普通 shell 不持有代理权限，离线 `check-image-prompt` 只读指定文本，可独立运行。Python 3.10+，Pillow 仅用于 PNG 派生。账号 Cookie 与 test/pre/prod 代理仍归宿主，工具只内部消费宿主注入的 loopback 地址/token；不会读取公开 AK/SK 或 Cookie 文件。参数、任务状态和认证不能与公共模式的账本互换。

| 模块 | 接口与职责 |
| --- | --- |
| hi3d_api | parser/execute/main：check-image-prompt 离线读取 UTF-8 最终文本，输出 characters/max_characters/valid，合格退出0、超长退出1，保留空格/换行、无客户端或 job 副作用；defaults、submit、adopt、query、wait、download、generate-image、generate-3d、retry-quota、retry、export-image；retry-quota 只读原任务剩余免费次数；retry 将 parentGenerateId POST 到本地代理 /model3d/retry，再由宿主转正式账号接口 /aigc/api/generate/img2model3d-url 并走新 job 的等待/下载；离线 dry-run 不建客户端；中断转 SystemExit 以清理临时文件 |
| hi3d_client | Client.auth/check_job/request：验证 /session 元数据、账号/环境并限制生成、查询 /model3d/result 和本地 /model3d/retry 路由；send 只允许公开 mesh/invoke POST；Client 初始化时保存宿主提供的请求关联头，_send 统一附加；无重定向、无自动 POST 重试；ApiError 提供受限错误消息 |
| hi3d_parameters | load_defaults/image_prompt_budget/build_plan/multipart/secure_url：按唯一 scripts/runtime/defaults.json 生成原生 scene/version/otherParam 或 image DTO，保留稀疏槽位；v3.0 默认原生 modelType=standard，旧 2048quality/2048master 分别转换为 standard/quality，显式原生值仍按原值覆盖；image_prompt_budget(str) 用 Python len 返回 characters/max_characters/valid，非字符串抛 ValueError；在 request/--set 覆盖后检查最终图像 prompt ≤4000 字符，超限拒绝不截断；校验文件大小、MIME、哈希和实际上传字节，禁止身份/计费字段与非 HTTPS 资源 |
| web_option_gates | project_web_options/reject_gated_request/display_overrides/native_display_overrides/project_parameter_interaction/submit_choice_gate/gate_parameter_overrides/validate_generation_selection：网页会员带钻目录；`generation_type=texture` 为公共 `request_type=2`、原生 `scene=texture`+`generationType=texture`，CLI 把 `has_mesh`（`--request` 存在时为 None）传入门禁，无 GLB 或 v2.0/v2.1 档位在上传前抛 ValueError；3D `model_type` 的 option `label` 为提交 id，`description` 为网页短文案；文生图/图生图的 selected_complete 恒为 true、project_parameter_interaction 返回 None、门禁直接 ready，不要求面板答案；其他需要选择的任务返回合法 `preference`（默认答案、60 秒）；可选图片 settings 与 3D 弹窗 id 换成公共或 native 字段，v2.0 原生档位 balanced/quality、v2.1 原生档位 fast/quality；v3.0 前端 quality/master 分别对应公共 2048quality/2048master 与原生 modelType=standard/quality，默认推荐前端 quality（实际传 standard）；生模/浮雕/拆件参数不完整时返回 waiting_choice 且不 POST，参数齐全后 ready；surface=agent 标准用户可选，surface=web 锁定；credits_unlock=false |
| hi3d_jobs | submit_job/adopt_job/query_job/wait_job/job_outcome（response_error 兼容导出自 storage）：持久化一次意图和 task ID，绑定账号环境；不确定提交不自动重发；图像 status=2 时提取 task_failure 到 error，result 仅保留数值状态/进度，避免保存自由文本；提交/查询异常记录 exception_summary；仅新鲜查询原响应供本次下载；retry_quota_view/read_retry_quota 从结果响应 retryCount 投影 remaining/eligible/can_retry，缺计数字段视为不可重试；record_parent 保存响应的 parentId 并拒绝重试根任务冲突；retry_root_id 对 retry job 读取 parent_task_id，对普通 job 读取 task_id（可采用已有 parentId）；retry_parent/retry_job 把根任务写入新 job 的 parent_task_id，POST 正文仅 parentGenerateId，不覆盖原 job，retryType/tier/amount 仍禁止 |
| hi3d_generation_workflow | generate_task：一次 submit→wait→download；恢复同一任务，GET 错误可显式继续；等待/下载异常重读最新账本并返回 phase、error_type、安全 error 摘要；图片失败附 next_action 停止提示；generate_retry_task：一次 retry_job→wait→download，新 outputDir，新 ID 和可用的 submitted_retry_quota 快照持久化后立即回调 event=submitted，成功结果含 parent_task_id |
| hi3d_image_workflow | image_plan/generate_image：由工具包统一组装图像 DTO 和转换模型别名；request 字典/文件覆盖便利参数，--set 最后覆盖；不修改调用方原请求；主图/参考/多视图编辑，原始图与 PNG 派生分开 |
| hi3d_progress | progress_snapshot/job_summary/emit_progress：有限百分比、排队/阶段变化及有效进度增量；stderr JSONL 与 stdout 最终结果分开，不推测 ETA；job_summary 保留 task_id/job_file 及 error/last_query_error，旧失败 job 从 result 提取原因，图片失败/歧义附 next_action |
| hi3d_storage | workspace_path/digest/load/save：工作区内无符号链接路径、SHA256、0600 排他意图/原子 JSON；safe_error_message/response_error/task_failure/exception_summary 集中构造安全错误摘要，保留 submission_has_task_id 以区分明确拒绝与可能受理；public_record 脱敏键、嵌套 JSON、URL 查询/片段；private_result_path/save_private_result/load_private_result 只供宿主管理的响应续下载缓存，目录由宿主注入且必须在工作区外，权限受限，不是交付产物 |
| hi3d_artifacts | fetch/unpack/validate_glb/result_urls：无鉴权 HTTPS 下载 ≤1GiB，≤10000 文件/8GiB 的安全解压，GLB 校验与结果/附件提取；download_job 以逐结果账本验证已发布字节、补齐中断的文件、恢复后续下载并汇总 immutable artifact；export_image 以 Pillow 转 PNG，排他发布或校验相同内容 |

详细调用、字段类型、文件限制、视图约定与错误/恢复规则分别见 [入口](../hi3d/SKILL.md)、[参数](../hi3d/references/parameters.md)、[桌面参数](../hi3d/references/desktop-parameters.md)、[desktop 免费重试清单](../hi3d/references/desktop-free-retry.md)、[图像](../hi3d/references/image-generation.md)、[调用](../hi3d/references/calling.md)、[网页 option 门禁](../hi3d/references/web-option-gates.md)。这些接口来自 desktop 的账号客户端契约，维护仅离线模拟；不据此声称实际环境的模型或服务已验证可用。

文生图/图生图调用失败即停止并报告，不因原有生成授权自动更换参数、模型、路径或工具重提；用户明确要求后才恢复。正常 pending 仍可继续查询同一任务，已有单次 POST 和稳定 job 复用不变。调用成功且取得图片后，效果不佳、视角错误或质量验收不通过属于质量迭代，可按已有授权和调用方原有次数限制继续修图或重新生成，无需逐轮重新确认，不因此暂停整项任务。质量新版本使用新的 job/输出目录，保留成功任务及产物；这不允许绕过调用失败或提交不确定的原 job。质量验收状态不得写成服务任务的 failed；最终验收门槛照常执行。

错误摘要契约：`safe_error_message(message)` 仅接受非空字符串，清除控制字符、压成单行并限制 500 字；敏感标记整段隐藏，URL/JWT/长凭据片段脱敏。`response_error(status, body)` 保留受限 HTTP/code/domainCode/trace/source 及 msg/message/error.message。`task_failure(result)` 从 failReason/failureReason/errorMessage/errorMsg/message/msg/字符串 error 或 error.message 按顺序取首个非空原因，取 errorCode/error.code/code 为可选数字码，返回 phase=generation；没有原因明确说明服务未提供，不使用查询外层成功消息代替原因。字段缺失不影响失败判定，不保证目标服务都提供这些可选字段。`exception_summary(error)` 对本地 ValueError/TypeError 和 ApiError 脱敏，超时给出固定原因，OSError 只取 errno 对应系统说明（无 errno 时使用固定文件/网络提示），其他异常仅保留类型及固定指引，不回显任意传输正文。CLI main 保留原 error_type/message/code，另附 error、可用 job_file 和图像停止提示；不改变退出码。

普通输出不保存 token、Cookie 或签名下载 URL。MDF 无查询接口，需恢复下载的原响应只进入 Runtime 私有结果缓存；工作区 job 保存脱敏响应与存在标记，缓存丢失时保留原任务并报告不可续下载，不重发生成。公开模式无需该缓存。

账号 `response_error` 统一提取 code/domainCode 和脱敏 message/trace/source，由纯函数 `business_error_details(code, domain_code)` 为[查询错误码映射](#查询错误码映射)的全部12类错误附 category、reason 和 next_action。表中领域码与顶层码按明确配对分类；系统 domainCode=500 独立识别。未知或格式非法的领域码不猜测含义，desktop-proxy 自身错误不冒充服务业务错误。

`query_job` 仅接受 HTTP 200、code=200 和合法任务状态。有效业务拒绝（HTTP 200、有效 code!=200、来源非 desktop-proxy）通过 record_query_failure 的 business_failure=true 设置 state=failed、error、空 result 和终态观测时间；last_query_error.query_failed=true，返回 failed / 1，进度 stale=false。未知业务码也适用，不依赖领域码白名单。HTTP/代理错误、无效响应及传输异常只更新 last_query_error 和查询时间，保留 state、result、result_observed_at；返回 attention / 2、stale=true，不宣称任务失败。两类情况均停止当前轮询；下载刷新遇到错误也保留诊断。

state=failed 在此表示明确业务失败；正常成功响应中的图片 status=2 也表示任务失败。Runtime 对上述失败通知回补本地预估消耗；查询本身失败不回补，即使缓存 state 已为 failed。账本按任务ID保证已记账且幂等回补。用户主动恢复查询不可用的任务时，同参数 generate 查询原 ID，不重复提交。显式 query 得到合法状态后清除旧错误。Agent 用用户语言说明具体原因后结束本轮，默认不展示数字错误码。

账号回归覆盖表中所有业务错误、数字/字符串码、model/image、错误落盘、停止轮询与显式恢复。桌面集成验证业务失败触发本地预估回补，HTTP/连接/无效响应不回补、保留状态和进度且可恢复原任务；账本验证重复通知和重启不重复回补。

[账号测试](../hi3d/tests/runtime/test_account.py) 验证本地模拟的传输隔离、真实上传字节、任务恢复、错误脱敏及 PNG 不覆盖；另覆盖 v3.0 前端 quality/master 经参数面板和旧 resolution 两条路径生成 standard/quality 原生请求、默认推荐高质、显式原生值不被二次转换，以及更正默认值后旧 job 不被覆盖、图片计划指纹不变。图像失败回归覆盖文生图/图生图的提交拒绝、提交歧义、服务终态失败原因及旧 job 摘要、查询异常、等待/下载异常与 CLI 校验；核对单次 POST、失败不下载、不泄漏合成敏感文本，正常 pending 仍可恢复同一任务；成功出图后的质量修订可在新 job/输出目录继续，视觉未通过不附调用失败停止提示，旧任务与产物保持不变；[下载恢复测试](../hi3d/tests/runtime/test_recovery.py) 验证部分下载和文件发布中断续跑、内容变化拒绝与临时目录清理。

图像 prompt 的 4000 字符预算由 `hi3d_parameters.IMAGE_PROMPT_MAX_LENGTH`、纯函数 `image_prompt_budget` 与 `build_plan` 在最终 DTO 统一执行，`image_plan`、普通 `submit` 和 native request 都不能绕过。一个中文字、英文字母或非 BMP 码点算一个字符，空格、换行和标点同样计入，不按 UTF-16 单元、UTF-8 字节或 token 计数。Agent 先保存按 settings/request/便利参数优先级确定的最终文本，离线执行 `check-image-prompt --prompt-file`；超长等义精简到4000字符以下、复查通过才生成，追加修订后重复检查，不机械截断。脚本只读指定 UTF-8 文件，不修改文本、不创建客户端或 job；本地超长准备可直接修订，不授权重试已有失败或不确定任务。中英文、非 BMP 与混合文本的4000/4001边界、CRLF/末尾换行、`--set` 覆盖、原请求不变性和正式调用前阻断由账号离线测试覆盖。本地计数说明与调用示例见上面的图像参考，未以收费生成验证服务端行为。`defaults.json` 的两种图像任务默认 `modelName="GPT Image 2"`，`generate-image --model` 默认读取文生图配置；显式模型、原生 request 与 --set 保持原有覆盖优先级。离线测试验证默认、模型覆盖与 dry-run 不创建客户端或 job。

文生图和图生图免参数弹窗，默认使用 `gpt-image-2`；Agent 根据内容、用途与参考图推荐支持的比例并显式传入 `aspectRatio`，用户明确指定的模型和比例优先。CLI 的 `1:1` 保留为未传比例时的兼容回退，不是 AI 推荐逻辑。账号离线测试覆盖两类图片无需面板答案即可提交、推荐比例传递及已有任务复用；其他生成任务的参数面板保持原有门禁。

图片默认模型、AI 推荐比例和 prompt 预算必须在 [Hi3D agent 必读入口](../hi3d/SKILL.md#图片生成与编辑) 明确提供；desktop 的工具 schema 只描述转发契约，不保存模型枚举/别名映射、默认模型或 prompt 最大长度。`imageModel` / `aspectRatio` 直接转为 CLI 的 `--model` / `--aspect-ratio`，缺省不传；原生 request 原样写入临时文件，由 `image_plan` 将其叠加到便利参数形成的 DTO，再交给 `build_plan` 执行最终覆盖与校验。相同最终 DTO 保持同一指纹，可继续恢复既有 job。宿主参数面板回答复用原有 `settings → --set` 转发，由 Python 门禁组装 DTO。这样参数目录仍由 skill 包维护，参数更新不要求同步修改客户端 Runtime。

`response_error` 仅接受最多12位非负整数或纯数字字符串的 domainCode，规范为整数；空值、布尔、对象和任意文本不保存。桌面代理也须透传该字段，否则本层无法恢复已被丢弃的领域码。完整分类和停止行为见上面的查询错误契约；所有表内业务错误均结束当前流程，不以请求失败推断退款到账或远端引擎状态。

查询恢复与回补边界：query_job 在错误捕获内执行 check_job，登录失效、账号/环境不匹配也写入 last_query_error 并返回 attention。submit_job 的 check_existing 默认为 true；generate_task 复用既有 job 时设为 false，仅延后到 query_job 校验，原 backend/fingerprint 校验仍保留，所有实际查询前仍验证账号。最近一次为查询不可用时可越过缓存 failed 重新 GET，不改变提交歧义的停止规则。无缓存产物的 download 同样由 query_job 校验；缓存产物继续单独校验账号。Runtime 对比调用开始时的 result_observed_at，只有新观测且没有查询不可用错误的 failed 才通知回补，避免鉴权/进程失败或缓存复用触发旧记录回补。回归覆盖鉴权失败、账号/环境切换、HTTP 错误、旧失败后恢复原任务和未查询时不回补。

### 查询错误码映射

以下映射供工具实现维护与排查使用，Agent 使用工具返回的结果、原因和恢复指引，不自行实现分类、状态持久化或积分回补。入口与调用参考只保留调用方行为和结果读取契约。

| code | domainCode | 原因 | 处理提示 |
| --- | --- | --- | --- |
| 1003 | 空 | 请求参数错误 | 核对参数，不重复原请求 |
| 1003 | 10030103 | 通用生成失败 | 保留任务；文档所述约15分钟退积分不是到账确认 |
| 1003 | 10030104 | 找不到原始重试任务 | 核对原任务ID及账号环境 |
| 1003 | 10030105 | 超过允许的重试次数 | 停止重试，不自行新建任务绕过 |
| 1003 | 10030106 | 超过套餐并发任务数 | 等已有任务结束，用户要求后再处理 |
| 1003 | 10030107 | 当前套餐功能额度耗尽 | 提示核对套餐额度 |
| 1003 | 10000024 | 输入图片不符合平台规则 | 停止生成，由用户决定是否更换合规输入 |
| 1003 | 32001 | 模型包含违规内容 | 停止交付，不下载该结果 |
| 30010000 | 空 | 积分余额不足 | 提示余额不足，不自动购买或重提 |
| 30010001 | 空 | 需要确认积分消耗 | 等用户明确授权，不自动确认扣费 |
| 409 | 空 | 数据版本不是最新 | 后续继续前刷新数据，不重复旧版本提交 |
| 系统错误 | 500 | 系统繁忙或未知异常 | 保留任务，用户要求后再查 |

账号免费重试：CLI retry-quota --job 联网前校验原 job；retry --parent-job 归一化根任务并复用同一新 job。HTTP 200、code=1003 且 domainCode 为 10030104/10030105/10030106/10030107，明确来自上游且没有任务受理标记时记录 submission_rejected；其他不确定结果保留，不重发。Runtime 动态工具传 fileName 或 retryRequestId，自动登记与意图持久化由 desktop 维护；CLI 路径只供宿主映射，不是 Agent 可自选的生成计划。
