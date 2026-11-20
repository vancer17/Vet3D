# 网格与图像处理接口：POST /v1/mesh/invoke

面向前端、客户端及服务调用方，覆盖当前代码实现的全部 **14 项能力**。本文包含 mesh-lod、auto-rig；目标环境需部署相应版本后才能使用，不代表全部算法已完成线上联调。

## 1. 接口与鉴权

| 项目 | 说明 |
|---|---|
| 方法 | `POST` |
| 路径 | `/v1/mesh/invoke` |
| 服务地址 | `https://agent.hi3d.ai`，其他环境替换为对应服务域名 |
| 请求类型 | `multipart/form-data` |
| 登录鉴权 | 携带有效 C 端登录 Cookie：`MM_AIGC=<登录凭据>` |
| 响应类型 | `application/json` |
| 执行方式 | 同步等待结果，无提交后轮询接口 |

所有能力都需要登录。缺失或过期的登录态会被拒绝，不派发算法。不要把 Cookie 写入代码、共享文档或日志。

## 2. 请求格式

请求由两个 multipart part 组成，不是直接提交 JSON，也不是直接提交 TOS key。

| Part | 必填 | 类型 | 说明 |
|---|---|---|---|
| `request` | 是 | `application/json` | 能力名、业务参数和可选关联 ID |
| `file` | 是 | 二进制文件 | 一个本地图片或模型，保留正确的文件扩展名 |

`request` 对象：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `capability` | string | 是 | 下文定义的能力名，区分大小写 |
| `params` | object | 否 | 仅允许对应能力的公开参数；省略、null 或 `{}` 使用默认值 |
| `sessionId` | string | 否 | 业务会话 ID，用于调用记录关联 |
| `turnId` | string | 否 | 业务轮次 ID，用于同一轮调用关联 |

ID 允许 `[A-Za-z0-9_.:-]`，长度1–128；也可通过 `X-Session-Id`、`X-Turn-Id` 传入。正文非空值优先，否则使用请求头。没有真实关联 ID 时省略，不用登录 session 代替。ID 不提供请求去重或幂等保证。

只开放下文列出的 `params` 字段。不要提交 `target_service`、`assets`、`func`、`task`、`timeout_sec`、`return_fields` 或嵌套 `options`；这些由服务端组装。参数类型错误、未知参数会在调用算法前被拒绝。

### 文件限制

| 能力类型 | 格式 | 单文件上限 |
|---|---|---|
| 去背景及人体分析 | PNG / JPEG / WebP | 40 MiB |
| 普通网格处理、LOD、PCG | GLB | 200 MiB |
| auto-rig | OBJ / FBX / GLB | 256 MiB |

仅支持一个文件，不上传 ZIP、文件列表或外部依赖。OBJ/FBX 的外部材质与贴图不会一并上传；需要保留材质时优先选择自包含 GLB。图片及 GLB 校验文件头，OBJ/FBX 的模型结构由算法校验。反向代理还需允许对应请求体大小。

### cURL 示例

以下为 Bash 示例，`MM_AIGC` 由调用者在本机安全设置；示例没有真实凭据。`request` part 必须声明 `application/json`。

Runtime 使用 `mdf_api` 的结构化参数调用；登录态由宿主处理，本参考不提供 Agent shell 的鉴权示例。


换能力时替换 `request` JSON 和文件即可。**mesh-lod 将 `--max-time` 改为7500**。不要启用自动重试或跟随重定向。

## 3. 全部能力与参数

本节每个 JSON 都是 multipart 中的 `request` 内容；表中默认值由服务端补齐。

### 3.1 去背景：remove-background

- 输入：图片。无公开参数。
- 输出：`data.image`，去背景 PNG 的 TOS key。

```json
{"capability":"remove-background","params":{}}
```

### 3.2 展 UV：unwrap-uv

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `texture_size` | integer | 8192 | 正整数，目标贴图分辨率；算法支持的规格以部署版本为准 |
| `need_repair` | boolean | true | 是否先修复网格再展开 |

输入 GLB，输出 `data.uv_mesh_glb`。可能附带顶点数、面数、UV 面积比例、修复状态等字段。

```json
{"capability":"unwrap-uv","params":{"texture_size":8192,"need_repair":true}}
```

### 3.3 转 3MF：convert-3mf

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `threemf_mode` | string | auto | `auto` / `standard` / `orca`；Orca/Bambu 切片场景用 `orca` |
| `threemf_target_size_mm` | integer | 100 | 非负数；最长边目标毫米数，0关闭定尺 |

输入 GLB，输出 `data["3mf"]`。

```json
{"capability":"convert-3mf","params":{"threemf_mode":"orca","threemf_target_size_mm":100}}
```

### 3.4 水密处理：watertight

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `watertight_resolution` | integer | 4096 | 正的2次幂，最大4096 |
| `target_face_num` | integer | 5000000 | 大于等于-1；0或-1表示不减面 |
| `is_fillhole` | boolean | true | 是否补洞 |

输入 GLB，输出 `data.watertight_mesh_glb`。水密处理可能改变细薄结构，结果需按用途检查。

```json
{"capability":"watertight","params":{"watertight_resolution":4096,"target_face_num":5000000,"is_fillhole":true}}
```

### 3.5 重拓扑：retopology

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `face` | integer | 50000 | 正整数，目标面数 |
| `face_type` | string | triangles | `triangles` / `quads` |
| `topology_method` | string | standard | `standard` / `feature`；feature仅在triangles时生效 |

输入 GLB，输出 `data.model_glb`，同时提供 `data.model_obj`（OBJ ZIP key）及 `data.files.model_obj.key/url`（完整下载地址）。四边面消费者应下载 OBJ ZIP 以保留原生面连接；请求参数及鉴权不变。客户端保存 ZIP，不自动解压；新增格式不意味着服务包含烘焙。算法还会限制输入顶点/面数（文档上限600万），文件大小以本接口200 MiB为准。
返回的 `face_topology`、`vertices_topology` 是重拓扑结果；`num_faces`、`num_vertices` 是输入网格统计。目标面数不保证精确达到。

```json
{"capability":"retopology","params":{"face":50000,"face_type":"triangles","topology_method":"standard"}}
```

### 3.6 LOD 减面烘焙：mesh-lod

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `target_face_num_list` | integer[] | [2000000,500000,200000] | 非空、正整数、严格从大到小，不重复；允许单档 |

输入 GLB。逐档减面、展 UV、烘焙法线；输入有 baseColorTexture 时可携带颜色/PBR。算法超时7200秒。

```json
{"capability":"mesh-lod","params":{"target_face_num_list":[500000,200000]}}
```

输出字段是动态的，具体解析见第5节：

- `data.mesh_lod_glbs`：目标面数字符串 → 顶层文件字段名。
- `data.mesh_lod_glbs_<N>`：对应档位 GLB 的 TOS key。
- `data.mesh_lod_metadata`：上游提供时返回，含各档实际面数等信息。

### 3.7 自动绑定：auto-rig

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `use_skeleton` | boolean | false | true使用模型已有骨架，仅预测蒙皮 |
| `use_transfer` | boolean | true | 保留原材质与尺度 |
| `num_beams` | integer | 10 | beam数量，本接口允许1–20 |

输入 OBJ/FBX/GLB，输出 `data.rigged_mesh`，带骨架与蒙皮的 GLB。算法超时1800秒。
这里的 `params` 是扁平对象；服务端负责转成中控需要的 `params.options`。

```json
{"capability":"auto-rig","params":{"use_skeleton":false,"use_transfer":true,"num_beams":10}}
```

上游提供时返回 `data.metadata`：`joints`（关节数）、`skins`（蒙皮数）、`skinned_primitives`（蒙皮图元数）、`vertices`（顶点数）、`elapsed_seconds`（算法耗时秒）。不生成动画，仍需检查骨架及动作变形。

### 3.8 人体关键点：pose

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `detect_persons` | boolean | false | 是否先做人检测；已裁剪的人像通常用false |

输入图片，输出 `data.pose_data`（NPZ）及 `data.pose_visualization`（PNG）。
NPZ 包含 `keypoints[N,308,2]`、`scores[N,308]`、`bboxes[N,4]`；坐标为原图像素，N为人数，未检测到人时可以为0。

```json
{"capability":"pose","params":{"detect_persons":false}}
```

### 3.9 人体分割：seg

输入图片，无公开参数。输出 `data.seg_data`（NPZ）及 `data.seg_visualization`（PNG）。NPZ 的 `labels[H,W]` 为uint8，共29类，0为背景。

```json
{"capability":"seg","params":{}}
```

### 3.10 人体法线：normal

输入图片，无公开参数。输出 `data.normal_data`（NPZ）及 `data.normal_visualization`（PNG）。NPZ 的 `normals[H,W,3]` 为float32相机坐标法线，不是模型世界坐标或切线空间法线贴图。

```json
{"capability":"normal","params":{}}
```

### 3.11 点图/深度：pointmap

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `pointmap_smooth` | boolean | true | 放大时是否平滑 |

输入图片，输出 `data.pointmap_data`（NPZ）及 `data.pointmap_visualization`（PNG）。NPZ 包含 `pointmap[H,W,3]`、`depth[H,W]`、`scale[1,1]`。相机坐标、米制估计，不能直接作为 GLB 世界坐标。

```json
{"capability":"pointmap","params":{"pointmap_smooth":true}}
```

### 3.12 人像抠像：matting

输入图片，无公开参数。输出 `data.matting_data`（NPZ）及 `data.matting_visualization`（PNG）。NPZ 包含 `alpha[H,W]`、`foreground_premultiplied[H,W,3]`，值域[0,1]；前景已预乘alpha，不要再次相乘。

```json
{"capability":"matting","params":{}}
```

### 3.13 抽中心线：extract-centerline

输入 GLB，无公开参数。输出 `data.result_json.centerline`，包含 `points`、`edges`、`radii`、`branches`、`pointCount`、`edgeCount`、`branchCount` 等结构化数据。
本能力不返回可下载模型，`data.files` 为空对象。

```json
{"capability":"extract-centerline","params":{}}
```

### 3.14 可打印性检测：check-printability

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `require_single_body` | boolean | true | 要求恰好一个实体 |
| `require_watertight` | boolean | true | 要求水密，并检查绕序/法线、正体积、退化面等 |

输入 GLB，输出 `data.result_json.topology_ok`，及上游提供的 `topology_report`（**JSON字符串**，需要时再解析）。不修改模型，也不返回下载文件。

```json
{"capability":"check-printability","params":{"require_single_body":true,"require_watertight":true}}
```

`topology_ok=false` 表示检测不通过，但接口仍可返回 `code=0`、`status=SUCCEEDED`，因为检测调用本身成功。

## 4. 通用响应与下载

成功示例：

```json
{
  "requestId": "example-request-id",
  "code": 0,
  "msg": "success",
  "status": "SUCCEEDED",
  "durationMs": 1387,
  "data": {
    "image": "jjewelry/ainode/model3d/general/example-request-id/image.png",
    "files": {
      "image": {
        "key": "jjewelry/ainode/model3d/general/example-request-id/image.png",
        "url": "https://hitem3dstatic.zaohaowu.net/jjewelry/ainode/model3d/general/example-request-id/image.png"
      }
    }
  }
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `requestId` | string | 服务端调用ID，用于排查及日志关联；不等同3D jobId或2D taskId |
| `code` | integer | 本接口成功为0；不要套用其他生成接口的成功码200 |
| `msg` | string | 简短说明 |
| `status` | string | SUCCEEDED / FAILED / UNKNOWN / REJECTED |
| `durationMs` | number | 服务处理耗时毫秒，不包含客户端下载文件的耗时 |
| `data` | object | 能力对应的文件key、结构化结果与可选统计 |
| `data.files` | object | 输出字段名 → `{key,url}`；无文件能力为空对象 |
| `downloadUnavailable` | boolean，可选 | 有结果，但下载URL构造失败；保留key并联系服务端，不重跑算法 |
| `recordingIncomplete` | boolean，可选 | 结束记录写入失败，已得到的业务结果仍可使用 |
| `error` | string，可选 | 部分失败响应提供机器可读原因，不能假设所有错误都有此字段 |

成功请求还返回 `X-Request-Id` 响应头；进入调用编排的失败响应也会携带。鉴权、multipart解析等前置失败可能不具备上述完整结构，应先检查HTTP状态。

固定文件按结果字段读取，例如 `data.files.uv_mesh_glb.url`、`data.files.rigged_mesh.url`、`data.files["3mf"].url`。
`data.image` 等字段是 TOS key，不是完整URL。优先直接使用服务返回的 `url`；域名按部署环境配置，不在客户端写死，不向CDN附加登录Cookie。
当前 mesh URL 为 CDN 公网地址，没有TOS一小时预签名参数。URL不代表文件永久保留，客户端需要时下载保存。

## 5. LOD 动态结果解析

请求 `[500000,200000]` 时，`data` 示例：

```json
{
  "mesh_lod_glbs": {
    "500000": "mesh_lod_glbs_500000",
    "200000": "mesh_lod_glbs_200000"
  },
  "mesh_lod_glbs_500000": "jjewelry/ainode/model3d/general/example-request-id/input_50w.glb",
  "mesh_lod_glbs_200000": "jjewelry/ainode/model3d/general/example-request-id/input_20w.glb",
  "mesh_lod_metadata": {
    "500000": {"requested_faces":500000,"actual_faces":499980,"size_bytes":8000000},
    "200000": {"requested_faces":200000,"actual_faces":199950,"size_bytes":7600000}
  },
  "files": {
    "mesh_lod_glbs_500000": {
      "key":"jjewelry/ainode/model3d/general/example-request-id/input_50w.glb",
      "url":"https://hitem3dstatic.zaohaowu.net/jjewelry/ainode/model3d/general/example-request-id/input_50w.glb"
    },
    "mesh_lod_glbs_200000": {
      "key":"jjewelry/ainode/model3d/general/example-request-id/input_20w.glb",
      "url":"https://hitem3dstatic.zaohaowu.net/jjewelry/ainode/model3d/general/example-request-id/input_20w.glb"
    }
  }
}
```

JavaScript解析示例（在确认响应成功后执行）：

```javascript
const lods = Object.entries(response.data.mesh_lod_glbs).map(([target, field]) => {
  const asset = response.data.files?.[field];
  return {
    targetFaces: Number(target),
    actualFaces: response.data.mesh_lod_metadata?.[target]?.actual_faces ?? null,
    key: asset?.key ?? response.data[field],
    url: asset?.url ?? null
  };
}).sort((a, b) => b.targetFaces - a.targetFaces);
// url为null时处理下载不可用，不重新提交算法。
```

不要把 `mesh_lod_glbs` 中的值当作URL或key，它是**字段名指针**；不要写死默认三档，也不要依赖JSON对象的枚举顺序。实际面数以元数据为准。缺档、无效指针或非GLB输出会被服务端判为异常结果。

## 6. 状态、失败与超时

| 情况 | HTTP / 状态 | 调用方处理 |
|---|---|---|
| 正常完成 | 200，code=0，SUCCEEDED | 获取结构化结果或下载文件；按业务检查质量 |
| 非法参数/文件 | 400，通常REJECTED | 修改请求；未提交算法 |
| 登录无效 | 鉴权拒绝，常见401 | 更新登录态；认证错误结构以统一鉴权层为准 |
| 无空闲算力 | 429，FAILED，algorithm_busy | 尚未派发；稍后显式重试，避免高频循环 |
| 配置缺失/容量查询失败 | 503，FAILED | 排查配置与中控/CLB；未派发 |
| 初始调用记录写入失败 | 503，FAILED，recording_unavailable | 未派发，联系服务端排查数据库 |
| 上传失败 | 502，FAILED | 未派发，排查上传链路 |
| 算法明确失败 | 502，FAILED，algorithm_failed | 算法返回success=false；检查输入和服务日志 |
| 中控非2xx/连接异常/返回不合法 | 502，UNKNOWN | 可能已执行，保留requestId，不自动重提 |
| 算法调用等待超时 | 504，UNKNOWN，algorithm_timeout | 可能仍在运行，保留requestId，不自动重提 |
| 客户端断线或自身超时 | 可能无响应 | 不能认定服务未执行；联系服务端核对原请求 |

状态说明：SUCCEEDED为调用成功；FAILED为明确失败；UNKNOWN为执行结果不确定；REJECTED为非法输入。完整失败响应示例：

```json
{
  "requestId":"example-request-id",
  "code":429,
  "msg":"No algorithm capacity available",
  "error":"algorithm_busy",
  "status":"FAILED",
  "durationMs":20
}
```

本接口没有基于requestId的公开查询接口，也没有幂等键。一次调用只提交一次，超时、断线、下载失败都不能通过换ID重提来恢复。
尤其注意：**下载失败不等于算法失败**；保留key和requestId，只处理下载或联系服务端。

| 能力 | 算法等待预算 |
|---|---|
| 去背景 | 中控默认；本服务调用等待约665秒 |
| unwrap-uv、auto-rig | 1800秒 |
| watertight | 1400秒 |
| retopology | 900秒 |
| convert-3mf、人体分析5项、PCG两项 | 600秒 |
| mesh-lod | 7200秒 |

非去背景能力服务端在算法预算外另留65秒完整响应等待余量。客户端、网关及反向代理建议：普通能力至少2100秒，mesh-lod至少7500秒，并计入文件上传耗时。服务是同步接口，不能只调整MVC异步超时。

## 7. 对接检查

1. 目标环境已部署包含所需capability的服务版本。
2. 登录Cookie有效，request part类型为application/json，文件格式和大小正确。
3. 客户端支持新的capability，并为LOD设置足够超时；旧skill不会因后端升级自动支持新能力。
4. 若走桌面本机代理，需放行POST /v1/mesh/invoke，支持对应上传大小和超时。
5. 根据HTTP状态、code和status共同处理响应；打印检测另看topology_ok。
6. 使用data.files下载，LOD按映射解析；下载请求不携带登录Cookie。

中控、CLB、CDN、数据库等属于服务端部署范围，相关部署文档未随本 skill 提供。调用方不需要自行连接中控、配置CLB或持有TOS密钥。
