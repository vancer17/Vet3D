# 部署、传输与诊断

## 默认 HTTP 中控

调用链：调用端 HTTP → 中控 `generic-forward` → TaskQueue → worker → 中控 TCP → HTTP 结果。worker 不需要连接调用端；中控与 worker 仍须位于能双向通信的网络。

地址按显式 `--endpoint` / Python `endpoint`、`MDF_ENDPOINT`、随包默认 `http://172.31.192.135:7789/generate_model` 选择。默认入口来自 [generic-forward 官方调用方](http://172.31.0.3:8099/video-to-3d/service/video-to-3d-center/-/blob/c567a59c4c9c5102353088fc03cceec8241e1ead/API/generic_forward.py)。环境变量存在但为空时拒绝，不悄悄回退。地址必须是无凭据、query 和 fragment 的 HTTP(S) URL。`--environment` 默认 test，在 HTTP 模式只记录部署标签，不切换服务端环境。

```bash
"$PYTHON" "$SKILL_DIR/scripts/mdf_endpoint.py" --output "$RUN_DIR/gateway.json"
```

只 GET 同一路径前缀下的 `/health`，核对 `service_name=CenterControlService-Generic-Forward`、`status=healthy`。`--expected-service` 用于其他已确认的网关身份。退出 0 仅证明中控身份与健康，不证明任何下游在线。默认入口不要求鉴权头；其他已确认部署的 headers 由授权调用进程注入，不读取 Hi3D AK/SK 或 SDK YAML。

## 显式 SDK 直连

`--transport sdk` 使用官方 [ServiceInvokeSession](http://172.31.0.3:8099/TangPei/mdf3/-/blob/28f0983a99f40cb73a226611c3a04ca55812d4f5/service_invoke_tool.py)，在调用端启动临时 TCP 服务，向 TaskQueue 投递，worker 回连调用端 fetch 输入和 result。队列可达不足以证明这条回路可用；Mac、VPN、NAT 等环境不能默认满足回连。

配置按 `--config`（YAML 文件）、`MDF3_CONFIG_PATH`（文件或含 `config.<environment>.yaml` 的目录）、随包 test 配置选择。空配置环境变量拒绝；非 test 环境必须显式配置。随包配置只有 TaskQueue 连接参数与 Nacos 地址，无 TOS、Kafka、飞书或认证字段。此调用链只需要队列配置，不使用 Nacos 发现。

```bash
"$PYTHON" "$SKILL_DIR/scripts/mdf_endpoint.py" --transport sdk --output "$RUN_DIR/config.json"
```

此检查只读取 YAML，验证 `task_queue.endpoints` 合法，不联网或证明 worker 回连。HTTP 模式不能传 `--config`，SDK 模式不能传 `--endpoint`，错误组合在提交前拒绝。不会根据超时、配置或服务名自动更换传输。

## 业务调用与产物

```bash
"$PYTHON" "$SKILL_DIR/scripts/mdf_call.py" \
  --service auto-rig --input "$RUN_DIR/request.json" --run-dir "$RUN_DIR/call"

# 仅在完整 SDK 和回连网络已满足时显式选择
"$PYTHON" "$SKILL_DIR/scripts/mdf_call.py" --transport sdk \
  --service auto-rig --input "$RUN_DIR/request.json" --run-dir "$RUN_DIR/sdk-call"
```

两种模式均要求顶层业务 JSON；`{"$file":"input.glb"}` 按 JSON 所在目录解析并读取已授权文件，可附加 `field_name`、`file_name`，支持嵌套容器。`--run-dir` 必须不存在。`--timeout` 默认 3600 秒；`--require-numpy` 显式检查数组依赖。默认 `success` 严格为 bool True，可用 `--success-field` 点路径与 JSON `--success-value` 指定其他已确认条件。

`invocation.json` 保存 transport、trace、入口别名、成功条件、耗时和产物大小/SHA-256；SDK 额外记录配置文件名。`runtime.json` 记录实际 codec 与依赖；`audit.jsonl` 保存请求/终态配对；BinaryFile 与 bytes 保存到 `artifacts/`，通过 `files[].field_path` 定位。`result.summary.json` 截断并脱敏，不能用来恢复完整数组或深层结构。返回 0 只表示业务成功且输出保存完成；还须按契约验收产物。退出 1 表示调用/输出失败，2 表示提交前校验或参数错误。

## 显式逐服务诊断

```bash
"$PYTHON" "$SKILL_DIR/scripts/mdf_probe.py" --service auto-rig --run-dir "$RUN_DIR/probe"
```

可重复 `--service`，或用户要求全量检查时使用 `--all-services`；并发 `--workers` 为 1–4，默认 1。默认 HTTP，可显式选择 SDK。诊断会向真实业务队列提交 `__mdf_connectivity_probe__=True`，不提供业务输入；只在用户要求时执行，不能作为自动健康检查。HTTP 先检查网关，SDK 先检查配置。预检失败退出 1，不提交下游。

可解码下游字典记为 `downstream_response_received`；即使业务失败也证明往返，业务验证仍为 `not_run`。超时、断连或不可解码结果保持 `unverified`，不能据此断言服务不存在。全部往返确认退出 0，存在未确认项退出 2。

## 不明结果与恢复

每次业务或诊断只提交一次，不自动重试、重定向或切换 HTTP/SDK。客户端超时不是服务端取消。进程中断后的 `IN_PROGRESS` 保留原 trace 与审计；不能删除目录、换 ID 或切换通道掩盖不明结果。先用原任务标识检查是否已处理，再按已有授权恢复。旧记录缺少 transport 时保留原记录并根据已记录入口识别，不推断为未提交。
