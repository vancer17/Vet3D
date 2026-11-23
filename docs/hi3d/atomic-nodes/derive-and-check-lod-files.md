# 派生并核对档位文件

以 Hi3D Agent 1.2.11（Windows x64）为核查基准。桌面 `mdf_api` 同步提交一次 `mesh-lod`，将服务回执保存到原作业，再解析动态档位和下载文件。**服务成功由作业状态确认，档位齐全由每个预期档位对应的实际 GLB 确认。** [随包 MDF 接口契约](../upstream/1.2.11/prebuilt-skills/mdf-api/references/mesh-invoke-api.md#5-lod-动态结果解析)

## 业务定义

| 项目 | 契约 |
| --- | --- |
| 触发 | 上游已确定新派生路线并通过离线预检，或已有同一派生作业需要恢复。已选的合格复用档位直接进入本次逐档验收。 |
| 上游与输入 | 当前工作区、已确认源 GLB 路径和摘要、预期目标面数、原 `jobPath` 与 `outputDir`、本次用途及必保要求。确认计划和实际文件属于同一处理意图。恢复已有作业时使用原账号与环境。 [LOD 规划与预检](plan-lod-source-and-budgets.md) |
| 网格与图片角色 | `file` 只传派生基准 GLB。各档以目标面数关联。若需按方向比对外观，原参考图和必保特征随验收要求交接。 |
| 输出 | 保留原作业状态与可用的 `requestId`，以及目标面数、动态字段、可用本地文件和账本摘要的逐档对应。服务报告面数可选。记录缺档、重复指向、无效文件与可恢复原因。 |
| 完成条件 | 已保存服务成功回执，每个所需目标均有可用的、与账本摘要相符的实际 GLB，重复引用已得到明确处置。仅取得部分文件时保留可用档位及问题清单，整组仍待补齐或调整交付范围。 |
| 下游 | 将齐全的档位文件清单、源与作业引用、用途和验收要求交给[逐档验收与整组定稿](review-and-finalize-lod-set.md)。面数、材质、保形和动画质量以该阶段的回读为准，按需再登记。 [模型版本登记](../infrastructure/workspace/import-or-register-model-version.md) |

## Skill 绑定

工作区通用规则约束文件归属、产物命名和实际路径。新派生及其下载恢复共用桌面 MDF 入口。角色动画及游戏演示的额外交接由实际选用的 Skill 决定。 [工作区模板](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:5>) · [桌面 Runtime 约定](../upstream/1.2.11/prebuilt-skills/.dependency-run-tools/references/desktop-runtime.md)

| 归档入口 | 选用条件与作用 |
| --- | --- |
| [mdf-api](../upstream/1.2.11/prebuilt-skills/mdf-api/SKILL.md) | 桌面新派生与恢复的通用入口。指导同意图先预检再正式提交，使用稳定作业路径，按保存的结果恢复文件。 [公开接口](../upstream/1.2.11/prebuilt-skills/mdf-api/references/mesh-invoke-api.md#36-lod-减面烘焙mesh-lod) |
| [rig-retarget](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) | 当档位要交给绑定、换网格或动画时选用。按其桌面参考核对实际档位、GLB 和材质，交接通过后按任务继续本地准备或绑定。 [桌面 LOD 参考](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/runtime-mesh-lod.md) |
| [hi3d-game-demo](../upstream/1.2.11/prebuilt-skills/hi3d-game-demo/SKILL.md) | 游戏演示确需减面时进入 LOD 检查点，将派生文件与其材质和元数据交给资产接入。复用合格资产的路线可跳过该检查点。 [PCG 路线](../upstream/1.2.11/prebuilt-skills/hi3d-game-demo/pcg/routes.yaml) · [游戏资产接入](../upstream/1.2.11/prebuilt-skills/hi3d-game-demo/references/assets.md) |

## LLM Tools

| 独立工具说明 | 调用时机与条件 | 注册与核查情况 |
| --- | --- | --- |
| [mdf_api](../tools/mdf-api.md) | 新派生且离线计划已确认时执行 `invoke`，能力为 `mesh-lod`。原账本已有成功回执，需要补取或复核下载时执行 `download`，沿用原作业与输出目录。 | Runtime 动态工具。安装包核实了分派及动作。隔离回放实际执行原脚本，本机样例会话没有该能力的实际调用。 |
| [exec](../tools/exec.md) · [wait](../tools/wait.md) | 当前以 Code Mode 包装调用时，用 `exec` 承载工具。只有取得运行中的 `cell_id` 时，用 `wait` 续读同一单元。 | 等待对象是本地执行单元。MDF 公开路由为同步提交。 |
| [exec_command](../tools/exec-command.md) | 按需读取工作区内的作业摘要，核对本地路径、摘要和实际 GLB 内容。 | 本地执行入口。随包 GLB 检验和按用途回读可分开验证。 |
| [workflow_report](../tools/workflow-report.md) | 已选有流程图的专项且实际维护该图时，按当前节点上报进度、阻塞或产物归属。 | Runtime 动态工具。完成应以已核对的逐档文件清单为依据。 |

`invoke`、`download` 是 Tool 动作，`mesh-lod` 是能力枚举，`target_face_num_list` 是能力参数。`mdf_api.py` 及其 `lods`、`download` 函数是本地实现。PCG 的 `mdf.invoke` 是操作标签，`confirm_required` 是检查点声明。独立环境中的 `$mdf-call` 使用另一个调用契约。桌面专项的公开分支统一使用 `mdf_api`。 [工具注册](../tools/README.md#注册与可见性) · [桌面 LOD 分支](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/runtime-mesh-lod.md)

## Hi3D 实现

### 决策

新派生沿用预检的源文件、参数和路径。需要跨调用锁定输入时，业务侧保留上游批准摘要，检查实际提交的字节。再次 `invoke` 会重算指纹，既有同路径账本匹配时进入保存结果的恢复，指纹冲突则保留原账本并报错。已知成功账本时可以直接 `download`，仅需原 `jobPath` 和 `outputDir`。脚本经宿主取得当前账号和环境，并与账本核对。 [上游摘要边界](plan-lod-source-and-budgets.md#执行) · [执行与恢复分流](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:180>) · [会话与账号核对](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/hi3d_client.py:50>)

### 执行

#### 同步提交与留档

**根据已验证行为重建的正式请求。** 输入与路径沿用先前的预检计划。

```json
{
  "action": "invoke",
  "capability": "mesh-lod",
  "file": "inputs/character-rest.glb",
  "params": { "target_face_num_list": [500000, 200000] },
  "jobPath": ".hi3d/mdf/character-lod.json",
  "outputDir": "exports/character-lod"
}
```

1. **复核身份。** Runtime 从工作区工具参数组装受管脚本调用，并传入会话和轮次关联信息。Python 计算能力、参数、源文件 SHA-256 和解析后的输出目录构成的指纹。指纹不包含文件名和会话轮次。原作业的账号和环境另行核对。Skill 指导正式提交使用宿主确认流程，桌面 MDF 实际登录态下的确认与扣费尚待验证。 [Runtime 分派证据](../tools/mdf-api.md#核查依据) · [源文件和指纹](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:180>) · [账号核对](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/hi3d_client.py:50>)
2. **占位后提交。** 新作业检查宿主私有缓存路径，再独占创建并同步写入 `UNKNOWN`。之后才将 `request` JSON 和单个 `file` 二进制部分组为 multipart，发送同步 `POST /v1/mesh/invoke`。组包时复核实际读取字节。随包服务文档给出的算法预算是 7200 秒，Python 传入的请求超时是 7500 秒，Electron 代理期限和 Runtime 进程预算分别是 7800 秒与 8100 秒。 [占位写入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/hi3d_storage.py:175>) · [multipart 组包](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:70>) · [服务等待契约](../upstream/1.2.11/prebuilt-skills/mdf-api/references/mesh-invoke-api.md#6-状态失败与超时)
3. **保存回执。** HTTP `200`、类型为整数的 `code: 0`、业务 `status: "SUCCEEDED"` 三项符合时才记本地成功。有效的明确失败或拒绝状态保留。提交、回包处理或写盘异常可能留下 `UNKNOWN`。账本保存脱敏响应，完整下载信息留在工作区之外的宿主缓存，按作业路径与账号环境关联。下载开始前已持久化本地成功状态，所以下载报错后账本可能仍为 `SUCCEEDED`。 [回包与状态保存](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:215>) · [脱敏与私有缓存](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/hi3d_storage.py:200>)

#### 解析档位与逐项下载

以请求的 `500000` 档为例，`data.mesh_lod_glbs["500000"]` 可以指向回包字段 `near`。映射要求目标是无前导零的正整数键，字段指针是字符串。客户端先取 `data.files["near"].key`，该值缺失或为假值时回退到 `data["near"]`，随后校验所取 key 是否以 `.glb` 结尾。下载描述来自 `data.files["near"]`。下载记录成功后，用该 `field` 查工具结果 `files["near"]`。客户端按**目标面数数值降序**排列 `lods`，比较原列表。省略参数时比较随包契约的默认列表 `[2000000, 500000, 200000]`。原响应可选的 `mesh_lod_metadata[target].actual_faces` 透传为 `actualFaces`。 [动态字段契约与示例](../upstream/1.2.11/prebuilt-skills/mdf-api/references/mesh-invoke-api.md#5-lod-动态结果解析) · [档位解析](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:97>)

下载遍历整个 `data.files`，其中可以有档位之外的描述符。文件名为 `hi3d-<field><后缀>`，可下载文件的后缀取自 URL 路径。真实下载使用 HTTPS，通过临时文件排他发布，单文件上限为 1 GiB。对于 `.glb`，MDF 检查魔数、版本和声明长度，随后逐项将成功的路径和 SHA-256 写入账本。工具 `files` 映射取自账本记录。 [MDF 下载循环](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:114>) · [共享下载与容器校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/hi3d_artifacts.py:26>)

**根据安装包实现重建的伪代码。** 概括成功回执之后的档位解析与通用下载分支。

```python
def collect_saved_lod_result(job, record, output_dir):
    if record.status != "SUCCEEDED":
        return summarize(job, record)

    data = load_original_response(job, record).get("data") or {}
    descriptors = require_object(data.get("files", {}))
    issues = []
    try:
        record.lods = parse_and_sort_lod_pointers(data)
        expected = record.request["params"].get(
            "target_face_num_list", [2000000, 500000, 200000]
        )
        if [lod.target_faces for lod in record.lods] != expected:
            issues.append("LOD targets do not match the request")
    except (ValueError, TypeError, AttributeError):
        issues.append("Invalid LOD result")

    if not descriptors:
        issues.append("No downloadable file descriptors")
    for field, descriptor in descriptors.items():
        verify_saved_file_or_download_and_record(
            job, record, output_dir, field, descriptor, issues
        )

    record.download_issues = issues
    save(job, record)
    return summarize(job, record)
```

### 验收

这里验收档位文件能否交接。先核对原请求的目标集合，再逐项走 `lods[].field → files[field] → 实际 GLB → 账本摘要`。同一份文件被多档引用时标出冲突和受影响档位。若用途明确允许共用，应记录为已约定的复用。本节点只确认文件与档位身份。每档可读且摘要匹配后，面数和几何、UV、材质、动作质量交给逐档验收。 [随包档位核查指导](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/runtime-mesh-lod.md)

| 原回包或文件情况 | 已核查的客户端行为 | 交接判定 |
| --- | --- | --- |
| 档位列表缺失、无效字段指针或取不到有效 GLB key | 报 `Invalid LOD result`。有效下载描述符仍可处理。 | 档位身份不明确，保留成功下载的文件及原回包待核对。 |
| 解析后少档或多档 | 报 `LOD targets do not match the request`，继续下载现有描述符。 | 按原目标标出缺失和多出档位。多出文件无法补足缺档。 |
| 有顶层 GLB key，缺少该字段的下载描述符 | `lods` 能列出该档，`files` 没有该字段。其他下载正常时 `downloadIssues` 可以为空。描述符存在但缺 URL 时报告 `download unavailable`。 | 该档缺本地 GLB，保留 key 和 `requestId`。 |
| 多个目标指向同一个字段 | 生成多条 `lods`，同一 `files[field]` 只记录一次。问题列表可以为空。 | 标注重复指向，按原计划区分独立派生档位和获准复用。 |
| GLB 存储 key 对应 PNG 等 URL | 该档映射可通过，通用下载器可按 URL 后缀交出其他格式文件。 | 实际文件需符合 GLB 交接要求。 |
| `data.files` 整体类型无效 | 下载分支抛错，原账本可保留 `SUCCEEDED`。 | 保存原账本，按下载结构异常处理。 |

工具进程可在本地作业状态为 `SUCCEEDED` 时返回退出码 `0`，即使 `downloadIssues` 非空。相反，下载阶段抛错可返回失败退出码，而已保存的服务状态仍成功。完整性以逐档对应和实际文件为准。 [摘要及异常退出](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:253>)

## 完成与恢复

| 当前状态 | 恢复入口 |
| --- | --- |
| 原 Code Mode 单元仍在运行 | 用原 `cell_id` 调 `wait` 续读同次执行。这里的等待发生在本地执行单元。 |
| 原账本显示 `UNKNOWN`，或同步提交断线、中断且结果不明 | 保留原 `jobPath`、请求及已知的 `requestId`，交服务侧核对并暂停重提。公开接口无按 `requestId` 查询或远端幂等入口。匹配指纹的同路径重入只读取原记录。 |
| 原账本保存 `SUCCEEDED`，且部分结果尚未记入下载清单 | 按下例使用 `download`。沿用原目录及当前匹配的账号环境，只处理缓存响应所描述的文件。缺 URL 或 URL 不可用时保留 key，交服务侧核对。恢复复用原下载信息。 |
| 已入账文件缺失、改变或路径不符 | 报 `saved artifact changed or missing`，保留原清单和摘要，跳过该字段重取。工具回包可带旧路径。未入账旧文件占据目标位置时也会触发排他保护。先按实际文件和账本核对冲突，保留原作业。 |
| 明确 `FAILED` 或 `REJECTED` | 处理已知原因。确需重新派生时，用新的明确意图建立新作业，保留旧记录。 |
| 仅部分档位可用，或档位文件已齐全但质量未过 | 保留已取得的候选、摘要和仍缺的档位。补文件沿原成功回执处理，调整档位或交付范围时回到规划。质量不符按受影响的档位修订并复验。 |

**根据已验证行为重建的下载恢复请求。** 使用同一作业的原路径，选择 `download` 时只提供以下三项。

```json
{
  "action": "download",
  "jobPath": ".hi3d/mdf/character-lod.json",
  "outputDir": "exports/character-lod"
}
```

下载恢复可经过桌面本地会话鉴权。有原成功回执且下载描述有效时，从宿主私有缓存恢复文件。算法 POST 次数不因恢复而增加。档位逐项核对完毕后，交付档位文件清单及上游验收要求。需要版本登记时，在下游验收后按实际导出文件交给工作区登记。 [原作业恢复实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:180>) · [MDF 作业状态契约](../upstream/1.2.11/prebuilt-skills/mdf-api/references/mesh-invoke-api.md#6-状态失败与超时) · [工作区登记](../infrastructure/workspace/import-or-register-model-version.md)

## Vet3D 迁移与核查范围

### 供应商无关的交接契约

保留三个独立结果。执行记录保存原计划、输入摘要、供应商回执和提交状态。逐档记录保存预期目标与实际文件、摘要、可选服务元数据及缺档或重复原因。后续质量结论绑定每档实际文件及用途。供应商适配器把动态字段翻译成逐档记录，并按相同作业恢复可取文件。业务层核对必交档位和是否允许共用文件。

只有当每个预期档位都有可读 GLB 且身份可核对时，向下游声明文件齐全。可用的部分档位保留为候选，连同缺口交恢复或修订。不明提交保留原作业及关联号。如果选型支持查询，适配器应沿原远端任务继续。当前 Hi3D MDF 适配依据为同步回执和本地账本。 [预期档位与必保要求](plan-lod-source-and-budgets.md#供应商无关的交接契约)

### 下游接收检查

Vet3D 按上游业务档位标识记录预期输出及实际文件。缺档或同一文件意外对应多个档位时，将受影响的档位和原作业引用交恢复步骤。已取回档位可以先保存测量结果，最终验收仍按批准的必交范围逐档完成。 [分档预算](plan-lod-source-and-budgets.md#供应商无关的交接契约) · [逐档与整组验收](review-and-finalize-lod-set.md#供应商无关的交接契约)

### 安装包证据、样例与缺口

- **静态证据。** `runtime.mjs` 内 `Qj` 与 `runMdf` 的零基字节偏移分别为 `2513223` 和 `2538264`。`app.asar` 的 `out/main/index.js` 内，`212862` 对应代理路由白名单，`214629` 对应 mesh multipart 校验，`215315` 对应代理超时。随包 `mdf_api.py` 的 SHA-256 为 `5042920c95a891987f81e9e8cc53f96e81c936f54989cbff94f90af1fc35ef05`。其中 `execute`、`lods`、`download` 分别覆盖提交、档位解析和恢复。 [Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) · [桌面 ASAR](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) · [客户端脚本](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py>) · [Skill 与专项参考归档](../upstream/1.2.11/README.md#确定-lod-源网格与分档预算的随包证据)
- **隔离核查。** 随包 7 项 MDF 测试通过。隔离回包和下载替身覆盖同步组包、倒序目标、部分下载、原账本恢复、漏描述符、重复指向、非 GLB 后缀以及已记录路径失效。双档指向同一字段和只缺描述符分别复现了 `SUCCEEDED`、空问题列表且只有一份本地 GLB。超时后重入保持原 `UNKNOWN`，累计只有一次模拟算法 POST。证据覆盖客户端分支，模型质量由真实产物验证。 [随包 LOD 测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/tests/runtime/test_mdf_api.py:76>)
- **样例范围。** 三份留存 GLB 用于工作区版本、文件尺寸和本地预检样例。两个留存会话中的实际工具调用未见 `mesh-lod`。样例缺少可用于确认真实逐档输出的生产回执。 [样例工作区](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40>) · [活跃会话](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl>) · [归档会话](<D:/download/.sparc3d-runtime/environments/prod/codex-home/archived_sessions/rollout-2026-11-11T11-24-05-01a1c8a2-5bab-7df0-8557-d36af12e8411.jsonl>)
- **待实测。** 真实账号与环境下的宿主确认、计费及中断行为，生产服务对缺档、重复引用与无效档位的判定，CDN 下载及恢复的实际可用性，以及交付 GLB 的有效面数、材质与动画质量。
