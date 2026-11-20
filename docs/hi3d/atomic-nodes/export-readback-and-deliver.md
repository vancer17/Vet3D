# 导出、回读与交付

以 Hi3D Agent 1.2.11（Windows x64）为核查基准。本节点接收已验收候选，按用途生成最终文件、回读实际内容，按需登记版本或展示，再通过工作区文件引用交付。文件生成、回读通过、登记、Studio 就绪、链接可用和用户实际另存分别确认；安装包没有统一完成这些步骤的最终角色导出 CLI。 [归档绑定 Skill](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) · [交付约定](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/game-delivery.md#导出后回读) · [宿主文件交付](../infrastructure/workspace/preview-and-deliver-files.md)

工作区已有文件另存复制原文件；Studio 导出重新组包当前编辑器对象。二者不能视作同一实现。特别是当前 Studio GLB 导出未提供动画列表、多部件路径重建普通 Mesh，不能据此推定已验收的骨架与动画等价保留。此差异的静态证据和待实测范围见下文。

## 业务定义

| 项目 | 契约 |
| --- | --- |
| 触发 | 上游工程或已有交付候选已通过当前用途所需检查，需要交付原生工程、GLB、各 LOD、独立道具或配套文件。已有合格交付文件可按身份及要求复用，不强制再次导出。 |
| 上游与输入 | 确切 `.blend` 或既有交付文件、字节摘要、目标部件及骨架、保留项、单位和朝向；有动作时附实际 Action／slot／NLA、fps／帧段／循环与 clip 要求。各 LOD、挂点、独立道具和依赖分别列清。 [工程验收](reopen-and-review-rig-and-motion.md#验收) · [LOD 整组](review-and-finalize-lod-set.md#验收) |
| 图片角色 | 主图和补充方向图用于核对认可外观，导出后对照图来自确切输出，关联文件摘要、方向、机位及时间。本地导出接收工程、对象、路径及格式选项；登记与另存接收文件引用，没有主图／参考图 URL 槽位。图片及保留项随检查记录交接。 [视觉证据](../infrastructure/workspace/acquire-model-visual-evidence.md) |
| 输出 | 实际可交付工程／模型／ZIP及配套报告、输入和输出身份、导出对象与选项、回读覆盖；条件性的登记回执、版本摘要、Studio 身份和另存结果。安装包没有统一交付 manifest schema，清单由执行者维护。 |
| 完成条件 | 当前用途所需文件已生成或可证明复用，实际回读通过且证据匹配。需要版本时返回文件与已验文件完成摘要对账。以“备妥并提供链接”为目标时可完成 Agent 交接；要求证明用户已保存时还需实际另存／下载终态。 |
| 下游 | 交付使用者、目标加载器或后续项目。引擎、布料、打印与物理设备按实际需求另验。未通过则保留候选及诊断，退导出配置、资产修订或上游验收；新输出重新回读，不覆盖认可原件。 |

## Skill 绑定

通用工作区入口负责实际文件、`hi3d-` 命名、导出单位元数据、原件保护和工作区链接。领域规则决定交付哪些骨架、动作、LOD和挂点，以及如何验收；普通文件另存本身不要求调用建模 Skill。 [归档工作区模板](../upstream/1.2.11/archived-p0/resources/runtime/templates/AGENTS.md#操作规则)

| 归档入口或安装包参考 | 作用与选用条件 |
| --- | --- |
| [rig-retarget / SKILL.md](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) | 绑定／动作交付的主 Skill，保留原生工程、映射、来源、规则和检查范围，最终重开。主要面向人形，四足仍需另验。 |
| [绑定与动作验收](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/validation.md) · [游戏角色交付](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/game-delivery.md) | 主 Skill 的参考文件，规定各交付件回读、真实蒙皮尺寸、辅助对象排除、影响数及目标加载器检查。仅 Blender 交付不自动增加引擎或 LOD。 |
| [hi3d / SKILL.md](../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md) | 已实际选择通用生成／修订路线时，沿用其当前任务与产物交接要求；本节点不因此重提生成。 |
| [hi3d-game-demo / SKILL.md](../upstream/1.2.11/prebuilt-skills/hi3d-game-demo/SKILL.md) | 实际任务涉及游戏接入或 demo 时另选。普通 GLB 导出不自动触发完整游戏制作。 |
| [hi3d-model-gpt-animation / SKILL.md（安装包）](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d-model-gpt-animation/SKILL.md>) | 实际采用舞台、动作裁剪、布料／次级运动编排时补其最终工程及依赖要求；未纳入当前仓库原文快照，按安装副本核查。[专项验收参考](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d-model-gpt-animation/references/validation-and-runtime.md>) |

P0／P1 资源是执行依赖或可选接口，不是另外注册的 Skill 或 LLM Tool。P1 `glb_export`、`glb_clips`、`glb_bounds` 和 `asset_scene` 可由调用方选用；最终导出和完整回读没有一个强制统一入口。 [P0 包装](../resources/README.md#专项-blender-命令的执行包装) · [P1 资源](../resources/p1/README.md)

## LLM Tools

| 独立工具说明 | 本节点调用时机与条件 | 注册及结果边界 |
| --- | --- | --- |
| [exec](../tools/exec.md) · [exec_command](../tools/exec-command.md) | 读取摘要、启动 Blender 导出／回读、打包实际文件或生成检查报告。 | 随包 Codex 宿主工具。执行退出和文件内容验收分开；前序隔离探针调用了本地脚本。 |
| [wait](../tools/wait.md) · [write_stdin](../tools/write-stdin.md) | 本地任务未结束时依原 `cell_id` 或 `session_id` 续取。 | 不是登记版本或下载任务身份，句柄失效后按实际文件恢复。 |
| [view_image](../tools/view-image.md) | 有来自确切导出或回读候选的图像时按需读取。 | 不解析模型 skin／clip，摘要、帧号、方向和机位由取证记录关联。 |
| [workspace_commit_model](../tools/workspace-commit-model.md) | 需要把 `exports/` 内已验 GLB登记为模型版本时调用。 | Runtime 动态工具。回执确认版本，容器及复用不证明骨架／动画质量；返回路径必须与已验文件摘要对账。 |
| [image_classification](../tools/image-classification.md) | 缺少适用分类且需要保存本轮通用分类时使用。也可在登记时直接给有效 `tag4`。 | Runtime 动态工具。分类更新有既定范围，不能为补录一个版本而盲目更新整轮。 |
| [studio_load_revision](../tools/studio-load-revision.md) · [studio_get_state](../tools/studio-get-state.md) · [studio_capture_view](../tools/studio-capture-view.md) | 已登记版本需视窗展示或取证时使用。 | 桌面动态工具。加载、快照和截图不是最终文件复制；状态不包含完整权重／动作验收。 |
| [workflow_report](../tools/workflow-report.md) | 已实际选用 Skill 并维护工作流图时，按规范图既有节点记录文件、版本和检查结果。 | Runtime 动态工具。`artifact` 不完成节点，`completed` 不验收质量；本页名称不是自动存在的 `nodeId`。 |
| [user_interaction](../tools/user-interaction.md) | 交付范围、目标格式或允许改变内容仍有现有任务无法确定的关键歧义时使用。 | Runtime 动态工具，已有明确要求直接采用；取消或拒绝也可能有外层成功回包。 |
| [studio_export_3mf](../tools/studio-export-3mf.md) | 仅任务实际涉及打印计划时使用。 | 桌面动态工具，只打开计划入口；下载、第三方读取与打印不由 `opened:true` 证明。 |

`export_glb` 是 Python 函数，`bpy.ops.export_scene.gltf` 是 Blender 算子，`audit_models.py` 是本地脚本，`file:saveAs` 是 Electron IPC，`will-download` 是 Electron 事件；均不是同名 LLM Tool。没有已核实的 `studio_export_glb` LLM Tool。模型可见 description、通用 schema 和权限由独立工具页维护；本页仅说明调用条件。

## Hi3D 实现

### 决策

| 交付路线 | 采用条件与边界 |
| --- | --- |
| 仅原生工程／报告 | 使用已通过相应验收的文件，核打包依赖及最终重开，提供工作区链接。无需强制导 GLB或登记模型。 |
| Blender 生成最终 GLB | 从认可工程显式选择身体、骨架、软部件、挂点及需要的独立对象，按实际 exporter 选项导出并回读。 |
| 复用已有最终文件 | 文件身份、要求、回读覆盖和环境仍匹配时可以复用；不只按文件名、旧 `pass` 或旧版本号判断。 |
| Studio 重新导出 | 用户实际从编辑器请求时走其重组包链。它不是原文件复制；动画／skin 不具等价保留保证，输出视作新候选。 |
| LOD／独立道具／整组 ZIP | 列明必交文件，逐件回读及核摘要后打包。ZIP 提供文件集合，不替代逐件内容验收。 |
| 打印／外部应用 | 仅本次用途需要时走对应格式和宿主交接。不能从动画交付推断打印或设备接收已完成。 |

需要保留绑定／动作／形态键的最终角色 GLB不能使用 `service_rig export` 代替：该操作复制基础静止身体、清形态键，明确传 `export_animations=False`、`export_skins=False`、`export_morph=False`，服务提交件与最终绑定产物用途不同。仅静态单身体是否可复用该入口，仍按实际输出和本次要求验收。 [静止提交件源码](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:127>)

### 执行

#### 1. 固定交付清单和原生工程

对账上游工程和验收记录的摘要，固定对象、动作、时间、单位及保留项。排除隐藏服务参考体、无关舞台和骨骼显示对象；通过 `pose_bone.custom_shape` 引用识别辅助体，不靠固定名称。独立道具和挂点按实际握点、父骨及局部变换交接。原工程和来源保留，修改为新候选。 [交付参考](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/game-delivery.md#挂点和独立道具)

BLEND按用途打包贴图，重开最终交付文件核对实际绑定、Action/NLA、时间及依赖。旧 builder 可在 `START_HERE` 写入动作范围和 provenance，但该文本不是所有路径的通用交付清单，也不代替回读。 [工程验收](reopen-and-review-rig-and-motion.md#验收) · [旧构建说明](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py:115>)

本步放行：输入与输出身份和范围清楚，所需依赖可取得；缺件或要求变化回上游核对，不直接发布文件。

#### 2. 显式导出最终文件

P1 `export_glb(path, objects, *, convert_curves=False, unhide=False, exporter=None, **options)` 要求对象非空、唯一、属于当前活动视图层，并处于 Object mode。它固定 `filepath`、`export_format="GLB"`、`use_selection=True`，其余选项透传实际导出器。`convert_curves` 生成临时静态网格；`unhide` 只处理对象的 `hide_set`，集合和视图层由调用方准备。 [P1 导出契约](../resources/p1/glb-export.md)

封装在 `finally` 清理临时对象／网格并恢复选择、活动对象、隐藏、frame/subframe；只检查导出器是否返回 `FINISHED`，不检查文件存在、字节、skin或质量。输出父目录、新文件及覆盖策略由调用方负责，失败可能留下部分输出。 [实际封装](../upstream/1.2.11/archived-p1/resources/runtime/prebuilt-skills/.dependency-model-preview/scripts/glb_export.py)

**根据前序实测重建的 Blender Python 请求。** 在包外运行，示例只选择当前活动动作模式；不是随包统一导出命令。对象、帧段、单位和保留项已在上游准备，输出须是新路径。参数已在本机 Blender 4.5.16 验证，多 clip／NLA 和其他版本需另选及回读。

```python
from pathlib import Path
import sys
import bpy

sys.dont_write_bytecode = True
sys.path.insert(
    0, "D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/"
       "prebuilt-skills/.dependency-model-preview/scripts"
)
from glb_export import export_glb

source = Path("exports/hi3d-approved.blend").resolve()
output = Path("exports/hi3d-bound-motion.glb").resolve()
if output.exists():
    raise ValueError("Use a new export path")
output.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(source), use_scripts=False)
if bpy.context.object and bpy.context.object.mode != "OBJECT":
    bpy.ops.object.mode_set(mode="OBJECT")

body = bpy.data.objects["Body"]
rig = bpy.data.objects["Target"]
export_glb(
    output, [body, rig], unhide=True,
    export_skins=True, export_animations=True, export_morph=True,
    export_extras=True, export_animation_mode="ACTIVE_ACTIONS",
    export_frame_range=True, export_force_sampling=True,
)
```

新路径检查和父目录创建是示例调用方补充，不是封装的内置事务。示例也不自动准备物理单位。工作区模板要求节点 `extras.sparc3dPhysicalUnits` 为 `{version:1,unit:"meter"}`，并使用 `export_extras=True`。后者只导出已有属性，不会生成标记或修正尺度，必须回读实际节点与尺寸。部件名保持稳定，影响数按目标要求确定；本机 exporter 默认四影响不是所有引擎的固有要求。 [通用模板](../upstream/1.2.11/archived-p0/resources/runtime/templates/AGENTS.md#操作规则) · [影响数交接](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/game-delivery.md#lod-与绑定交接)

#### 3. 分层回读实际输出

| 回读层次 | 本步通过条件与工具范围 | 未通过时 |
| --- | --- | --- |
| 文件／容器 | 确认实际路径、字节数、SHA-256及容器。P1 `read_glb` 可读首部、对齐、chunk及JSON。 | 保留失败输出，修正导出条件并新建路径；容器通过不放行内容。 |
| 内容结构 | 按用途核网格、skin、关节、绑定矩阵、权重属性、形态键、材质／贴图、clip及独立依赖。 | 缺项回导出范围／选项或资产准备，不能因存在 GLB或容器合法而登记为合格。 |
| 实际载入 | 用新进程／实际加载器导入，核身体与骨架真实关联、米制尺寸和静止／指定时间求值，排除骨骼显示辅助网格。 | 原工程通过不代替输出通过。报告需附实际输出摘要、对象和时间覆盖。 |
| 时间与动作 | 按实际 clip映射、秒采样、目标 fps、播放范围和循环对账；逐交付LOD／clip检查要求范围。 | 名称、帧号和键数不要求机械原样一致，但业务动作与时间必须符合约定。 |
| 目标环境 | 明确需要引擎时检查实际蒙皮方式、影响数、材质、挂点及动作。 | Blender 保体积结果不代替目标线性蒙皮或导入器通过，未经测试明确待验。 |

[P1 容器接口](../resources/p1/glb-clips.md) · [资产重新载入](../resources/p1/asset-scene.md) · [导出后要求](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/game-delivery.md#导出后回读)

P1 `glb_bounds` 读取基础 POSITION和静态节点变换，不计算 skin或动画形变。随包 `audit_models.py --input <GLB或目录> --output <JSON>` 会重置场景并导入，报告摘要、网格、三角计数、尺寸与动画数量；但它收集全部导入Mesh，动画范围使用整数帧的对象包围盒，没有统一排除骨骼显示体，也没有完整蒙皮质量门槛。报告可覆盖既有文件，应在单独进程用新路径执行。 [静态尺寸边界](../resources/p1/glb-bounds.md) · [回读脚本契约](../resources/specialized-mesh-scripts.md#audit_modelspy-独立-glb-回读) · [实际回读实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/audit_models.py:14>)

#### 4. 按需登记并核对返回文件

**根据已核实 Tool schema 重建的登记请求。** 假定该工作区的导出文件已通过本次内容验收；`null` 表示已确认不适用命名类别，不是省略字段。已有规范工作流且需归属时，另提供实际存在的 `workflowNodeId`，不能直接用本页业务名称。

```json
{
  "name": "example",
  "exportPath": "exports/hi3d-example.glb",
  "tag4": null
}
```

Runtime要求真实文件在工作区 `exports/` 中、文件名以 `hi3d-` 开头，拒绝越界、符号链接和非普通文件，新导入要求 `.glb`。分类依显式值、本线程／轮次、同名家族回退；显式 `null` 有效且结束回退，枚举没有 `animal`。缺分类返回 `classificationRequired:true`，发生在导出文件检查之前，不能从该回包推定文件已合法；补录后沿原导出再登记，无需生成新模型。 [参数与分类](../tools/workspace-commit-model.md#参数与结果)

登记先确定可信下载来源，再尝试复用或创建版本。新建结果以 `hi3d-<家族>_<序号>.glb` 发布，源导出保留。成功负载为 `{file}` 或 `{file,unchanged:true}`；校验主要覆盖 GLB容器与版本身份，不覆盖 skin、clip或材质质量。可信同任务／账号／环境复用优先，可能返回同任务下另一份字节不同的文件；其他路径再比较最新版本大小与SHA。必须从返回 `file.path` 读取实际版本并与已验导出SHA对账，未匹配时暂停交付并核对返回内容。 [身份和复用](../tools/workspace-commit-model.md#文件身份与复用)

#### 5. 条件展示和产物归属

需要Studio时以确切 `fileName` 加载，核顶层 `loaded/assetId/fileName` 和随后 `state.ready/assetId/fileName` 均匹配。同工作区切换可使两处身份不同；`physicalSize.source:"default-longest"` 来自最长边75mm默认比例，不能替代真实单位验收。视窗状态和截图也不提供完整绑定／动作证明。 [加载验收](../tools/studio-load-revision.md#版本身份与就绪确认) · [状态边界](../tools/studio-get-state.md#使用视窗快照)

工作流 `kind:"model"` 使用登记版本的准确 `fileName`；工程、JSON、ZIP等用 `kind:"file"` 和工作区路径。图保存引用，不冻结字节、不配对报告或验收内容。登记及产物上报不完成节点，执行者在本轮工作结束后按现有规范图报告完成。 [图引用与状态](../tools/workflow-report.md#参数与结果)

#### 6. 交付已有文件并记录实际完成层级

通用模板要求先确认文件已生成，再交付工作区相对路径链接。普通文件无需额外模型登记，目录先打包，空格／括号等使用百分号编码。模型版本还可以输出 `产物：<实际 GLB 文件名>`，文件名以真实回执为准。 [归档模板](../upstream/1.2.11/archived-p0/resources/runtime/templates/AGENTS.md#操作规则)

**根据已核实客户端约定重建的 Markdown 示例。**

```markdown
[hi3d-project.zip](exports/hi3d-project.zip)
```

聊天链接进入 `file:saveAs`：主进程复核工作区内真实普通文件，打开源句柄后检查身份，展示保存对话框。取消返回 `{canceled:true}`；接受后检查目标，源／目标同文件身份直接成功，其他目标截断后流式复制，完成返回 `{canceled:false,path}`。没有内容SHA前后比较或持久复制任务，失败可能留下空／部分目标文件。 [宿主实现与协议](../infrastructure/workspace/preview-and-deliver-files.md#普通保存与-studio-下载)

Agent提供链接表示文件已备妥。用户已保存要以复制回执及实际路径确认；需严格内容对账时再比较实际目标字节，这是额外验收而非IPC自动保证。仅交链接的任务不为等待用户点击而虚构 pending作业，也不把链接输出描述成已另存到外部目录。

#### Studio 重新导出的独立条件分支

Studio从当前编辑器对象重组包，不读取原文件后直接复制。固定renderer的 `createExportObject` 多网格分支逐部件复制几何／材质，再构造普通Mesh，未重建Skeleton；单网格 `createExportMesh` 有条件返回当前对象，其他路径也构造普通Mesh。物理GLB再按 `mmPerUnit/1000` 根缩放并加入单位元数据。 [固定原包](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>)

**根据已核实源码重建的 GLTFExporter 选项示例。** 这是renderer内部调用的参数，不是LLM Tool请求。

```json
{
  "binary": true,
  "maxTextureSize": 8192,
  "includeCustomExtensions": false
}
```

此调用没有提供 `animations`；随包GLTFExporter默认空列表，并只遍历该选项写clips。因此不能依这条重新导出链宣告保留原动画，也不能把多网格输出当作一般的skin保留保证。输出在单位、几何组织、材质／颜色及纹理上限等方面也可能改变，应视作新候选回读。本节点的绑定／动画交付采用已验输出的普通文件复制，不能以Studio重新导出替代后跳过验收。

Studio底栏可输出GLB、STL、OBJ、3MF、USDZ、FBX及条件ZIP；格式选项存在不证明各项能保留相同资产语义。Blob URL和 `<a download>` 触发后，Electron `will-download` 设置保存对话框并发布 `selecting/completed/cancelled/failed`，完成时带实际路径。UI导出提示和下载触发早于磁盘完成；`completed` 才可记录下载完成。本轮没有运行真实Studio重导出或系统保存对话框，以上是静态链结论。 [下载完成层级](../infrastructure/workspace/preview-and-deliver-files.md#验收)

#### 核心分支控制流

**实现伪代码。** 归纳Skill指导、已核实局部实现和执行者的验收职责；不是Hi3D已有的单一函数或自动状态机。Studio导出下载由用户动作触发，不虚构可直接调用的 `studio_export_glb` Tool。`receipt` 表示调用方归一化的结果，不是原始Tool schema。

```python
def export_and_deliver(approved, requirements):
    source = verify_approved_identity_and_scope(approved, requirements)
    files = reuse_or_export_required_files(source, requirements)
    evidence = read_actual_outputs_in_requested_environment(files, requirements)
    if evidence.failed:
        return retain_outputs_and_handoff_revision(evidence)
    if evidence.required_items_missing:
        return retain_outputs_pending_evidence(evidence)

    versions = []
    for file in files_requiring_model_versions(files, requirements):
        receipt = commit_export(file)
        if receipt.classification_required:
            return retain_same_export_for_classification()
        if not receipt.succeeded:
            return reconcile_existing_version_and_metadata(file, receipt)
        if digest(receipt.file_path) != digest(file.path):
            return suspend_delivery_and_review_returned_version(receipt)
        versions.append(receipt)

    if requirements.needs_studio:
        verify_exact_version_loaded_and_ready(versions)
    record_actual_files_versions_and_scoped_evidence(files, versions, evidence)
    links = provide_existing_workspace_file_links(files, versions)
    # 提供链接是Agent交接；外部保存状态只读取真实宿主回执。
    return record_ready_links_and_any_observed_save_results(links)
```

### 验收

| 步骤 | 当前放行条件 | 后续交接 |
| --- | --- | --- |
| 原生工程及清单 | 文件身份、对象、动作、单位和必交依赖明确，所需工程可重开。 | 交最终导出或直接工程交付。 |
| 文件生成 | 实际新文件可读、摘要及对象范围有记录；封装或进程成功不能单独放行。 | 交容器、内容和加载器回读。 |
| 回读与实际表现 | 当前用途所需结构、尺度、时间、材质／依赖和实际动作覆盖通过；逐LOD／clip对应。 | 交登记或可交付文件，未测引擎留待验。 |
| 条件版本登记 | 新建／复用回执有效，返回文件可读且SHA与已验输出一致。 | 交确切版本名及摘要，按需展示。 |
| 条件展示 | 顶层和state身份匹配目标，`ready:true`；截图另绑定方向及文件身份。 | 交展示证据，不扩大为skin或clip质量通过。 |
| Agent交接 | 实际文件、清单和链接可用，必要检查齐备，范围及残留明确。 | 可记录“文件备妥／链接已提供”。 |
| 用户实际保存 | 普通另存复制完成，或Blob下载 `completed`，有实际目标路径。 | 才可记录“用户已另存”；外部应用读取和引擎使用另验。 |

## 完成与恢复

| 状态 | 恢复和继续条件 |
| --- | --- |
| 本地导出／回读 pending | 按原 `cell_id/session_id` 续取，句柄失效后核对进程、日志及实际输出。没有统一的持久导出任务账本；重启脚本是新尝试。 |
| 来源云任务受理不明或缺件 | 保留原任务、路径和诊断，回[原作业恢复](submit-and-recover-auto-rig.md#完成与恢复)按原身份处理。正常导出和另存不需要重新生成／绑定，不把本地故障变成新云提交。 |
| 导出失败、超时或回执不明 | 封装会恢复规定的内存状态，但不回滚输出文件。核对是否已有完整／部分输出；保留原工程，以新路径重做所需导出并重新回读。 |
| 有文件但回读未通过 | 缺skin、clip、材质、单位或时间错误时，退对象清单、参数、兼容性或资产准备。修订后固定新摘要，不复用旧文件验收。 |
| 登记缺分类 | 保存原导出，按既定分类范围补录并重试同一 `name/exportPath`。不生成新文件；显式 `tag4:null` 需符合本次实际分类意图。 |
| 登记flush失败或回执丢失 | 版本文件及图挂接可能已发生。核编号文件、元数据和摘要，保留原参数再决定重调。复用可直接返回 `unchanged`，不是强制重刷上次失败状态。 |
| 登记返回另一份字节／不可读 | 暂停交付，保留已验导出和回执；按实际返回内容核验，不能用同任务或 `unchanged` 代替摘要一致。 |
| Studio超时／切换／下载不明 | 加载可能晚到，先取当前状态对确切版本；Blob下载沿原宿主事件等待终态，不能用另一文件的就绪代替。无公开的通用LLM下载查询Tool。 |
| 另存取消／复制失败 | 取消独立记录，可重用同一可信源；失败先查实际目标部分文件。无持久复制ID和回滚，后续另存为新操作，不能称恢复原复制进度。 |
| ZIP／依赖缺失或外部应用失败 | 核逐项文件和相对依赖。普通文件链接不需要专门ZIP登记。第三方没有读回证据时只报告文件已备妥或已交接，不声称实际解析／执行通过。 |
| 条件打印／切片器 | `studio_export_3mf` 只打开入口；实际下载等终态，发送按既有3MF登记引用交宿主。`handed-to-slicer` 不证明切片器已读取，`device/direct` 的 `file-ready` 不证明设备上传或打印。此路线不是动画交付默认步骤。 |

[登记失败与重入](../tools/workspace-commit-model.md#失败与重入) · [文件交付恢复](../infrastructure/workspace/preview-and-deliver-files.md#完成与恢复) · [打印入口边界](../tools/studio-export-3mf.md)

## Vet3D 迁移与核查范围

### 供应商无关的交接契约

| 记录 | 业务语义 |
| --- | --- |
| 输入及用途 | 确切认可资产和摘要、保留项、目标格式／加载器、部件、骨架、动作、时间、单位及逐档要求。 |
| 导出计划和结果 | 实际对象白名单、必要依赖、导出器及选项版本、输出文件和摘要；区分字节复制与重新编码／组包。 |
| 回读证据 | 容器、结构、实际载入、时间、目标表现各自的对象、范围、结论和缺口；不能只存单一success。 |
| 登记对账 | 候选身份、返回版本身份、新建／复用及实际SHA关系。登记来源和内容一致性分别表达。 |
| 交付状态 | 工作区文件存在、链接已提供、版本已登记、视窗就绪、用户另存、第三方读取分别记录。 |
| 恢复 | 原尝试、输入输出及诊断保留；新导出新身份，部分写盘、回执不明和后续重试分别对账。 |

Vet3D 的LLM、生图、3D、绑定和动作模型及API仍待选型，先定义上述语义，导出／存储／登记／宿主适配器分别实现。可设计独占产物目录、逐文件摘要清单、源／目标复制后对账及独立回读任务；这些是迁移建议，不能写成Hi3D已有的事务或自动质量保证。

### 安装包证据、样例与缺口

核查日2026-11-20，版本固定在 `D:/install/Hi3DAgent.__hi3d-transaction/resources`，manifest为Runtime `1.2.11 win32/x64`。主安装目录当前缺完整资源，引用真实事务副本及仓库归档。 [manifest](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) · [归档说明](../upstream/1.2.11/README.md)

| 固定来源 | SHA-256／可复核位置 |
| --- | --- |
| [rig-retarget / SKILL.md](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) | `8237ec25a4cf0b06a49723f21c168eee36f5848f64256fd357993d0a2b04f17d`；工程交付、保护及真实回读要求。 |
| [P1 glb_export.py](../upstream/1.2.11/archived-p1/resources/runtime/prebuilt-skills/.dependency-model-preview/scripts/glb_export.py) | `8f92bd1c2c0664febbd8f7c841531c546c4feb34e52e088b39ca40a9529069a4`；选择导出封装，原件与安装副本一致。 |
| [P1 glb_clips.py](../upstream/1.2.11/archived-p1/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/glb_clips.py) | `9a6be55268d9156efcccbd9572206cbbc4ffef4a462d1615e89e1560ecd89412`；容器读取，不是完整skin／动画验证器。 |
| [P1 glb_bounds.py](../upstream/1.2.11/archived-p1/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/glb_bounds.py) | `3431b26d8238ba6448b7efc28099f911b3f98e1fc7e6bb94fbb9b416a0b8a6b4`；静态节点／位置尺寸。 |
| [runtime.mjs](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) | `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`；登记注册与复用。零基UTF-8字节 `2151223` 注册，`2695691` 登记，`3197710` 分派／图归属／flush。 |
| [app.asar](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) | `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`；宿主与renderer实现，成员内偏移见下表。 |

| ASAR成员内零基UTF-8字节 | 结论及证据性质 |
| --- | --- |
| `out/main/index.js:100599/101148/180430` | 文件解析、句柄复验、保存对话框与复制。 |
| `out/main/index.js:264515` | `will-download` 及实际磁盘完成事件。 |
| `out/renderer/assets/index-CDPCug_K.js:2865989/2866809` | 单网格条件分支和多网格普通Mesh重建。 |
| 同renderer `3206150/3207127/3209396` | 物理单位缩放、GLB链及无animations的导出选项。 |
| 同renderer `2942503/2961380/3284197` | GLTFExporter默认空动画、按列表写clip及Blob触发下载。 |

renderer单成员已只读抽取，SHA为 `4ca3ecffe377be3014e38f807ed9f788fd9bb64ce86529687d896870757d6abc`。前序REA 6.8.0静态分析主Evidence为 `ev_dd1b2ba5bddc15ba312afd6da31f0a0a768e6e9004c6310013689915e0b4989a`；[提取成员](<C:/Users/11408/AppData/Local/Temp/hi3d-studio-export-0yi501pk/index-CDPCug_K.js>)及[证据包](<C:/Users/11408/AppData/Local/Temp/hi3d-studio-export-0yi501pk/rea-evidence.json>)为临时辅助证据。它只分析一个成员、未执行bootstrap，语义节点／unknown与字符串预算命中，图为partial；上文链路由固定原文逐段复核，不用缺边证明能力不存在，也没有声称已运行Studio重导出。

**前序隔离导出与回读实测。** 使用未改写P1封装、本机Blender 4.5.16 LTS／glTF I/O 4.5.51，在包外合成工程导出并新进程导入；未调用生产云端、未登记真实工作区、未操作真实保存对话框。

| 观察 | 覆盖与限制 |
| --- | --- |
| 七骨三帧输出 | 仅选 `Body/Target`，输出1个skin、7个joints与绑定矩阵，包含 `JOINTS_0/WEIGHTS_0`；未选 `HeldProp` 未导出，封装恢复临时状态。源工程SHA `759a870845d88cba755bbd381285cf4a2b7a2434596882a77d6b69186a00e1dd` 未变，GLB SHA `c31796d06e9e81a4f53f7f2e9c3a99012ee9d61b2b77d46a69c54337f4926a5f`。 |
| 实际新进程导入 | 通过 `custom_shape` 引用排除辅助显示Mesh后，实际身体与骨架关联有效；30fps下10–12帧世界坐标最大差约 `1.19e-7`，权重和约 `1.0000000149`。导入Armature为线性蒙皮，不扩大成任意保体积结果等价。导出器曾提示夹具Armature父级关系警告，随后只验证该夹具回读，不保证任意实例／父级结构。 |
| clip和采样 | 源 `MappedMotion` 导出为 `Animation`，21通道被优化为2或3键。实际秒时间约0.333333–0.4；同GLB导入24fps场景范围变为约8–9.6帧。按秒对账，不机械比较名称／帧号／键数。 |
| 未覆盖的属性 | 夹具没有材质，输出materials为空；没有物理单位extras。不能宣称材质、贴图、单位标记、完整动作或真实四足交付通过。 |
| 非1 fps_base边界 | 场景 `fps=30,fps_base=1.25` 有效为24fps，10／11／12帧预期约0.416667／0.458333／0.5秒，实际写0.266667／0.293333／0.32秒。有效fps本身为整数，实际验证的是 `fps_base!=1`，未直接测试29.97等分数有效fps；不能归为Hi3D云端或其他版本行为。 |

最后一项可在本机外部Blender源码 [keyframes.py:13](<D:/install/blender/4.5/scripts/addons_core/io_scene_gltf2/blender/exp/animation/keyframes.py:13>) 与 [armature/sampler.py:108](<D:/install/blender/4.5/scripts/addons_core/io_scene_gltf2/blender/exp/animation/sampled/armature/sampler.py:108>) 核对 `frame/(fps*fps_base)`。该导出器入口 `io_scene_gltf2/__init__.py` SHA为 `ec64056ad551a5b54801aacd48e7f60fb769a653f97b1e1ade2d146a341898a4`，属于实际外部依赖版本，不是Hi3D安装包的云端算法。

本机临时探针目录为 `C:/Users/11408/AppData/Local/Temp/hi3d-delivery-export-i3gii0cn`，包含可复核的[export.py](<C:/Users/11408/AppData/Local/Temp/hi3d-delivery-export-i3gii0cn/export.py>)、[import.py](<C:/Users/11408/AppData/Local/Temp/hi3d-delivery-export-i3gii0cn/import.py>)、[导出记录](<C:/Users/11408/AppData/Local/Temp/hi3d-delivery-export-i3gii0cn/export-result.json>)、[GLB结构](<C:/Users/11408/AppData/Local/Temp/hi3d-delivery-export-i3gii0cn/glb-structure.json>)、[独立回读](<C:/Users/11408/AppData/Local/Temp/hi3d-delivery-export-i3gii0cn/import-result.json>)及[fps_base探针报告](<C:/Users/11408/AppData/Local/Temp/hi3d-delivery-export-i3gii0cn/fractional-time-result.json>)。这些路径可能被清理，长期证据是固定包／依赖版本与前述请求和源码；临时输出字节摘要只标识该次运行，不要求每次重跑完全相同。

**登记、宿主与留存样例。** 前序Node VM替身复核登记的同任务不同字节复用、最新版本摘要复用及来源失效分支；宿主离线替身覆盖另存取消／复制顺序和下载状态，不能替代真实桌面完成保存。两份留存会话观察到普通登记、本地导出登记、另行Studio加载及文件引用；三个登记GLB均无 `skins/animations/JOINTS_*/WEIGHTS_*`，不代表绑定／动画分支全集。 [登记观测](../tools/workspace-commit-model.md#核查依据) · [宿主证据](../infrastructure/workspace/preview-and-deliver-files.md#vet3d-迁移与核查范围) · [样例工作区](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40>)

**待实测。** 真实四足、高模、多软层、材质纹理、复杂shape keys／驱动／修改器、多clip／NLA与长动作循环、全LOD及挂点、目标引擎；不同Blender导出器尤其分数fps；生产登记flush故障及重入持久状态；真实Studio重新导出、加载／相机并发切换、系统另存及目标摘要；第三方文件读取、切片器和设备。离线参数与合成运行只证明所验本地分支，不能证明云端结果、最终画质或用户已完成保存。
