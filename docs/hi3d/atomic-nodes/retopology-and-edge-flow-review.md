# 重拓扑与边流验收

以 Hi3D Agent 1.2.11（Windows x64）为核查基准。MDF 为已有 GLB 生成重拓扑候选，四边通 Plus 编排初始后端、保形减密和边链约束重建，`head-lowpoly` 将 MDF 原生四边面接入人头眼口重布线和本地烘焙。三份留存 GLB 与会话只用于核对实际观察，分支范围以安装包和随包代码为依据。 [版本归档](../upstream/1.2.11/README.md)

## 业务定义

| 项目 | 契约 |
| --- | --- |
| 触发 | 用户要求改面连接、控制面数、建立可编辑四边面或保护指定边流。上游诊断发现拓扑会妨碍当前交付时，也可进入本节点。仅修局部裂缝、水密化或逐档生成 LOD 时按实际目标选对应能力。 [候选适用性](check-model-candidate-suitability.md) · [网格缺陷与水密化](repair-mesh-and-make-watertight.md) |
| 上游与输入 | 固定源版本、实际文件和摘要。按任务补充可编辑四边面基线、同主体的高模及配准信息、各部件坐标与单位、目标面型和面数口径、误差预算、必保边链、接缝、UV、材质、蒙皮或形态键，以及允许改动的范围。用户已有合格的工作副本时可从该版本继续。 [查询模型版本](../infrastructure/workspace/query-assets-and-model-versions.md) |
| 图片角色 | 几何输入是实际网格或工程。主参考图锚定主体外观，补充图核对遮挡区域及各方向轮廓，复验时固定前后对照相机。MDF `retopology` 只上传一个 GLB，公开 schema 无主图、补充参考、目标方向、边线遮罩或保留项字段。Instant Meshes 2026 的引导是经确认的 Blender 曲线或标注。人头脚本使用与源绑定的眼口区域配置。 [模型视觉取证](../infrastructure/workspace/acquire-model-visual-evidence.md) · [初始后端输入](../upstream/1.2.11/prebuilt-skills/quad-flow-plus/references/hi3d-initial-remesh.md) |
| 输出与完成条件 | 服务侧阶段交付有来源记录的候选文件。正式完成按约定面型、面数、真实边链、保形和属性逐项验收，并绑定实际候选摘要。要求原生 quad 时交付可编辑 `.blend` 或保留原生面连接的 OBJ。供 Studio 预览或登记的 GLB 另列。动画或制造用途需要对应验收。 |
| 下游 | 向纹理转移、绑定、动画或制造流程提供确切候选和通过范围。登记交接模型家族 `name` 及选定 `exportPath`，下游展示以回包的确切版本为准。编辑工程、OBJ 和证据报告按工作区文件交付。 [版本登记](../infrastructure/workspace/import-or-register-model-version.md) · [Studio 加载](../infrastructure/workspace/load-studio-revision.md) · [文件交付](../infrastructure/workspace/preview-and-deliver-files.md) |

## Skill 绑定

**通用入口。** 宿主工作区 `AGENTS.md` 指导复用已有资产和合格上游，保留已确认特征、单位和稳定部件名。局部编辑可用 Blender 工作副本，导出选定 GLB 后显式登记。安装包的通用入口未规定按曲率、面数或局部失败次数自动切换重拓扑后端。 [工作区模板](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:25>)

| 归档 Skill | 选用条件与作用 |
| --- | --- |
| [MDF Skill](../upstream/1.2.11/prebuilt-skills/mdf-api/SKILL.md) | 已决定走公开网格处理服务时，按 `retopology` 契约提交和恢复。人头桌面专项也从此调用。 [公开能力契约](../upstream/1.2.11/prebuilt-skills/mdf-api/references/mesh-invoke-api.md#35-重拓扑retopology) |
| [四边通 Plus](../upstream/1.2.11/prebuilt-skills/quad-flow-plus/SKILL.md) | 选用该专项后，先复用合格基线，确需新基线时选后端，再按允许的范围做保形减密或边链约束重建。判定脚本、阶段回填和保形门槛属于这个入口的约定。 |
| [尺度感知四边环](../upstream/1.2.11/prebuilt-skills/scale-aware-quad-rings/SKILL.md) | 已有可编辑 quad 且要选择性粗化时，冻结尺度、识别保护区和规划粗细过渡。具体网格改动由执行者在 Blender 上落实。 |
| [闭合四边过渡](../upstream/1.2.11/prebuilt-skills/closed-quad-transition/SKILL.md) | 局部满足规则 4×4 结构且可守住外边链时，按 16→15 模板构造过渡。随包 NumPy 脚本生成和检查模板，实际回投、属性处理与替换另做。 |
| [低模四边面与面颈校准](../upstream/1.2.11/prebuilt-skills/lowpoly-quad-face-neck/SKILL.md) | 需要基础 quad 或人脸、拟人脸面颈语义校准，且有同主体、可对齐的约两百万三角面量级高模时使用。无脸资产按该 Skill 的基础路径处理。高模门槛仅限该能力。 |
| [人头低模 `head-lowpoly`](../upstream/1.2.11/prebuilt-skills/head-lowpoly/SKILL.md) | 已选人头专项且满足源、眼口区域及相关输入约定时使用。桌面 MDF 取得初始四边面，本地脚本负责眼口重排、绑定验证及从原高模烘焙。 [Runtime 交接](../upstream/1.2.11/prebuilt-skills/head-lowpoly/references/retopology-api.md) |

通用网格测量、Blender 环境及贴图烘焙分别可调用随包依赖。`mesh-audit` 测量边界、非流形、退化和连通等指标，语义边流另按任务验证。专项判定、边链预算、闭合模板和人头交接的命令与校验条件可独立复核。 [专项脚本说明](../resources/specialized-mesh-scripts.md) · [mesh-audit](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/REFERENCE.md>) · [纹理烘焙资源](../resources/p1/texture-bake.md)

## LLM Tools

| 独立工具说明 | 在本节点的调用时机 | 核查状态 |
| --- | --- | --- |
| [`mdf_api`](../tools/mdf-api.md) | 选择服务重拓扑后用 `invoke`，传 `capability: "retopology"`，按 Skill 要求先离线预检。成功回包已保存但产物尚未下载时，用 `download` 和原作业目录恢复。 | 已核查 Runtime 注册、随包脚本和离线传输。留存会话记录了工具可见性，生产重拓扑请求及返回仍需实测。 |
| [`exec`](../tools/exec.md) · [`exec_command`](../tools/exec-command.md) | 检查本地环境、用 Blender 或 CLI 处理工作副本、执行 JSON 判定和回读可编辑候选。 | QRemeshify、AutoRemesher、Instant Meshes 2026、判定脚本及 Blender 都是实际执行的程序。外部后端须检查当前安装。 |
| [`wait`](../tools/wait.md) · [`write_stdin`](../tools/write-stdin.md) | Code Mode 返回 `cell_id` 时等待原单元，命令返回 `session_id` 时续查原本地进程。 | 两类句柄各自续接。桌面 MDF 接口无远端查询动作。 |
| [`user_interaction`](../tools/user-interaction.md) | 四边通 Plus 缺少可复用的初始选择时，专项参考用 `kind: "preference"` 收集后端偏好。已选 Instant Meshes 2026 且缺少用户曲线或标注时用 `kind: "input"`。 | 已核查通用面板桥接和 Skill 的显式调用说明。根入口另描述宿主 `waiting_choice`，实际桌面选路和交互回包仍待实测。 |
| [`workflow_report`](../tools/workflow-report.md) | 选用有 PCG 架构的 Skill 并实际执行任务时，按原节点 ID 读取或恢复状态，回填进度和产物归属。 | Runtime 依据已安装架构生成图。节点完成回执只记录状态，几何验收由实际执行和测量给出。 |
| [`view_image`](../tools/view-image.md) · [`studio_load_revision`](../tools/studio-load-revision.md) · [`studio_get_state`](../tools/studio-get-state.md) · [`studio_capture_view`](../tools/studio-capture-view.md) | 用 `view_image` 查看候选本地渲染。需要在 Studio 展示时加载准确的登记版本，回执不明或需核对时读取状态，需要留存当前画面时再截图。 | 视窗就绪用于确认展示身份，截图回执提供产物 ID。原生面型与边流以实际工作副本为准。 |
| [`workspace_commit_model`](../tools/workspace-commit-model.md) · [`image_classification`](../tools/image-classification.md) | 交付 GLB 时登记已选定文件。同主体可继承分类，若回包为 `classificationRequired`，补分类后重用原导出。 | 登记验证版本、路径及容器，与编辑工程和质量报告的交付分别记录。 |

## Hi3D 实现

### 决策

1. **先确认交付标准。** 普通重拓扑可以交服务候选。要求保持指定位形、材质边界、骨骼或真实语义边流时，需按支持这些约束的路线处理。MDF 公开参数只表达面数、面型和方法，不接收保护链。用户指定工作流优先。普通入口缺少细化选路条件时，由调用方按资产和用途判断。 [公开参数](../upstream/1.2.11/prebuilt-skills/mdf-api/references/mesh-invoke-api.md#35-重拓扑retopology) · [通用路线](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:25>)
2. **选用四边通 Plus 后先复用基线。** 已有通过的 `.blend` 或原生 quad OBJ 时跳过初始重拓扑。需要新基线才进入四选一。硬表面推荐 QRemeshify，少干预的自动初版推荐 AutoRemesher，需要显式参考控制边流时优先考虑 Instant Meshes 2026，有条件时可走原四边通。后续默认 `preserve_topology`，用户允许重建且需要显著减面并有可靠边链时可进入 `chain_constrained_rebuild`。Skill 未设置固定减面百分比作为切换条件。 [初始方案](../upstream/1.2.11/prebuilt-skills/quad-flow-plus/references/hi3d-initial-remesh.md) · [预算重建条件](../upstream/1.2.11/prebuilt-skills/quad-flow-plus/references/hi3d-budget-rebuild.md)
3. **专项规则随对应 Skill 生效。** `head-lowpoly` 在桌面受管发行中默认 `retopology_backend=runtime`。独立包缺少 `.runtime-profile.json` 时，脚本默认 `instant_meshes` 并检查独立可执行文件。桌面的人头默认不能套到四边通 Plus 或动物模型。 [脚本预检](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/run.py:34>)

### 执行

#### MDF 通用重拓扑

**根据已核实 schema 重建的离线请求。** 源 GLB 位于当前工作区。示例显式要求原生四边面候选，目标面数为 `20000`。

```json
{
  "action": "invoke",
  "capability": "retopology",
  "file": "assets/source.glb",
  "params": {
    "face": 20000,
    "face_type": "quads",
    "topology_method": "standard"
  },
  "jobPath": ".hi3d/mdf/retopo.json",
  "outputDir": "exports/retopo",
  "dryRun": true
}
```

`dryRun` 只验证工作区文件、GLB v2 容器和参数，返回请求预览。桌面网格文件上限为 200 MiB，公开服务文档另列网格规模限制为 600 万。正式调用沿用参数和作业路径，去掉 `dryRun` 或传 `false`。客户端独占建立 `UNKNOWN` 账本后把参数和源 GLB 字节组为 multipart，经桌面账号代理同步 `POST /v1/mesh/invoke`。Python 等待预算为 2100 秒。`face` 是目标，服务不保证精确达到。默认值由服务契约声明，依次为 `50000`、`triangles`、`standard`。`feature` 按服务契约仅在 `triangles` 时生效，客户端会分别检查枚举，离线测试中也接受并组包 `quads + feature`。生产服务对该组合的行为仍待实测。 [客户端校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:27>) · [同步调用与作业](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:180>) · [宿主与预算](../tools/mdf-api.md#宿主确认与执行预算)

HTTP 200、整数 `code: 0` 与业务 `SUCCEEDED` 同时通过后进入下载。公开契约提供 `model_glb` 和 `model_obj`，其中原生面连接通过 `model_obj` 的 OBJ ZIP 交付。通用客户端下载到 `files` 中的对应路径，检查 GLB 容器或 ZIP 格式并记录摘要。它不解压 OBJ ZIP，也不检查里面是否确有四边面。`face_topology`、`vertices_topology` 表示结果统计，`num_faces`、`num_vertices` 表示输入统计。烘焙另行执行。邻接的 `mesh-lod` 能力才明确包含逐档减面、展 UV 和法线烘焙。 [重拓扑与 LOD 公开契约](../upstream/1.2.11/prebuilt-skills/mdf-api/references/mesh-invoke-api.md#35-重拓扑retopology) · [通用下载分支](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:114>)

#### 四边通 Plus 的本地执行

初始四选一顺序为 QRemeshify、AutoRemesher、Instant Meshes 2026、原四边通。已有用户选项或续接任务时复用。入口和 PCG 用 `waiting_choice` 与 `choices_example` 描述方案选择，初始方案参考另给出 `user_interaction(kind="preference")` 的 60 秒偏好示例。已核查的桌面 Runtime 读取 `pcg/architecture.yaml` 来构建工作流图，尚未定位到依据此 Skill 的 `routes.yaml` 自动弹窗或派发执行的接线。配置选项只确定后端，缺少后端时按安装参考核查具体来源、系统和版本。安装来源需另行确认。 [初始方案和面板契约](../upstream/1.2.11/prebuilt-skills/quad-flow-plus/references/hi3d-initial-remesh.md#面板契约) · [PCG 架构](../upstream/1.2.11/prebuilt-skills/quad-flow-plus/pcg/architecture.yaml) · [PCG 路线](../upstream/1.2.11/prebuilt-skills/quad-flow-plus/pcg/routes.yaml) · [安装参考](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/quad-flow-plus/references/hi3d-install.md:1>)

| 初始后端 | 执行和结果检查 |
| --- | --- |
| QRemeshify | Blender 对象模式启用指定扩展，以 `bpy.ops.qremeshify.remesh()` 处理工作副本。检查新的非空网格、真实面型、坐标、硬边和分件。 |
| AutoRemesher | 三角 OBJ 作为输入，独立 CLI 用 `--input`、`--output`、`--target-quads` 建初版。依实际 `--help` 使用选项，回读核对原坐标、尺度、部件和面数。 |
| Instant Meshes 2026 | 使用 `bpy.ops.mesh.instant_retopo_execute()` 及核实的用户曲线或视窗标注。按当前环境使用 `pyretopo` 或扩展支持的 CLI。参考注明 CLI 降级路径不传曲线的 `mirror_x` 标记，引导是否生效以实际边线复验。 |
| 原四边通 | `hi3d-quad-judge.py route` 读取执行者测量的候选标准体、至少三视角轮廓 IoU、内腔证据和分件需求。需要分件评估时先返回 `inspect_components`，否则内腔未知时返回 `inspect_geometry`。已验证无内腔、标准体受支持且最差视角达到默认 `0.95` 时选 `primitive_align`。存在内腔、标准体不受支持或轮廓不符时选 `v5_baseline`。实际对齐与重建由执行者完成。 |

[外部后端调用与验收](../upstream/1.2.11/prebuilt-skills/quad-flow-plus/references/hi3d-initial-remesh.md#三项插件的实际调用) · [标准体选路实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/quad-flow-plus/scripts/hi3d-quad-judge.py:145>)

**本地长任务。** 四边通 Plus 要求外部重拓扑、表面投射和离线烘焙等步骤先准备预算与心跳，再由本地脚本调用 `process_run.run_budgeted`。该 Skill 建议低、中、高档分别为 120、600、1800 秒。中高档和超时加时有各自的用户确认条件，超时记录为中断并保留日志。选择继续时按确认结果使用新输出目录和新预算。 [Skill 的预算约定](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/quad-flow-plus/SKILL.md:192>) · [P0 运行预算](../resources/process-run.md)

**保形减密。** 在不可变基线上冻结对象、尺度、误差预算和保护集合，按红、黄、灰区分配保护和减密。规则 4×4 局部可用 16→15 闭合模板。模板脚本处理面连接，执行者在 Blender 中回投、替换实际局部并复测。`hi3d-quad-judge.py predict` 估算减密下限，`verdict` 对实测指标统一判定。未覆盖门槛时，最小角、长宽比上限、法线角偏差上限和 UV 拉伸上限依次为 20°、8、20° 和 1.25。失败按粗化等级 `8→6→4→3→2→1` 回退细化，最细等级失败则保留原片。只有显式 `probe: true` 且验收通过的工作副本才回填实测面数为 `learned_floor`。 [尺度分区与回退](../upstream/1.2.11/prebuilt-skills/quad-flow-plus/SKILL.md) · [判定脚本](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/quad-flow-plus/scripts/hi3d-quad-judge.py:64>) · [闭合过渡脚本](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/closed-quad-transition/scripts/hi3d-quad-template.py:66>)

**边链约束预算重建。** 从认可的原生网格提取有序边链，确定允许变化的对象并记录必保链。随包参考记载的一种试做是限制受保护链处的 Decimate 边收缩，然后为三角基片的邻边共用中点，每片在其中心拆成三个 quad。原样保留 `K` 个 quad、重建 `T` 个三角基片时，`hi3d-chain-budget.py plan` 用 `K + 3T` 估算面数，并计算必要的拓扑下限。数量可行后仍须检查实测边链、保形和属性。预算重建不自动解除蒙皮、形态键或用户保护要求。 [预算重建路径](../upstream/1.2.11/prebuilt-skills/quad-flow-plus/references/hi3d-budget-rebuild.md) · [预算计算](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/quad-flow-plus/scripts/hi3d-chain-budget.py:24>)

#### 人头 `head-lowpoly` 的云端与本地交接

1. **准备和暂停。** `run.py` 先保留完整高模，再导出仅为请求准备的 `working_surface.glb`。缺少原作业或可用结果时，按对应分支保存 `retopology-request.json`，以退出码 `3` 返回 `waiting_retopology`。Agent 读其中的 `arguments`，走 MDF `quads + standard`，`face` 取配置的 `remesh_face_goal`。 [执行阶段](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/run.py:115>) · [专项交接规则](../upstream/1.2.11/prebuilt-skills/head-lowpoly/references/retopology-api.md)
2. **恢复、核对并导入。** 用同一配置恢复时读**实际作业账本**，比对输入摘要、参数、输出目录和指纹，复核 HTTP、业务状态与文件摘要。只读取 ZIP 内唯一、非空且不超过 512 MiB 的 OBJ 成员，只抽取几何相关行。导入按输入 GLB 的 Y-up 约定转换，保留在单个网格内。有限坐标、每面四角、非退化和包围盒均通过后才写出 `source_quads.obj`。任一轴的包围盒端点偏差超过源最长跨度的 10% 时停止检查，保留候选。 [账本与 ZIP 检查](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/mdf_handoff.py:30>) · [原生 quad 导入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/retopology.py:72>)
3. **语义重布线、验证和烘焙。** 本地脚本根据人头眼口配置选取连通面片，检查真实简单闭环，按边界弧长生成多圈并向原高模表面投射，再连成四边面。后续对绑定、表情及实际形变做专项检查，从完整原高模本地烘焙颜色、法线及需要的 PBR 通道。眼口配置与源摘要绑定，四足动物需要独立的语义区域和动作验收。 [局部重布线](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/retopology.py:122>) · [人头配置](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/references/inputs.md:46>) · [本地执行阶段](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/run.py:123>)

### 验收

回读资产时按需用 P1 场景载入和网格快照取证。使用快照记录三角片、面角 UV 和材质时，同时从可编辑工程或 OBJ 的原生面环提取面型与保护边链。需要视觉对比时，按实际尺度固定前后相机。需要绑定或动画交付时，在同一份最终候选上采集静止与动作帧，再做形变检查。 [场景载入](../resources/p1/asset-scene.md) · [网格快照](../resources/p1/mesh-snapshot.md) · [定向视图](../resources/p1/source-views.md) · [姿态取样](../resources/p1/scene-samples.md) · [权重及拉伸](../resources/p1/skin-weights.md)

**回读实际可编辑网格。** 分别统计原生 quad、tri、ngon 及 GLB 的三角数，统一比较面数口径。检查实际保护链、边界、非流形边与顶点、退化、绕向和极点。确认几何与外观时，使用冻结基线和源高模的双向抽样、同相机轮廓，以及具体 UV、材质和接缝对照。P95 描述误差分布，最大采样误差独立判断。动画需求另验语义环线、蒙皮权重和目标动作。 [共同验收与交付](../upstream/1.2.11/prebuilt-skills/quad-flow-plus/SKILL.md) · [边流、保形与属性检查](../upstream/1.2.11/prebuilt-skills/quad-flow-plus/references/hi3d-budget-rebuild.md)

**根据随包 `verify_chains` 重建的实现伪代码。** 实现先校验面索引、链 ID、`closed`、`required` 和坐标，再从真实多边形周边提取无向边。这里省略输入异常和报告格式，展示通过条件。

```python
edges = build_undirected_perimeter_edges(faces)

for chain in chains:
    ids = chain.vertices
    pairs = list(zip(ids, ids[1:]))
    if chain.closed and ids:
        pairs.append((ids[-1], ids[0]))
    missing = [pair for pair in pairs if undirected(pair) not in edges]
    displacement = max_marker_displacement(chain, vertices)  # 无标记时为 None
    chain.valid = (
        len(ids) >= (3 if chain.closed else 2)
        and len(ids) == len(set(ids))
        and not missing
        and (displacement is None or displacement <= tolerance)
    )

required = [chain for chain in chains if chain.required]
all_required_chains_valid = bool(required) and all(c.valid for c in required)
```

真实脚本验证的是已给出的链及标记点偏差。离线复现中，一个开放四边面的外环可以通过，链经过不存在的对角线就失败。`closed: false` 只省略末首相连的要求，零参考标记时偏差为未知。`required` 默认为 `true`，全部设为可选时聚合检查不会通过。实际模型仍要分别检查水密、语义归属和形变。随包另记一个角色实例，由 401,336 降到 40,117 个原生四边面，四条闭链通过，最大采样偏差约 9.367 mm，未过原保形门槛。 [边链实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/quad-flow-plus/scripts/hi3d-chain-budget.py:77>) · [随包角色实例](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/quad-flow-plus/references/hi3d-scope.md:37>)

读取脚本报告后再回填验收。离线复现中，`hi3d-quad-judge.py verdict` 给出 `rollback_refine` 时仍退出 `0`。`hi3d-chain-budget.py plan` 也可以在报告 `count_bounds_feasible: false` 时正常退出。`verify-chains` 的必保链聚合失败则保留报告并退出 `1`。 [判定 CLI](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/quad-flow-plus/scripts/hi3d-quad-judge.py:228>) · [边链 CLI](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/quad-flow-plus/scripts/hi3d-chain-budget.py:140>)

Skill 通过 `workflow_report` 回填阶段与产物。候选通过后按任务交付原生工程、报告和预览。GLB 模型登记使用确切已选定导出，Studio 加载状态仍单独确认。 [阶段回填](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/quad-flow-plus/references/hi3d-workflow.md:3>) · [登记 Tool](../tools/workspace-commit-model.md)

## 完成与恢复

| 情况 | 续接与交付条件 |
| --- | --- |
| 等待用户选后端、提供引导或确认必要取舍 | 保留当前选项、源文件和已经认可的基线。同任务恢复时沿用有效选择。缺少用户曲线或当前系统后端时，停在对应分支，失败候选仍可作为诊断资料。 |
| 本地执行或同一 MDF 调用仍在运行 | 用实际返回的 `session_id` 或 `cell_id` 续接原执行。处理器以终态、实际输出文件和摘要判定可读候选。`head-lowpoly` 的 `waiting_retopology` 是本地交接状态，桌面 MDF 服务没有远端查询动作。 |
| MDF 提交或结果不明 | 保留同一 `jobPath`、源摘要、参数指纹和已取得的 `requestId`。`UNKNOWN` 可能发生在 POST 前或后，按现有证据核对原请求。换新路径提交会失去该作业的防重关联。 [MDF 恢复](../tools/mdf-api.md#实现伪代码) |
| MDF 已成功，OBJ ZIP 尚未下载 | 保留成功账本，用同账号、环境、原 `jobPath` 及 `outputDir` 补取。若已记录文件缺失或改动，响应可仍带旧路径和 `downloadIssues`，原下载分支不会重新拉取该键。人头交接也会拒绝该摘要异常。仅有 GLB 的旧响应保留原记录，原生四边面交付仍需可验证的 OBJ。 [下载与记录检查](../tools/mdf-api.md#实现伪代码) · [专项恢复](../upstream/1.2.11/prebuilt-skills/head-lowpoly/references/retopology-api.md) |
| 返回候选但拓扑或边流验收未过 | 保存候选、未通过指标和原基线。按失败区域修订选区或引导，按对应 Skill 回退细化或重新确认后端，复验所有受影响条件。数量达标但保形失败的版本只有按约定作为试做候选交付，状态保留未通过项。 |
| 候选通过，登记或展示回执不明 | 先核对实际导出、当前登记版本与摘要。登记返回 `unchanged: true` 时复核回包路径和文件匹配。通过验收的编辑工程及证据一同交接，Studio 需要时加载同一正式版本。 [登记恢复](../tools/workspace-commit-model.md#失败与重入) · [Studio 状态](../infrastructure/workspace/read-studio-state.md) |

## Vet3D 迁移与核查范围

### 供应商无关的实现契约

宿主固定源版本、摘要与参考坐标。LLM 把目标面型、计数口径、尺寸和误差预算、允许重建范围及必须保留的边链和属性整理为可复核意图。适配层按能力受理该意图并保存执行回执。验收层对精确候选单独保存原生面型数量、边链与对应、保形误差、保留项和形变证据。区域链使用稳定 ID 和空间对应，换网格或参考后重新绑定索引。根据实际动作定义四足口鼻、肩胯、肘膝等部位的环线和变形条件。

**Vet3D 设计示例。** 以下是业务字段，面数与容差是示例值。

```json
{
  "sourceVersionId": "version-23",
  "scope": ["body"],
  "targetTopology": {"faceType": "quad", "faceCountGoal": 12000},
  "allowTopologyRebuild": true,
  "requiredChains": ["mouth-rim", "left-shoulder-loop", "right-shoulder-loop"],
  "surfaceTolerance": {"value": 1.0, "unit": "mm"},
  "preserve": ["ear-silhouette", "separate-whiskers", "material-assignments"],
  "delivery": ["editable-mesh", "preview-glb", "review-report"]
}
```

作业受理、候选落盘和质量通过分别记录。最终验收绑定可编辑文件与展示 GLB 的实际摘要。需要动画时独立检查关节、权重及目标动作的变形，按证据区分已经通过、需要重做和未测。LLM、生成模型与重拓扑后端仍可独立选型。

### 安装包、运行记录与缺口

- **安装身份。** 使用事务目录的 Windows x64 1.2.11 资源。`app.asar` SHA-256 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`，`runtime.mjs` 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`。已核对四边通 Plus、人头和三个本地专项的本机受管 Skill 与预置副本一致，归档摘要见版本快照。 [桌面 ASAR](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) · [Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) · [版本归档](../upstream/1.2.11/README.md)
- **Studio 实现。** ASAR renderer 成员 `out/renderer/assets/index-CDPCug_K.js` 的零基字节 `1090971` 是五项 Studio Tool 定义，`3534907` 是通用编辑器 Smart Decimate 的请求，`4725587` 是实际宿主挂载的编辑标签配置。该挂载未开放 Smart Decimate 的工具页及所需配置。摆盘的临时三角抽样用于姿态估算，离线复测源索引保持原状。 [Studio 工具目录](../tools/README.md#注册与可见性) · [摆盘证据](../tools/studio-arrange.md#核查依据)
- **已离线复核。** 随包四边通判定 39 项、边链与预算 13 项、闭合模板 8 项、人头 MDF 交接 10 项及 MDF 通用 7 项测试通过。本页请求用临时 GLB 在已安装脚本中通过预检，返回 2100 秒等待预算，未创建账本或输出目录。此前模拟确认有效 ZIP 即使只含文本也能通过通用下载器，人头专项对 OBJ 和原生四边面另设实际检查。上述验证覆盖判定、请求和恢复代码。 [四边通测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/quad-flow-plus/scripts/hi3d-test-quad-judge.py>) · [人头交接测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/test_mdf_handoff.py>) · [MDF 测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/tests/runtime/test_mdf_api.py>)
- **样本与待实测。** 三份样例 GLB 都声明三角面图元，留存会话有 `mdf_api` 和四边通 Plus 可见声明，所查执行记录未见此节点专项调用。Windows 上外部重拓扑后端、实际面板接线、生产 MDF 返回、UV/蒙皮保留和四足动作形变仍需实测。随包内部 `retopology-V2-0` 资料固定的是 Geo 调用方，使用 `pamo`。桌面公开枚举拒绝该值，线上 worker 与内部资料的对应关系尚未核实。 [样例工具声明](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:1>) · [外部后端已测范围](../upstream/1.2.11/prebuilt-skills/quad-flow-plus/references/hi3d-initial-remesh.md#本次已实测范围) · [内部调用方证据](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-service-select/references/mdf/retopology-V2-0.md:17>)
