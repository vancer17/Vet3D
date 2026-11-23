# mdf_api

## 工具名称与注册来源

`mdf_api` 是 Hi3D Agent 1.2.11（Windows x64）随包 Runtime 注册的工作区动态工具。`thread/start` 将 `Vg` 中的 `Xj` 定义交给随包 Codex 0.166.0。已核查的 `thread/resume` 和 `thread/fork` 不重新注入该定义，工具可用性以当前线程的实际声明为准。工具动作有 `invoke` 和 `download`，`retopology` 等能力通过 `invoke` 的 `capability` 枚举选择。`mdf-api` 是调用指导 Skill。实现脚本 `mdf_api.py` 由 `runMdf` 从当前环境的 `codex-home/skills/buildin/mdf-api/scripts/` 解析并启动，正式请求经桌面宿主的账号代理发出。 [Runtime 工具调用入口](exec.md) · [随包 MDF Skill](../upstream/1.2.11/prebuilt-skills/mdf-api/SKILL.md)

## 暴露给 LLM 的描述

以下为 Runtime 工具定义的 `description` 原文。

```text
Invoke the desktop account mesh API once for mesh processing, auto-rig or image analysis. Read mdf-api skill for capability params. First dryRun, then invoke using the same stable jobPath. Saves response and downloads data.files. UNKNOWN/interrupted jobs must never be resubmitted; download only resumes saved successful results. No query/polling endpoint exists. Commit resulting models with workspace_commit_model.
```

## 参数与结果

| 参数 | 必填与默认值 | 已核查的范围 |
| --- | --- | --- |
| `action` | 必填 | `invoke` 校验或提交，`download` 读取原作业并恢复下载。 |
| `jobPath` | 必填 | 当前工作区内的作业 JSON 路径。`invoke` 要求它与输入文件、输出目录分离，且位于输出目录之外。 |
| `outputDir` | 必填 | 当前工作区内的输出目录。`download` 必须使用作业记录中的原目录。 |
| `capability` | `invoke` 必填 | 下表中的能力枚举。 |
| `file` | `invoke` 必填 | 当前工作区内的单个本地文件。目录、URL、ZIP 和文件列表无法用作输入。 |
| `params` | `invoke` 可选，省略或 `null` 时为 `{}` | 扁平对象，键和值按所选能力检查。 |
| `dryRun` | `invoke` 可选，默认 `false` | 为 `true` 时只做离线校验并返回请求预览。 |

模型可见 schema 将 `action`、`jobPath`、`outputDir` 列为必填，顶层拒绝额外字段。`invoke` 对 `capability` 和 `file` 的必填约束由 Runtime 的 `Qj` 检查，`params` 的能力级白名单由 Python 校验。`download` 的公开调用只传 `action`、`jobPath`、`outputDir`。`Qj` 拒绝附带能力、输入文件、参数对象和 `dryRun: true`，兼容并忽略 `params: null` 和 `dryRun: false`。Runtime 从当前调用上下文取得会话及轮次 ID，有效值写入提交 JSON 及 `X-Session-Id`、`X-Turn-Id` 请求头。

| `capability` | 可选 `params` 与服务文档默认值 |
| --- | --- |
| `remove-background`、`seg`、`normal`、`matting`、`extract-centerline` | 无公开参数。 |
| `unwrap-uv` | `texture_size` 为正整数，默认 `8192`。`need_repair` 为布尔值，默认 `true`，用于展开前的网格处理。此开关与独立水密能力之间的算法关系未核实。 |
| `convert-3mf` | `threemf_mode` 为 `auto`、`standard` 或 `orca`，默认 `auto`。`threemf_target_size_mm` 为非负整数，默认 `100`。 |
| `watertight` | `watertight_resolution` 为不超过 `4096` 的正整数二次幂，默认 `4096`。`target_face_num` 为至少 `-1` 的整数，默认 `5000000`，`0` 或 `-1` 表示跳过减面。`is_fillhole` 为布尔值，默认 `true`。成功响应的文件键为 `watertight_mesh_glb`。 |
| `retopology` | `face` 为正整数，默认 `50000`。`face_type` 为 `triangles` 或 `quads`，默认 `triangles`。`topology_method` 为 `standard` 或 `feature`，默认 `standard`。目标面数允许与实际面数不同。 |
| `mesh-lod` | `target_face_num_list` 为非空、严格降序的正整数数组，默认 `[2000000, 500000, 200000]`。 |
| `auto-rig` | `use_skeleton`、`use_transfer` 为布尔值，分别默认 `false`、`true`。`num_beams` 为 `1` 至 `20` 的整数，默认 `10`。 |
| `pose` | `detect_persons` 为布尔值，默认 `false`。 |
| `pointmap` | `pointmap_smooth` 为布尔值，默认 `true`。 |
| `check-printability` | `require_single_body`、`require_watertight` 为布尔值，均默认 `true`。按服务契约只返回诊断。从 `response.data.result_json` 读取 `topology_ok`，存在 `topology_report` 时按 JSON 字符串解析。 |

图片能力 `remove-background`、`pose`、`seg`、`normal`、`pointmap`、`matting` 接受 PNG、JPEG 或 WebP，最大 40 MiB。`auto-rig` 接受 OBJ、FBX 或 GLB，最大 256 MiB。其余能力接受 GLB，最大 200 MiB。脚本检查文件存在性、工作区归属、非空、扩展名和大小，并校验 GLB 与图片的文件头。上表参数默认值由随包服务文档声明，客户端请求保留实际传入的 `params`。

| 结果 | 结构与副作用 |
| --- | --- |
| Runtime 工具响应 | `{success, contentItems}`。`contentItems` 中的文本承载 `{exitCode, stdout, stderr?}` 的 JSON，`stdout` 是脚本输出的 JSON 文本，`success` 取决于退出码是否为 `0`。工作区、参数或进程派发错误可返回 `success: false`，文本内容为 `{error}`。 |
| 离线校验 | `{dryRun: true, request, file, jobPath, timeoutSeconds}`。脚本读取并校验输入、计算指纹，然后直接返回。该分支不构造 multipart，不登录或提交，也不创建作业记录。 |
| 作业摘要 | `{status, jobPath, requestId, response, files, lods, downloadIssues, message}`。`response` 是脱敏的服务回包，`files` 是已记录的结果键到本地路径的映射，`requestId` 和 `lods` 可为 `null`。正式调用保存本地记录，成功后从宿主私有缓存读取原始下载信息并将文件写入 `outputDir`。 |
| 失败、诊断与下载异常 | 脚本以退出码 `2` 表示非成功作业或异常。结构化异常包含 `error`，并附 `code` 或 `type`。服务成功时，退出码 `0` 和 `SUCCEEDED` 可以与 `topology_ok: false` 或非空 `downloadIssues` 同时出现。 |

正式 `invoke` 携带所选能力及源文件，由服务处理。`watertight` 在同步请求内执行水密处理并返回候选 GLB 的文件描述。客户端下载使用 `data.files` 中的 URL，保存为 `hi3d-<结果键><扩展名>`。首次取回 `watertight` 的 GLB 后，`files.watertight_mesh_glb` 指向本地 `hi3d-watertight_mesh_glb.glb`。脚本支持 GLB、3MF、PNG、JPEG、WebP 和 NPZ，另有 `retopology` 的 OBJ ZIP 分支。记录下载结果时将文件路径和摘要写入本地账本。`check-printability` 和 `extract-centerline` 可以只返回数据。 [公开能力与结果契约](../upstream/1.2.11/prebuilt-skills/mdf-api/references/mesh-invoke-api.md)

### `retopology` 的输入与产物

`invoke` 传 `capability: "retopology"`，接收当前工作区内单个非空、至多 200 MiB 的 GLB v2。客户端校验容器头和文件长度，网格顶点数和面数各 600 万的上限来自随包服务契约。`params` 仅接受正整数 `face`、`face_type`（`triangles` 或 `quads`）和 `topology_method`（`standard` 或 `feature`）。省略项由服务按公开默认值处理。`face` 是目标面数，验收时读取实际产物。额外字段如 `edge_chains`、布尔值 `face` 和内部 Geo 调用方资料中的 `pamo` 均会被公开参数校验拒绝。客户端独立检查两个枚举，`quads + feature` 能通过离线预检。服务契约只声明 `feature` 对 `triangles` 生效，该组合的生产行为待实测。 [公开重拓扑契约](../upstream/1.2.11/prebuilt-skills/mdf-api/references/mesh-invoke-api.md#35-重拓扑retopology) · [客户端校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:21>) · [内部 Geo 调用方资料](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-service-select/references/mdf/retopology-V2-0.md:15>)

| 回包位置 | 内容与验证范围 |
| --- | --- |
| `response.data` | 服务结果键 `model_glb`、`model_obj`，以及 `face_topology`、`vertices_topology` 等结果统计。`num_faces`、`num_vertices` 描述输入。`response` 在本地回包及账本中按脱敏规则保存。 |
| 原始 `data.files` | 下载器从宿主私有缓存读取各结果的描述对象，使用其 `url` 下载。顶层结果键可留作核对服务产物的依据。 |
| `files.model_glb`、`files.model_obj` | 下载后登记的本地路径，通常为 `hi3d-model_glb.glb` 和 `hi3d-model_obj.zip`。GLB 检查容器头和文件长度。只有 `retopology` 的 `model_obj` 与 `.zip` 后缀组合才进入 OBJ ZIP 分支，校验限于 `zipfile.is_zipfile`。 |

请求四边面时，读取实际 ZIP 内的 OBJ 并检查原生面连接。工具 `SUCCEEDED` 表示本地已记录同步服务的成功回包。若只收到 GLB 描述，`downloadIssues` 可以为空。只含文本的合法 ZIP 也会通过容器校验。需要提交可用文件时，同时核实文件内容、记录摘要与 `downloadIssues`。原账本中缺少 OBJ 下载描述时，保留可得的结果键交服务侧核对。存在该描述但尚未记入下载清单时，按原成功记录续取。已记录 ZIP 删除或变更时，`files.model_obj` 仍可能保留原路径，并伴随 `saved artifact changed or missing`。具体恢复条件见[实现伪代码](#实现伪代码)。单独展 UV 按 `unwrap-uv` 契约处理。逐档减面、展 UV 和法线烘焙由 `mesh-lod` 定义，结果按[档位契约](#mesh-lod-的档位与结果)读取。 [下载与摘要实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:114>) · [GLB 容器校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/hi3d_artifacts.py:26>)

工作区版本由 `workspace_commit_model` 登记。MDF 的 `requestId` 用于服务端排查和日志关联。Runtime 的可信生成来源读取要求作业记录含 `backend: "hi3d-codex-v1"` 与 `state: "success"`，而 MDF 记录使用自己的 `status` 和响应。因此 MDF 结果走本地导出登记路径，`requestId` 不会被转换为 Hi3D 生成 `taskId` 或免费重试来源。 [版本登记](workspace-commit-model.md) · [生成重试来源要求](model-retry-prepare.md#参数与结果)

### `mesh-lod` 的档位与结果

`target_face_num_list` 表示预期档位。成功响应的 `data.mesh_lod_glbs` 将正整数目标面数的字符串映射到响应字段名。安装包解析器从该字段的 `data.files[field].key` 读取存储键，缺失时尝试同名顶层值，并检验 `.glb` 后缀。下载描述仍取 `data.files[field]`。工具将档位按目标面数数值降序整理为 `lods`，其中 `targetFaces` 给出目标面数，`field` 与 `key` 分别是响应字段和存储键。`actualFaces` 取服务元数据，缺失时为 `null`。本地路径在 `files[field]` 中。 [档位解析实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:97>) · [动态结果契约](../upstream/1.2.11/prebuilt-skills/mdf-api/references/mesh-invoke-api.md#5-lod-动态结果解析)

服务回包为 `SUCCEEDED` 时，缺档、映射无效或下载不完整仍可在 `downloadIssues` 中留下诊断。档位标识、实际下载文件及其内容应分别核对。恢复仍使用同一 `jobPath`、`outputDir` 和原始服务回包。实际面数、贴图、模型属性及档位质量依赖产物验证。

### `auto-rig` 的输入与产物

`invoke` 接收工作区内单个非空 OBJ、FBX 或 GLB 文件，大小最多 256 MiB。路径必须解析到当前工作区，GLB 还会校验 `glTF` 魔数、版本 2、头内长度与实际文件长度一致且至少 20 字节。客户端未解析 GLB 的 JSON/BIN 块或网格、骨架、姿态和材质内容。OBJ 和 FBX 经过路径、扩展名与大小检查。单次请求只上传指定文件的字节，需要随模型提供材质时可选用自包含 GLB。 [公开自动绑定契约](../upstream/1.2.11/prebuilt-skills/mdf-api/references/mesh-invoke-api.md#37-自动绑定auto-rig) · [客户端输入校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:45>) · [GLB 头部校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/hi3d_artifacts.py:26>)

| 可选参数 | 服务文档默认值 | 公开语义 |
| --- | --- | --- |
| `use_skeleton` | `false` | 布尔值。为 `true` 时请求用输入中的已有骨架预测蒙皮。骨名和层级的精确保留没有服务承诺。 |
| `use_transfer` | `true` | 布尔值。为 `true` 时请求把预测绑定转移回上传的网格以保留材质和尺度，逐顶点及拓扑对应仍需验收。 |
| `num_beams` | `10` | 整数 `1` 至 `20`。字符串、浮点和布尔值会被参数校验拒绝。 |

客户端保留显式传入的参数，省略项留给服务处理。`params` 是扁平对象，包装键 `options`、未公开参数 `seed` 等均会被拒绝。`dryRun: true` 在本地计算输入摘要与请求指纹并返回 `{dryRun, request, file, jobPath, timeoutSeconds: 2100}`。预览没有返回摘要、指纹或 `outputDir`，也不生成 multipart、鉴权、上传或落盘账本。随包契约给出服务器算法超时 1800 秒，客户端 HTTP 和 Runtime 等待预算见[宿主确认与执行预算](#宿主确认与执行预算)。 [公开参数校验](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:21>) · [预检与提交实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:180>) · [输入与选项语义](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-service-select/references/mdf/auto-rig.md:18>)

| 回包位置 | 内容与验证范围 |
| --- | --- |
| `response.data.rigged_mesh` | 脱敏服务回包中的结果字段。公开契约将其定义为带骨架与蒙皮的 GLB 结果。 |
| 原始 `data.files.rigged_mesh` | 预期的下载描述 `{key, url}`。下载器遍历宿主私有缓存中原回包的 `data.files`，并使用适用描述中的 `url`。服务仅提供结果字段时，客户端缺少可供下载的描述。 |
| 工具 `files.rigged_mesh` | 下载并记入账本后返回本地路径。使用 `.glb` 后缀时命名为 `hi3d-rigged_mesh.glb`，校验容器头并记录 SHA-256。仍需读取实际模型确认骨架、蒙皮、尺度和材质。 |

`SUCCEEDED` 表示同步回包已录为成功，本地可能尚无 `files.rigged_mesh`，或伴随 `downloadIssues`。下载描述存在且该结果尚未记入账本时，可在同一账号、环境及原 `jobPath`、`outputDir` 下用 `download` 恢复。已记录文件缺失或摘要变化时，下载器保留原路径并报告异常。同步调用中断或 `UNKNOWN` 时保留原作业及已取得的 `requestId`，公开工具只有 `invoke` 与 `download`。恢复细节见[实现伪代码](#实现伪代码)。 [公开回包与下载契约](../upstream/1.2.11/prebuilt-skills/mdf-api/references/mesh-invoke-api.md#4-通用响应与下载) · [下载实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:114>)

骨架与蒙皮的实际内容可通过本地 Blender 读取，已有工程可用 `rig_adapter inspect` 盘点骨架，已关联身体与骨架可按实际帧段使用 `service_rig inspect` 取得权重及形变报告。文件身份、骨架结构和所查姿势范围分别随结果记录。 [已有骨架脚本](../resources/specialized-mesh-scripts.md#rig_adapter-已有骨架检查与调整) · [单身体蒙皮脚本](../resources/specialized-mesh-scripts.md#service_rig-inspect-单身体蒙皮检查)

## 宿主确认与执行预算

随包 Skill 指导先 `dryRun`，正式提交由宿主通过 `waiting_choice` 确认，Agent 不另行调用 `user_interaction` 申请同一授权。1.2.11 已定位的自动生成参数面板分支要求已解析的 `hi3d_api` 参数，`mdf_api` 走独立的脚本分派。MDF 实际登录会话中的宿主确认和扣费接线仍待实测。 [随包 MDF Skill](../upstream/1.2.11/prebuilt-skills/mdf-api/SKILL.md) · [Runtime 分派定位](#核查依据)

正式提交使用同步 `POST /v1/mesh/invoke`。调用把 `request` JSON 和一个名为 `file` 的二进制部分放入 `multipart/form-data`，上传文件名由输入后缀生成，例如 `input.glb`。组包重新核对字节哈希。普通能力的 Python POST 等待预算为 2100 秒，`mesh-lod` 为 7500 秒，预检的 `timeoutSeconds` 返回这层预算。`Qj` 的 Runtime 进程外层预算分别为 2700 秒和 8100 秒。`download` 不带能力，适用普通外层预算。 [POST 组包](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:70>) · [公开请求与响应契约](../upstream/1.2.11/prebuilt-skills/mdf-api/references/mesh-invoke-api.md)

## 实现伪代码

以下伪代码对应 Runtime 参数检查与脚本 `execute`、`download` 的主要分支。API 在同一次 HTTP 调用中返回状态，客户端没有远端查询或轮询动作。一次提交的本地身份由稳定的 `jobPath`、账号与环境，以及能力、参数、输入内容哈希和输出目录构成的请求指纹共同约束。回包中的 `requestId` 用于关联服务记录。

```python
def mdf_api(call, context):
    args = validate_runtime_schema_and_workspace(call, context)

    if args.action == "download":
        record = load_record(args.job_path)
        require_current_account_environment_and_output(record, args, context)
        return resume_saved_result(record)

    file = validate_input(args.capability, args.params, args.file)
    require_separate_record_path(args.job_path, file, args.output_dir)
    request = build_request(args.capability, args.params, context)
    file_hash = sha256(file)
    fingerprint = hash_request(args.capability, args.params, file_hash, args.output_dir)
    timeout = 7500 if args.capability == "mesh-lod" else 2100
    if args.dry_run:
        return offline_preview(request, file, args.job_path, timeout)

    account = authenticate_through_desktop_proxy(context)
    if record_exists(args.job_path):
        record = load_record(args.job_path)
        require_account_environment_and_fingerprint(record, account, fingerprint)
        return resume_saved_result(record)

    require_private_cache(account, args.job_path)
    record = reserve_record_exclusively(args, account, fingerprint, status="UNKNOWN")
    try:
        multipart = encode_multipart(request, file, expected_sha256=file_hash)
        http_status, response = post_once("/mesh/invoke", multipart, timeout)
        persist_private_response_and_public_summary(record, response)
        record.status = classify_response(http_status, response)
        save(record)
    except Exception:
        record.status = "UNKNOWN"
        save(record)
        return summarize(record)
    return resume_saved_result(record)


def resume_saved_result(record):
    if record.status != "SUCCEEDED":
        return summarize(record)
    for asset in load_saved_file_descriptors(record):
        if already_recorded(record, asset):
            verify_existing_file_or_report_issue(record, asset)
        else:
            download_validate_and_record_or_report_issue(record, asset)
    return summarize(record)
```

HTTP 200、整数 `code: 0` 与业务 `status: "SUCCEEDED"` 同时成立才进入成功分支。明确返回的 `FAILED`、`REJECTED` 或 `UNKNOWN` 会保留。其余结果及占位后出现的提交异常归为 `UNKNOWN`。因为脚本在组包和 POST 之前写入占位，`UNKNOWN` 既可能出现在请求发送前，也可能出现在服务已受理但没有可用回包时。

中断或结果不明时，保留原 `jobPath` 与已取得的 `requestId` 供服务侧核对。`requestId` 没有公开查询接口。原工具调用仍由 Code Mode 单元持有时，可用 `cell_id` 续读同一单元。再次调用时，`download` 使用原 `jobPath` 与 `outputDir`。匹配原指纹的 `invoke` 也进入恢复分支，指纹不匹配则报错并保留原记录。已确认失败时，先处理原因，再为明确的新重试意图创建新记录。 [wait](wait.md)

已有成功记录才会恢复尚未写入下载清单的文件。恢复读取宿主私有缓存里原响应的 URL，不会刷新下载签名。已记录文件只核对路径、存在性与哈希，异常时保留原下载清单并在 `downloadIssues` 报告 `saved artifact changed or missing`。此时 `files` 仍可能含旧路径，再调 `download` 也不会重下该结果键。确认产物可用时需同时核对 `downloadIssues`、实际文件和记录摘要。URL 缺失时保留存储 key，向服务侧核对。 [下载与摘要实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py:114>)

## 调用示例

**根据已核查 schema 重建的工具参数。** 对工作区内 `assets/sample.glb` 离线校验水密请求，`target_face_num: 0` 表示跳过减面。

```json
{
  "action": "invoke",
  "capability": "watertight",
  "file": "assets/sample.glb",
  "params": {
    "watertight_resolution": 1024,
    "target_face_num": 0,
    "is_fillhole": true
  },
  "jobPath": ".hi3d/mdf/sample-watertight.json",
  "outputDir": "exports/sample-watertight",
  "dryRun": true
}
```

确认同一意图的参数后，正式调用将 `dryRun` 改为 `false`。服务结果已成功保存后，可以按下例恢复该作业的下载。

```json
{
  "action": "download",
  "jobPath": ".hi3d/mdf/sample-watertight.json",
  "outputDir": "exports/sample-watertight"
}
```

**根据已核查 schema 重建的只读调用示例。** 此预检以多个实体可接受、水密仍为检测目标为例。

```json
{
  "action": "invoke",
  "capability": "check-printability",
  "file": "assets/sample.glb",
  "params": {
    "require_single_body": false,
    "require_watertight": true
  },
  "jobPath": ".hi3d/mdf/sample-check.json",
  "outputDir": "exports/sample-check",
  "dryRun": true
}
```

**根据已核查 schema 重建的重拓扑离线预检。** 以工作区内的样例 GLB 为输入，请求原生四边面候选。`face` 表示目标面数，返回的 `request` 是提交预览。

```json
{
  "action": "invoke",
  "capability": "retopology",
  "file": "assets/sample.glb",
  "params": {
    "face": 20000,
    "face_type": "quads",
    "topology_method": "standard"
  },
  "jobPath": ".hi3d/mdf/sample-retopology.json",
  "outputDir": "exports/sample-retopology",
  "dryRun": true
}
```

**根据已核查 schema 重建的工具参数。** 对工作区内 `assets/sample.glb` 离线校验 UV 展开请求。

```json
{
  "action": "invoke",
  "capability": "unwrap-uv",
  "file": "assets/sample.glb",
  "params": {
    "texture_size": 4096,
    "need_repair": true
  },
  "jobPath": ".hi3d/mdf/sample-uv.json",
  "outputDir": "outputs/sample-uv",
  "dryRun": true
}
```

**根据已核查 schema 重建的自动绑定离线预检。** 输入为工作区内的样例 GLB，返回请求和执行预算预览。

```json
{
  "action": "invoke",
  "capability": "auto-rig",
  "file": "assets/sample.glb",
  "params": {
    "use_skeleton": false,
    "use_transfer": true,
    "num_beams": 10
  },
  "jobPath": ".hi3d/mdf/sample-rig.json",
  "outputDir": "outputs/sample-rig",
  "dryRun": true
}
```

## 核查依据

- 核查使用 Hi3D Agent 1.2.11（Windows x64）留存包。`runtime/dist/runtime.mjs` 的 SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`。原文件零基字节偏移 `2512000` 为 `qre` 参数校验，`2512504` 为 `Xj` 定义，`2513223` 为 `Qj` 参数转换和外层超时，`2538264` 为 `runMdf`，`2671153` 为 `Vg`，`3156315` 附近为新建线程合并。 [原始 Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>)
- 同一 Runtime 文件中，`3193800` 附近为 MDF 分派，`3195660` 附近为生成参数面板条件，`3196610` 附近将进程结果和退出状态交给 `ge`。`ge` 位于 `2108731`，负责构造 `{success, contentItems}`。`2693701` 为可信生成下载来源处理。
- 桌面代理见 `app.asar` 成员 `out/main/index.js`。成员内零基字节偏移 `212966` 为代理路径白名单，`214629` 为 multipart 校验。`app.asar` 的 SHA-256 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`。 [桌面 ASAR](<D:/install/Hi3DAgent.__hi3d-transaction/resources/app.asar>)
- `runMdf` 通过 `r$` 解析已安装 Skill 的脚本路径。`r$` 位于 `runtime.mjs` 原文件零基字节偏移 `2462032`，会检查 Skill 的管理标记。本机 `prod` 环境的已安装脚本与预置脚本 SHA-256 一致，均为 `5042920c95a891987f81e9e8cc53f96e81c936f54989cbff94f90af1fc35ef05`。本地校验、占位、回包判定和恢复分别见脚本的 `validate`、`multipart`、`execute` 和 `download`。鉴权和作业归属校验来自同目录的 `hi3d_client.py`，存储与脱敏来自 `hi3d_storage.py`。 [已安装脚本](<D:/download/.sparc3d-runtime/environments/prod/codex-home/skills/buildin/mdf-api/scripts/mdf_api.py>) · [预置脚本](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py>)
- 能力默认值见 `runtime/prebuilt-skills/mdf-api/references/mesh-invoke-api.md`，SHA-256 为 `fd5233d32594fb95df308055a1d319023466c268f1b6e8266ccdf00e4a1dd2b6`。同一 Skill 的 `SKILL.md` 指导离线校验后复用同一作业路径进行正式调用。
- **离线核查。** 随包 `tests/runtime/test_mdf_api.py` 的七项测试通过，覆盖参数和文件校验、multipart 组包、同一作业下载恢复及不明提交留存。水密、可打印性检查和重拓扑示例离线返回请求预览，未创建账本或输出目录。隔离响应夹具另确认 `topology_ok: false` 与服务成功可以并存。 [随包测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/tests/runtime/test_mdf_api.py>)
- **重拓扑隔离复核。** 用临时 GLB 验证 `quads + feature` 通过预检，`pamo`、布尔或零 `face`、单数 `quad` 和额外的 `edge_chains` 被拒绝。替身传输复现首次只有 GLB 下载完成、随后从同一成功账本补取只含文本的合法 ZIP。删除已记录的 ZIP 后，再恢复时回包同时保留原路径和 `saved artifact changed or missing`。全程只发生一次替身 POST。证据覆盖客户端校验、下载和恢复。 [参数与下载源码](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/scripts/mdf_api.py>)
- **自动绑定离线复核。** 随包 Blender 回归生成的合成 GLB 可通过 `auto-rig` 预检。客户端也接受只有合法文件头及填充字节的 20 字节 GLB，并拒绝 GLB 版本 1、布尔值 `num_beams` 与未公开的 `seed`。离线命令返回请求预览，未创建账本或输出目录。替身传输复现了只有结果键时成功回包中没有本地文件，以及有文件描述但下载中断后按原账本补取并记录路径。补取期间未再次 POST。修改已记录文件后，工具报告摘要异常并保留原记录。`mdf-api/package.json` 固定 `mdf_api.py` 及其直接导入的 `hi3d_client.py`、`hi3d_storage.py` 和 `hi3d_artifacts.py` 的物化来源。预检执行路径、摘要与容器头校验，客户端鉴权在正式调用分支。 [安装包物化映射](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/mdf-api/package.json:15>) · [合成 GLB 回归](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rig-retarget/scripts/rigging/test_service_rig.py:14>)
- **待实测。** 真实账号下的宿主确认与扣费，生产服务对各参数组合的行为，实际下载结果及 OBJ 的兼容性，重建结果的原生面型、边流、外观和属性保留，以及云端返回 GLB 的骨架、蒙皮和真实四足资产的形变质量。离线预检和下载器验证的证据范围在客户端。
