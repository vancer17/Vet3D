# 网格缺陷修复与水密化

以 Hi3D Agent 1.2.11（Windows x64）为核查基准。本节点处理已有 GLB 的拓扑缺陷，按任务选择只读诊断、本地局部修复或调用 MDF 服务做整网格水密重建。Agent 通过已安装的 `mdf_api` 提交源网格，服务生成候选，客户端下载候选并另行验收。三份留存 GLB 和历史会话只用于验证其中一次本地补片、导出及登记。 [版本归档](../upstream/1.2.11/README.md) · [工作区模板](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:23>)

## 业务定义

| 项目 | 契约 |
| --- | --- |
| 触发 | 用户要求检查、修复或水密化已有网格，或上游候选检查发现会影响当前交付的裂缝、退化面、非流形边、绕序异常等缺陷。闭合、单体和可打印性按用途分别要求。 |
| 上游与输入 | 接收候选适用性检查结果，或从工作区选定已有模型。确定家族、确切源版本及 GLB 路径、缺陷证据、目标对象或区域、允许修改范围、预期连通件与必保项。按通用入口默认复用最新家族版本。执行和恢复期间固定选中的实际文件。 [候选适用性](check-model-candidate-suitability.md) · [查询模型版本](../infrastructure/workspace/query-assets-and-model-versions.md) |
| 图片角色 | 几何主输入是源 GLB。已有主参考图用于比对主体轮廓和个体特征，补充参考图用于核对侧面、背面或遮挡区域。目标方向由本地对照渲染的相机或 Studio 截图视角表达。图像工具只接收相应图片文件。必保项由任务上下文、局部脚本及验收记录承载。MDF 这两项能力只上传一个 GLB，schema 无主图、补充图、方向、局部遮罩或保留项字段。 [模型视觉取证](../infrastructure/workspace/acquire-model-visual-evidence.md) · [MDF 参数](../tools/mdf-api.md#参数与结果) |
| 输出与完成条件 | 只读分支交付与源文件对应的诊断、检查范围及结论。修复分支交付另存的候选 GLB，回读后按当前用途复验拓扑及必保项。候选的验收结果绑定实际文件，只有通过后才交登记或下一项加工。正式模型交付以登记回包中的版本为准。 |
| 下游 | 登记交接模型家族 `name` 及选定的 `exportPath`。后续展示、绑定或动画引用返回的确切版本。打印另按任务检查尺寸、壁厚及工艺，再交摆盘、切片或文件交付。 [版本登记](../infrastructure/workspace/import-or-register-model-version.md) · [Studio 加载](../infrastructure/workspace/load-studio-revision.md) · [文件交付](../infrastructure/workspace/preview-and-deliver-files.md) |

## Skill 绑定

**通用入口。** 宿主注入的 `AGENTS.md` 指示已有模型的局部修复优先复用当前资产，保留历史版本、物理单位标记与稳定部件名。局部编辑可在 Blender 工作副本上执行，导出到 `exports/` 后显式登记。该入口提供执行路线与工作区约定。局部缺陷的具体算法由任务和所选 Skill 决定。 [随包模板](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:31>)

| Skill 或依赖 | 选用条件与作用 |
| --- | --- |
| [MDF Skill](../upstream/1.2.11/prebuilt-skills/mdf-api/SKILL.md) | 选定服务侧可打印性诊断或整网格水密重建时读取。按公开能力白名单准备单文件，先 dry-run，再使用稳定作业路径正式调用。遵循宿主确认与原作业下载恢复规则。 [随包接口契约归档](../upstream/1.2.11/prebuilt-skills/mdf-api/references/mesh-invoke-api.md) |
| [图片到高精度组装模型](../upstream/1.2.11/prebuilt-skills/image-to-assembly/SKILL.md) | 已选用语义拆件或装配路线，且缺陷涉及预期接口时执行。先处理开放裁切和误切孤片归属，再按实际尺度焊接预期接缝、保留逐角 UV、定向封口并检查加工新引入的干涉或自交。 [整模拆件](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/image-to-assembly/references/existing-sculpture.md:13>) · [装配验收](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/image-to-assembly/references/validation.md:37>) |
| [Hi3D 通用建模](../upstream/1.2.11/prebuilt-skills/hi3d/SKILL.md) | 上游使用 Hi3D 生成路线时提供建模与分类上下文。同主体修订可沿用已有分类。局部修复按工作区规则使用现有 GLB。 |
| [随包 mesh-audit 依赖](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/REFERENCE.md>) | 本地诊断与回读验收可复用其网格测量。它属于脚本依赖，测量输出供调用方做业务判断。 |

其他专项修复由其自身条件启用。例如水景包的 `repair_stl` 清理毫米 STL 量化产生的近退化面。其函数只在边界、非流形及退化均清零后写出另一个 STL。脚本没有通用补洞步骤，当前核查也未发现宿主将它作为每个 GLB 的自动处理。 [水景修复实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/water-feature/scripts/water_model/repair.py:6>)

## LLM Tools

| 独立工具说明 | 在本节点的调用时机 | 样例或核查状态 |
| --- | --- | --- |
| [`exec`](../tools/exec.md) · [`exec_command`](../tools/exec-command.md) | 检查工作区源文件、运行本地测量与 Blender 脚本、回读候选及生成对照渲染。Blender、随包测量器和用户工作区脚本是被执行的程序。 | 猫模型样例实际运行 Blender 脚本。 |
| [`write_stdin`](../tools/write-stdin.md) · [`wait`](../tools/wait.md) | 前者使用 `session_id` 续查本地命令，后者仅在 Code Mode 调用返回 `cell_id` 时续接该单元。 | 样例实际以 `write_stdin` 续查 Blender。 |
| [`mdf_api`](../tools/mdf-api.md) | `invoke` 以 `check-printability` 请求服务侧只读拓扑诊断，或以 `watertight` 上传源 GLB 并请求服务生成水密候选。`download` 在原成功响应已保存时取回尚未落盘的产物。 | Runtime 已注册，MDF Skill 指导调用，已离线复核。留存修复样例走本地脚本。 |
| [`view_image`](../tools/view-image.md) · [`studio_get_state`](../tools/studio-get-state.md) · [`studio_capture_view`](../tools/studio-capture-view.md) | 分别查阅本地候选渲染、核对已加载版本及状态、获取该版本的视窗截图。候选还在 `exports/` 时可直接做本地渲染。 | 样例查看本地近景，登记加载后有 Studio 状态回包。截图工具为条件入口。 |
| [`workspace_commit_model`](../tools/workspace-commit-model.md) · [`studio_load_revision`](../tools/studio-load-revision.md) | 通过验收后以选定导出登记。需要在 Studio 展示时按回包的确切版本加载。 | 样例实际登记并加载 `hi3d-猫_3.glb`。 |
| [`image_classification`](../tools/image-classification.md) | 登记返回 `classificationRequired` 时按工具契约补分类，复用原候选和家族再次登记。 | 样例继承分类，该轮无需再调用。 |

`invoke` 与 `download` 是 `mdf_api` 的动作。`watertight` 与 `check-printability` 是能力枚举。两项枚举共享一个 Runtime 工具。模型可见的描述原文、全部参数和通用恢复规则由独立工具页维护。 [MDF 工具定义](../tools/mdf-api.md)

## Hi3D 实现

### 决策

1. **确定诊断范围。** 对实际源文件查拓扑，明确按整场景、对象或局部边链统计。GLB 的材质图元、UV 或法线拆点可能让原索引表现出开放边。`measure_indexed` 可在保留输入数组的同时追加完全同坐标的虚拟焊接诊断。`measure_mesh` 在临时 BMesh 上测量边界、非流形、绕序异常、退化、连通和体积。记录坐标系、是否焊接及所用阈值。 [数组测量](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/triangle_arrays.py:33>) · [BMesh 测量](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/mesh_measure.py:6>)
2. **按用途选择执行方式。** 只需要报告时，保存本地诊断，或按需调用 `check-printability`。指定裂缝、接缝或须保留的开口优先走可控的本地修复。明确需要闭合候选且允许重建影响时，才进入 MDF `watertight`。该能力没有逐部件或逐孔的保护参数，`is_fillhole: false` 仅关闭补洞选项，开口能否保留仍由候选实测确认。 [已有模型路线](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:31>) · [水密参数](../upstream/1.2.11/prebuilt-skills/mdf-api/references/mesh-invoke-api.md#34-水密处理watertight)

### 执行

**本地局部修复。** Agent 按模型结构编写脚本，用宿主提供的 Blender 路径执行 `--background --python <脚本>`。猫模型样例从 `_1` 取身体，从 `_2` 保留左右胡须。它删除已确定的错误顶点，合并距离在 `1e-6` 范围内的顶点，要求边界环上的每个顶点恰连两条边界边，再对简单闭环加中心点并以三角扇补片。脚本局部平滑、更新法线，另行核对胡须的坐标、世界矩阵与面数。随后带物理单位标记另存 GLB。这个算法来自该次局部修订脚本。 [样例脚本](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/scripts/hi3d-cat-face-finish_12.py:15>) · [执行与续查](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:921>)

#### MDF 水密重建与候选取回

**预检。** 下面是**根据已核实 schema 重建的 `mdf_api` 离线预检示例**。假定源文件在工作区内，任务允许补洞，并用 `target_face_num: 0` 跳过减面。

```json
{
  "action": "invoke",
  "capability": "watertight",
  "file": "hi3d-example_1.glb",
  "params": {
    "watertight_resolution": 4096,
    "target_face_num": 0,
    "is_fillhole": true
  },
  "jobPath": ".hi3d/mdf/example-watertight.json",
  "outputDir": "exports/example-watertight",
  "dryRun": true
}
```

两项能力均校验工作区范围、GLB v2 文件头和 200 MiB 上限。水密分辨率为不超过 4096 的正整数二次幂，减面目标为至少 `-1` 的整数，`0` 与 `-1` 均跳过减面。补洞开关为布尔值。省略参数由服务补齐，客户端保留实际传入的 `params`。`dryRun` 返回请求预览、输入路径、作业路径和客户端等待预算，当时尚未构造 multipart、登录或写入作业。 [桌面参数校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:45>) · [水密参数与默认值](../upstream/1.2.11/prebuilt-skills/mdf-api/references/mesh-invoke-api.md#34-水密处理watertight)

**正式提交与服务端重建。** 沿用同一参数与作业路径，省略 `dryRun` 或传 `false`。Runtime 启动当前环境已安装的 `mdf_api.py`，经 Electron 桌面账号代理同步 `POST /v1/mesh/invoke`。multipart 的 `request` 部分包含 `capability: "watertight"`、处理参数和可用的会话关联 ID，`file` 部分上传源 GLB 的原始字节，上传名为 `input.glb`。组包时复核输入摘要。`jobPath` 与 `outputDir` 由客户端用于作业记录与落盘。公开契约把该 POST 定义为接收源 GLB 并执行水密处理的服务入口，因此**网格重建发生在同步请求的服务端处理阶段**。脚本等待预算为 2100 秒。Skill 对正式调用有宿主确认约定，实际是否出现提示仍待登录环境实测。 [已安装调用脚本](<D:/download/.sparc3d-runtime/environments/prod/codex-home/skills/buildin/mdf-api/scripts/mdf_api.py:180>) · [公开请求契约](../upstream/1.2.11/prebuilt-skills/mdf-api/references/mesh-invoke-api.md#2-请求格式) · [确认与执行预算](../tools/mdf-api.md#宿主确认与执行预算)

**服务处理的细化证据。** 随包的独立 `mesh-watertight` 契约固定到服务提交 `861eb6919bd4f715dae98b389589cfe49c185713`，记录了可选的补洞预处理、`wt_finally` 水密重建、可选减面与细长三角面清理，最后验证并发布一个 GLB。按该契约，`is_fillhole` 控制预处理，`watertight_resolution` 是重建分辨率请求，实际分辨率还可能受输入分类和显存容量策略影响，`target_face_num: 0` 只跳过减面。该资料描述独立 BinaryFile 服务接口，`watertight_succeeded`、`resolution_actual` 等诊断属于其契约。其文件 API 仅读第一个 mesh primitive。桌面公开接口有自己的请求白名单与回包，生产部署是否运行相同版本、是否透出上述诊断、如何处理多图元或多对象 GLB，仍待核实。 [固定版本服务契约](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mdf-call-source/references/mesh-watertight.md:3>) · [独立服务参数和输出](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mdf-call-source/references/mesh-watertight.md:29>)

本机已安装的 MDF Skill 提供调用脚本，脚本与安装包预置副本摘要一致。其打包清单列出调用、校验和存储组件。MDF 路径的算法依赖由服务部署提供，桌面另有供本地脚本使用的 Blender 环境。 [桌面 Skill 打包清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/package.json:12>) · [服务端依赖](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mdf-call-source/references/mesh-watertight.md:65>)

**根据随包脚本重建的客户端实现伪代码。** `post_multipart_once` 提交同步服务请求，由服务执行 `watertight` 对应的网格处理。`download_saved` 从成功的原响应取回可用文件，并核对账号、环境与原输出目录。脚本在 POST 之前独占建立 `UNKNOWN` 记录。

```python
def execute_mdf(args):
    if args.action == "download":
        return download_saved(args.job_path, args.output_dir)

    request = validate_and_prepare(args)
    input_hash = sha256(request.file)
    fingerprint = fingerprint_of(request.capability, request.params,
                                 input_hash, args.output_dir)
    if args.dry_run:
        return request_preview(request)

    authenticate_desktop_context()
    if job_exists(args.job_path):
        verify_original_fingerprint(args.job_path, fingerprint)
        return download_saved(args.job_path, args.output_dir)

    reserve_job_exclusively(args.job_path, fingerprint, status="UNKNOWN")
    try:
        http_status, body = post_multipart_once(request, expected_input_hash=input_hash)
        save_response(args.job_path, body)
        succeeded = (http_status == 200 and type(body.get("code")) is int
                     and body["code"] == 0 and body.get("status") == "SUCCEEDED")
        status = "SUCCEEDED" if succeeded else normalize_failure_status(body)
        persist_job_status(args.job_path, status)
    except Exception:
        persist_job_status(args.job_path, "UNKNOWN")

    return download_saved(args.job_path, args.output_dir)
```

**保存服务回执并取回候选。** HTTP 200、整数 `code: 0` 和服务 `status: "SUCCEEDED"` 同时成立时，客户端记录本次处理成功。它从 `data.files.watertight_mesh_glb` 读取服务已生成的候选描述，用其中的 `url` 下载 GLB。首次取回并通过文件头校验后，记录路径和摘要，在 `files.watertight_mesh_glb` 返回本地路径。`action: "download"` 可以恢复原响应中的产物取回，全程沿用原记录。此时拿到的是供验收的候选，边界、薄结构和属性由回读后的检查确认。 [服务响应与下载契约](../upstream/1.2.11/prebuilt-skills/mdf-api/references/mesh-invoke-api.md#4-通用响应与下载) · [客户端下载实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:114>)

**只读检测。** `check-printability` 同样用 `invoke` 提交待测 GLB，由服务返回拓扑诊断。`require_single_body` 与 `require_watertight` 均为布尔值，服务默认均为 `true`。从 `response.data.result_json` 读取 `topology_ok`，有 `topology_report` 时解析其 JSON 字符串。调用成功可以与 `topology_ok: false` 并存，该能力按契约只返回诊断。 [可打印性检测契约](../upstream/1.2.11/prebuilt-skills/mdf-api/references/mesh-invoke-api.md#314-可打印性检测check-printability)

**桌面可达性。** 随包通用编辑器的 Worker 可按无向索引边检测边界和非流形，修复分支会删除退化面和重复三角面。`fixBoundary` 在实现中将 `fixedBoundary` 设为 `0`。离线执行原 Worker，缺一面的四面体报三条边界，开启修复后索引没有变化。另一条通用 Smart Repair 路径依赖 `smartToolConfig`，上传快照、提交 `repair-mesh-from-trimesh` 并按任务 ID 查询，候选经用户确认后才应用。本版 `StudioHost` 隐藏左侧工具栏，仅开放 `joint`、`arrange`，并且未传上述配置。实际注册给 LLM 的五个 `studio_*` 工具没有网格检测及修复入口。普通 3MF 导出检查坐标与索引等组包条件，水密检查仍由另行验收承担。 [桌面 ASAR](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) · [打印计划工具](../tools/studio-export-3mf.md)

### 验收

1. **回读候选文件。** 绑定实际文件的路径和摘要，按与源诊断相同的对象和焊接口径复测。要求闭合时检查边界、非流形、退化和绕序，再按用途核对连通件、体积、自交或壁厚。随包 `crossing_pairs` 只计严格内交并排除共享顶点索引的面。要求完整自交检查时，另行覆盖共享边、共享点、重合及内含等相关场景。 [网格验收契约](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/references/code-contract.md:40>) · [相交检测实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/collision.py:26>)
2. **核对缺陷位置与保留项。** 对比源和候选的同机位整体视图及局部近景，核对有意开口、薄结构、独立部件、单位和外观。要求纹理或动画时，按当前任务进一步检查 UV、材质、骨骼及蒙皮。样例的 Blender 断言覆盖身体对象。回读留存 `_3.glb` 时，其身体含两个材质图元。以同一身体对象为范围，原索引有 39,228 条边界，完全同坐标虚拟焊接后边界边与超过两面共享的边均为 0。两侧胡须未并入此测量。该结果仅支持所用口径下的身体边闭合。 [样例断言](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/scripts/hi3d-cat-face-finish_12.py:60>) · [留存 GLB](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/hi3d-猫_3.glb>) · [候选检查记录](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:932>)
3. **登记已通过的确切文件。** 用 `workspace_commit_model` 将 `exports/` 下已选定的 `hi3d-` 前缀 GLB 登记到原家族。同主体可继承分类。遇到 `classificationRequired` 时补分类，仍用原候选登记。样例实际以 `name: "猫"` 和 `exportPath: "exports/face-repair/hi3d-cat-face-repaired-final.glb"` 登记为 `hi3d-猫_3.glb`，再按该版本加载。登记工具检查路径和容器，业务拓扑与保留项由前面的验收负责。 [实际登记与加载](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:941>) · [登记 Tool](../tools/workspace-commit-model.md)

## 完成与恢复

| 情况 | 续接与交付条件 |
| --- | --- |
| 本地命令仍在执行 | 用实际返回的 `session_id` 或 `cell_id` 续接原命令或单元。保存脚本、源文件路径、选区依据及计划输出位置。候选交接要等命令终态和回读验收。启动结果不明时先核对原进程和输出。 |
| MDF 等待确认或同步返回 | `waiting_choice` 由宿主交互处理。已提交后沿同一次同步调用等待。桌面 MDF 的工具动作没有远端查询入口，原 3D 生成作业的轮询也不适用于 MDF。 |
| MDF 提交或结果不明 | 保留原 `jobPath`、指纹关联及已知 `requestId`，用现有证据核对服务端。`UNKNOWN` 可能发生在 POST 前，也可能发生在远端处理后，单看状态无法判定是否受理。同作业和指纹重入只读原记录。明确失败并处理原因后，新的重试意图才使用新记录。 |
| 服务成功，下载缺失或异常 | 保留已保存响应，使用同账号、环境、原 `jobPath` 和原 `outputDir` 调 `download`，取回尚未记录下载的结果。仅有存储 key 时保留 key 并核对服务响应。已记录文件缺失或被修改时，`files` 仍可能保留旧路径，脚本通过 `downloadIssues` 报告问题。核对实际路径、摘要与可读性后再验收。 [下载与恢复](../tools/mdf-api.md#实现伪代码) |
| 候选未通过验收 | 保留候选与失败证据，固定原源版本。修订局部选区、操作或服务参数时，建立新候选，重做受影响项的检查。MDF 参数变更属于新的处理意图。正式版本和下游继续引用上一个已验收版本。 |
| 候选通过，登记或加载回执不明 | 核对工作区注册记录、确切文件和摘要。同家族可复用已有版本。遇到 `unchanged: true` 时核对回包、落盘状态及版本摘要与选定候选是否一致。登记成功后保存正式文件名，需展示时用同一版本确认 Studio 就绪。 [版本登记恢复](../tools/workspace-commit-model.md#失败与重入) · [Studio 状态](../infrastructure/workspace/read-studio-state.md) |

## Vet3D 迁移与核查范围

### 供应商无关的实现契约

由宿主固定源版本和摘要，由 LLM 将缺陷、处理区域及必保项整理为结构化意图。诊断、局部修复和整网格重建分别声明可处理范围及可承诺的保留项。部件身份用稳定 ID，几何阈值需有明确单位和参考系。整网格重建接口无法表达有意开口或蒙皮保留时，按任务约束选择可控的局部能力，或由用户决定可接受的变化。作业记录与候选验收分别保存，使同步调用、带任务 ID 的异步调用及本地进程都能用各自的身份续接。

远端适配层分别记录处理回执、候选落盘与几何验收。服务报告完成后可恢复候选取回。候选落盘后用实际文件及摘要开始检查，通过后才登记为新版本。

**Vet3D 设计示例。** 仅修补身体的指定接缝，保留口腔开口、胡须部件与现有蒙皮。字段表示业务语义，由后续适配层映射到选定的实现。

```json
{
  "sourceVersionId": "version-17",
  "operation": "repair-local-defect",
  "scope": {"kind": "region", "partId": "body", "regionId": "seam-04"},
  "defects": ["unintended-open-boundary"],
  "preserve": ["mouth-opening", "independent-whiskers", "uv-seams", "skin-weights"],
  "allowWholeMeshReconstruction": false,
  "expectedResult": {"scope": "seam-04", "boundary": "closed", "delivery": "model-revision"}
}
```

按源摘要、范围、参数和候选摘要保存验收记录，分别记录拓扑指标、保留项证据及未测项。动画交付依据绑定与动作要求额外检查关节层级、权重有效性、必要的关节动作和形变。修复候选通过后交正式登记，后续节点持有版本引用。真实网格的质量标准和恢复能力随供应商选型及实测确定。

### 安装包、运行记录与缺口

- **版本身份。** 当前读取事务目录 `D:/install/Hi3DAgent.__hi3d-transaction/resources/` 的 Windows x64 1.2.11 资源。`app.asar` 的 SHA-256 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`，`runtime.mjs` 的 SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`。 [版本清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>) · [桌面 ASAR](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>) · [Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>)
- **静态与隔离复核。** 随包 MDF 的 7 项离线测试与数组拓扑的 3 项测试均通过。本页的 `watertight` 示例用临时 GLB 复跑通过，返回 2100 秒等待预算，未创建作业记录或输出目录。用已安装脚本和模拟传输复核了源 GLB 经 multipart 提交、成功回执在下载开始前已写盘、补下载不再 POST，以及落盘字节和摘要与模拟回包指定的候选一致。该实验验证客户端执行顺序，服务端候选为测试预置文件。其他隔离试验覆盖 `topology_ok: false` 保留、`UNKNOWN` 防重复提交和 Studio Worker 的缺面、重复面及退化面分支。 [MDF 测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/tests/runtime/test_mdf_api.py>) · [拓扑测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/tests/test_triangle_arrays.py>)
- **实际运行与待实测。** 留存会话验证了局部脚本执行、候选检查及正式版本登记，文件回读验证了样例身体的边闭合。样例对整体连通、自交、打印准备和动画数据保留的覆盖有限。生产部署与随包服务提交的对应关系、桌面确认弹窗、真实 MDF 输出、薄结构及 UV 和蒙皮保留仍待联调。 [样例运行](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:921>)

| 安装包零基 UTF-8 字节锚点 | 核查内容 |
| --- | --- |
| `runtime/dist/runtime.mjs` 的 `2512504`、`2513223`、`2538264`、`3193846` | `mdf_api` 工具声明、参数转换、`runMdf` 和 Runtime 执行分派。 |
| ASAR `out/main/index.js` 的 `212966`、`214629` | 桌面代理允许 `POST /v1/mesh/invoke`，并校验 multipart boundary。 |
| ASAR `out/renderer/assets/index-CDPCug_K.js` 的 `3490808`、`3499865`、`3535100`、`3543919` | 内嵌检测与修复 Worker、本地修复入口、Smart Repair 和配置门。 |
| 同一 renderer 成员的 `1090983`、`4725292`、`3256290` | Studio 工具定义、实际宿主挂载、3MF 组件校验。 |
