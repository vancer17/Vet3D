# 导出并验收云端绑定身体 GLB

以 Hi3D Agent 1.2.11（Windows x64）为核查基准。`rig-retarget` 指导 Agent 在休止空间准备身体，随包的 `service_rig export` 写出指定对象的静态 GLB。Agent 回读实际文件，核对身体范围和空间，再经 `mdf_api` 离线预检。随包 PCG 将服务绑骨列为可选阶段，身体导出由该 Skill 的参考文件约定。 [绑定 Skill](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) · [身体输入与服务交接](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/runtime-service-rig.md#身体输入与服务交接) · [安装包 PCG](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/pcg/architecture.yaml:27>)

## 业务定义

| 项目 | 契约 |
| --- | --- |
| 触发 | 已选云端新绑路线，身体与附属部件的绑定域已确认，需要导出身体或复用已有身体 GLB。随包路线推荐用于未绑定的静止 T/A-Pose 人形。有合格绑定时沿用已有结果。 [路线选择](confirm-rigging-purpose-pose-and-route.md) |
| 上游与输入 | 确切源版本、工作副本或候选 LOD、身体对象及允许表面、休止姿态、轴向和单位、需保留的外观或关键部位、原高模与拟回迁的对象。 [上游分域](define-body-and-accessory-binding-domains.md) |
| 图片角色 | 主参考图可核对身份与必保外观，补充参考图和注明方向的固定视图可核对侧背轮廓、左右和隔离边界。导出及 MDF 请求只消费确切的网格文件，参考图、方向和保留项留在本地验收记录。 [视觉取证](../infrastructure/workspace/acquire-model-visual-evidence.md) |
| 输出 | 确切身体 GLB 及 SHA-256、源身份和休止空间、选用路线与回读证据。新导出带脚本报告，复用带原档位与验收记录。附相同文件的 MDF 预检结果、拟用参数、原高模和回迁清单。 |
| 完成条件与下游 | GLB 实际回读通过，调用方用同一文件完成离线预检，交给云端绑骨提交。原高模、软部件目标和独立部件继续留给本地回迁或装配。 |

## Skill 绑定

通用工作区规则负责源版本定位、原件保留、文件路径和交付登记。身体范围、休止状态和代理准备从领域 Skill 继承。 [工作区模板](../upstream/1.2.11/archived-p0/resources/runtime/templates/AGENTS.md#建模路线选择)

| 入口 | 选用条件与作用 |
| --- | --- |
| [rig-retarget](../upstream/1.2.11/prebuilt-skills/rig-retarget/SKILL.md) | 已选云端新绑时，按 Runtime 参考准备一个身体对象或复用已合格的 LOD，约定本地导出和原高模回迁。 [身体导出参考](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/runtime-service-rig.md#身体输入与服务交接) |
| [mdf-api](../upstream/1.2.11/prebuilt-skills/mdf-api/SKILL.md) | 在提供公开 `mdf_api` 的桌面 Runtime 中，按 `auto-rig` 契约预检。正式提交、原账本恢复和下载由下游沿用同一 Skill。 [公开绑定契约](../upstream/1.2.11/prebuilt-skills/mdf-api/references/mesh-invoke-api.md#37-自动绑定auto-rig) |
| [rig-retarget 的 LOD 参考](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/runtime-mesh-lod.md) | 需要最终档位的减面与重烘时执行。已有合格档位可以复用，单纯上传代理可在身体导出时准备。 [既有 LOD 的准备规则](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/mesh-lod.md#准备与替换网格) |

`service-rig.md` 还保留独立 `mdf-call` 的内部调用方式。当前桌面流程以 `runtime-service-rig.md` 为准，公开 Tool 使用 `file` 和扁平 `params`。 [内部入口参考](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/service-rig.md:24>) · [公开 Runtime 请求](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/runtime-service-rig.md#身体输入与服务交接)

## LLM Tools

| 独立工具说明 | 本节点的调用时机与条件 | 注册与核查 |
| --- | --- | --- |
| [exec](../tools/exec.md) · [exec_command](../tools/exec-command.md) | 定位源文件、执行 Blender 后台导出或回读、计算摘要及检查 GLB。 | 分别为 Code Mode 和本地命令入口。`service_rig export` 是执行的随包脚本命令。 |
| [view_image](../tools/view-image.md) | 数值检查无法确认身体轮廓、左右或接触边界时，查看与实际 GLB 对应的取证图。 | 本地图像查看工具，固定视图生成属于本地资源。 |
| [mdf_api](../tools/mdf-api.md#auto-rig-的输入与产物) | 仅在确切身体 GLB 回读达标后调用 `invoke`，选择 `auto-rig`，并传 `dryRun:true`。同一请求的正式提交与下载在下游。 | Runtime 动态工具。`invoke` 是动作，`auto-rig` 是能力枚举，`dryRun` 是工具参数。 |
| [wait](../tools/wait.md) · [write_stdin](../tools/write-stdin.md) | 本地导出或回读仍在运行时，分别按原 `cell_id` 或 `session_id` 续取结果。 | 续取 Code Mode 单元或本地进程。 |
| [studio_get_state](../tools/studio-get-state.md) · [workflow_report](../tools/workflow-report.md) | 仅在视窗身份待确认时查 Studio 状态，或在已选工作流图时记录实际进度和产物。 | 桌面或 Runtime 动态工具，返回视窗状态或图记录。GLB 验收依据来自实际回读。 |

上述调用时机来自随包指导和已核实实现。留存样例未观察到本节点的生产工具调用，离线复核直接运行了随包 Blender 和 MDF 脚本。`workspace_commit_model` 用于最终登记，身体中间输入由 Skill 直接以文件交给 MDF。 [专项导出脚本](../resources/specialized-mesh-scripts.md#rig-retarget-静态网格导出) · [版本登记](../infrastructure/workspace/import-or-register-model-version.md)

## Hi3D 实现

### 决策

先冻结身体分域与休止空间。在工作副本上明确身体对象名、所属表面和实际对象变换。可合并已确认连续的身体对象，衣物、护甲、毛发和道具按分域保留。若所需休止外形依赖静态修改器、非零形态键或多对象装配，先在副本中准备实际基础网格。 [身体准备规则](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/runtime-service-rig.md#身体输入与服务交接)

| 路线 | 进入条件与处理 | 输出身份 |
| --- | --- | --- |
| 基础网格导出 | 副本的基础身体网格已经符合休止姿态及外观要求。显式指定对象名，调用 `service_rig export` 并省略 `--faces`。 | 新的身体 GLB 和导出报告。 |
| 合格 LOD 复用 | 已有档位符合本次身体范围、休止空间、属性和用途。回读具体文件后可复用该 GLB。若档位含额外衣层、装配或绑定数据，先按分域准备合格的静止身体输入。明确要求新的最终档位时先走 LOD 减面与重烘。 | 原档位、文件摘要及本次复用验收记录。 |
| 仅供提交的减面代理 | 需要限制上传体量或提交三角数。对工作副本导出时加 `--faces N`，必要时在副本另行缩小贴图。Agent 按角色确定预算及保留项。 | 提交代理及实际面数。原高模和其休止空间单独保留，交后续回迁。 |

三种路线由 Agent 按资产和需求选择。`service_rig export` 接收确切对象名及可选面数，未实现自动选档和部件识别。 [随包路径规则](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/runtime-service-rig.md#身体输入与服务交接) · [LOD 整组定稿](review-and-finalize-lod-set.md)

### 执行

**根据随包命令重建的 PowerShell 示例。** 从工作区根目录启动。替换源工程和确切对象名，提交代理才追加 `--faces N`。

```powershell
$blender = 'D:/install/blender/blender.exe'
$skill = 'D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget'

& $blender --background --factory-startup --disable-autoexec --python-exit-code 1 `
  --python "$skill/scripts/run.py" -- service_rig export `
  --input 'work/rig-rest.blend' --body 'Body' `
  --output 'exports/hi3d-body.glb' --report 'exports/hi3d-body-export.json'
```

脚本检查 GLB 与报告为互不相同的新路径，并防止覆盖输入。打开指定 `.blend` 后切到对象模式，按 `--body` 精确取对象，要求非空 Mesh 和有限的基础顶点坐标。`--faces` 如提供，须为至少 `4` 的整数。 [命令和路径校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:372>) · [基础坐标与三角计数](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:15>)

**根据已核实源码重建的实现伪代码。** 减面只作用于提交副本，导出后清理副本并恢复选择。

```python
body = open_blend_in_object_mode_and_lookup(input_blend, exact_body_name)
copy = link_temporary_object("AutoRig submission", body.data.copy())
copy.matrix_world = body.matrix_world.copy()
try:
    clear_shape_keys_and_select_only(copy)
    triangles = count_loop_triangles_and_check_coordinates(copy)
    if faces is not None and triangles > faces:
        apply_decimate(copy, ratio=faces / triangles)
    export_selected_glb(output, animations=False, skins=False, morph=False)
    result = dict(
        mesh=str(output),
        sha256=sha256(output),
        triangles=count_loop_triangles_and_check_coordinates(copy),
        source_object=body.name,
        base_mesh_only=True,
    )
finally:
    remove_temporary_object_and_restore_selection()

result["input_sha256"] = sha256(input_blend)
write_json_atomically(report, result)
```

对象复制使用基础 Mesh 数据，保留打开工程时的 `matrix_world`。形态键在副本上清除，原修改器、骨骼变形和动作不会烘焙进入 GLB。调用方要先确定工程所处的休止帧和姿态。`--faces` 按准备后副本的三角数计算比例，验收以实际结果为准。`base_mesh_only:true` 在减面分支也成立。GLB 先写入，JSON 报告最后原子落盘。 [导出实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:127>) · [报告写入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/service_rig.py:450>)

### 验收

#### 回读实际身体 GLB

| 检查 | 放行条件及实现边界 |
| --- | --- |
| 文件身份与可读性 | 重算确切 GLB 的 SHA-256。新导出的源和产物应匹配报告，复用档位应匹配原身份及本次验收记录。重新解析或导入实际 GLB，确认存在可读取的有效几何。 |
| 身体范围 | 实际导出面属于批准的身体域，附属部件仍能在源工程定位。单对象可包含多个离散网格岛，脚本没有人体识别、连通性或自交验收。 |
| 休止空间与代理质量 | 将实际世界坐标、物理尺度、正侧背轮廓与源休止基准比较。包围盒先用于发现尺度和偏移，再看易粘连处、关节区和必保细节。代理核对实际面数、形状偏差及边界，阈值由任务决定。 |
| 静态结构与外观 | 此新绑输入应无 skin、动画和 morph。按用途核对 UV、实际材质和内嵌贴图。脚本未启用 `export_extras`，物理单位须结合实际空间及交接记录核对。Mesh 数据材质可随副本导出，对象级材质覆盖在隔离试验中没有保留。 |

可使用 P1 资源读实际 GLB 的静态包围盒，或在 Blender 中分开采样基础、求值网格及世界空间，并生成固定取景图。需要单独落盘回读范围和计数时，可显式调用 `audit_models.py`。这些是独立复核手段，由调用方按验收要求选择。 [GLB 包围盒](../resources/p1/glb-bounds.md) · [场景载入](../resources/p1/asset-scene.md) · [网格快照](../resources/p1/mesh-snapshot.md) · [固定视图](../resources/p1/source-views.md) · [独立 GLB 回读](../resources/specialized-mesh-scripts.md#audit_modelspy-独立-glb-回读) · [工作区单位标记](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:40>)

#### MDF 离线预检

**随包 Runtime 请求示例。** `file` 是刚通过回读的工作区相对路径。`use_skeleton:false` 选择新绑。`use_transfer:true` 请求服务将预测绑定迁回实际提交的网格，以保留尺度与材质，服务产物仍需确认实际拓扑和外观。另存的原高模由后续本地阶段回迁。

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
  "outputDir": "exports/hi3d-body-rig",
  "dryRun": true
}
```

客户端检查工作区内单个非空文件、扩展名和大小。`auto-rig` 接受 GLB、OBJ 或 FBX，上限为 `256 MiB`。GLB 分支只校验魔数、版本、声明长度与实际长度，且要求至少 20 字节。参数允许两个布尔值和 `1` 至 `20` 的整数 `num_beams`，另检查作业路径与输入和输出目录的关系。`dryRun` 计算输入指纹，返回请求、文件、作业路径和客户端等待预算 `2100` 秒，随后结束。它没有读取旧账本来仲裁冲突，也没有登录、组 multipart、发送 POST 或保存账本。内部没有有效 JSON 的合成 GLB 也曾通过该预检，因此放行仍依赖前一节的实际回读。 [随包 Runtime 示例](../upstream/1.2.11/prebuilt-skills/rig-retarget/references/runtime-service-rig.md#身体输入与服务交接) · [容器头校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/hi3d_artifacts.py:26>) · [参数校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:45>) · [预检分支](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:180>)

## 完成与恢复

| 当前情况 | 恢复或交接 |
| --- | --- |
| 本地导出或回读仍在运行 | 通过原执行句柄续取结果。若进程中断且只有 GLB，保留该文件用于排查，需重导时使用新的 GLB 和报告路径。 |
| 回读失败或候选不满足任务 | 保留失败候选和证据。按问题修正休止帧、身体范围、代理预算或贴图准备，重导或换档后重新回读和预检。路径、字节、休止空间或必保要求变化时重新确认受影响的验收记录。 |
| MDF 预检失败 | 按实际错误修正输入、大小、参数或路径。若更改候选，先复验实际 GLB。预检通过后固定同一文件、参数、`jobPath` 和 `outputDir`。 |
| 业务回读及预检均通过 | 将确切 GLB、验收记录、源与休止空间、原高模及回迁名单交给[提交并恢复自动绑定](submit-and-recover-auto-rig.md)。正式调用以同一已验收文件移除 `dryRun`，宿主确认按随包 `waiting_choice` 指导处理。身体 GLB 此时作为内部交接件。 |
| 下游已开始提交、结果不明 | 保留原账本、`outputDir` 和已取得的 `requestId`。公开 MDF 是同步 POST，未提供按 ID 查询；`UNKNOWN` 或断线时暂停重提。同一作业路径与文件或参数指纹冲突时保留原记录。 |
| 下游已保存成功、缺本地结果 | 同账号、环境、原 `jobPath` 与 `outputDir` 用 `download` 补取。取得 `files.rigged_mesh` 后交实际骨架、权重、材质与尺度验收和本地回迁，再按交付需要登记模型。 |

[原作业与下载契约](../tools/mdf-api.md#实现伪代码) · [宿主确认范围](../tools/mdf-api.md#宿主确认与执行预算) · [安装包回迁参考](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/references/service-rig.md:37>)

## Vet3D 迁移与核查范围

### 供应商无关的交接契约

| 记录 | 应表达的业务语义 |
| --- | --- |
| 身体基准 | 确切源、批准提交的表面和排除对象、原高模身份、休止姿态及坐标约定，必要时保存固定方向的证据图。 |
| 提交候选 | 基础导出、已验收档位或临时代理的来源，实际文件与摘要、实际三角数、需保留的外观和局部边界，代理与高模的对应关系。 |
| 验收与能力适配 | 分别记录提交件的实际回读证据，以及绑定供应商对格式、大小、骨架输入和参数的预检结果。预检与后续正式操作绑定同一文件摘要。 |
| 下游恢复与回迁 | 分开保存准备结果、供应商原作业身份和下载结果。原高模及逐对象回迁意图随业务上下文交接。 |

Vet3D 的绑定供应商仍待选型。四足角色按实际解剖和目标动作核查四肢间隙、耳根、尾根、须部及其他独立表面的归属。能否复用云端人形路线，以及代理的形状偏差和变形验收标准，需用目标资产验证。

### 安装包证据、样例与缺口

- **版本与原件。** 本地核查基于 1.2.11 安装事务备份。已比对备份与留存生产 Runtime 物化文件，`rig-retarget` 的 Skill、Runtime 参考、`run.py` 和核心导出脚本，以及 `mdf_api.py` 的摘要一致。`service_rig.py` 的 SHA-256 为 `b1090def180cd66ce35bb0c2f1ec4b2343df93ab039fc6fad7958bd989ffcd76`。`mdf_api.py` 为 `5042920c95a891987f81e9e8cc53f96e81c936f54989cbff94f90af1fc35ef05`。 [安装清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) · [仓库 Skill 版本归档](../upstream/1.2.11/README.md)
- **已离线验证。** Blender 4.5.16 LTS 随包 `test_service_rig` 合成回归通过。独立夹具含额外附件、形态键、修改器、打包贴图和对象动画。无减面导出为 224 个三角面，`--faces 61` 在该夹具上得到 60 个。两份结果均只含提交对象并保留测试材质与内嵌贴图，摘要匹配，源工程未改。默认导出回读包围盒匹配当前帧的基础网格，区别于求值后的可见网格。已用真实导出的合成文件跑通 MDF 离线预检，也复现了错误 GLB 版本、布尔 `num_beams` 被拒绝，以及头部合法、数据无效的 20 字节文件通过。 [随包 Blender 回归](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_service_rig.py:14>) · [MDF 客户端测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/tests/runtime/test_mdf_api.py>)
- **样例覆盖。** 留存三个登记 GLB 均为静态模型，首版仅含 `geometry_0`，后两版另有 `Whiskers_Left` 和 `Whiskers_Right`，三份均无 `skins` 和 `animations`。两份关联留存会话的实际调用中，四次 Blender GLB 导出用于胡须或面部修订，未观察到 `service_rig export` 或 `auto-rig`。样例支持静态对象结构和普通修订导出。 [留存工作区](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40>) · [关联样例说明](confirm-rigging-purpose-pose-and-route.md#安装包证据样例与缺口)
- **待实测。** 生产账号下的服务受理、实际宿主确认和返回文件仍待实测。本地夹具未覆盖真实四足角色的可用休止姿态、代理保形与自交、绑定质量、软部件回迁及最终动作形变。
