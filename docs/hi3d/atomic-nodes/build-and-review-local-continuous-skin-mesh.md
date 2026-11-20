# 构建并验收本地连续皮肤网格

以 Hi3D Agent 1.2.11（Windows x64）为核查基准。Agent 先将可共享形变的身体表面落实为独立输入，Blender 本地脚本 `prepare_mesh` 再合并、归一化、焊接和三角化。Agent 回读实际准备工程，确认身体拓扑、休止空间和保留项后，才将固定的网格交给骨架标定与权重求解。 [绑定 Skill](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) · [安装包焊接约定](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/geometry-and-binding.md:11>)

## 业务定义

| 项目 | 契约 |
| --- | --- |
| 触发 | 已选本地新绑定，需要从一张连续皮肤域建立可求权重的工作网格。已有合格绑定的角色按其实际用途复用或局部修订。需要替换已绑定工程的网格时，在独立准备工程处理，再按原休止空间交接。 [路线选择](confirm-rigging-purpose-pose-and-route.md) |
| 上游与输入 | 源版本和工作副本、允许共同焊接的对象或面范围、须隔离的软层／刚性部件／道具、休止姿态与轴向、实际单位和目标高度。已验收 LOD 可作为源，按任务附逐档身份和贴图保留要求。 [上游分域](define-body-and-accessory-binding-domains.md) · [LOD 整组定稿](review-and-finalize-lod-set.md) |
| 图片角色 | 有身份对应的主图核对角色和必保形态，补充方向图与模型的实际固定视图或截面核对肢体分隔、附着及接触区。`prepare_mesh` 接收网格文件，参考图、视向和保留项留在本地验收依据中。 [视觉取证](../infrastructure/workspace/acquire-model-visual-evidence.md) |
| 输出 | 已实际回读的准备 `.blend`、配套 `.mesh.json`、域清单与变换记录。交接确切源与候选身份、实际几何验证结果、原资产和可定位的独立部件。 |
| 完成条件与下游 | 最终基础三角网格在预定的休止空间内，预期连续位置已连接、独立部件隔离、几何和属性通过检查。固定该工程和最终拓扑，先交 [标定本地骨架与蒙皮范围](calibrate-local-skeleton-and-skinning-scope.md)，标定完成后以同一网格构建或导出权重求解输入。 |

## Skill 绑定

通用工作区规则负责版本定位、原件保护、执行路径和产物身份。哪些表面可共用皮肤、如何焊接以及怎样标定均由领域 Skill 定义。 [工作区模板](../upstream/1.2.11/archived-p0/resources/runtime/templates/AGENTS.md#建模路线选择)

| 入口 | 选用条件与作用 |
| --- | --- |
| [rig-retarget](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) | 新绑定选择本地校准和求权重时使用。四肢分离、连续域、焊接和标定以实际模型为依据。 [安装包几何与绑定](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/geometry-and-binding.md:5>) |
| [rig-retarget 的 LOD 参考](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/mesh-lod.md#准备与替换网格) | 有合格档位时直接交本地准备且省略重复减面。确需最终减面及重烘时先按 LOD 路线取得已验收档位。 |
| [hi3d-model-gpt-animation 的衣物与次级运动参考（安装包）](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/hi3d-model-gpt-animation/references/garments-and-secondary-motion.md:7>) | 任务含独立衣层、尾部或披风的运动时，按需补充语义标签、休止空间和独立权重或装配约定。 |

## LLM Tools

| 独立工具说明 | 本节点的调用时机与条件 | 注册与核查 |
| --- | --- | --- |
| [exec](../tools/exec.md) · [exec_command](../tools/exec-command.md) | 读取输入和报告、运行 Blender 后台准备和回读命令、计算身份摘要。 | Code Mode 和本地命令入口，通过本地 [准备脚本](../resources/specialized-mesh-scripts.md#prepare_mesh-网格准备)执行。 |
| [view_image](../tools/view-image.md) | 用实际候选生成方向或近景图后，按需核对轮廓、接缝、独立域和材质。 | 本地图像查看工具。生成或测量图像是独立资源操作。 |
| [wait](../tools/wait.md) · [write_stdin](../tools/write-stdin.md) | 本地准备或回读仍运行时，分别用原 `cell_id` 或 `session_id` 续取结果。 | 分别续取 Code Mode 执行单元与本地进程。 |
| [studio_get_state](../tools/studio-get-state.md) · [studio_load_revision](../tools/studio-load-revision.md) | 仅当用户指代当前视窗或需要确认登记的源 GLB 版本时用。 | 桌面动态工具。准备产物 `.blend` 通过 Blender 回读。 |
| [workflow_report](../tools/workflow-report.md) · [user_interaction](../tools/user-interaction.md) | 实际采用工作流图时上报其已有阶段及文件。分域或必保要求仍有实质歧义时按需澄清。 | Runtime 动态工具。PCG 中没有单独的 `prepare_mesh` 节点，命令自身没有独立参数面板。 |

随包指导将准备、回读和求权重安排为本地操作。`make_profile`、`build_character` 和 `weight_graph` 在下游接收准备结果。只有上游另行请求云端 LOD 派生时，才按该分支处理 MDF。留存会话有通用执行工具调用，本节点的专项链路由源码和隔离复核确认。 [下游权重输入接口](../resources/specialized-mesh-scripts.md#build_character-权重输入接口) · [安装包 PCG](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/pcg/architecture.yaml:7>) · [派生档位流程](derive-and-check-lod-files.md)

## Hi3D 实现

### 决策

先冻结要共同求权重的身体范围和休止空间，再制作只含允许表面的输入 GLB。`prepare_mesh` 会选择输入场景中的全部 Mesh，独立部件的分离须在调用前完成。确认连续的身体即使拆成多个对象或有独立面角 UV，仍可合入同一求解域。独立衣层和软部件保留各自附着位置与权重来源。刚性壳体和道具保留目标骨或挂点及局部变换。 [分域规则](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/geometry-and-binding.md:11>) · [各域的上游交接](define-body-and-accessory-binding-domains.md#决策)

分开保存的部件应使用同一休止坐标约定，以便最终回装。准备脚本每次根据当前输入的包围盒计算中心和缩放。每个独立部件自行归一化会改变与身体的相对尺度或位置，因此应保留实际身体变换及其对独立部件的应用关系。换已绑定网格时，保留原骨架、rest 变换及已有动作，在独立候选中处理。 [归一化实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/prepare_mesh.py:12>) · [既有绑定替换](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/mesh-lod.md#准备与替换网格)

| 路线 | 选择与约束 |
| --- | --- |
| 保留工作分辨率 | 从身体源网格准备，执行焊接和三角化，省略 `--faces`。 |
| 复用合格 LOD | 交已验收档位的实际 GLB 和源身份。省略 `--faces`，保留档位自带的 UV、材质和法线贴图，以本次工作拓扑重新建立索引证据。 |
| 可选本地减面 | 任务明确选择本地减面或允许预览代理时给 `--faces`。仅当三角化后超预算才使用 Decimate，结果面数为近似值。该分支缺少严格自交保护及贴图重烘，保形、自交和贴图质量须再验收。若任务要求最终减面并重烘，接入已有 LOD 路线。 |

[LOD 选择与约束](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/mesh-lod.md#推荐方法与边界) · [本地减面分支](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/prepare_mesh.py:77>)

### 执行

**根据随包 CLI 重建的 PowerShell 示例。** 从任务目录调用，输入为已隔离的身体 GLB。高度和 Z 旋转按实际角色设置，合格 LOD 复用与基础准备均可省略 `--faces`。

```powershell
$skill = 'D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget'
& 'D:/install/blender/blender.exe' --background --factory-startup `
  --disable-autoexec --python-exit-code 1 `
  --python "$skill/scripts/run.py" -- prepare_mesh `
  --input 'body-only.glb' --output 'prepared.blend' `
  --height 1.8 --rotation-deg 0 --weld-relative 1e-6
```

CLI 必填输入和新输出路径，派生的 `.mesh.json` 也须为新路径。`--height` 默认 `1.8`，`--weld-relative` 默认 `1e-6`，均须为有限正数。`--rotation-deg` 默认 `0` 并须有限，随包 CLI 用此参数对齐约定的朝前方向 `-Y`。`--faces` 如提供，须为正整数。脚本清理当前工作场景后导入 GLB；应在隔离的后台进程运行。 [命令定义与参数校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/prepare_mesh.py:89>) · [CLI 参数](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/prepare_mesh.py:138>)

**根据已核实源码重建的实现伪代码。** `body_glb` 已经过上游分域。节点组在整个已合并的表面执行距离合并。

```python
clear_working_scene()
import_gltf(body_glb)
surface = join_all_scene_meshes(name="CharacterSurface")
apply_object_transforms(surface)
rotate_mesh_data_about_z(surface, rotation_deg)
center, scale = normalize_base_vertices(surface, height)
before = vertex_count(surface)
distance = height * weld_relative
apply_geometry_nodes_merge_by_distance(surface, distance)
welded = vertex_count(surface)
triangulate(surface)
if faces is not None and face_count(surface) > faces:
    apply_decimate(surface, ratio=faces / face_count(surface))
mark_prepared(surface, height, weld_relative)
pack_assets_and_save_blend(surface, output)
write_mesh_report(output, before, welded, distance, center, scale)
```

归一化以转向后基础顶点的 XY 包围盒中点居中、将最低 Z 置零，并缩放至 H。脚本拒绝空顶点、非有限基础坐标或小于 `1e-8` 的源 Z 跨度。焊接用 Blender Geometry Nodes 的 `Merge by Distance`，测试中模式为 `ALL`，距离从 `H × weld_relative` 计算。位置合并后，已有面角仍可携带不同 UV。该分支先焊接后减面，翻边和其他拓扑修补由调用方另行决定。 [归一化](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/prepare_mesh.py:12>) · [全 Mesh 合并](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/prepare_mesh.py:32>) · [Geometry Nodes 焊接](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/prepare_mesh.py:52>)

保存前在对象上写入 `character_height_m`、`weld_relative` 与 `welded_before_weights`。工程打包并保存后才写报告。报告记录焊前／焊后顶点数、最终顶点和面数、目标高度、焊接距离、归一化中心及比例。源文件摘要、调用方给定旋转和父级变换另随任务交接。工程与报告分开写入，进程中断时可能只留下工程。 [落盘与报告字段](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/prepare_mesh.py:109>)

### 验收

| 检查 | 实际工程的放行条件 |
| --- | --- |
| 文件和网格身份 | 用实际落盘 `.blend` 开新的检查进程，核对相应报告和候选身份。求解场景中应恰有一个工作 Mesh，顶点有限，索引有效，实际存在非空的有效三角表面。`welded_before_weights` 是准备标记。实测过大焊接公差产生的空面候选仍能导出 NPZ，放行前须检查有效三角面。 |
| 域边界和拓扑 | 检查应连续的接缝是否共享顶点，独立衣层、相贴肢体和道具是否隔离。核对连通分量、边界、非流形、退化面和近重合点。结合分域意图判定有效边界，缩小公差只会改变点的合并，导入的对象仍会进入 `join()`。 |
| 休止空间 | 核对实际父级、`matrix_world`、基础局部和世界的包围盒、朝向及单位。安装包会应用对象变换，但父级可能保留，报告目标高度不能证明世界尺寸正确。下游用基础局部顶点建立骨架与图权重，交接前应确认该空间和原资产的对应。 |
| 保形与属性 | 回读并对照关节区、轮廓、实际面数、焊后新增交叉、面角 UV、逐面材质及贴图。不同拓扑按实际表面和同机位对照。若对针状面另做翻边，随包指导限于同材质且 UV 连续的内部边。 |

可选用 P1 `asset_scene` 重开工程、用 `mesh_snapshot` 取基础局部或世界顶点及属性。需要核对连通、边界和非流形时用 `measure_mesh(weld=None)`。需要汇总世界范围或复查三角边使用时按需选择 `scene_measure` 或 `triangle_arrays`。`collision.py` 可查严格三角穿越，切触、共面或共享顶点的面另行判断。`geometry_compare.py` 要求索引拓扑一致，焊接或减面改变拓扑后另建对照。以上回读由调用方执行。 [场景载入](../resources/p1/asset-scene.md) · [网格快照](../resources/p1/mesh-snapshot.md) · [独立测量接口](../resources/specialized-mesh-scripts.md#mesh-audit-网格测量函数)

## 完成与恢复

| 当前情况 | 恢复或交接 |
| --- | --- |
| 本地执行仍运行，或中断只留下部分文件 | 用原进程句柄续取结果。保留已有工程、报告和命令记录用于诊断，准备未完成或结果无法确认时使用新工程及报告路径。 |
| 独立部件合入、休止空间不一致或几何验收失败 | 分别回到分域隔离、父级与变换准备、焊接公差或减面选型。保留源和失败候选，新准备结果重新回读。若只缺贴图、UV 或近景证据，检查同一确切候选及保留项后再决定是否重做拓扑。 |
| 准备通过，交骨架标定 | 交确切 `.blend`、匹配报告、源与工作拓扑身份、身体范围、独立部件映射和休止空间。`make_profile` 产生 `calibrated:false` 的人形种子。执行者按最终网格的正面、侧面和关节截面校准骨点、骨轴、父子关系与初始配权区，校准完成再置 `calibrated:true`。 |
| 标定通过，交权重求解 | `build_character` 检查已标定配置、单 Mesh、焊接标记和 `character_height_m`，读取基础局部顶点和实际三角索引。可在兼容的 Blender 环境内用 SciPy 求解，或以 `--export-weight-input` 导出顶点、面、初始权重、骨名顺序、网格与标定摘要，由独立 NumPy/SciPy 环境求解，经 `weights_npz` 回读。 |
| 拓扑、休止坐标或标定改变，或外部求解失败 | 文件与数组身份、骨名顺序和标定摘要不符时保留旧缓存，重导受影响的标签或权重输入。求解参数改变时显式重算并更新缓存路径，标定摘要没有纳入 solver 参数。未收敛结果保留失败诊断，并按新路径重算。 |

统一皮肤域先求权重，再按实际面标签拆件。`labels_npz` 核对最终网格摘要和面数。拆件复制面角 UV、逐面材质及同一源顶点的权重，随后可给已声明的独立刚性壳体指定单骨。该阶段的输出仍需后续姿态和动作验收。 [校准种子](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/make_profile.py:111>) · [构建与权重输入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py:174>) · [外部求解及缓存](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/dense-skinning.md:15>) · [标签核对](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/build_character.py:71>) · [拆件权重复制](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/blender_core.py:107>)

## Vet3D 迁移与核查范围

### 供应商无关的交接契约

| 记录 | 应表达的业务语义 |
| --- | --- |
| 分域与休止空间 | 允许共同焊接和求权重的表面，以及软层、随骨部件和道具的对应关系。记录源、准备工程、轴向、单位、角色尺度和实际变换。 |
| 工作网格和验收 | 固定实际基础三角网格的版本和拓扑身份。关联焊接参数、真实面数、连通性、属性及视图。档位或拓扑变化后以新工作网格作基准。 |
| 标定与权重身份 | 确认骨架参数对应最终工作网格，缓存关联顶点、索引、骨名顺序、校准和求解配置。独立域的权重和装配保留单独记录。 |

Vet3D 仍待选择四足绑定和求解方案。可复用的工程边界是先隔离求解域，按最终网格回读放行，再将骨架标定和权重输入绑定同一休止空间与拓扑。猫狗等四足角色的骨点、耳根和尾根、相贴四肢及独立附件，应按实际解剖和目标动作定义。

### 安装包证据、样例与缺口

- **版本与原件。** 1.2.11 安装事务备份的 `prepare_mesh.py` SHA-256 为 `492728e7f666ae876113fb6ce994afb3ee82a4745145b165fbe31c587cb42da5`，`build_character.py` 为 `95cae0d242467669756f53b15ea28eabb01648d6f3b217fd7ad5cc6a7aa6bf53`，均与留存 Runtime 物化副本一致。 [安装包清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) · [归档 Skill 版本](../upstream/1.2.11/README.md) · [准备源码](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/prepare_mesh.py>)
- **隔离复核。** Blender 4.5.16 LTS 下，两张分属不同对象的三角片由 6 顶点焊为 4，仍保留 2 面、6 处面角 UV 与各自材质。混入近邻附件时可误焊，远离的附件仍会合并为同对象里的另一连通分量并改变归一化中心。过大公差可产生 `working_faces:0` 且脚本退出成功。带父级缩放的夹具复现了局部高度和世界高度差异。 [随包焊缝夹具](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_blender.py:22>) · [准备与保存](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/prepare_mesh.py:109>)
- **求解交接已离线复核。** 合成工程验证未校准配置、缺焊接标记和多个 Mesh 时拒绝导出权重输入。已跑通 Blender 权重输入导出、随包独立 Python 的 CG 求解及回 Blender 构建。修改骨端后旧缓存被拒绝，随包 `test_weight_graph` 五项通过。 [外部缓存入口](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/weight_graph.py:179>) · [随包求解测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_weight_graph.py>)
- **样例覆盖。** 三个登记 GLB 均为静态模型，后两版另有独立左右胡须。两份留存会话观察到的局部焊点用于面部或胡须修订，未观察到 `prepare_mesh` 到标定及权重求解的专用链路。 [留存工作区](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40>) · [关联样例说明](define-body-and-accessory-binding-domains.md#安装包证据样例与缺口)
- **待实测。** 生产宿主中的工具调度、真实四足模型的分域与尺度、不同 LOD 的局部保形和贴图、复杂软层回装、高面数资源消耗以及目标动作中的变形与接触。
