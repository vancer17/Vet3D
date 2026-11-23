# 确定 LOD 源网格与分档预算

以 Hi3D Agent 1.2.11（Windows x64）为核查基准。Agent 依据当前用途、确切模型文件和适用的 Skill 决定复用已有 LOD 或新派生。桌面 `mdf_api` 校验新派生的文件和请求格式。源网格身份、每档用途和验收要求由调用方保留。 [版本与原文归档](../upstream/1.2.11/README.md#确定-lod-源网格与分档预算的随包证据)

## 业务定义

| 项目 | 契约 |
| --- | --- |
| 触发 | 已有可处理模型，任务明确需要 LOD，或已确认面数、远近观察、动画或目标设备预算需要派生。没有减面需求时可继续使用原模型。 |
| 上游与输入 | 用户确认的用途、原模型或上游候选的确切文件引用、可复用的档位文件及既有验收依据。补齐影响交付的尺度、朝向、材质及适用的绑定要求。 [模型候选适用性](check-model-candidate-suitability.md) · [工作区素材与版本查询](../infrastructure/workspace/query-assets-and-model-versions.md) |
| 已有 LOD 复用 | 核对现有文件与本次档位要求的对应关系、摘要及原验收适用范围。交出逐档文件清单及已有证据，由下游完成本次整组核对。 |
| 新派生 | 选定一个源 GLB，确认档位预算与验收要求，形成可追溯的工作区请求并通过离线预检。将源引用、请求、预检和要求交给[派生并核对档位文件](derive-and-check-lod-files.md)。 |
| 完成条件 | 两条路线都能把实际文件绑定到明确用途和验收要求。复用路线已有可核对的候选清单。新派生路线具备源文件、已选预算和可执行请求。候选质量和版本登记依次由后续节点负责。 |

## Skill 绑定

工作区通用规则指导识别明确指定的文件、使用当前家族适用版本和保留原件。公共 MDF 规则在选中桌面新派生时生效，规定输入限制、离线预检与稳定作业路径。角色的休止姿态和游戏目标设备是选用对应专项后才核对的要求。 [工作区模板](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:23>) · [桌面 Runtime 执行约定](../upstream/1.2.11/prebuilt-skills/.dependency-run-tools/references/desktop-runtime.md)

| 归档入口 | 选用条件与作用 |
| --- | --- |
| [mdf-api](../upstream/1.2.11/prebuilt-skills/mdf-api/SKILL.md) | 选用桌面云端新派生时，读取 `mesh-lod` 公开能力契约，按同一计划先预检，再将正式调用交给宿主。 [公开参数](../upstream/1.2.11/prebuilt-skills/mdf-api/references/mesh-invoke-api.md#36-lod-减面烘焙mesh-lod) |
| [rig-retarget](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) | 需要向角色绑定、换网格或动画交付提供 LOD 时选用。先复用合格 LOD，新派生选择单角色休止姿态输入。按用途约定权重和动作验收。 [桌面 LOD 减面与动画交接](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/runtime-mesh-lod.md) |
| [hi3d-game-demo](../upstream/1.2.11/prebuilt-skills/hi3d-game-demo/SKILL.md) | 任务属于可玩演示或游戏资产接入时选用。先确定设备、观察方式、资产角色和保留精度，再决定是否派生以及各档的预算和证据。 [资产与运行时接入](../upstream/1.2.11/prebuilt-skills/hi3d-game-demo/references/assets.md) |

## LLM Tools

| 独立工具说明 | 用途、调用时机与条件 | 注册与核查情况 |
| --- | --- | --- |
| [studio_get_state](../tools/studio-get-state.md) | 用户指代当前视窗，且确切文件尚未确定时读取已加载身份。核对 `ready`、`assetId` 和 `fileName` 后解析磁盘路径。 | 桌面动态工具。已有通用视窗状态的运行记录。本次 LOD 规划没有生产工具回放。 |
| [exec](../tools/exec.md) · [exec_command](../tools/exec-command.md) | 按当前工具面核对本地路径、计算文件摘要，或读取已有档位的 GLB 元数据。 | `exec` 为 Code Mode 入口，`exec_command` 为本地执行入口。离线核查使用随包 Python。 |
| [user_interaction](../tools/user-interaction.md) | 已选游戏专项且缺少会影响方案的目标设备、用途或必要取舍时，按 Skill 收集业务输入。 | Runtime 动态工具。专项说明使用 `kind: "input"` 收集必要信息，沿用已经确认的事实。 |
| [mdf_api](../tools/mdf-api.md) | 新派生路径、预算和用途明确后，用 `invoke` 的 `dryRun: true` 执行离线预检。 | Runtime 动态工具。下文示例已在原脚本离线验证。正式提交确认属于后续执行。 |
| [workflow_report](../tools/workflow-report.md) | 选用有工作流图的游戏专项并实际维护该图时，按当前阶段记录计划和进度。 | Runtime 动态工具。图状态与源文件、预算和验收依据各自保留。 |

`workspace/open`、`workspace/models` 是宿主 RPC。`invoke` 是 Tool 动作，`mesh-lod` 是能力枚举，`target_face_num_list` 是公开参数。`mdf-api`、`rig-retarget` 和 `hi3d-game-demo` 是 Skill。游戏 PCG 的 `mdf.invoke` 是操作标签，`confirm_required` 是检查点声明。 [工具注册索引](../tools/README.md#注册与可见性) · [模型目录 RPC](../infrastructure/workspace/interfaces/model-catalog-rpc.md) · [游戏检查点](../upstream/1.2.11/prebuilt-skills/hi3d-game-demo/pcg/routes.yaml)

## Hi3D 实现

### 决策

1. **解析源版本。** 本轮指定的文件、已导入附件或已确认的上游结果直接解析到实际路径。指代「当前视窗」时读取实际加载身份，核对同工作区且已就绪的 `fileName`。按家族默认继续普通改模时，工作区规则取该家族数字序号最大的一版。指代仍不明确时先补齐具体文件。MDF 只接收调用方给出的 `file`。 [工作区规则](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:39>) · [版本目录与选择器](../infrastructure/workspace/query-assets-and-model-versions.md#执行) · [当前视窗状态](../infrastructure/workspace/read-studio-state.md)
2. **选择复用或新派生。** 已有 LOD 能覆盖本次所需档位和用途时，核对每个文件及其原验收依据。档位名称或工作区版本序号只提供查找线索，档位身份由来源、实际文件和对应的预算记录确认。需要生成新档位时选定一份原始 GLB 或已定稿的修订版本，保留原件，另设派生输出目录。动画专项使用单角色休止姿态，与已有骨架的休止空间核对。仅为绑定服务准备的代理单独记录用途，最终交付可以沿用原高模。 [动画源空间及摘要要求](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/mesh-lod.md#输入调用与产物) · [绑定代理](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/runtime-service-rig.md#身体输入与服务交接)
3. **确定各档预算。** 按用途给每档明确目标面数、必要时的实际面数上限、统计口径和必交范围。游戏专项还记录设备、观察距离、资产重要性和性能目标。源实际面数与材质证据帮助做取舍，客户端接受的目标范围由公开参数校验决定。生成模型的 Quality/Master、LOD 目标面数和贴图像素尺寸各自记录。已选游戏专项只有在关键要求缺失时补问，并保存用户已确认的方案。 [预算与统计口径](../upstream/1.2.11/prebuilt-skills/hi3d-game-demo/references/assets.md) · [专项需求输入](../upstream/1.2.11/prebuilt-skills/hi3d-game-demo/references/hi3d-game-brief.md)

`[500000, 200000]` 是桌面调用示例。公开参数 `target_face_num_list` 接受非空、严格降序的正整数列表，允许单档。省略参数或传外层 `params: null` 时，脚本用 `{}` 组请求。随包服务契约声明默认 `[2000000, 500000, 200000]`，客户端下载后也用该列表核对省略参数的回包。客户端预检检查参数类型、顺序与正值，实际源面数、角色数量、姿态和材质可用性由调用方另行取证。 [公开契约](../upstream/1.2.11/prebuilt-skills/mdf-api/references/mesh-invoke-api.md#36-lod-减面烘焙mesh-lod) · [参数与回包预期](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:27>) · [默认档位回包核对](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:132>)

### 执行

复用路线核对逐档实际文件和摘要，沿用仍覆盖本次用途的验收证据。证据不足的档位交给逐档验收，所缺的必交档位显式带入后续计划。游戏专项的 `reuse_asset` 路线声明可直接接入合格 GLB，跳过生成和 LOD 检查点。Vet3D 如需混合复用与补档，可由调用方维护逐档对应。 [桌面 LOD 复用](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/runtime-mesh-lod.md) · [游戏复用路线](../upstream/1.2.11/prebuilt-skills/hi3d-game-demo/pcg/routes.yaml)

新派生以当前工作区内的单个 GLB v2 为输入，大小须大于零且至多 200 MiB。路径解析约束到当前工作区，拒绝符号链接组件。脚本检查扩展名、大小、GLB 魔数、版本和声明长度。`jobPath` 须与源路径分离并位于输出目录之外。源 GLB 是唯一传给该能力的输入文件。原始参考图如需参与外观对照，随审查依据交接其方向与用途。 [工作区路径约束](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/hi3d_storage.py:144>) · [GLB 容器检查](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/hi3d_artifacts.py:26>)

**根据已验证行为重建的离线请求。** 示例的 `file` 是已确认的单角色休止姿态网格。

```json
{
  "action": "invoke",
  "capability": "mesh-lod",
  "file": "inputs/character-rest.glb",
  "params": {
    "target_face_num_list": [500000, 200000]
  },
  "jobPath": ".hi3d/mdf/character-lod.json",
  "outputDir": "exports/character-lod",
  "dryRun": true
}
```

**根据安装包实现重建的伪代码。** 概括 `mdf_api.execute` 的共同校验、预检返回和正式提交前的摘要校验。

```python
def invoke_mesh_lod(args, context):
    job_path = resolve_workspace_path(args.job_path)
    output_dir = resolve_workspace_path(args.output_dir)
    params = normalize_and_validate_public_params(args.params)
    source = validate_workspace_glb(args.file, max_mib=200)
    require_separate_job_path(job_path, source, output_dir)
    request = build_request("mesh-lod", params, context)
    source_hash = sha256(source)
    fingerprint = fingerprint_for("mesh-lod", params, source_hash, output_dir)

    if args.dry_run:
        return {
            "dryRun": True,
            "request": request,
            "file": str(source),
            "jobPath": str(job_path),
            "timeoutSeconds": 7500,
        }

    account = authenticate_desktop_account()
    if job_path.exists():
        return resume_existing_job(job_path, account, fingerprint, output_dir)
    reserve_unknown_job(job_path, account, fingerprint, request, output_dir)
    body = build_multipart(request, source, expected_sha256=source_hash)
    return submit_and_collect(body, job_path, output_dir)
```

离线分支读取源文件字节计算 SHA-256，并在鉴权、组包和写账本之前返回。可见回包仅含上例五项，原 `outputDir` 和批准时的摘要需要独立保留。首次正式调用重新读取文件摘要，组包时复核该次调用读取的摘要。已有账本才会比较原请求指纹。隔离验证中，换成另一份同路径 GLB 后，摘要改变而两次预检回包完全相同。若要锁定跨调用的源字节，应在交接中保存计划批准时的摘要，并在下游按实际路径重验。 [预检、指纹与续调](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:180>) · [组包摘要核对](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:70>)

MDF Skill 指导下游沿用同一意图的预检参数和作业路径，并在正式提交时使用宿主确认流程。游戏专项的业务输入用于确定需求，正式调用的确认另由其 PCG 检查点声明。实际登录环境的宿主接线待实测。 [MDF Skill](../upstream/1.2.11/prebuilt-skills/mdf-api/SKILL.md) · [游戏检查点](../upstream/1.2.11/prebuilt-skills/hi3d-game-demo/pcg/routes.yaml)

### 验收

本节点验收**交接是否就绪**。复用分支应能定位每份候选、核对摘要及证据适用范围。新派生应有明确的源引用、预算和通过的本地预检。下面的档位质量要求随计划交给下游执行，实际结果依据交付文件回读。

| 层级 | 约定的检查 |
| --- | --- |
| 通用档位与外观 | 必交档位齐全，每档可解析且文件对应正确。分别记录请求面数、服务报告面数和实际导入后的有效三角面数。按同一口径检查硬预算。对照源确认尺度、朝向、轮廓和细薄结构，实际查看 UV 接缝、贴图、法线及要求保留的材质通道。 |
| 绑定或动画 | 若只交给绑定，先核对休止姿态、坐标空间及应保留部件。若交付已含动画，按最终文件追加骨架、蒙皮、目标动作范围、形变与接触检查。验收范围和阈值随实际所选专项确定。 |
| 游戏或实时展示 | 按用例约定实际加载器、目标设备、观察距离及需要测量的加载、显存或帧表现。有切档交付时核对档间尺度、外观与必要的动作或挂点。 |

Vet3D 可在计划中为四足模型逐项列出耳尖、尾巴、趾部等必须保留的细节。将测量口径和对照源随同交接，便于验收者在各档重复同一检查。 [桌面档位检查](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/runtime-mesh-lod.md) · [动画专项验收](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/validation.md) · [游戏设备验收](../upstream/1.2.11/prebuilt-skills/hi3d-game-demo/references/validation.md) · [游戏角色回读](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/game-delivery.md#导出后回读)

## 完成与恢复

| 当前结果 | 后续处理 |
| --- | --- |
| 已有候选具备本次所需证据 | 交逐档文件、摘要、用途和已有结论给整组定稿。若证据只覆盖静态范围，动画或引擎结论留给相应下游。 |
| 已有档位缺失或旧证据失效 | 保留仍可用的档位，定位变化的文件或缺失的验收项。文件有效而证据不足时交复验。确需生成缺档时更新计划，记录其与保留档位的关系。 |
| 预检失败，或新派生源摘要改变 | 回到源选择或预算决策，确认实际文件、路径和变更范围后重新预检。 |
| 已有正式作业 | 把原 `jobPath` 和 `outputDir` 交给执行节点。原单元仍在运行时用 [wait](../tools/wait.md) 按 `cell_id` 续读。已保存 `SUCCEEDED` 时沿用原目录执行 `download` 补文件。提交不明时保留原记录和已知 `requestId`，暂停重提并用该编号交服务侧核对。公开同步入口只有提交与已保存结果的恢复。 |
| 上次候选已下载但未通过质量检查 | 保留候选及失败证据。仅重新测量或修订候选时交验收节点复验。改变源、档位或交付约束时修订计划，并按原作业状态决定后续执行。 |

通过本节点即可交接规划或已有候选。实际档位通过验收后方可定稿、交付或按需登记。登记由工作区节点负责。MDF 的公开同步入口在正式执行后按原账本恢复。 [MDF 作业与恢复](../tools/mdf-api.md#实现伪代码) · [模型版本登记](../infrastructure/workspace/import-or-register-model-version.md)

## Vet3D 迁移与核查范围

### 供应商无关的交接契约

业务层记录路线、源文件和内容摘要，有登记版本时附版本引用，并为每档记录目标、硬约束、必保特征和验收用途。复用路线挂接已有的候选文件和证据。新派生路线保存执行记录引用和输入摘要，适配器再映射供应商参数与作业路径。锁定源摘要时，让适配器针对实际读入请求的字节核对批准摘要，也可从已校验的不可变副本提交。变更源字节、档位或交付用途时重新检查受影响的计划与证据。

**Vet3D 设计示例。** 约定静态展示的两档预算。摘要和证据引用使用示例占位值。

```json
{
  "route": "derive",
  "source": {
    "versionRef": "character/rest-v3",
    "path": "inputs/character-rest.glb",
    "sha256": "<approved-source-sha256>"
  },
  "tiers": [
    { "id": "near", "targetFaces": 500000, "required": true },
    { "id": "far", "targetFaces": 200000, "maxFaces": 200000, "required": true }
  ],
  "review": {
    "purpose": "static-display",
    "faceCountBasis": "imported-effective-triangles",
    "preserve": ["silhouette", "ear tips", "tail", "scale", "material appearance"]
  },
  "executionRecordRef": "<stable-execution-record>"
}
```

### 下游接收检查

Vet3D 为每档分配跨执行与验收稳定的业务标识，并记录目标面数使用的计数口径及超限的处理方式。复用候选带着既有证据和待补检查项交逐档验收。新派生计划将预算、受理前核对的源文件身份和原执行记录引用一并交派生阶段。 [档位文件交接](derive-and-check-lod-files.md#供应商无关的交接契约) · [整组验收交接](review-and-finalize-lod-set.md#供应商无关的交接契约)

### 安装包证据、样例与缺口

- **随包实现。** `runtime.mjs` 的零基字节偏移 `2690065` 是 `Jg.listModels`，`2513223` 和 `2538264` 对应 MDF 参数转换和 `runMdf`。在 `app.asar` 的 `out/renderer/assets/index-CDPCug_K.js` 内，字节偏移 `4717250` 对应 `StudioHost.getState`。预检及摘要证据见预置 `mdf_api.py`，SHA-256 为 `5042920c95a891987f81e9e8cc53f96e81c936f54989cbff94f90af1fc35ef05`。归档的 Skill 与参考页按原字节保留。 [Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) · [桌面 ASAR](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) · [客户端脚本](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py>) · [归档哈希](../upstream/1.2.11/README.md#确定-lod-源网格与分档预算的随包证据)
- **隔离验证。** 随包 Python 读取一张三角面的 GLB，接受上述两档请求及单档，拒绝空列表、重复、升序、布尔值、小数及内部自交保护参数。省略参数时保留 `params: {}`。预检回包未随同路径文件的摘要变化而变化。客户端、组包和下载均设断言以验证未被调用，作业及输出目录均未创建。证据覆盖离线校验和交接风险。 [校验与预检实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:180>)
- **样例覆盖。** 三份留存 GLB 是工作区版本示例。用原脚本检查 `[500000, 200000]` 时，两份通过，第二份因 `210900336` 字节超过 200 MiB 被拒绝。两个留存会话的实际调用未见 `mesh-lod`。这些样例只支持本地校验和调用范围的结论。已有档位复用依据来自安装包 Skill。 [样例工作区](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40>) · [活跃会话](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl>) · [归档会话](<D:/download/.sparc3d-runtime/environments/prod/codex-home/archived_sessions/rollout-2026-11-11T11-24-05-01a1c8a2-5bab-7df0-8557-d36af12e8411.jsonl>)
- **待实测。** 登录态下 MDF 的宿主确认与计费，生产服务对默认、单档及大于源面数的目标的实际处理，真实四足资产逐档轮廓、UV、材质与动画表现，以及目标设备性能。分档质量与复用的场景适用性以回读的实际产物和证据为准。
