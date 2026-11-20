# 提交并恢复自动绑定

以 Hi3D Agent 1.2.11（Windows x64）为核查基准。桌面 Runtime 通过 `mdf_api` 的 `auto-rig` 能力提交已验收的身体网格，保存原请求与服务回执，再从同一作业下载候选 GLB。服务成功、候选文件可用和骨架蒙皮通过验收分别确认。 [桌面绑定交接](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/runtime-service-rig.md#身体输入与服务交接) · [自动绑定工具契约](../tools/mdf-api.md#auto-rig-的输入与产物)

## 业务定义

| 项目 | 契约 |
| --- | --- |
| 触发 | 已选云端绑定路线且身体提交件已通过回读和离线预检，或已有同意图作业需要对账或补下载。已有合格绑定时沿复用路线。 [绑定路线](confirm-rigging-purpose-pose-and-route.md#决策) |
| 上游与输入 | 已验收身体文件、SHA-256、拟用参数、稳定的 `jobPath`、原 `outputDir`、休止空间和用途。保留原高模身份及回迁名单。恢复时接收原工作区、原作业及可用的关联号。 [提交件验收与交接](export-and-review-cloud-rig-body-glb.md#验收) |
| 素材角色 | 正式请求上传单个身体网格。上游照片、对照图和非身体部件可随验收记录交接，原高模在回迁阶段仍可定位。 |
| 输出 | 原作业的已保存状态、可用的 `requestId`、下载检查点和异常。本轮所需文件齐全且通过实际文件核对时，输出 `files.rigged_mesh` 对应的可读 GLB、SHA-256 及来源。 |
| 完成与下游 | 同一作业已保存 `SUCCEEDED`，绑定结果键对应可读取且摘要相符的实际 GLB。交[骨架与蒙皮候选核验](review-rig-and-skinning-candidate.md)，并附原提交件与回迁约束。已有绑定缺陷或下载异常时保留候选和证据，按故障点恢复。 [随包回迁检查](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/service-rig.md:37>) |

## Skill 绑定

通用桌面入口提供当前工作区、会话与模型文件身份。选用云端绑定时，`rig-retarget` 定义身体输入和候选交接，`mdf-api` 定义公开请求、提交与恢复。 [工作区模板归档](../upstream/1.2.11/archived-p0/resources/runtime/templates/AGENTS.md#操作规则) · [桌面 Runtime 约定](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md#宿主执行模式)

| 归档入口 | 选用条件与作用 |
| --- | --- |
| [rig-retarget](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) | 判定需要服务自动绑定时选用。对照已验收的身体、轴向和单位，保留原高模，收到候选后交实际骨架、权重和回迁核验。 |
| [mdf-api](../upstream/1.2.11/prebuilt-skills/mdf-api/SKILL.md) | 桌面调用公开 `auto-rig` 时选用。先离线预检，再沿同一意图正式调用。已有作业按原记录核对或恢复。 |

## LLM Tools

| 独立工具说明 | 用途、调用时机与条件 | 注册与核查情况 |
| --- | --- | --- |
| [mdf_api](../tools/mdf-api.md#auto-rig-的输入与产物) | `invoke` 的预检沿用上游。提交件和意图与已验收记录一致后正式 `invoke`。已有 `SUCCEEDED` 且所需文件尚未入账时用 `download` 补取。 | Runtime 动态工具。分派、预检、提交与恢复等客户端分支已用隔离夹具复核。 |
| [exec](../tools/exec.md) · [wait](../tools/wait.md) | 使用 Code Mode 编排时，原调用仍在运行且有 `cell_id`，用 `wait` 续取同一单元。 | Code Mode 执行与续读入口。续取的是本地调用回包。 |
| [exec_command](../tools/exec-command.md) | 核对正式提交前的源摘要、原作业状态、实际下载文件和摘要。 | 本地执行入口。按报告或作业记录对账。 |
| [workflow_report](../tools/workflow-report.md) | 选用绑定 Skill 且维护工作流图时，按实际作业及候选状态上报进度。 | Runtime 动态工具。图状态与服务状态及候选可用性分别确认。 |

`invoke`、`download` 是同一工具的动作，`auto-rig` 是能力枚举，`mdf_api.py` 是随包 Runtime 脚本。`rig` 是 PCG 检查点，`mdf.invoke` 是其操作声明。Skill 指导等待宿主提交确认，确认步骤沿用宿主。 [公开工具入口](../tools/mdf-api.md) · [PCG 确认声明](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/pcg/routes.yaml:18>)

## Hi3D 实现

### 决策

1. **识别新提交或原作业。** 稳定的 `jobPath` 关联一次处理意图。已保存成功且需要补取时沿用原作业。提交不明时持续保留原记录，并核对原调用与已知的服务关联号。正式调用的同路径重入只处理现有记录。 [原作业分支](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:180>)
2. **核对预检与实际提交件。** 上游预检传单个当前工作区文件。OBJ、FBX 和 GLB 上限均为 256 MiB。GLB 分支检查容器头和长度，身体、姿态和外观依据由上游实际回读提供。`dryRun` 计算指纹并返回请求、实际输入路径、作业路径和 `timeoutSeconds: 2100`，在登录、组包和写账本之前结束。它未仲裁旧账本，预览也未包含输入摘要、指纹或输出目录。正式调用前用验收记录中的 SHA-256 对照当前文件。文件或处理意图变化时，重新核对上游验收及预检。 [本地校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:45>) · [上游预检](export-and-review-cloud-rig-body-glb.md#mdf-离线预检)
3. **沿用已确定的参数。** 公开 `params` 是扁平对象，只支持布尔 `use_skeleton`、布尔 `use_transfer` 和整数 `num_beams`。服务文档默认值分别为 `false`、`true`、`10`，`num_beams` 范围为 1–20。标准身体导出关闭蒙皮、动画和 morph，因此新绑示例使用 `use_skeleton: false`。`use_skeleton: true` 请求沿用可提取的输入骨架，内部资料记载缺骨骼 token 时可回退生成。`use_transfer: true` 的目标是提交网格，需要时再本地回迁高模。 [公开参数](../upstream/1.2.11/prebuilt-skills/mdf-api/references/mesh-invoke-api.md#37-自动绑定auto-rig) · [内部服务选项边界](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-service-select/references/mdf/auto-rig.md:18>)

### 执行

**根据已核查契约重建的正式请求示例。** 以下沿用仓库上游示例的文件、作业路径、输出目录和参数，省略 `dryRun`。

```json
{
  "action": "invoke",
  "capability": "auto-rig",
  "file": "exports/hi3d-body.glb",
  "params": {
    "use_skeleton": false,
    "use_transfer": true,
    "num_beams": 10
  },
  "jobPath": ".hi3d/mdf/body-rig.json",
  "outputDir": "exports/hi3d-body-rig"
}
```

随包 Skill 把正式请求的 `waiting_choice` 交给宿主。安装包 Runtime 已定位共享会话额度前门、`runMdf` 分派和 `hi3d_api` 专用生成参数面板分支。后者依赖 `hi3d_api` 参数解析结果。MDF 专项面板与扣费接线仍待登录态实测。 [随包提交指引](../upstream/1.2.11/prebuilt-skills/mdf-api/SKILL.md) · [宿主确认与执行预算](../tools/mdf-api.md#宿主确认与执行预算)

1. **鉴权并核对身份。** Python 通过桌面本机代理读取 `/v1/session` 的账号与环境。已有账本按当前账号、环境及指纹核对。指纹包含能力、实际参数对象、输入字节摘要和解析后的输出目录。事后显式补写服务默认参数也可能改变指纹。会话和轮次由 Runtime 注入，用于关联请求。 [鉴权与请求头](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/hi3d_client.py:30>) · [指纹与重入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:195>)
2. **先占位，再组包和 POST。** 新作业检查宿主私有缓存可用性，排他写入顶层 `UNKNOWN`。之后用 `request` JSON 和单个 `file` 二进制部分组成 multipart。组包再验输入字节摘要，经 Electron 本机代理同步 `POST /v1/mesh/invoke`。服务算法预算为 1800 秒，Python 的 POST timeout 参数为 2100 秒，Runtime 子进程预算为 2700 秒。 [独占账本写入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/hi3d_storage.py:175>) · [组包实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:70>) · [公开状态与超时](../upstream/1.2.11/prebuilt-skills/mdf-api/references/mesh-invoke-api.md#6-状态失败与超时)
3. **保存原回包，再进入下载。** HTTP `200`、整数 `code: 0`、业务 `status: "SUCCEEDED"` 同时成立时判为服务成功。完整回包进入按原作业路径和账号环境定位的宿主私有缓存，公开账本及工具输出使用脱敏回包。私有回包写入或提交中断可使账本停在 `UNKNOWN`，即使内层已有成功状态。 [回包和落盘顺序](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:216>) · [私有缓存定位](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/hi3d_storage.py:244>)

**按随包脚本归纳的实现伪代码。** 以下省略通用 schema 校验与异常回包包装，展示本地占位边界和同路径重入。

```python
def invoke_auto_rig(call, context):
    request, source_digest, fingerprint = validate_and_plan(call, context)
    if call.dry_run:
        return preview(request, call.file, call.job_path, timeout_seconds=2100)

    account = authenticate_desktop()
    if record_exists(call.job_path):
        original = load_record(call.job_path)
        verify_owner_environment_and_fingerprint(original, account, fingerprint)
        return download_or_summarize_original(original, call.output_dir)

    require_private_cache(call.job_path, account)
    record = reserve_exclusively(call, account, request, fingerprint, status="UNKNOWN")
    try:
        multipart = pack_and_check_source(request, call.file, source_digest)
        http_status, response = post_once("/v1/mesh/invoke", multipart)
        record.response = sanitize(response)
        save_private_response(call.job_path, account, response)
        record.status = classify_response(http_status, response)
        save_record(record)
    except Exception:
        record.status = "UNKNOWN"
        save_record(record)
        return summarize(record)

    return download_or_summarize_original(record, call.output_dir)
```

`download_or_summarize_original` 对非 `SUCCEEDED` 记录返回摘要。对于成功记录，下载器从私有回包的 `data.files` 读取描述符。`response.data.rigged_mesh` 是结果字段，实际取件依赖 `data.files.rigged_mesh.url`。HTTPS 下载通过临时文件排他发布，常规 GLB 文件名为 `hi3d-rigged_mesh.glb`，容器校验通过后将文件路径及 SHA-256 逐项写入账本。`files.rigged_mesh` 取自该下载检查点。 [下载与摘要实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:114>) · [文件写入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/hi3d_artifacts.py:37>)

### 验收

1. **确认原作业已保存成功。** Runtime 外层 `success` 对应脚本退出码，解析 `stdout` 中的业务 JSON 核对原作业状态。服务成功时仍可能带下载异常，下载阶段异常也可使工具退出失败而原账本仍为 `SUCCEEDED`。 [工具回包结构](../tools/mdf-api.md#参数与结果)
2. **确认绑定候选的实际文件。** 从 `files.rigged_mesh` 定位 GLB，核对下载诊断、实际可读性、输出路径和账本 SHA-256。通用下载器接受多种后缀，也可能在仅有其他结果字段时返回空的 `downloadIssues`。结果键与无异常回包不能代替实际 GLB 检查。 [候选下载源码](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:140>)
3. **交付核验材料。** 附原作业及可用的 `requestId`、原提交件、休止空间、原高模与回迁目标。下游核对实际骨架层级、skin、权重、尺度和材质后决定能否回迁。已有证据表明候选缺失所需蒙皮或存在缺陷时，保留失败文件与证据供核对。正式模型登记在适用验收通过后按交付要求进行。 [回迁门槛](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:180>) · [版本登记与文件身份](../tools/workspace-commit-model.md#文件身份与复用)

## 完成与恢复

| 现场状态 | 后续处理 |
| --- | --- |
| 原调用仍运行 | 已获 Code Mode `cell_id` 时，以 `wait` 续读原单元。等待中的 `UNKNOWN` 可能只是已写入的占位。 |
| 未占位，且已确认失败发生在预检、鉴权或缓存准备阶段 | 修正实际原因并核对原提交计划。已有原账本时转相应恢复分支。 |
| 本地停止、同步请求中断或顶层 `UNKNOWN` | 保留原 `jobPath`、`outputDir`、请求和已知的 `requestId`。组包前已占位，所以零次 POST 和已发送后的超时都可能出现同一状态。同路径重入不会再次 POST，公开入口没有查询动作。按原请求交服务侧核对。 |
| 已保存 `SUCCEEDED`，有下载描述且结果未入账 | 同账号、环境、原路径与原目录使用 `download`。缺描述、URL 失效或宿主私有缓存丢失时保留原回执及结果键。恢复使用原描述符。 |
| 文件已入账但缺失、变化，或同名目标存在而未入账 | 原路径可能仍在 `files` 中，伴随 `saved artifact changed or missing`。已入账项会直接跳过下载，已有同名目的文件也会被拒绝覆盖。保留原记录和现有文件供对账。 |
| `FAILED` 或 `REJECTED` | 结合 HTTP、`error_source`、消息和服务记录界定失败阶段。主进程读取上游响应超限时也可返回 HTTP `502`、`REJECTED` 和 `error_source: desktop-proxy`，该场景仍需核实原请求是否已执行。确认原请求结果及修正原因后，明确的新尝试才分配新账本。 |

**根据公开 schema 重建的恢复请求。** 沿用上例的作业和输出目录，参数交给 `mdf_api`。

```json
{
  "action": "download",
  "jobPath": ".hi3d/mdf/body-rig.json",
  "outputDir": "exports/hi3d-body-rig"
}
```

恢复分支先核对当前账号、环境和原输出目录，再按账本状态处理。非成功账本返回原摘要。`download` 在读入原账本后进入恢复分支，所需请求字段见上例。正式调用与恢复动作的通用行为见独立工具页。 [原作业恢复](../tools/mdf-api.md#实现伪代码) · [续读原单元](../tools/wait.md)

## Vet3D 迁移与核查范围

### 供应商无关的交接契约

| 记录 | 业务语义 |
| --- | --- |
| 已验收提交计划 | 按实际输入摘要关联拟用绑定能力、参数和输出位置。保存上游回读证据。文件或意图变化时，更新验收和提交计划。 |
| 原作业身份及服务回执 | 保存同一尝试的本地记录、可用远端关联号、提交阶段、可确认结果和异常来源。结果不明时保留原尝试和对账所需信息。由适配器记录所选供应商是否支持查询或安全重试。 |
| 下载检查点及候选 | 保存结果角色、确切文件、摘要、可读性和未解决的下载问题。带访问凭据的下载信息由宿主持有。记录原提交件与认可高模间的关系。 |

Vet3D 的绑定供应商尚未选型。先定义身体提交件、已有骨架复用意图、期望保留的材质与尺度、候选用途和后续验收边界，由适配器映射到供应商契约。四足业务保留自身的休止姿态及骨骼语义，能否走供应商自动绑定需另外验证。

### 下游接收检查

绑定候选核验接收与原作业摘要匹配的实际 GLB，并能定位被提交的身体、原高模及二者的休止空间。候选的结构和蒙皮经核验后，按用途复用、回迁或退回修订。恢复同一次下载与修订后重新提交分别保留各自的记录。

### 安装包证据、样例与缺口

- **版本与原件。** 核查使用 Hi3D 1.2.11（Windows x64）安装事务备份。`mdf_api.py` 的 SHA-256 为 `5042920c95a891987f81e9e8cc53f96e81c936f54989cbff94f90af1fc35ef05`。`runtime.mjs` 的 `Qj` 与 `runMdf` 零基字节偏移分别为 `2513223`、`2538264`。`app.asar` 的 `out/main/index.js` 成员内，`216340` 对应从正文或头部补关联号的逻辑，`217246` 附近对应代理构造超限错误。 [版本清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) · [Runtime 与脚本定位](../tools/mdf-api.md#核查依据) · [桌面 ASAR](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>)
- **隔离实测。** 随包 Python 的 7 项 MDF 测试通过。独立替身覆盖组包摘要变化导致零次 POST 的 `UNKNOWN`、提交超时后同路径重入、成功后补下载、私有缓存写入失败和已记录路径变化。实测一般结果键可使下载问题列表为空而缺少 `rigged_mesh`，无蒙皮的 GLB 也可通过容器校验。这些试验验证客户端分支和候选检查边界。 [随包测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/tests/runtime/test_mdf_api.py>) · [GLB 容器校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/hi3d_artifacts.py:26>)
- **样例覆盖。** 三个留存猫模型 GLB 均通过离线 `auto-rig` 预检，其中第二份为 210900336 字节，低于 256 MiB。预检未启动传输，也未创建账本和输出目录。三份模型均无蒙皮和动作，两份关联会话未见自动绑定调用。样例只覆盖这些现有文件的客户端预检。 [样例工作区](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40>) · [留存会话证据](export-and-review-cloud-rig-body-glb.md#安装包证据样例与缺口)
- **待实测。** 生产桌面的实际确认与扣费、真实服务回包和签名下载恢复、超时或取消后服务侧最终状态，以及真实四足模型能否获得可用骨架、权重与可回迁候选。随包内部文档记录过特定测试部署的 GLB 调用，生产桌面与四足效果仍需直接检验。 [随包历史部署范围](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-service-select/references/mdf/auto-rig.md:5>)
