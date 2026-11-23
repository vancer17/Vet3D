# 工作区模型目录 RPC

## 名称、来源与核查版本

`workspace/open` 和 `workspace/models` 是 Hi3D Agent 1.2.11（Windows x64）Runtime 提供的桌面宿主 RPC。`workspace/modelUpdated` 是 Runtime 向宿主发送的通知。Runtime 的 `cg` 定义请求及返回结构，工作区处理器通过 `Jg.listModels` 读取目录。桌面 renderer 的 `Jr` 处理打开结果和版本更新通知。

## 接口说明

这三个名称属于 Runtime 宿主协议。对应定义包含参数、返回或通知结构，没有 LLM Tool 的 `description` 字段。下表为接口概述。

| 名称 | 协议类型 | 用途 |
| --- | --- | --- |
| `workspace/open` | 请求 | 返回工作区记录和该工作区的模型家族列表。 |
| `workspace/models` | 请求 | 返回指定工作区的模型家族列表。 |
| `workspace/modelUpdated` | 通知 | 交付一个新增或更新的模型版本及其工作区记录。 |

## 参数、结果与错误

两个请求均要求 `params.assetId` 为字符串，无默认值。`assetId` 由 Runtime 注册表解析，无需传目录路径。底层 JSONL 请求带 `type: "request"` 和 `requestId`，响应带 `type: "response"` 并沿用同一个 `requestId`。成功时数据放在 `result` 中。

| 接口 | 返回或通知字段 |
| --- | --- |
| `workspace/open` | `result: {workspace, models}`。 |
| `workspace/models` | `result: {models}`。 |
| `workspace/modelUpdated` | `params: {assetId, name, file, workspace, threadId?, turnId?, note?}`。通知携带 `type: "notification"` 和 `method`。 |

- `workspace` 必有 `assetId`、`name`、`cwd`、`threadIds`、`createdAt`、`updatedAt`。契约另允许 `missing?: boolean` 和 `projectId?: string | null`。目录是否可读仍由本次扫描校验。
- `models` 是 `{name, versions, latest}` 数组。`versions` 按数字版本号升序排列，`latest` 是该家族序号最大的版本。没有匹配文件时返回空数组。
- 版本对象和通知的 `file` 使用同一结构。声明的必填字段为 `name`、正整数 `index`、`fileName`、`path`、非负整数 `size` 及数值 `updatedAt`。`path` 是工作区根目录下的文件名，`size` 是文件字节数，`updatedAt` 来源是文件的 `mtimeMs`。可选元数据为 `threadId`、`turnId`、`note`、`tags` 和 `source`。`tags` 含可为 `null` 的 `tag4`。生成来源 `source` 记录 `provider`、`taskId`、`retryRootId`、`jobPath`、`kind`、`environment` 和 `ownerId`。

参数缺失、类型不符或工作区 ID 未登记时，Runtime 应答 `error.data.errorCode: "INVALID_ARGUMENT"`。已登记目录无效、真实路径超出受管根目录，或 `readdir`、`lstat`、`stat` 抛出未单独映射的错误时，经通用 RPC 包装返回 `INTERNAL`。运行时启动并正在安装随包 Skill 时，网关可返回 `CODEX_NOT_RUNNING`。文件系统错误和合法的空列表有不同结果。GLB 扫描只检查文件名、文件类型和文件属性，成功回包不证明 GLB 可解码。

查询处理器读取注册表和磁盘。通用 Runtime 分派会把已解析的工作区 ID 加入内存里的草稿保护集合。桌面处理成功的 `workspace/open` 结果时，会设置当前工作区及版本列表。通知异步发出，触发源包括模型导入、登记和已登记模型的分类更新。renderer 接到通知时更新工作区记录，并在工作区处于活动状态时按家族和实际文件名合并 `file`。该事件与请求响应分别交付。

## 实现伪代码

**根据已核查实现重建的伪代码。** 省略 JSONL 收发和界面状态。`require_registered_workspace` 检查 `assetId`。`assert_managed_cwd` 要求逻辑目录和真实目录均对应 `<workspacesRoot>/<assetId>`，并排除工作区目录自身为符号链接的情况。

```python
import re

MODEL_FILE = re.compile(r"^(.+)_(\d+)\.glb$", re.IGNORECASE)
MODEL_PREFIX = re.compile(r"^hi3d[-_.\s]+(.+)$", re.IGNORECASE)


def workspace_model_query(method, params):
    asset_id = parse_asset_id(params)
    workspace = require_registered_workspace(asset_id)
    models = list_models(workspace)
    if method == "workspace/open":
        return {"workspace": workspace, "models": models}
    return {"models": models}


def list_models(workspace):
    cwd = assert_managed_cwd(workspace)
    families = {}
    for file_name in read_root_names(cwd):
        match = MODEL_FILE.match(file_name)
        if match is None:
            continue
        file_path = join_path(cwd, file_name)
        if lstat(file_path).is_symlink:
            continue
        attributes = stat(file_path)
        if not attributes.is_regular_file:
            continue

        family, index = match.groups()
        prefixed = MODEL_PREFIX.match(family)
        if prefixed is not None:
            family = prefixed[1]
        metadata = find_model_metadata(workspace["assetId"], file_name) or {}
        version = {
            "name": family,
            "index": int(index),
            "fileName": file_name,
            "path": file_name,
            "size": attributes.size,
            "updatedAt": attributes.mtime_ms,
            **metadata,
        }
        families.setdefault(family, []).append(version)

    models = []
    for family, versions in families.items():
        versions.sort(key=lambda version: version["index"])
        models.append({"name": family, "versions": versions, "latest": versions[-1]})
    return sort_by_localized_family_name(models)
```

Runtime 只扫描根目录。带 `hi3d` 前缀的名称和历史无前缀名称都可匹配版本模式。元数据按 `assetId` 和精确文件名补入，缺失时只返回文件属性。目录扫描采用能匹配任意数字序号的正则，返回契约则声明正整数，扫描函数未额外筛除手工放入的 `_0.glb`。同一家族允许扫描到序号相同、实际文件名不同的条目，排序代码没有另外定义序号相同时的取舍。

## 例子与核查依据

**根据已核查协议重建的示例。** 假设工作区 `asset_demo` 已登记。查询请求以发起方分配的 `requestId` 关联返回。

```json
{
  "type": "request",
  "requestId": "query-demo-1",
  "method": "workspace/models",
  "params": { "assetId": "asset_demo" }
}
```

**根据已核查返回结构重建的示例。** 工作区只有 `sample` 家族的一个可见版本。示例采用合成文件属性。

```json
{
  "type": "response",
  "requestId": "query-demo-1",
  "result": {
    "models": [
      {
        "name": "sample",
        "versions": [
          {
            "name": "sample",
            "index": 2,
            "fileName": "hi3d-sample_2.glb",
            "path": "hi3d-sample_2.glb",
            "size": 4096,
            "updatedAt": 1700000000000
          }
        ],
        "latest": {
          "name": "sample",
          "index": 2,
          "fileName": "hi3d-sample_2.glb",
          "path": "hi3d-sample_2.glb",
          "size": 4096,
          "updatedAt": 1700000000000
        }
      }
    ]
  }
}
```

- 本次核查的软件包位于 `D:/install/Hi3DAgent.__hi3d-transaction/resources/`。`runtime/manifest.json` 标明 1.2.11（Windows x64）。`runtime/dist/runtime.mjs` SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`，`app.asar` SHA-256 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`，与此前核查的版本一致。
- 声明与实现见 Runtime 的 `cg`、`Qu`、`XL`、`kn`、`dispatchRuntimeMethod`、`Jg.assertWorkspaceCwd`、`Jg.listModels`、`notify` 和工作区方法分派。桌面同步见 ASAR 成员 `out/renderer/assets/index-CDPCug_K.js` 的 `Jr`。
- 安装包静态核查覆盖协议字段、查询分支、通知来源和界面合并条件。以合成目录项及文件属性独立执行提取的版本扫描函数，可复现家族归组、数值排序、元数据合并和被排除的文件类型。实际桌面请求和增量通知时序尚待实测。
