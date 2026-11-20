# 调用与恢复

## 独立依赖

按 [打包约定](../../.dependency-package-tools/references/usage.md) 提供完整分发目录，其中 `service-select` 是原子能力，`mdf-call` 与 `hi3d-api` 是实际调用工具。每个入口各占所属类别的直接子文件夹；保留共享资料与引用布局，不把其他入口嵌套进本包。MDF_DIR、API_DIR、ATOM_DIR 均由本次实际安装位置显式确定；目录存在不能替代宿主发现验证。仅使用一个后端时无需安装另一个后端。

本包服务契约自包含，协议和网络行为唯一实现在对应工具包。只调用单个原子时无需启动 Geo 中控、加载模型或安装其全部 GPU 依赖。不要为探测功能直接 import `workflow_online.py`；中控模块有顶层配置和外部运行时副作用。

## MDF

先读独立 `mdf-call/SKILL.md` 及它的 `references/deployment-and-probes.md`。默认 HTTP 中控，地址优先级为 `--endpoint` → `MDF_ENDPOINT` → 工具包默认地址。只有显式 `--transport sdk` 才读取 `--config` → `MDF3_CONFIG_PATH` → 随包 test 配置，并要求 worker 回连调用端。HTTP 健康检查与 SDK 配置预检都不能代替逐服务验收。[auto-rig](mdf/auto-rig.md#调用依赖与最小交接) 使用相同入口。

请求 JSON 只放目标服务业务字段。例如去背景：

```json
{"image":{"$file":"input.png"},"only_remove":true}
```

```bash
"$PYTHON" "$MDF_DIR/scripts/mdf_call.py" \
  --service image-process-service-v2-0 \
  --input "$RUN_DIR/request.json" --run-dir "$RUN_DIR/remove-background"
```

`$file` 路径相对 request.json，支持绝对路径、嵌套对象和列表。文件引用只允许 `$file`、可选 `file_name`、`field_name`；保持真实文件格式和后缀一致。未知服务不能靠改名称或猜 schema 提交；先确认契约再更新工具清单。

CLI 默认 `success` 严格为 bool True；其他字段用 `--success-field/--success-value` 明确指定已知业务条件。`--timeout` 是客户端等待秒数，不等于服务端任务取消。调用目录必须不存在；返回文件在 `artifacts/`，`invocation.json` 将业务字段位置映射到实际文件名，不能假定第一个文件就是最终模型。`result.summary.json` 是截断摘要，不用于无损恢复数组或深层结构；需要完整对象时调用所选传输的 `call_once` 并注入相应解析器。

直接 Python 复用时显式将 **MDF_DIR/scripts** 加入 sys.path，HTTP 使用 `MDF3GenericForwardCaller`，显式 SDK 使用 `MDF3ServiceInvokeCaller`，审计共用 `AuditWriter`；按工具说明注入 `success_predicate`。HTTP 文件调用无需完整 SDK，SDK 直连需要完整 SDK 与 worker 到调用端的 TCP 网络。先运行其 `scripts/check_runtime.py`，含数组的契约添加 `--require-numpy`。不能套用 Hi3D AK/SK。

## Hi3D API

先读独立 `hi3d-api/SKILL.md`、`references/calling.md`、`references/parameters.md`。例如单图几何计划：

```bash
"$PYTHON" "$API_DIR/scripts/hi3d_api.py" submit model \
  --image "$RUN_DIR/input.png" --set request_type=1 \
  --set model=hi3dv3.0 --set resolution=2048quality \
  --set format=glb --job "$RUN_DIR/model.job.json" --dry-run
```

dry-run 不联网、不鉴权、不创建 job；检查输入和计划后去掉 `--dry-run`；`waiting_choice` 交给宿主全局弹窗。余额查询不提交收费任务。后续使用同一 job：

```bash
"$PYTHON" "$API_DIR/scripts/hi3d_api.py" query --job "$RUN_DIR/model.job.json"
"$PYTHON" "$API_DIR/scripts/hi3d_api.py" wait --job "$RUN_DIR/model.job.json" --seconds 50
"$PYTHON" "$API_DIR/scripts/hi3d_api.py" download --job "$RUN_DIR/model.job.json" --out "$RUN_DIR/model-result"
```

参数例值用于表达调用形状，不是用户默认规格。已知 task ID 可用 `adopt <kind> <task_id> --job <新文件>` 接管；完整保留含点号的 ID。`submitting/submission_uncertain` 先找回原任务，不删除 job 或换路径绕过。查询失败不能依赖旧 success 继续下载。

## 验收与证据

文件哈希只验证交接完整性。服务目录各页列出对应业务检查。将请求输入摘要、任务标识、参数、产物映射和实测结果保存在任务目录；凭据、鉴权头、签名 URL 与原始敏感错误正文不写日志。明确区分当前调用的成功、历史可用性、源码契约和视觉判断。
