# 迁移已有贴图与烘焙细节

以 Hi3D Agent 1.2.11（Windows x64）为核查基准。目标是把可追溯的已有外观交给确切目标网格。逐角对应有效时保留原贴图，局部改面时修订受影响区域，目标图集或拓扑重建时可从已配准的高模烘焙。随包公共执行器是 Blender Python 函数，阶段决策、材质接线和验收由调用方负责。 [版本归档](../upstream/1.2.11/README.md)

## 业务定义

| 项目 | 契约 |
| --- | --- |
| 触发 | 用户要求保留原外观进行网格修订或重拓扑、修复局部贴图，或将可信高模的材质与细节迁到目标网格。已有映射与外观仍有效时复用已通过结果。 |
| 上游与输入 | 固定源模型、原始贴图和材质版本，以及目标网格、已验收 UV、单位和配准关系。记录需交付的通道、冻结区、改动区、过渡带和允许变化的部件。法线烘焙需要明确目标 UV 和切线约定。 [重拓扑交接](retopology-and-edge-flow-review.md) · [目标 UV 交接](establish-and-review-target-uv.md) |
| 图片角色 | 本地运行以源网格实际材质引用或已有贴图为信号，以目标网格的 UV 为接收坐标。原照片、补充图和方向可用于视觉对照。需要根据照片生成新的表面外观时交给独立贴纹理流程。 [生成新纹理](generate-texture-for-existing-mesh.md) |
| 输出与完成条件 | 输出绑定目标网格和 UV 的原图或新图、逐通道材质接线、选定工作工程及验收依据。分支完成时确认被保留区域、实际迁移区域及仍未覆盖的范围。工件落盘、材质引用和图像质量分别核对。 |
| 下游 | 将确切工程或带纹理 GLB、实际贴图与常量通道、UV 绑定和验收范围交给导出、版次登记、展示或后续动画验证。辅助覆盖图和报告作为独立文件随产物交接。 [登记与版本](../infrastructure/workspace/import-or-register-model-version.md) · [文件交付](../infrastructure/workspace/preview-and-deliver-files.md) |

## Skill 绑定

**通用入口。** 工作区 `AGENTS.md` 指导先固定编辑意图和应保留的特征，使用工作副本，通过绝对路径启动后台 Blender。源和目标具体怎么配准、采用哪个通道和是否融合，由任务与所选 Skill 决定。 [工作副本与导出](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:39>) · [本地 Blender](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:47>)

| 归档入口 | 选用条件与作用 |
| --- | --- |
| [`texture-bake` 依赖入口](../upstream/1.2.11/prebuilt-skills/.dependency-texture-bake/REFERENCE.md) | 需要把已存在的场景表面信号投到目标 UV 时，指导调用 Blender Python 函数。提供通道、设备、输出和恢复约定。 [函数契约](../upstream/1.2.11/prebuilt-skills/.dependency-texture-bake/references/contract.md) |
| [`quad-flow-plus`](../upstream/1.2.11/prebuilt-skills/quad-flow-plus/SKILL.md) | 四边通改布线后，复用未受影响且合格的贴图与接缝。旧烘焙失效时修订或重烘，并保存布局与接线检查点。 [预算重建与交付](../upstream/1.2.11/prebuilt-skills/quad-flow-plus/references/hi3d-budget-rebuild.md) |
| [`lowpoly-quad-face-neck`](../upstream/1.2.11/prebuilt-skills/lowpoly-quad-face-neck/SKILL.md) | 已选面颈专项且源与目标可可靠对齐时，定义局部接收片、冻结区和过渡带的融合方法。执行者在 Blender 落实。 [局部烘焙与融合](../upstream/1.2.11/prebuilt-skills/lowpoly-quad-face-neck/references/method.md#烘焙与旧贴图融合) |
| [`head-lowpoly`](../upstream/1.2.11/prebuilt-skills/head-lowpoly/SKILL.md) | 人头低模与绑定已准备时，按专项从原始高模迁移底色、相关 PBR 通道和切线法线。独立眼面与发片还可分别继承原属性，须按实际对象复验。 |
| [`metahuman-fit`](../upstream/1.2.11/prebuilt-skills/metahuman-fit/SKILL.md) | 使用已注册的模板 UV，从同一份 quality 高模烘焙。模板底色已配置时启用局部 Coverage 和融合分支。 |
| [`head-hair-split` 依赖入口](../upstream/1.2.11/prebuilt-skills/.dependency-head-hair-split/REFERENCE.md) | 条件 CLI 只在用户明确选择代分件且确认阈值时执行。用验证通过的逐面对应回写原纹理 GLB 的面归属。 |
| [`mdf-api`](../upstream/1.2.11/prebuilt-skills/mdf-api/SKILL.md) | 用户接受按档减面、展 UV 和烘法线的组合产物时，按公开 `mesh-lod` 契约处理。 |

## LLM Tools

| 独立工具说明 | 调用时机与条件 | 核查状态 |
| --- | --- | --- |
| [`exec`](../tools/exec.md) · [`exec_command`](../tools/exec-command.md) | 有实际对象或文件后，用本地命令检查来源、启动 Blender、执行投射、读回或渲染。Code Mode 下可经 `exec` 编排。 | 随包函数和专项脚本经合成夹具实跑。本地工具交付进程结果。 |
| [`wait`](../tools/wait.md) · [`write_stdin`](../tools/write-stdin.md) | `exec` 返回 `cell_id` 或命令返回可续接 `session_id` 时，分别续接原单元或进程。 | 两个 ID 分别属于 Code Mode 与命令进程。文件检查点由调用方自己保存。 |
| [`view_image`](../tools/view-image.md) | 本地已有实际烘焙图、覆盖图或同机位渲染，需要查看颜色、接缝、投射边缘时调用。 | 视觉样本和文件结构分别核对。 |
| [`workflow_report`](../tools/workflow-report.md) | 选定带 PCG 架构的 Skill 并实际执行时，按已初始化的图和节点回填真实阶段及产物归属。 | 工作流回填记录进度，不执行投射或验收。 |
| [`mdf_api`](../tools/mdf-api.md) | 仅在选择 LOD 组合处理时执行 `invoke` 的 `mesh-lod`，先预检再沿原计划正式调用。已有成功账本需要补取产物时用 `download`。 | Runtime 工具和客户端已核查，生产逐档产物的通道保留待实测。 |
| [`workspace_commit_model`](../tools/workspace-commit-model.md) | 确切 GLB 已通过验收且需要登记为模型版本时，在交付阶段调用。 | 登记交接按实际返回的版本身份核对。 |

`bake_image` 是本地函数，`DIFFUSE`、`EMIT`、`NORMAL` 是 Blender 烘焙类型。`mesh-lod` 是 MDF 能力枚举，`invoke`、`download` 是 Tool 动作。PCG 的 `blender.write` 是操作标签。安装包的 Runtime 与 Studio 工具目录未发现独立烘焙 Tool。 [工具注册索引](../tools/README.md#注册与可见性) · [本地烘焙架构](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-texture-bake/pcg/architecture.yaml>)

## Hi3D 实现

### 决策

1. **先确定可保留范围。** 回读原图、目标图元的逐角 UV 和面材质。对应成立且原外观仍适用时保留。只能追溯部分来源面时，单独处理新切面和失配区域。 [已有高模与新面规则](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/image-to-assembly/references/existing-sculpture.md:17>)
2. **再选局部迁移或重烘。** 已验收几何和 UV 可以复用。小范围变更时约定冻结区与过渡带。拓扑或图集大范围改变而原高模可信时，将对应通道重投到目标 UV。面颈 Skill 要求配准不可靠时暂停投射，保留已通过几何。 [冻结与配准](../upstream/1.2.11/prebuilt-skills/lowpoly-quad-face-neck/SKILL.md)
3. **按任务约定信号与出口。** 原高模实际拥有的颜色、标量与法线分别取证。需要从照片推定新外观时使用独立贴纹理流程。需要各档独立网格及图集时才选择 `mesh-lod`。 [MDF 服务范围](../upstream/1.2.11/prebuilt-skills/mdf-api/SKILL.md)

### 执行

#### 原贴图与映射复用

`source_normalize.py` 从活动 UV 读逐 loop 坐标，按三角角点存储，并记录面材质索引。`product_scene.loadmesh(original=True)` 恢复原材质槽、面材质和 `Source UV`。无活动层时中间数据可带全零占位，重建也可能生成同名层，因此需核对实际值。来源面部分改变时，随包 `solid_tools.Source.write` 依据 Manifold 来源及 `face_id` 在原三角上逐角重心插值，保留面材质。新切面用零 UV 和 `material_index=-1` 标记，由后续构建分配独立材质。需上图的新面另建或验证其映射。 [源数据](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-source-prepare/scripts/source_normalize.py:76>) · [属性恢复](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-model-preview/scripts/product_scene.py:25>) · [局部插值](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-solid-edit/scripts/solid_tools.py:19>)

头发分件专项的条件 CLI 从标签模型取得面分类，依次检查原顶点及索引、同序逐面和一对一面心匹配，并核对角点、法线与面积。发现面数变化或映射不唯一即停止。它追加分区索引，并回读核对原 BIN 字节前缀、材质、图像、纹理、采样器和节点变换。由此保留原贴图与面角数据。 [面对应验证](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-head-hair-split/scripts/apply_labels.py:38>) · [分区回读](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-head-hair-split/scripts/apply_labels.py:121>)

#### 局部迁移与融合

面颈 Skill 要求几何冻结后用可追溯的局部选区和目标 UV。将原认可贴图与新高模颜色投到同一目标图集，在冻结边界保留旧色，在局部内部采用新色，在过渡带按权重在线性色彩中融合，保留 alpha 和边缘扩展。局部 cage、选区、混合和接线由执行者处理。其规程本身没有通用可执行融合脚本。 [归档方法](../upstream/1.2.11/prebuilt-skills/lowpoly-quad-face-neck/references/method.md#烘焙与旧贴图融合)

`metahuman-fit` 有可执行的专项融合。`review.py` 在注册模板 UV 上建立临时接收片，只选择至少三个角点满足掩模的四边面，排除模板保护区等不可烘区域。先取 `DIFFUSE` Albedo 与 `NORMAL`，未投到的位置用预填色或平法线。配置 `template_albedo` 时另烘白色 EMIT Coverage。`skin_tone.py` 从 Coverage 取观察区域，排除保护区域，进行 Lab 色调匹配与颜色 Poisson 融合。切线法线单独与平法线过渡并重新归一化。工作流接入对应的 `_Fused` 图并 pack。Coverage 表示射线命中，边缘误差和外观由实际验收判断。 [局部烘焙](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/metahuman-fit/scripts/review.py:19>) · [颜色与法线融合](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/metahuman-fit/scripts/skin_tone.py:109>)

#### 高模向目标 UV 烘焙

随包 `bake_image` 在 Blender Object Mode 下接收同场景的源网格与目标网格，检查目标活动 UV、可用节点材质、数值参数及源目标材质分离。它设置 Cycles selected-to-active、单采样和无降噪，为目标每个材质建立临时 active Image Texture 节点。`DIFFUSE` 取纯颜色，`EMIT` 读取调用方接入源发光输出的信号，`NORMAL` 用 OpenGL `+Y` 切线空间。`cage`、`ray` 为场景单位下的数值，分别传给 `cage_extrusion`、`max_ray_distance`。调用方负责配准、自定义 cage 和目标通道的永久绑定。 [输入和投射](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-texture-bake/scripts/texture_bake.py:15>) · [单通道实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-texture-bake/scripts/texture_bake.py:75>)

**根据随包接口重建的本地调用。** `high` 是已配准的原高模，`low` 是活动 UV 已核实的目标对象。距离是当前场景单位下的示例值。

```python
from texture_bake import bake_image

image, report = bake_image(
    [high], low,
    path=output_dir / "normal.png",
    name="Target normal",
    size=128,
    kind="NORMAL",
    colorspace="Non-Color",
    cage=0.01,
    ray=0.05,
    margin=8,
    use_clear=True,
    normal_16=True,
    device="CPU",
)
```

函数输出 PNG、已 pack 的图像和投射参数报告。`normal_16` 保存 Raw RGB 16 位 PNG。默认禁止覆盖，CPU 回退需显式启用。临时节点、设备、渲染、可见性和选择状态在结束时恢复。核心图像 `alpha=False`，AO、透明和位移需要具体分支另行处理。已测 Blender 4.5.16 中，切换目标编辑活动 UV 会移动烘焙像素，单独切换渲染活动 UV 不会。函数报告没有层名，调用方须记录烘焙层，并核对材质采样与 GLB 引用。 [保存与清理](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-texture-bake/scripts/texture_bake.py:58>) · [设备选择](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-texture-bake/scripts/cycles_device.py:10>)

`head-lowpoly` 从 `Lowpoly_Rigged.blend` 第 1 帧取原完整 `Source_High` 和 `Lowpoly_Head`。默认 cage 为高模最长维度的 `.009`，ray 为 `.04`，margin 为 `max(8, size // 170)`，显式允许 Metal 回退 CPU。底色、粗糙度和金属度取自源 Principled 的已连接信号或常量，经暂时的 `EMIT` 烘焙。`auto` 将各源材质同值且未连接的粗糙度、金属度保留为标量，`all` 也为它们生成图。烘法线前恢复原 Surface，源着色法线可参与已测路径。最终底色与标量通道接到目标 Principled，法线经 `Normal Map` 接线，保存 `Lowpoly_Baked.blend` 和 `bake_report.json`。 [专项通道与绑定](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/bake.py:14>) · [阶段产物定义](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/run.py:123>)

**云端组合能力。** 公开 `mesh-lod` 接收单个 GLB 和严格降序的 `target_face_num_list`，组合减面、展 UV 与法线烘焙。随包契约称输入有 `baseColorTexture` 时可携颜色和 PBR。客户端以 `lods[].field` 查 `files`，档位不匹配可和 `SUCCEEDED` 同时出现在 `downloadIssues`。每档独立回读。内部 `texture-bake-v3-0` 的同序相机投射和 `compose` 有各自调用方契约，桌面公开 MDF 的旧纹理烘焙能力未开放。 [公开 LOD 契约](../upstream/1.2.11/prebuilt-skills/mdf-api/references/mesh-invoke-api.md#36-lod-减面烘焙mesh-lod) · [档位解析](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:97>) · [内部调用方契约](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-service-select/references/mdf/texture-bake-v3-0.md>)

### 验收

| 分支 | 通过条件与依据 |
| --- | --- |
| 原图与映射复用 | 回读确切网格的材质实际引用、逐角 UV 和区域。需要字节保留时对比内嵌或外部原图摘要。标明未覆盖的新面其材质归属。样例能核对保留区域，专项 GLB 分区还能核对原 BIN 与材质引用。 |
| 局部迁移与融合 | 核对原图与新图使用同一验收目标 UV，冻结区仅作允许的改动。回读覆盖、透明边缘、边界 padding、色差、黑边、错位及穿透。对照同机位、同光照渲染，记录投射缺口与补色来源。 [局部验收约定](../upstream/1.2.11/prebuilt-skills/lowpoly-quad-face-neck/references/method.md#烘焙与旧贴图融合) |
| 高模烘焙 | 检查确切源和目标，回读当前通道文件、分辨率、颜色空间、位深、法线方向、UV 层及实际材质引用。用同机位材质图和侧光对照检查接缝、重影及细薄部位串色。`head-lowpoly` 的 GLB 检查确认属性和材质引用，`metahuman-fit` 另外回导对比几何。视觉与投射覆盖分别验收。 [人头结构检查](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/deliver.py:8>) · [模板 GLB 回读](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/metahuman-fit/scripts/preview_export.py:46>) |

## 完成与恢复

| 分支或状态 | 恢复与交接 |
| --- | --- |
| 复用路径 | 保留原件和当前候选的对应关系。失配时保留可证明的原图与区域，重新建立对应或进入局部修订。通过后交接原图引用、面材质和确切目标 UV。 |
| 局部迁移路径 | 按源、目标 UV 和冻结区域恢复掩模、过渡、配准和产物。失败时保留已通过区域，回到局部选区、投射距离或融合参数修订。通过后交接本次图、覆盖范围、保留范围和实际接线。 |
| 本地进程仍在运行或已中断 | 按原 `cell_id` 或 `session_id` 续读已启动的执行。中断后检查已保存工程与报告。核心逐图落盘，后续通道失败时可能已有 PNG。人头与模板专项以阶段指纹、依赖和全部预期产物摘要复用。失效阶段重新执行。 [人头恢复](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/run.py:227>) · [模板恢复](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/metahuman-fit/scripts/content_journal.py:53>) |
| 本地返回候选但验收未过 | 回到同版源、目标和 UV，核对实际工作层、通道、投射命中与材质引用。保留报告和已验证通道。已有 PNG 但缺少对应 UV 检查点时，先恢复或验证原布局，再决定重烘。最终导出失败时保留验收工程，仅恢复导出。 [UV、贴图检查点](../upstream/1.2.11/prebuilt-skills/quad-flow-plus/references/hi3d-budget-rebuild.md#5-属性恢复与交付) |
| LOD 提交不明或下载中断 | MDF 正式请求同步，无远端任务查询。`UNKNOWN` 时保留原 `jobPath`、指纹和可用的 `requestId`。已保存成功响应时，同账号及环境使用原路径及输出目录做 `download`，同时核对 `downloadIssues` 和实际文件。按每档候选的验收范围交接。 [MDF 恢复](../tools/mdf-api.md#实现伪代码) |

**完成条件。** 工程、UV、通道文件和材质引用对应同一已验收版本时才回填。当前交付以烘焙报告、真实材质接线和实际文件为准。人头专项把 `all` 改为 `auto` 的离线夹具中，目录仍保留旧金属度 PNG，当前报告和 GLB 已采用标量。`delivery.json.files` 只列基础底色和法线 PNG，可选通道应从本次 `bake_report.json` 的 `textures`、`constant_channels` 及实际接线核对。已通过的目标及证据交给下游，登记和显示分别确认。 [人头缓存与产物摘要](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/run.py:227>) · [交付清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/deliver.py:56>)

## Vet3D 迁移与核查范围

### 供应商无关的交接契约

在业务层固定源版本、目标网格摘要、目标 UV 标识和作用区域。为每个通道记录来源、色彩空间、常量或图、目标材质绑定和验收范围。仅在需要时提供投射执行参数。局部复用、映射插值和烘焙可以组合，结果按区域及通道回填。后端适配器返回候选和执行依据，业务验收保存对应的实际文件摘要。模型与工具供应商可独立选型。

**Vet3D 设计示例。** 目标工程已验收 UV，工作请求只烘指定局部。示例中的名称属于业务语义。

```json
{
  "sourceRevision": "high-07",
  "targetMesh": {
    "revision": "low-03",
    "sha256": "6fe817dcf0d7d55a5e44777943a5d2464393ae39f07b32dcd500bdbc28e10b92"
  },
  "uvLayout": {"layer": "Surface UV"},
  "regions": {"reuse": ["body"], "rebake": ["face_patch"]},
  "channels": [
    {"semantic": "base_color", "colorSpace": "sRGB"},
    {"semantic": "tangent_normal", "convention": "OpenGL +Y"}
  ],
  "review": {"status": "pending", "evidenceFiles": []}
}
```

### 下游接收检查

Vet3D 交接给导出者时，逐项核对最终材质实际引用的图、常量和 UV 层，并把覆盖图与验收报告作为独立证据关联到对应通道。导出后若发现贴图引用缺失或色彩空间、切线约定不符，先定位接线与封装问题。只在对应的贴图像素或布局本身失效时重做迁移或烘焙。 [目标 UV 身份](establish-and-review-target-uv.md#供应商无关的交接契约) · [文件交付](../infrastructure/workspace/preview-and-deliver-files.md)

### 安装包证据、样例与缺口

- **安装包证据。** 以 `D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/` 的 1.2.11 Windows x64 快照核查。公共 `.dependency-texture-bake` 与分发到 `head-lowpoly`、`metahuman-fit` 的 `scripts/texture_bake.py` 原文件摘要一致，SHA-256 为 `af6018e9708b459448fd01485b3a5e88acc32d7b360803ba3a8798e7f94347d9`。 [版本清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) · [随包核心实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-texture-bake/scripts/texture_bake.py>) · [版本归档](../upstream/1.2.11/README.md)
- **本地执行已核查。** Blender 4.5.16 后台复跑本页示例，得到已 pack 的 `128×128` RGB 16 位法线图，目标 UV 前后一致。随包测试和其他合成夹具覆盖 Cycles 三类烘焙、目标编辑活动层选择、源 Normal Map 参与、通道失败清理、当前报告与旧 PNG 的区分。人头合成 GLB 的内嵌 Normal 与磁盘 PNG 均为 RGB 16 位，解码像素一致，内嵌图附加元数据后字节不同。模板夹具复核了 Coverage、保护区、融合、GLB 导出与回导。 [随包 Blender 测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-texture-bake/tests/test_device_context.py:19>) · [人头导出实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/deliver.py:34>)
- **留存样例。** 三个 GLB 的身体底色和 metallic-roughness 图分别字节一致。最终脚本从原版本重读带图身体，新增胡须封口用独立常量材质。另一个局部图集脚本记录了此前的试做。样例证据只覆盖该次复用、局部处理及实际操作。 [局部图集试做](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/scripts/hi3d-cat-face-repair-surface_8.py:100>) · [最终交付脚本](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/scripts/hi3d-cat-face-finish_12.py:6>)
- **待实测。** 真实四足模型的局部遮挡、薄片、毛发透明、接缝和动作下纹理表现，较复杂源材质的逐通道适配，生产 `mesh-lod` 的图集、PBR 保留和实际输出质量，以及内部服务与桌面部署的对应关系。
