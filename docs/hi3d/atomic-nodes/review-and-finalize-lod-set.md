# 逐档验收与整组定稿

以 Hi3D Agent 1.2.11（Windows x64）为核查基准。Agent 按用途回读每档候选，组合随包测量、视觉取证和专项验收。档位文件齐全、逐档质量通过、整组定稿和工作区版本登记分别确认。 [桌面 LOD 交接](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/runtime-mesh-lod.md) · [前序档位文件核对](derive-and-check-lod-files.md)

## 业务定义

| 项目 | 契约 |
| --- | --- |
| 触发 | 新派生取得可核对的逐档文件，或已有档位带着文件及既有证据进入复用路线。修订后的候选沿原用途和档位关系复验。 |
| 上游与输入 | 已确认的源版本及摘要、各档候选文件与摘要、必交档位、目标面数和硬预算口径、外形或材质保留项及适用的绑定、动画或设备要求。新派生保留原作业与服务元数据，复用档位附已有验收证据。 [源与分档计划](plan-lod-source-and-budgets.md) · [派生文件交接](derive-and-check-lod-files.md#验收) |
| 图片角色 | 比较源网格和各档实际候选时，以确认的相同方向、尺度和观察条件获取画面。参考照片按实际用途提供主体和局部细节对照，渲染或截图需绑定实际候选身份。 [视觉证据](../infrastructure/workspace/acquire-model-visual-evidence.md) |
| 输出 | 每档绑定文件摘要的测量值、质量结论、已覆盖范围和问题记录，以及整组定稿清单或仍待修订的档位。 |
| 完成条件 | 必交档位均通过适用的检查，完成任务要求的档间核对，并固定最终文件及证据。单档通过可单独记录。交付范围变动时先确认更新后的必交清单。 |
| 下游 | 按实际目的交给展示、绑定或游戏接入。需要工作区版本时，将选定的确切 GLB 交登记，并保留档位到登记回执的对应。 [工作区登记](../infrastructure/workspace/import-or-register-model-version.md) · [文件交付](../infrastructure/workspace/preview-and-deliver-files.md) |

## Skill 绑定

通用工作区规则提供确切版本、工作副本、单位和登记约定。桌面 MDF Skill 指导按用途核查处理后的实际 GLB。角色动作、游戏交互和设备验收随选用的专项生效。 [工作区模板](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:37>) · [LOD 规划 Skill 归档](../upstream/1.2.11/README.md#确定-lod-源网格与分档预算的随包证据)

| 归档入口 | 选用条件与作用 |
| --- | --- |
| [mdf-api](../upstream/1.2.11/prebuilt-skills/mdf-api/SKILL.md) | 来自桌面 MDF 的档位保留原账本和下载清单，按用途检查后再交登记。只在仍需从原成功回包补齐文件时回到前序下载。 |
| [rig-retarget](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) | 面向角色绑定、换网格和动画交付。回读每档面数、UV、材质和法线，按用途追加休止空间、权重、动作与接触检查。 [LOD 验收与交接](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/mesh-lod.md#验收与记录) · [动画验收](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/validation.md) |
| [hi3d-game-demo](../upstream/1.2.11/prebuilt-skills/hi3d-game-demo/SKILL.md) | 面向游戏演示或实时接入。按实际加载器、设备、场景和交互验收。局部失败时复现并检查受影响范围。 [资产接入](../upstream/1.2.11/prebuilt-skills/hi3d-game-demo/references/assets.md) · [增量验收](../upstream/1.2.11/prebuilt-skills/hi3d-game-demo/references/validation.md) |

## LLM Tools

| 独立工具说明 | 调用时机与条件 | 注册与核查情况 |
| --- | --- | --- |
| [exec_command](../tools/exec-command.md) · [exec](../tools/exec.md) | 从实际 GLB 或工程提取几何、UV、材质数据，按需运行 Blender 检查、修订或渲染。使用 Code Mode 时由 `exec` 编排。 | 本地执行入口与 Code Mode。随包脚本已在本机隔离测试。 |
| [wait](../tools/wait.md) · [write_stdin](../tools/write-stdin.md) | 长时间本地检查尚在运行时，分别按原 `cell_id` 或原命令 `session_id` 续读。 | 两类句柄各由其执行入口管理。进程完成后仍须核对报告的文件及检查范围。 |
| [studio_load_revision](../tools/studio-load-revision.md) · [studio_get_state](../tools/studio-get-state.md) | 仅在需查看已登记候选时，使用确切 `fileName` 加载并核对实际工作区、版本及就绪状态。 | 桌面动态工具。未登记候选可在本地直接回读。 |
| [studio_capture_view](../tools/studio-capture-view.md) · [view_image](../tools/view-image.md) | 当前 Studio 镜头满足观察要求时取证。已有可信截图或同相机渲染的实际文件路径时按需读取像素。 | 调用方将截图与已确认的视窗身份绑定。指定尺度与观察方向的对比可由本地渲染完成。 |
| [mdf_api](../tools/mdf-api.md) | 发现缺档或下载异常并符合原作业恢复条件时，由前序节点使用 `download`。明确改变派生意图时先回规划。 | Runtime 动态工具。已保存的成功回执可恢复尚可下载的文件。 [档位恢复](derive-and-check-lod-files.md#完成与恢复) |
| [workspace_commit_model](../tools/workspace-commit-model.md) · [image_classification](../tools/image-classification.md) | 已定稿且需要工作区版本时，逐个登记选定导出。收到 `classificationRequired` 时补分类，再用原导出重试。 | Runtime 动态工具。留存样例有普通模型登记，暂无 LOD 组登记回放。 |
| [workflow_report](../tools/workflow-report.md) | 使用工作流图时，在实际完成约定检查后回填状态，按需关联确切登记版本或独立报告。 | Runtime 动态工具。图状态及产物归属由图单独记录。 |

`fresh_review.py`、`mesh_snapshot.py`、`service_rig inspect` 和 `validate_blend` 是包内脚本或子命令。`mesh-lod` 是 MDF 能力枚举，`quality_fail` 是通用 PCG 指导中的软门原因。 [工具注册](../tools/README.md#注册与可见性) · [宿主编排参考](../upstream/1.2.11/prebuilt-skills/.dependency-pcg-view/references/host-orchestration.md)

## Hi3D 实现

### 决策

1. **先确认档位身份。** 将上游必交目标和档位文件清单逐项对照，复核实际路径、摘要与源版本。指针重复、格式错误、缺文件或摘要不符先按档位文件核对处理。进入本节点的每份候选都要能追溯到确切文件。 [逐档文件身份](derive-and-check-lod-files.md#验收)
2. **按本轮用途取证。** 从同一源空间和尺度出发，先取得每档静态数据和必要画面，再按交付范围加入绑定准备、最终动作或设备检查。只交待绑定网格时，验收范围止于可交接的休止网格。已有证据可沿用，前提是候选摘要、验收范围以及所依赖的源与运行条件仍匹配。 [LOD 后续本地阶段](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/runtime-mesh-lod.md) · [资产替换与依赖](../upstream/1.2.11/prebuilt-skills/hi3d-game-demo/references/assets.md)
3. **以实际候选文件复验。** 未登记导出直接用 Blender 或使用场景的加载器打开。已有版本需要 Studio 取证时，按精确版本加载。对比源与各档时，沿用同一坐标、尺度和相机设置，避免各档自动取景掩盖比例变化。 [实际模型与相机](../infrastructure/workspace/acquire-model-visual-evidence.md#执行)

### 执行

#### 通用逐档回读

| 检查项 | 取证与判定 |
| --- | --- |
| 实际面数 | 分列请求目标、服务 `actualFaces`、GLB 声明三角数及实际导入的有效三角数。记录统计对象、是否按场景实例展开、原始或求值网格口径。多个图元、实例、退化面和加载器会改变计数。用计划中约定的实际口径检查硬预算。 |
| 保形 | 应用节点层级变换并核对单位，比较源与各档的世界包围盒、朝向和同视角轮廓，再观察主要结构及细薄部位。中性材质或线框可协助辨认几何细节。允许偏差及保护区域由本次任务确定。 |
| UV | 查看实际面角坐标和每个材质使用的 UV 层。按需检查非有限值、塌缩、拉伸、接缝、覆盖和非预期重叠。重烘后的网格使用其实际新 UV。先确认面角和贴图的对应，再判断既有贴图能否沿用。 |
| 材质与法线 | 确认每个需上图区域的材质绑定和实际可加载的纹理。按任务核对底色、法线和要求保留的 PBR 通道、像素尺寸及打包或外部资源。对比中性光下以及实际展示条件下的接缝、发黑、法线和细节。随包 MDF 契约将颜色和 PBR 列为源有 `baseColorTexture` 时可携带的产物。 |

随包 `fresh_review.py` 重新载入指定目录下的 GLB，用 `scene_measure.measure_objects` 记录摘要、世界包围盒、尺寸、逐对象三角面数和动作名称。这里的场景测量基于导入后的原始网格。需要查看可选的求值网格、面角 UV 或逐三角材质编号时，可使用 `mesh_snapshot.py`。这些脚本输出测量，不读取业务档位预算或自动给出整组结论。同拓扑的 `compare_geometry` 只适用于顶点和拓扑可对应的基线比较。 [文件回读](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/fresh_review.py:17>) · [场景测量](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/scene_measure.py:27>) · [网格快照](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/mesh_snapshot.py:23>) · [同拓扑比较契约](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/references/geometry-comparison.md:1>) · [LOD 服务契约](../upstream/1.2.11/prebuilt-skills/mdf-api/references/mesh-invoke-api.md#36-lod-减面烘焙mesh-lod)

#### 动画及游戏专项

- **交接绑定与换网格。** 单独记录休止姿态和坐标空间，保留实际新面角 UV、材质与法线。使用 `prepare_mesh` 时省略 `--faces`，跳过再次减面。脚本仍有归一化、焊接和三角化，`working_faces` 是准备后计数。替换已有蒙皮时另存候选，按同一休止空间和部件语义转移或重算权重，保护原骨架、休止变换、Action/NLA、帧范围及 fps。权重交接应核对归一化、未绑定点和接缝，避免跨肢体或衣物层匹配。 [准备与替换网格](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/mesh-lod.md#准备与替换网格) · [准备脚本](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/prepare_mesh.py:77>)
- **最终动画验收。** 重开实际保存的工程，在该档新拓扑上建立休止基线。随包 `service_rig inspect` 核对求值顶点及三角索引并报告逐帧变形，`validate_blend` 面向准备过的三角部件，另查变形权重和共享接缝。两者共用边长倍率 `>3` 且增量 `>H/120`，或双面积倍率 `>8` 且增量 `>H²/81000` 的严重变形筛查，`H` 与网格同单位。数值 `pass` 与 `motion_observed` 独立。非循环检查全整数帧，循环检查完整周期及接续姿态与速度。再结合视口核查深屈关节、脚底接触、穿插和材质，记录取样范围。 [专项验收](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/validation.md) · [单网格检查](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:288>) · [多部件检查](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/validate_blend.py:160>) · [阈值实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/skin_weights.py:93>)
- **游戏与实时接入。** 用实际加载器和解码器回读最终场景，核对变换、可加载资源、显示模型与交互代理。在目标设备测下载、解码、空间数据准备、首帧和帧时。交付游戏角色时，所有要求交付的档位回读静止和动作，检查骨架、蒙皮、材质、所需 clip 与挂点、米制身高、fps 和循环。测尺寸和导出时排除骨骼辅助显示网格。有切档要求时，按任务增加实际切换的外观连续性和运行效果检查。 [游戏验收层次](../upstream/1.2.11/prebuilt-skills/hi3d-game-demo/references/validation.md#验收层次) · [每档导出后回读](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/game-delivery.md#导出后回读)

### 验收

每档报告记录对应文件摘要、对照源、预算口径、测量结果、观察区域及适用专项的实测范围。档位齐全后仍需逐档完成这些检查。整组定稿时，根据已确认的必交档位集合核对所有通过项，复核任务约定的档间尺度、朝向、材质或切换要求，并固定交付清单。游戏 PCG 定义 LOD 产物槽及后续接入验收节点，Runtime 的 `reportNode` 写入节点状态。整组质量依据来自实际验收记录。 [游戏检查点与复用路线](../upstream/1.2.11/prebuilt-skills/hi3d-game-demo/pcg/routes.yaml) · [工作流完成状态](../infrastructure/workspace/workflow-graph-state.md#节点完成如何生效)

**根据随包验收指导重建的业务伪代码。** 下面表示调用方的判断顺序，具体测量、视觉对照、专项检查及允许的例外由本次计划提供。

```python
def review_lod_set(plan, artifacts, prior_reports):
    files = verify_expected_tier_files(plan, artifacts)
    if not files.complete:
        return hold_for_file_recovery(files.available, files.issues)

    reports = {}
    for tier in plan.delivery_tiers:
        file = files.by_tier.get(tier.id)
        if file is None:
            continue
        report = matching_report(prior_reports, file.sha256, plan, tier)
        if report is None:
            report = review_final_file(file, source=plan.source, checks=tier.checks)
        reports[tier.id] = report

    if any(not reports[tier.id].passed for tier in plan.required_tiers):
        return hold_for_revision(reports)
    accepted = select_accepted_tiers(plan, files, reports)
    cross_tier = review_required_group_checks(plan, accepted)
    if not cross_tier.passed:
        return hold_for_revision(reports, cross_tier)
    return finalize_delivery_manifest(plan, accepted, reports, cross_tier)
```

## 完成与恢复

| 情况 | 处理与交接 |
| --- | --- |
| 文件未齐、摘要缺失或失配 | 保留原作业和可用档位，回到派生文件核对。原成功回包可补下载时沿用原目录。提交或下载恢复仍使用原记录。 |
| 检查仍在运行 | 沿原 `cell_id` 或本地 `session_id` 续读。报告仅覆盖本次实际打开的文件、帧或观察范围。 |
| 仅部分档位通过 | 保留通过档及未过档证据，记录具体指标、位置、视角或帧。先复现问题，再另存失效档位的修订候选。若远档 UV 塌缩，可修订其布局并重烘受影响贴图，再核对新文件和所需档间一致性。 |
| 局部权重修订 | 先定位失败帧、异常三角面和实际权重。从检查报告取得网格摘要、骨架摘要和骨名顺序，连同明确的局部修订范围写入 `--rules`。随包 `service_rig repair` 核对这些身份后修订并另存工程，标记 `pose_qa_pending`。随后重开，沿同动作、帧范围和阈值复验，并检查接缝或接触。 |
| 源、预算、交付范围或运行条件变化 | 先确认受影响的要求。只重做失效证据所依赖的阶段，保留其余已核对的档位。必交档位仍未过时，整组保留待修状态。范围明确调整后按更新清单记录交付与缺项。 |
| 整组已定稿，准备登记 | 用实际通过的 `exports/hi3d-*.glb` 逐个登记。核对工具返回的确切版本路径与摘要。复用回执 `unchanged` 也要记录其对应档位。登记失败时先查原导出和已落盘版本，再按失败原因续调。 |

**根据已核实工具参数重建的单档登记请求。** 示例使用已通过验收的导出，并显式记录适用的空分类。档位、原文件、摘要和登记返回版本由交付清单关联。

```json
{
  "name": "example-near",
  "exportPath": "exports/hi3d-example-near.glb",
  "tag4": null
}
```

登记一次处理一份 GLB。已存在工作流图时可按工具契约提供 `workflowNodeId`，并用 `workflow_report` 单独记录完成与独立评审报告。已登记档位和仍待登记档位分别跟踪，整组交付清单保留每次返回的确切身份。若本轮只为绑定准备网格，清单按该范围交下游。 [局部修订与回归](../upstream/1.2.11/prebuilt-skills/hi3d-game-demo/references/validation.md#最小影响面) · [权重修复实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:423>) · [登记失败与重入](../tools/workspace-commit-model.md#失败与重入) · [工作流产物与状态](../tools/workflow-report.md#参数与结果)

## Vet3D 迁移与核查范围

### 供应商无关的交接契约

以业务档位 ID、源版本、候选摘要和验收配置标识一份结论。档位记录分别保存来源、请求预算、实测口径与结果、外观或专项证据、失败与修订历史。整组清单保留必交范围、最终文件、档间验收及登记回执。适配器可提供服务元数据，实际读回报告应能独立核对。

**Vet3D 设计示例。** 此例表示近档静态通过、远档待修时可持久化的状态。文件、摘要和报告引用为示例。

```json
{
  "scope": "static-display",
  "sourceVersion": "character/rest-v3",
  "requiredTiers": ["near", "far"],
  "filesComplete": true,
  "tierReviews": {
    "near": { "sha256": "<near-sha256>", "result": "passed", "evidence": "near-review.json" },
    "far": { "sha256": "<far-sha256>", "result": "needs-revision", "issue": "collapsed UV" }
  },
  "setStatus": "needs-revision"
}
```

### 下游接收检查

Vet3D 交付时分开记录各档质量结论、整组定稿和正式版本登记。某档需要换文件时重新验收该档，档间一致性只复核受变化影响的比较项。目标用途或必交集合变更时重新核对整组门槛。需要登记时，将每档最终摘要与返回的正式版本对应，保留可续办的未登记项。 [模型登记与恢复](../infrastructure/workspace/import-or-register-model-version.md) · [文件交付](../infrastructure/workspace/preview-and-deliver-files.md)

### 安装包证据、样例与缺口

- **静态证据。** `mdf_api.py` 的 `download` 和共享 `validate_glb` 提供下载与容器证据。随包动画、游戏参考规定实际质量检查。Runtime 的 `reportNode` 和 `commitExport` 分别位于 `runtime.mjs` 零基字节偏移 `3072320` 和 `2695691`，可复核图状态写入及单文件登记。 [MDF 下载](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:114>) · [容器检查](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/hi3d_artifacts.py:26>) · [Runtime 原件](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) · [Skill 哈希归档](../upstream/1.2.11/README.md#确定-lod-源网格与分档预算的随包证据)
- **隔离核查。** Blender 4.5.16 的三项随包场景测量测试通过。离线制作的两个合成 GLB 均通过容器校验，均声明一个三角形图元、两个实例，回读均为两个场景三角形，底色和法线图片均可加载。两个文件的世界宽度分别为 3000 和 2500 mm，UV 三角形面积分别为 `0.5` 和 `0`。随包五项权重测试与合成绑定、局部修复、回读也通过。修复后只查休止首帧可得到 `pass: true` 和 `motion_observed: false`。这些证据覆盖检查和修复逻辑。 [场景测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/tests/test_scene_measure.py>) · [权重测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_skin_weights.py>) · [合成动画测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_service_rig.py:116>)
- **样例范围。** 三份留存 GLB 只用于普通工作区版本、网格检查和登记样例，均无 `skins` 和 `animations`。两个留存会话的实际工具调用未见 `mesh-lod`。实际样例覆盖普通模型的部分检查和登记路径，未提供 LOD 整组验收记录。 [样例工作区](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40>) · [活跃会话](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl>) · [归档会话](<D:/download/.sparc3d-runtime/environments/prod/codex-home/archived_sessions/rollout-2026-11-11T11-24-05-01a1c8a2-5bab-7df0-8557-d36af12e8411.jsonl>)
- **待实测。** 生产 `mesh-lod` 每档实际面数与尺寸差、薄部位保形、材质与法线重烘质量，真实四足角色的每档权重、动作接触及档间外观，以及目标引擎、设备加载表现和实际整组登记回执。
