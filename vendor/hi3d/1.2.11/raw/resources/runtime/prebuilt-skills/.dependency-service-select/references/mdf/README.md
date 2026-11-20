# MDF 文件与响应契约

按 [能力目录](../catalog.md) 选择服务。各页标明契约来源：[mesh-lod](mesh-lod.md)、[mesh-watertight](mesh-watertight.md)、量化 Geo2 入口和 [sapiens2](sapiens2.md) 有服务源码契约；其他服务记录已确认调用方字段与兼容限制；不可把静态源码分析或单例推理推广为全部线上服务验证。

MDF 调用、入口与恢复由独立 mdf-call 工具负责，默认使用 HTTP 中控；显式 SDK 直连需要完整 SDK 和 worker 回连调用端，接入方式见 [调用说明](../calling.md)。[auto-rig](auto-rig.md) 的已部署适配器契约、测试环境与双向回调网络前提见专页，适配器尚未发布固定提交。BinaryFile 的文件字节需保存到客户端，再交给下游；服务端临时路径不能当可下载产物。

## 二进制与数组

`BinaryFile` 表示 MDF 对象，携带 `content: bytes`、`file_name`，按适配器要求设置 `field_name`；服务通常通过对象属性读取内容。表中必填文件须非空。`file_name` 后缀可能决定视频、PNG、GLB 或 `.zst` 的解码方式，不能任意更名。可选文件为空时是否忽略，以服务页为准。

`.zst` 使用 data-io 数组容器（`read_array_data` / `write_array_data`），不是 NumPy `.npz`；源码中的历史 `npz` 变量/参数名不改变实际格式。应复用同版本序列化依赖，保留数组 dtype、shape 和键名。

返回 `BinaryFile` 是内存数据，服务临时路径在请求结束后清理；调用方保存并校验产物后再交接下游。

## 公共输出与失败

[mesh-lod](mesh-lod.md) 返回 `success: bool`；失败包含 `error_type: str`、`error_message: str`，**不返回 status**。各页列出全部额外业务字段及条件性诊断；不要要求所有服务具备同一个 status 字段。

HTTP 成功、worker 完成或非空响应都不足以证明业务成功。失败诊断不等于可用模型；某些中控继续使用原输入网格属于调用方回退，不代表下游服务成功。重试与已有任务恢复按 mdf-call 契约处理。

## 公共部署 CLI

以下默认值适用于 mesh-lod 的固定 MDF 入口；其他服务按各自部署契约配置。

| 参数 | 默认 / 范围 | 用途 |
| --- | --- | --- |
| `--env` / `-e` | test；dev/test/prod | MDF 环境。 |
| `--service_name` | 对应服务名 | 注册名；默认 mesh-lod；mesh-watertight 的部署参数见其专页。 |
| `--port` / `--tcp_port` | None；int | worker TCP 端口，由框架在未传时处理。 |
| `--arbiter-host` | 127.0.0.1 | arbiter 主机。 |
| `--arbiter-port` | 19600；int | arbiter 端口。 |

模型路径、显存、超时等部署变量只记录源码名称/默认值，不读取运行环境或凭据来验证。

Sapiens2 使用 NPZ 原始数组，默认 ManagedServiceBase 单 GPU 托管，并保留 standalone 路线。其 CPU offload 约束、部署 CLI 与自动构建见[专页](sapiens2.md)。

auto-rig 使用 standalone ServiceBase，部署 CLI、单实例 Blender 端口限制及模型常驻行为见[专页](auto-rig.md#部署参数与本地-api-区别)，不能套用上表的托管入口参数。
