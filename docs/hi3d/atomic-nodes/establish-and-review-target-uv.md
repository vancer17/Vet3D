# 建立与验收目标 UV

以 Hi3D Agent 1.2.11（Windows x64）为核查基准。目标网格上的 UV 可沿用现有逐角布局、调用 MDF 展开，或在 Blender 走专项展开。交给下游的是绑定到确切网格版本、已经按用途核验的 UV。 [版本归档](../upstream/1.2.11/README.md)

## 业务定义

| 项目 | 契约 |
| --- | --- |
| 触发 | 需要为选定网格确认可用 UV，或用户要求展开、改接缝、重新分配图集。已有 UV 缺失、失效或拓扑修订后需复核时也进入。已知布局及适用范围仍有效时可直接复用。 |
| 上游与输入 | 固定源版本和确切目标网格或可编辑工程。记录单位、对象及需上图的区域、既有 UV 与材质、可用的逐角对应、允许改变的几何与接缝、需要保留的属性及图集约定。拓扑或几何发生超出许可的变化时回到上游验收。 [候选适用性](check-model-candidate-suitability.md) · [重拓扑交接](retopology-and-edge-flow-review.md) |
| 图片角色 | MDF 展开上传一个目标 GLB。Blender 以实际目标网格及接缝或模板为输入。两条展开路径均无需主图、补充参考图或目标视角。已有贴图在复用路径用于核对 UV 对应，参考照片与方向在后续纹理生成或视觉复验时使用。 |
| 输出与完成条件 | 交付通过检查的目标网格或工程、选定 UV 层及对应范围、保留与改动记录，以及适用的质量证据。服务回包、进程退出和 UV 属性存在分别记录。需要上图的区域须通过实际布局检查才能完成。 |
| 下游 | 交贴图迁移、烘焙或参考图生成纹理时提供同一网格、UV 层及其验收范围。原来可复用的贴图也要匹配该布局。只要求展开时，可以交付已验收的网格或工程。模型版本登记和最终展示按交付需要另行执行。 [贴图迁移与烘焙](migrate-textures-and-bake-details.md) · [生成新纹理](generate-texture-for-existing-mesh.md) · [版本登记](../infrastructure/workspace/import-or-register-model-version.md) · [文件交付](../infrastructure/workspace/preview-and-deliver-files.md) |

## Skill 绑定

**通用入口。** 工作区 `AGENTS.md` 指导先确定用途和保留项，编辑使用工作副本。当前模板提供 Blender 绝对路径，通过后台 Python 启动。已核查的通用入口没有规定单一展 UV 算法或通用通过阈值。下表的接缝、模板与阈值随所选 Skill 生效。 [工作区任务路由](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:25>) · [工作副本](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:39>) · [Blender 执行入口](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:47>)

| 归档 Skill | 选用条件与作用 |
| --- | --- |
| [`mdf-api`](../upstream/1.2.11/prebuilt-skills/mdf-api/SKILL.md) | 选择桌面账号的公开展开服务时使用。按 `unwrap-uv` 的输入和参数预检，保留原作业并恢复已保存成功响应的下载。 [公开契约](../upstream/1.2.11/prebuilt-skills/mdf-api/references/mesh-invoke-api.md#32-展-uvunwrap-uv) |
| [`quad-flow-plus`](../upstream/1.2.11/prebuilt-skills/quad-flow-plus/SKILL.md) | 已选四边通路线时，保留未受影响且合格的原 UV、材质和接缝。重布线使旧布局失效后按实际范围重展，保存 UV 检查点。 [重建与恢复](../upstream/1.2.11/prebuilt-skills/quad-flow-plus/references/hi3d-budget-rebuild.md) |
| [`closed-quad-transition`](../upstream/1.2.11/prebuilt-skills/closed-quad-transition/SKILL.md) | 采用局部闭合四边过渡时保护 UV 接缝。跨接缝区域跳过此过渡。改动其余区域后，显式插值并检查，或在最终布局上展开。 |
| [`head-lowpoly`](../upstream/1.2.11/prebuilt-skills/head-lowpoly/SKILL.md) | 已选人头低模专项且眼口布局准备完成时，按人头坐标标后脑接缝，然后执行 Blender 展开。方法白名单、默认值和回看位置只适用于该脚本。 |
| [`lowpoly-quad-face-neck`](../upstream/1.2.11/prebuilt-skills/lowpoly-quad-face-neck/SKILL.md) | 面颈修订冻结几何后，按眼睑、唇线、下颌底及颈部形状布置接缝、岛与 texel 密度。执行者在 Blender 落实这部分规程。 [面颈操作指导](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/lowpoly-quad-face-neck/references/method.md:74>) |
| [`metahuman-fit`](../upstream/1.2.11/prebuilt-skills/metahuman-fit/SKILL.md) | 默认保留注册模板 UV。仅显式选择分体扩展时，桌面规划脚本可根据调用方的 `has_uv` 决定是否准备 MDF UV 请求。 [桌面分体交接](../upstream/1.2.11/prebuilt-skills/metahuman-fit/references/runtime-handoff.md) |

## LLM Tools

| 独立工具说明 | 调用时机与条件 | 核查状态 |
| --- | --- | --- |
| [`mdf_api`](../tools/mdf-api.md) | 确定采用公开服务展开后，用 `action: "invoke"` 和 `capability: "unwrap-uv"`，按 Skill 先做 `dryRun`，再沿原计划正式调用。原作业已保存成功结果且产物尚未下载时，用 `action: "download"`。 | Runtime 已注册。随包校验、组包和恢复经过离线复核，真实服务输出待实测。 |
| [`exec`](../tools/exec.md) · [`exec_command`](../tools/exec-command.md) | 需要读回局部 UV、运行 Blender、测量候选或导出测试图时执行。使用 `exec_command` 启动本地程序，Code Mode 可通过 `exec` 编排。 | 随包代码和合成夹具使用实际 Blender。执行工具交付进程输出，UV 判定来自实际检查。 |
| [`wait`](../tools/wait.md) · [`write_stdin`](../tools/write-stdin.md) | 仅在 `exec` 返回 `cell_id` 或 `exec_command` 返回可续接 `session_id` 时，分别等待原执行单元或进程。 | 这是执行层续接。MDF 正式调用为同步请求，服务没有作业查询。 |
| [`view_image`](../tools/view-image.md) | 已将 UV 棋盘格或前后对比渲染为本地图片，需要检查接缝和拉伸时调用。 | 图像观察可作视觉证据。逐角数值与几何仍从候选读取。 |
| [`workflow_report`](../tools/workflow-report.md) | 选定有 PCG 架构的 Skill 并实际执行时，按已有图和节点记录阶段与产物。 | 状态回填与几何验收各有证据。 |

`unwrap-uv` 是 MDF 能力枚举，`dryRun` 是 `invoke` 的参数，`waiting_choice` 是宿主状态。`retopology.py`、`texture_pipeline.py` 和 Blender 的 `bpy.ops.uv.unwrap` 属于脚本或程序接口。当前 Studio 工具可核对显示版本及快照，状态回包没有 UV 布局。 [工具注册索引](../tools/README.md#注册与可见性) · [Studio 状态](../tools/studio-get-state.md#参数与结果)

## Hi3D 实现

### 决策

1. **先验证能否复用。** 固定目标文件及需上图区域，回读实际 UV 与材质选用层。表面位置改过时还要确定逐角对应与变形后的布局是否可用。拓扑变化后，对没有可证实对应的区域走局部重展或新布局。
2. **再选展开入口。** 单个 GLB 可由服务决定布局时，使用公开 `unwrap-uv`。任务要求指定接缝、锁定模板或保留局部图集时，按所选 Blender 路线处理工作副本。涉及 `mesh-lod` 的逐档减面、展 UV 和法线烘焙时，按组合能力生成，每档独立回读。通用入口未实现自动选择展开后端和接缝的决策器。 [MDF 公开契约](../upstream/1.2.11/prebuilt-skills/mdf-api/references/mesh-invoke-api.md) · [局部 UV 决策](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/lowpoly-quad-face-neck/references/method.md:74>)

### 执行

#### 已有 UV 复用

随包 `source_normalize.py` 从活动层读取 loop UV，再用三角形角点索引把 UV 与面材质索引保存到 NPZ。`product_scene.loadmesh(original=True)` 用对应面恢复材质和 `Source UV`。输入没有活动 UV 时，NPZ 保留全零占位，而重建仍会生成同名 UV 层。必须读取数值，并核对各材质实际使用的布局。布尔派生有独立的来源面插值，保留面按原面逐角插值，新切面保持零 UV 与独立材质标记，需上图时单独处理这些新面。 [UV 提取](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-source-prepare/scripts/source_normalize.py:76>) · [重建](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-model-preview/scripts/product_scene.py:25>) · [面来源与插值](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-solid-edit/scripts/solid_tools.py:19>)

`metahuman-fit` 的默认注册复用模板 `quad_uvs`。输入校验要求每四边面四个二维角点且值有限。阶段检查逐项比较 `quads`、`quad_uvs` 与模板数据。分体扩展的 `texture_pipeline.py` 则使用调用方给出的 `has_uv` 生成计划。缺省或 false 时，它规划 `4096`、`need_repair: false`，并约定从 `uv.files.uv_mesh_glb` 取实际网格。true 时计划沿用原网格。这个辅助脚本返回 `plan_only`，并保留 `geometry_preservation_verified: false`，调用方负责读取和验收。 [模板输入校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/metahuman-fit/scripts/fit.py:64>) · [模板一致性](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/metahuman-fit/scripts/image_pipeline.py:221>) · [实际规划脚本](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/metahuman-fit/scripts/texture_pipeline.py:24>)

#### MDF 展开

**根据已核实 schema 重建的离线预检。** `file` 是当前工作区已选目标 GLB。本例显式关闭展开前的修复选项。这个选项只约束服务所请求的预修复，候选仍需检查有无 UV 缝拆点和索引重排。

```json
{
  "action": "invoke",
  "capability": "unwrap-uv",
  "file": "inputs/target.glb",
  "params": {
    "texture_size": 4096,
    "need_repair": false
  },
  "jobPath": ".hi3d/mdf/uv.json",
  "outputDir": "exports/uv",
  "dryRun": true
}
```

预检接受单个工作区 GLB v2，大小上限为 200 MiB。`texture_size` 为正整数，`need_repair` 为布尔值。整个 `params` 省略时客户端发送 `{}`，只传其中一项时保留该项。`8192` 与 `true` 是随包服务契约的默认值。预检读取输入并生成计划，正式调用才组 multipart。接缝、选区、展开方法、源贴图和参考方向均不在这项能力的公开参数中。 [参数与容器校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:21>) · [公开参数](../upstream/1.2.11/prebuilt-skills/mdf-api/references/mesh-invoke-api.md#32-展-uvunwrap-uv)

正式调用沿用同一文件、参数、`jobPath` 和 `outputDir`。脚本绑定账号和环境，按能力、参数、源摘要和输出目录计算指纹，先独占保存 `UNKNOWN`，再同步 `POST /v1/mesh/invoke`。该能力 Python POST 等待预算为 2100 秒。Skill 指导正式提交走宿主 `waiting_choice`，桌面 MDF 实机确认和扣费接线仍待验证。 [同步提交](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:180>) · [宿主确认与预算](../tools/mdf-api.md#宿主确认与执行预算)

HTTP 200、整数 `code: 0` 和业务 `SUCCEEDED` 同时成立后，脚本按 `data.files` 下载。服务契约中的 `data.uv_mesh_glb` 提供存储 key，文件 URL 取自 `data.files.uv_mesh_glb.url`。正常 GLB 落盘为 `hi3d-uv_mesh_glb.glb`，本地路径见 `files.uv_mesh_glb`。通用下载器按 URL 后缀检查相应容器，业务侧还需核对预期结果键、实际文件类型、所需 UV 及几何。服务可能附带面积比例和修复状态，作为辅助证据。 [下载实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:114>) · [UV 产物检查参考](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-service-select/references/mdf/texture-uv-unwrap-v3-0.md:15>)

#### Blender 专项展开

`head-lowpoly` 的 `facial_topology` 读取同源配置，在眼口布局完成后的 `Lowpoly_Head` 上标后脑接缝。横跨 X 中线且中点 Y 超出 `uv_back_depth` 的边作为 seam。默认 `CONFORMAL`，配置另允许 `ANGLE_BASED`、`MINIMUM_STRETCH`。这是人头坐标下的专项规则。 [阶段入口](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/retopology.py:318>) · [配置校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/run.py:73>)

**根据随包源码重建的核心代码。** 输入 `low` 是已构造的目标 Blender 对象。省略阶段计时和落盘步骤。

```python
for edge in low.data.edges:
    a, b = vertices[list(edge.vertices)]
    if a[0] * b[0] <= 0 and (a[1] + b[1]) * 0.5 > face["uv_back_depth"]:
        edge.use_seam = True

bpy.ops.object.select_all(action="DESELECT")
low.select_set(True)
bpy.context.view_layer.objects.active = low
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.unwrap(method=config.get("uv_method", "CONFORMAL"), margin=0.02)
bpy.ops.object.mode_set(mode="OBJECT")
```

实际 UV 随 `Lowpoly_Unbaked.blend` 保存。`lowpoly_patch_data.npz` 只存顶点和区域元数据，`lowpoly_report.json` 记录 `uv_method` 与 `uv_seconds`。阶段缓存包含 `uv_method` 和下游依赖。重要区域拉伸过大时，人头 Skill 指导试用 `ANGLE_BASED`，再核对眼睛、嘴、耳朵和接缝。已存在贴图的局部修订则按所选 Skill 保护冻结区域。 [源码与结果](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/retopology.py:403>) · [阶段缓存](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/run.py:123>) · [复验指导](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/references/implementation.md:30>)

### 验收

| 检查 | 证据与判据 |
| --- | --- |
| 文件、区域和几何 | 打开实际产物，核对工作区路径和文件摘要，确认对象、需上图的图元、目标 UV 层、材质选择及允许的几何变化。GLB 展开后可能因接缝拆点而改变顶点索引。需要继续使用逐顶点权重或形态键时，另核对映射。 [UV 结果参考](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-service-select/references/mdf/texture-uv-unwrap-v3-0.md:22>) |
| UV 布局 | 回读需上图区域的有限坐标、实际 UV 面积、覆盖、翻转、非预期重叠、接缝和密度。按任务决定镜像、重叠或图集复用是否允许。涉及已有外观时对照原材质和棋盘格或渲染，明确局部未通过项。 [面颈 UV 布局](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/lowpoly-quad-face-neck/references/method.md:74>) · [覆盖、重复和翻转检查](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/teapot-design/references/kettle-routes.md:69>) |
| 随包实测边界 | `head-lowpoly` 的最终导出函数检查头部图元的 `TEXCOORD_0` 和相关材质引用，未读取实际 UV 数组。四边通 Plus 的 `verdict` 检查调用方提供的 `max_uv_stretch`，默认 `1.25`，缺值报错，超限回退或保留旧片。该阈值属于四边通专项，测量由执行方完成。 [GLB 检查](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/deliver.py:8>) · [四边通判定](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/quad-flow-plus/scripts/hi3d-quad-judge.py:64>) |

## 完成与恢复

| 分支或状态 | 恢复与交接 |
| --- | --- |
| 复用已有 UV | 保留原件和已验收布局。逐角对应、材质引用和使用范围均通过后，交接实际网格和复用范围。部分区域失配时保留通过区域，在工作副本修订受影响区域并复验。 |
| MDF 调用仍在运行 | 仅用实际返回的 `cell_id` 等待原执行单元。正式请求同步返回，MDF `requestId` 用于核对记录。 |
| MDF 提交或结果不明 | 保留 `UNKNOWN` 账本、原 `jobPath`、输入指纹和已取得的 `requestId`。MDF 无服务端查询动作，同一作业不得换路径重复提交。 |
| MDF 已保存成功响应，需取回产物 | 同账号、同环境使用原 `jobPath` 与 `outputDir` 调用 `download`。没有下载记录的产物可由原成功响应补取。已记录文件后来缺失或被修改时，`files` 可能仍含原路径，同时有 `downloadIssues`，该字段不会自动重下。按实际文件与摘要判断恢复。 [MDF 恢复](../tools/mdf-api.md#实现伪代码) |
| Blender 仍在运行或已中断 | 有可续接 `session_id` 时读取原进程。退出后回读已保存工程与诊断。专项工作流恢复原配置和检查点，按配置、脚本、依赖和文件摘要复用。修改接缝或展开方法后复查对应阶段及其下游。 [阶段复用实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/run.py:149>) |
| 取得候选但布局未通过 | 保留源版本与失败证据，定位失效图元、接缝或 UV 岛。复用分支重新建立对应或重展受影响部分；MDF 分支保留原回包，按修订后的处理意图或本地受控路径得到新候选；Blender 分支回到合格几何，修订布局后再跑。已有 PNG 但缺少与之对应的 UV 检查点时，先恢复或验证该布局，再决定重烘范围。只有实际网格和 UV 通过后才回填完成或交给下游。 [检查点恢复](../upstream/1.2.11/prebuilt-skills/quad-flow-plus/references/hi3d-budget-rebuild.md) |

## Vet3D 迁移与核查范围

### 供应商无关的交接契约

把确切网格、作用区域、需保留的几何与接缝、允许的图集复用方式和检查证据放在业务层。对拆点或面序变化的结果，记录可验证的对应关系，再交给需要逐顶点属性的阶段。为每个已验收布局固定网格摘要及 UV 标识。后续贴图或烘焙只使用同一个验收版本。

**Vet3D 设计示例。** 示例设定目标是保留既有图集，只允许未通过的局部面片进入修订。字段由 Vet3D 自己维护。

```json
{
  "targetMesh": {
    "revision": "target-03",
    "file": "work/target.blend",
    "sha256": "6fe817dcf0d7d55a5e44777943a5d2464393ae39f07b32dcd500bdbc28e10b92"
  },
  "uvLayout": {"layer": "Surface UV", "strategy": "reuse"},
  "texturedRegions": ["body", "ears"],
  "preserve": ["part_boundaries", "material_assignments", "approved_seams"],
  "allowIntentionalOverlap": false,
  "review": {"status": "pending", "evidenceFiles": []}
}
```

执行适配层保存本地进程或服务作业的恢复依据，验收层根据候选摘要保存覆盖、布局及几何检查结果。申请新候选与重新验收分别记录。未来 LLM、网格处理和纹理服务仍可独立选型。

### 下游接收检查

Vet3D 交接时，以目标网格摘要、对象与 UV 层标识匹配验收记录。若后续导出只改容器或对象命名，先回读导出后的对象对应与 UV 层，确认逐角映射和材质绑定是否仍可复用。布局或对应关系变化时，重新验收受影响区域，再用同一新目标工件发起后续处理。 [贴图迁移与烘焙](migrate-textures-and-bake-details.md#供应商无关的交接契约) · [参考图纹理生成](generate-texture-for-existing-mesh.md#供应商无关的交接契约)

### 安装包证据、样例与缺口

- **静态核查。** 使用 `D:/install/Hi3DAgent.__hi3d-transaction/resources/` 的 1.2.11 Windows x64 快照。`runtime.mjs` 中 `Xj`、`Qj`、`runMdf` 的 UTF-8 零基字节分别为 `2512504`、`2513223`、`2538264`。`app.asar` 的 `out/main/index.js` 成员零基字节 `212966` 定位 MDF POST 白名单。已核查的 Runtime 与 Studio 注册表中无通用独立 UV 验收 Tool。 [版本清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) · [Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) · [桌面 ASAR](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>)
- **离线核查。** 随包 MDF 测试 7 项、四边通判定 39 项通过。本页 `dryRun` 示例由随包脚本复跑，返回 2100 秒等待预算，未创建账本或输出目录。模拟传输验证了同一作业下载恢复，以及服务成功但候选没有 UV、缺结果键或结果为 PNG 的情形。Blender 4.5.16 实跑人头展开块的三种方法，验证合成网格逐角 UV、几何保持和保存回读。无 UV 输入产生全零 `Source UV` 层与塌缩 UV 通过最终导出结构检查，均以单独夹具复现。 [MDF 随包测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/tests/runtime/test_mdf_api.py>) · [判定测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/quad-flow-plus/scripts/hi3d-test-quad-judge.py>)
- **留存样例。** 三个 GLB 内嵌的身体底色与 metallic-roughness 图片分别字节一致。最终脚本重新导入带纹理身体，并为新封口使用独立常量材质。封口图元的 UV 全部落在同一点。留存文件和会话只说明该次复用与局部处理。 [留存交付脚本](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/scripts/hi3d-cat-face-finish_12.py:6>)
- **待实测。** 生产 MDF 执行算法、支持的分辨率规格、宿主确认与扣费、原几何与属性保留，以及真实四足模型的接缝、覆盖、密度和动作下的纹理变形。内部 `texture-uv-unwrap-v3-0` 随包资料仅记录固定调用方契约，实际桌面部署对应关系待核。 [内部调用方参考](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-service-select/references/mdf/texture-uv-unwrap-v3-0.md>)
