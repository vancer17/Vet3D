# 核对候选对当前任务的适用性

本节点按当前用途核对每份候选模型，交付确切文件引用、检查结果及缺失证据。以 Hi3D Agent 1.2.11（Windows x64）和随包 Codex 0.166.0 为核查基准。Hi3D 的工作区及工具负责提供可核对的文件和观察，Agent 据当前要求判断。留存会话中的具体动作见[运行证据](#运行证据)。

## 业务定义

| 项目 | 契约 |
| --- | --- |
| 触发 | 上游提供了一份或多份可供检查的本地候选，或者已取得正式版本而当前用途仍要求核对模型。单份候选同样适用。 |
| 输入 | 当前工作区、待核对的候选路径或已登记的确切版本、任务用途和硬性要求。下载件沿用原 `jobPath`、任务 ID、实际文件清单及可用的来源和摘要记录。修订候选交接实际相对路径、文件 SHA-256、源模型引用及本次变更和保留项。已登记产物可从版本记录取得路径。 [逐项落盘与清单复验](download-and-persist-artifact-manifest.md) · [模型版本查询](../infrastructure/workspace/query-assets-and-model-versions.md) |
| 图片角色 | 主参考图用于核对个体和基准姿态，补充图用于核对相应方向的轮廓、纹理或必保特征。目标方向通过候选渲染的相机或已核实的截图视角表达，保留项来自任务要求。作业封面或下载清单中的预览图片提供整项作业的外观线索，需要证明文件和画面的对应关系后才可归到具体候选。 [整组视图定稿](review-and-finalize-view-set.md) · [模型视觉证据](../infrastructure/workspace/acquire-model-visual-evidence.md) |
| 输出与完成条件 | 按候选交付确切文件引用、所检查的用途、证据覆盖范围和结论。当前用途的必需检查通过时可交下游。检查已明确失败时记录不符原因，证据暂缺时记录待查项和取证方法。 |
| 下游 | [主模型选定](select-primary-model-and-confirm-handoff.md)接收可用候选及依据。需改形、修补或重建局部时交局部结构修订，需调整整模或已有部件的尺寸、位置或朝向时交模型与部件变换。确切版本的登记、Studio 展示确认、用户放行及后续骨骼绑定由各自环节按需要执行。 [局部结构修订](revise-local-structure.md) · [模型与部件变换](transform-model-and-parts.md) · [版本登记](../infrastructure/workspace/import-or-register-model-version.md) · [Studio 版本加载](../infrastructure/workspace/load-studio-revision.md) |

## Skill 绑定

工作区 `AGENTS.md` 是宿主的通用入口，指导 Agent 根据外观、工程精度、装配、可编辑性或打印等用途选择检查，并在硬性要求缺少依据时收集必要信息。普通路线的基础检查与领域 Skill 的额外验收条件分别来自以下规则。 [随包工作区模板](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:23>)

| Skill | 选用条件与适用规则 |
| --- | --- |
| [Hi3D 通用建模](../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md#3d-任务工作流) | 普通图生 3D 路线选用。按返回的 `registeredModel` 或输出中的实际 GLB 继续。用户要求质量检查时，按用途核对载入、外形、材质与 UV、部件关系和明显网格问题。普通生成的 Blender 渲染、审计和报告按任务需要追加。 |
| [图片到高精度组装模型](../upstream/1.2.11/prebuilt-skills/image-to-assembly/SKILL.md#主流程与阶段出口) | 选用部件重建与装配路线时才追加在位环绕、承接、干涉与必要项检查。依赖当前部件结构的后续步骤，沿对应验收出口继续。 [随包配准说明](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/image-to-assembly/references/registration.md:24>) · [随包验收说明](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/image-to-assembly/references/validation.md:83>) |
| [Hi3D 人形动画 Skill（安装包）](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d-model-gpt-animation/SKILL.md:45>) | 选用人形动画路线时，才依该 Skill 核对姿势、绑定和变形。此入口尚未收入仓库快照。动物任务的骨骼与形变要求由自己的交付契约定义。 |

## LLM Tools

| 独立工具说明 | 调用时机与所得证据 |
| --- | --- |
| [`hi3d_api`](../tools/hi3d-api.md#已下载-3d-产物与登记) | 读取上游已取得的模型版本、作业和文件回包。原作业需要续查或恢复下载时，交回上游沿原作业继续。 |
| [`exec`](../tools/exec.md) · [`exec_command`](../tools/exec-command.md) | 在 Code Mode 中编排本地读取。对明确候选查询文件属性、读取 GLB 声明或运行需要的解析、渲染脚本。PowerShell、Python 和 Blender 属于由工具运行的程序。 |
| [`view_image`](../tools/view-image.md) | 将确切路径的本地像素提供给模型。先确定图像属于作业封面、原始参考图，还是某份候选的已知方向渲染。 |
| [`wait`](../tools/wait.md) · [`write_stdin`](../tools/write-stdin.md) | 确实有活动句柄时，分别续查原 Code Mode `cell_id` 与原本地进程 `session_id`。 |
| [`studio_get_state`](../tools/studio-get-state.md) · [`studio_load_revision`](../tools/studio-load-revision.md) · [`studio_capture_view`](../tools/studio-capture-view.md) | 需要对已登记版本取视窗证据时使用。先核对实际工作区和版本，必要时加载确切文件名，再核对所取画面的版本和视角。尚在导出目录的候选可用本地渲染取证。 |
| [`user_interaction`](../tools/user-interaction.md) | 仅在用途、目标文件或硬要求存在实质歧义，且需要用户给出信息或取舍时调用。 |
| [`workflow_report`](../tools/workflow-report.md) · [`workspace_commit_model`](../tools/workspace-commit-model.md) | 使用 Skill 图时可记录进度及产物归属。正式登记由下游使用选定的实际导出路径，本节点交付候选及检查依据。 |

## Hi3D 实现

### 决策

1. **从已确认的产物入口接入。** 组合生成和下载的回包可能带 `registeredModel`，也可能只交付本地文件清单。Runtime 的 `registerGeneratedModel` 在适用的自动登记分支中按普通文件、工作区范围与 `.glb` 扩展名计数。恰有一项时尝试登记。零项、多项或登记异常时，`stdout` 返回 `result: "attention"`、`phase: "register-model"`，原作业和文件清单仍可用于对账。此处确认的是登记分支状态。 [自动登记实现](../tools/hi3d-api.md#已下载-3d-产物与登记) · [原始 Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>)
2. **固定待核对的文件。** 已有正式版本时，按回包中的确切文件名和路径取证。使用旧证据前先确认它对应实际被检查的内容。可信同任务复用可返回字节不同的既有版本。只有下载件时，依据已复验的原作业文件清单确定候选，原下载记录、路径及摘要用于确认来源。对于本地修订导出的 GLB，候选直接由执行方给出确切路径，以工作区和内容摘要固定身份。工作区目录扫描可辅助定位。 [文件身份与版本复用](../tools/workspace-commit-model.md#文件身份与复用) · [上游下载来源](confirm-download-source-and-recovery.md)
3. **按用途决定检查深度。** 先取得本轮硬性要求。只要求交付可用的 GLB 时，可依产品契约核对文件身份与基本可读性。若要求外观、装配或动画证据，继续取得相应证据。此前留存的检查只有在候选内容与适用要求仍匹配时才可复用。 [常规质量检查规则](../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md#3d-任务工作流)

**根据已核查回包与文件接口重建的编排伪代码。** 此处展示云端生成或下载的交接。`output` 是解出的业务负载，已复验的下载清单来自上游。候选检查由 Agent 按用途选择。

```python
def candidate_references(output, workspace, verified_downloads):
    if output.get("registeredModel"):
        file_name = output["registeredModel"]["fileName"]
        return [resolve_exact_revision(workspace, file_name)]

    download_success = output.get("result") == "success"
    register_attention = (
        output.get("result") == "attention"
        and output.get("phase") == "register-model"
    )
    if download_success or register_attention:
        return match_verified_glbs(output.get("files", []), verified_downloads)
    return []
```

### 执行

| 检查 | 所需证据 | 结果能支持的判断 |
| --- | --- | --- |
| 文件身份与基础属性 | 确切路径或正式版本，普通文件和工作区范围，实际大小及可用的摘要。需要追溯下载来源时，核对原作业及记录。 | 确认实际访问的是哪份文件，以及来源或内容是否仍与记录匹配。 |
| 容器与声明字段 | 可读的 GLB 容器、首部、JSON 声明和按需取得的 mesh、`POSITION`、材质、UV、图片及骨骼等声明。 | 说明文件声明了哪些结构。需要确认这些结构能实际使用时，再取得对应解析或执行结果。 |
| 结构、呈现与任务要求 | 按用途取解码后的几何、材质和部件，或取得与候选内容绑定的指定方向渲染。按任务核对需要的尺寸、部件关系、外观或骨骼形变。 | 将观察与当前硬要求逐项比对。只记录实际覆盖的方向、特征和使用条件。 |

可用 `view_image` 读取已经确认来源和视向的本地渲染图。源照片及必保特征由任务上下文交给 Agent 比对，`view_image` 的实际输入是所读取图片的 `path`。Studio 加载就绪可证明该版本已进入视窗。验收若要求完整贴图，还应有可见的材质证据，因为安装包的贴图加载失败分支可以返回 `null`。 [视觉取证执行链](../infrastructure/workspace/acquire-model-visual-evidence.md#执行) · [Studio 加载契约](../tools/studio-load-revision.md)

**根据已核查工具契约重建的请求示例。** 已从原清单固定一个候选路径时，查询该文件的名称和字节数。此命令只读取文件属性。

```javascript
const result = await tools.exec_command({
  cmd: "Get-Item -LiteralPath 'exports/hi3d-example.glb' | Select-Object Name, Length",
  max_output_tokens: 256
});
text(result);
```

**根据历史 PowerShell 行为重建的伪代码。** 两次读取合并展示。命令扫描输出目录，未将候选与本次 `files` 取交集或核对摘要。两次均只解析第一个 chunk 的 JSON，未检查 chunk 类型及 BIN。 [元数据命令](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:131>) · [图片长度命令](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:138>)

```python
import json


def inspect_candidate_metadata(path):
    with open(path, "rb") as stream:
        stream.seek(12)
        size = int.from_bytes(stream.read(4), "little")
        stream.read(4)  # 实际命令跳过 chunk 类型
        doc = json.loads(stream.read(size).decode("utf-8"))

    primitives = [p for mesh in doc["meshes"] for p in mesh["primitives"]]
    counts = {key: len(doc.get(key, [])) for key in (
        "meshes", "materials", "textures", "images",
    )}
    return {
        **counts,
        "declared_positions": sum(
            doc["accessors"][p["attributes"]["POSITION"]]["count"]
            for p in primitives
        ),
        "node_names": [node.get("name") for node in doc.get("nodes", [])[:6]],
        "declared_image_bytes": [
            doc["bufferViews"][img["bufferView"]]["byteLength"]
            for img in doc["images"]
        ],
    }
```

### 验收

候选可交接时，Agent 交付实际文件或版本引用及其对应的检查依据。发现硬性不符时，留下具体失败项、源候选和必须保留的特征，以便修订或选择其他候选。证据不足时，保留该候选供后续补证。Hi3D 1.2.11 的所查实现中，候选适用性由 Agent 的后续交接体现，未发现独立的适用性判定 Tool 或通用排序器。 [工具注册索引](../tools/README.md) · [留存交接证据](#运行证据)

### 检查权限与事件

本地命令沿用当前工作区的执行权限与 `PreToolUse` Hook。回包需分别读取外层执行单元状态和实际命令结果。工具输出可进入本轮会话历史，跨轮或重连后按可取到的工具结果和实际文件重新核对。工作流图记录 Skill 进度及产物归属，候选的质量结论仍须引用对应证据。 [本地命令权限](../tools/exec-command.md#实现伪代码) · [有效历史恢复](../infrastructure/workspace/llm-context.md#读取线程和恢复有效历史) · [工作流状态](../infrastructure/workspace/workflow-graph-state.md)

- **额度、限流与重试。** 检查期间仍有普通模型采样。ASAR `out/main/index.js` 的 `qa`（`141965`）处理模型平台代理的费用或上游错误，普通限流路径可透传 `Retry-After`（`150387`）。`Nl.observeHost`（`223651`）节流 3D 代理诊断日志。没有发现候选专属额度、限流、自动重试或熔断。本轮仅换本地检查方式。下游动态登记另经过 `item/tool/call` 中的 `skillCredits.confirm`（Runtime `3167197`），不能从本地执行成功推出付费同意。 [桌面采样日志](<D:/download/.sparc3d-runtime/environments/prod/logs/desktop-20261111T032128Z-23156.log:1544>) · [桌面 ASAR](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>)
- **历史与 Memory。** rollout 第 111–112 行记内层完成，第 113 行保存关联原 `call_id` 的外层结果。顺序可用于对账，物理写盘时刻未实测。结果通过普通同轮历史进入后续上下文。生产未启用 `features.memories`，本机库的 `jobs`、`stage1_outputs` 均为零，未见独立 Memory 的评估写入、检索或注入。重连时 `thread/read(includeTurns:true)` 可补读桌面历史投影，`thread/resume` 恢复有效模型历史。压缩后后者可能不含旧图片或工具正文。 [模型与界面历史](../infrastructure/workspace/llm-context.md#读取线程和恢复有效历史) · [独立 Memory](../infrastructure/workspace/llm-context.md#独立-memory-的核查)
- **图事件。** Runtime `nw.mutate/save`（`3076125`、`3076703`）更新缓存和修订，尝试保存后发布 `workflow/graphUpdated`。写盘失败仍可通知。桌面消费该图，重连经 `workflow/read`（`2725466`）补读图与已登记产物引用。样本图只有 `references/generate/deliver`，未发现候选质量事件或自动回放检查。 [工作流落盘与续接](../infrastructure/workspace/workflow-graph-state.md)

## 完成与恢复

| 分支 | 续接与交接 |
| --- | --- |
| 证据达到要求 | 交给下游的是具体候选引用、已验证要求及对应证据。候选可以有多份，主模型选定由[下游交接](select-primary-model-and-confirm-handoff.md)完成。需要发布版本时，向登记提交已选且通过适用检查的实际导出路径。 |
| 本地检查 pending 或超时 | 有 `cell_id` 就用 `wait` 续查原执行单元，有 `session_id` 就用 `write_stdin` 续查原命令。句柄已失效时先核对已经落盘的输出，再对同一候选补取缺失的只读证据。 |
| 存在候选，证据不足或检查报错 | 保留源文件、已有结果和错误。可换检查方法、补必要视角，或在硬性信息有歧义时澄清。命令失败与文件损坏分别核对。 |
| 已取得证据，候选未通过 | 保留原因、依据和必保特征，交其他候选或修订。未登记的中间 GLB 若明确选为修订源，交接工作区、实际相对路径和 SHA-256。该选择只确定修订输入。新候选导出后，按其实际路径和摘要重新核对受影响的检查。其余证据在适用范围和对应文件一致时可复用。 [局部结构修订](revise-local-structure.md) · [模型与部件变换](transform-model-and-parts.md) |
| 提交不明或原下载未核实 | 保留原 `jobPath`、已有任务 ID 和诊断，回到原作业或下载来源节点。原任务可识别时沿原任务续查，缺 ID 时先对账。 |
| 登记回执待核对 | 保留实际导出路径、候选摘要和已有回包。有原作业时一并保留。交工作区登记流程核对实际文件与版本，分别恢复登记、视窗和工作流状态。 |
| 中断、重连或重复检查 | 保留已有文件和可重读的证据。仅复用仍匹配候选内容和任务要求的结果，按实际文件补齐缺失观察。 |

[本地执行单元续查](../tools/exec.md#用-wait-续查代码执行单元) · [原作业续查](locate-job-and-qualify-resume.md) · [登记恢复](../infrastructure/workspace/import-or-register-model-version.md#完成与恢复)

## Vet3D 迁移与核查范围

### 供应商无关的契约

可用工作区 ID、候选 ID、内容摘要、来源角色和任务要求版本固定待检查对象。由使用场景定义必需检查。外观任务可指定参考方向及必保特征。待绑定网格可检查肢体区分与关节附近结构。可动画交付可检查四足骨骼、权重及实际动作中的形变。供应商的角色字段、模型和 API 由后续适配层映射。

**Vet3D 设计伪代码。** 每份候选按当前用途单独得出结论。以下状态属于 Vet3D 的建议契约。

```python
def assess_candidate(candidate, requirement):
    identity = check_candidate_identity(candidate)
    checks = [identity]
    if identity.status == "passed":
        checks.extend(collect_required_checks(candidate, requirement))

    if any(check.status == "failed" for check in checks):
        return assessment(candidate, requirement, "unsuitable", checks)
    if any(check.status != "passed" for check in checks):
        return assessment(candidate, requirement, "needs_evidence", checks)
    return assessment(candidate, requirement, "usable", checks)
```

**Vet3D 设计示例。** 已核对候选几何可载入，动画证据仍待补。证据与候选摘要及要求版本绑定。

```json
{
  "workspaceId": "workspace-01",
  "candidate": {
    "artifactId": "candidate-01",
    "sha256": "c7e4a1cfeb732309479130d048026385bbde29b53f0034c97c915aaf2dd9e77a",
    "sourceJobId": "job-01",
    "sourceRole": "primary"
  },
  "requirement": {"purpose": "rigged_quadruped", "revision": 1},
  "assessment": "needs_evidence",
  "checks": {"geometryLoad": "passed", "motionDeformation": "not_checked"}
}
```

### 运行证据

以下记录来自一项普通多视图猫模型任务。它们用于复核运行行为与证据边界。

| 观察 | 可复核结果 |
| --- | --- |
| 输入与作业 | 用户提交正面、背面和右侧参考图。第 68 行发出组合调用，第 70–103 行沿同一 Code Mode 单元取得最终回包。账本保存原任务 `state: "success"`。自动登记收到两份 GLB 和一份 WebP，回包为 `attention/register-model`。 [用户输入](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:12>) · [回包](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:103>) · [作业账本](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/hi3d/hi3d-cat-multiview.json>) |
| 取证及恢复 | 第 109–113 行读取目录和作业封面，模型收到 `input_image`。第 124–127 行的 Python 单行命令因引号传递报 `SyntaxError`，随后改用 PowerShell 读取两份文件的 GLB JSON 声明。读取范围包括网格、`POSITION`、材质、贴图及图像声明长度，未解析 BIN。 [目录与封面](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:109>) · [错误及重取证](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:124>) · [元数据结果](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:134>) |
| 确切候选与来源 | 第 145 行将 `exports/hi3d-cat-multiview/hi3d-result-0/hi3d-api-result-0.glb` 交给登记，第 148 行返回正式文件 `hi3d-猫_1.glb`。事后用原作业和下载记录对账，所选件来自 `model3DGlbUrl`，另一件来自 `model3DPreviewUrl`。该样本中 Agent 未读取这些来源记录，记录也未提供可复核的排序算法。事后逐项核对两份候选时，各有一个 primitive 和两张嵌入 JPEG，JPEG 摘要逐张一致。两份文件的 `POSITION` 声明计数分别是 `1,022,866` 和 `1,022,200`。预览件声明量化及 meshopt 压缩。两份文件都没有声明蒙皮或动画。 [实际登记请求](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:145>) · [所选件下载记录](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/exports/hi3d-cat-multiview/hi3d-result-0/.download.json>) · [另一候选下载记录](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/exports/hi3d-cat-multiview/hi3d-result-1/.download.json>) |
| 下游证据 | 第 154–160 行确认正式文件存在，此时 Studio 仍返回 `ready: false`。第 164–167 行显式加载后，回包对同一文件确认 `loaded: true` 和 `state.ready: true`。第 171–175 行再报告图状态。该段覆盖登记、加载与上报，逐份候选渲染、用户放行及动画验收缺少对应记录。 [文件与视窗状态](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:154>) · [加载与工作流回包](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:164>) |
| 本地修订候选 | 第 479–482 行查看首次修订的最终正面近景，第 486 行提交对应导出。第 932–937 行查看第二次修订的正面和左侧近景，并读取 `hi3d-cat-face-repaired-final.glb` 的节点缩放、米制标记和资源声明，第 941 行提交该导出。 [首次修订取证](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:479>) · [再次修订取证](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:932>) |
| Skill 与上下文 | 第 5–6 行保存了通用工作区指令。第 19 行记录读取 `hi3d/SKILL.md`，第 28–31 行记录提交通用图。归档、随包入口及生产读取副本的 SHA-256 均为 `4c268ae14ece561234682d564cdfa6264c1f121a9ea118137c0388a9240c217d`。样本未选用装配或人形动画 Skill。 [工作区注入](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:5>) · [Skill 读取](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:19>) |

### 验证与缺口

- **安装包静态核查。** Windows x64 事务备份的 `app.asar` SHA-256 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`，`runtime/dist/runtime.mjs` 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`。Runtime 的自动登记、候选路径校验和登记首部校验分别在原文件零基字节 `3201579`、`3077348`、`2713155`。ASAR 的 `out/renderer/assets/index-CDPCug_K.js` 成员中，`loadFromUrl`、`loadTextureImage`、就绪事件匹配分别见 `2922827`、`2899313`、`4711410`。 [安装清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) · [原始 Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) · [桌面 ASAR](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) · [下载文件校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_artifacts.py:120>)
- **离线负例。** 将一份合成三角形 GLB 的 `BIN\0` chunk 标记改为 `JUNK`。正常件与修改件均通过随包首部校验和历史 JSON 读法，读到相同的网格与贴图声明。Blender 4.5.16 LTS 导入正常件成功，修改件在读取 accessor buffer 时返回 `KeyError: 0`。另将 JSON chunk 标记改坏后，ASAR 的 `ETe`（成员偏移 `2886765`）返回 `JSON content not found`。这些实验覆盖容器与实际解码的边界。 [随包首部校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d/scripts/hi3d_artifacts.py:26>)
- **待实测。** 对确切候选分别验证贴图解码、多方向还原和四足骨骼形变。受控重连后模型能收到哪些旧图像与工具结果、权限拒绝和命令终止的逐调用表现，也需按相应运行证据核对。云端结果质量需以实际产物检验。
