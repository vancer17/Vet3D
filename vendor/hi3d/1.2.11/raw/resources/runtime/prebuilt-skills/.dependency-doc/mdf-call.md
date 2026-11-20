# mdf-call：MDF 服务调用工具

[AI 入口](../mdf-api/SKILL.md)面向已部署 MDF 服务的单次调用、审计和验收；[mdf-call 工具包](../mdf-api/SKILL.md) 按 [打包约定](../.dependency-package-tools/references/usage.md) 随完整分发目录提供给 AI。默认调用走 HTTP `generic-forward` 中控，文件型调用无需完整 SDK；显式 `--transport sdk` 才使用官方 `ServiceInvokeSession`，需要完整 SDK、PyYAML 和 worker 回连调用端。数组另需 NumPy。业务成功谓词和产物解析器由调用方注入。

[MDF 服务功能与传参速查](mdf_list.md)列出已收录服务的名称、功能和输入输出，按需链接到完整服务契约。本工具需要调用方提供已确认的业务参数，不自动按服务名查询业务 schema；速查文档不是工具独立运行的必需依赖。

随包服务清单已收录 auto-rig，可选 `invocation` 标明其测试环境 SDK 队列/TCP 路径。auto-rig 与其他服务共用默认 HTTP 业务 CLI 与诊断入口，SDK 直连为显式选项；元数据不选择其他传输，不会自动安装 SDK 或切换环境，收录不保证当前在线或业务成功。

auto-rig 的身体文件请求与 `rigged_mesh` 产物定位见 [AI 入口](../mdf-api/SKILL.md#直接调用业务服务)及[服务契约](mdf/auto-rig.md)。调用端保持用户指定的主机；已有结果交给独立 rig-retarget 工作流 做高模回迁与权重修复，不另建客户端或为本地修复重提服务。

## 目录、依赖与组合

原子调用实现来源：`lichanghao/skills` 的 `invoke-online-service`，版本 `e07bd42be67d257c285d5f61bd731955fe85155e`；本仓库以 `mdf-call` 独立维护。

| 文件 | 职责 |
| --- | --- |
| [online_service_atoms.py](../.dependency-mdf-call-source/scripts/online_service_atoms.py) | 标准库原子：RunSpec、脱敏摘要、审计、原子落盘、文件验证和 checkpoint 判断。 |
| [config.test.yaml](../.dependency-mdf-call-source/assets/config.test.yaml) | 随包 MDF3 test 连接配置（TaskQueue 与 Nacos 地址，无凭据）；仅用于显式 SDK 模式，可用 `--config` 或 `MDF3_CONFIG_PATH` 覆盖。 |
| [mdf3_generic_forward.py](../.dependency-mdf-call-source/scripts/mdf3_generic_forward.py) | 默认 HTTP 适配器，构造 generic-forward envelope、trace header，分类 HTTP/业务/不明结果并记录单次审计。 |
| [mdf_gateway.py](../.dependency-mdf-call-source/scripts/mdf_gateway.py) | HTTP 地址解析与验证、同路径前缀健康 URL、身份和健康检查，无业务提交。 |
| [mdf_http.py](../.dependency-mdf-call-source/scripts/mdf_http.py) | 标准库单次 HTTP POST、JSON 响应、512 MiB 默认上限，禁止代理环境、重定向和重试。 |
| [mdf_runtime.py](../.dependency-mdf-call-source/scripts/mdf_runtime.py) | 按 transport 加载已有 codec；HTTP 缺 SDK 时启用随包 wire 子集，SDK 模式不回退。 |
| [_wire/mdf3](../.dependency-mdf-call-source/scripts/_wire/mdf3) | `__init__.py` 导出 wire 版本与类型；`mdf_tool.py` 保留官方 BinaryFile 状态、pickle protocol 4 和 dumps/loads，无服务或配置依赖。 |
| [test_mdf3_generic_forward.py](../.dependency-mdf-call-source/tests/test_mdf3_generic_forward.py) | 离线 HTTP envelope、trace、失败分类与单次提交行为。 |
| [test_mdf_gateway.py](../.dependency-mdf-call-source/tests/test_mdf_gateway.py) | 网关覆盖、健康身份、地址校验、失败与脱敏输出。 |
| [test_transport_selection.py](../.dependency-mdf-call-source/tests/test_transport_selection.py) | 默认 HTTP 文件返回、SDK 配置隔离、超时不切换、诊断与冲突参数拒绝。 |
| [mdf3_service_invoke.py](../.dependency-mdf-call-source/scripts/mdf3_service_invoke.py) | 可注入的 ServiceInvokeSession 适配器：单次 invoke、审计与失败分类。 |
| [check_runtime.py](../.dependency-mdf-call-source/scripts/check_runtime.py) | 按传输检查本地 BinaryFile 往返、可选 SDK/NumPy 依赖与模块来源。 |
| [test_standalone_wire.py](../.dependency-mdf-call-source/tests/test_standalone_wire.py) | 复制包后在无 site-packages 的进程中通过本机 HTTP 网关返回大文件、校验 wire 身份和已有目录拒绝。 |
| [mdf_call.py](../.dependency-mdf-call-source/scripts/mdf_call.py) | 业务 CLI：JSON/本地文件组装、单次调用、产物和摘要保存。 |
| [mdf_endpoint.py](../.dependency-mdf-call-source/scripts/mdf_endpoint.py) | 配置解析、YAML 预检、TaskQueue URL 校验及服务清单读取。 |
| [mdf_probe.py](../.dependency-mdf-call-source/scripts/mdf_probe.py) | 显式逐服务诊断、单次 invoke、trace/审计与覆盖报告。 |
| [inspect_runtime.py](../.dependency-mdf-call-source/scripts/inspect_runtime.py) | 收集解释器、模块、Git 和显式选定环境信息；CLI 可写来源报告。 |
| [validate_artifact.py](../.dependency-mdf-call-source/scripts/validate_artifact.py) | 文件验证 CLI，支持大小、SHA-256 与 JSON 解析。 |
| [verify_audit.py](../.dependency-mdf-call-source/scripts/verify_audit.py) | JSONL 审计配对与结果检查 CLI。 |
| [test_online_service_atoms.py](../.dependency-mdf-call-source/tests/test_online_service_atoms.py) | RunSpec、脱敏、原子写入、审计与 checkpoint 的离线行为测试。 |
| [test_mdf3_service_invoke.py](../.dependency-mdf-call-source/tests/test_mdf3_service_invoke.py) | 注入假 session，验证单次调用、审计与失败分类。 |
| [test_sdk_integration.py](../.dependency-mdf-call-source/tests/test_sdk_integration.py) | 完整 SDK 的本地 TCP 往返、仅队列配置、业务失败、超时与部分启动清理；模拟 TaskQueue 并阻止 HTTP 请求，SDK 缺失时跳过。 |
| [test_mdf_call.py](../.dependency-mdf-call-source/tests/test_mdf_call.py) | 模拟依赖运行完整业务入口，验证文件组装、产物落盘、成功判定和安全文件名。 |
| [test_mdf_endpoint.py](../.dependency-mdf-call-source/tests/test_mdf_endpoint.py) | 配置覆盖、空环境变量拒绝、凭据 URL 拒绝、报告不含密钥。 |
| [test_mdf_probe.py](../.dependency-mdf-call-source/tests/test_mdf_probe.py) | 下游错误与可达性区分、超时、单次提交和服务清单。 |
| [test_cli_helpers.py](../.dependency-mdf-call-source/tests/test_cli_helpers.py) | 通过子进程验证 3 个本地 CLI 的可观察输出与退出状态。 |

入口说明、随包 references、[服务清单](../.dependency-mdf-call-source/assets/services.json)、[test 配置](../.dependency-mdf-call-source/assets/config.test.yaml)、[auto-rig 请求示例](../.dependency-mdf-call-source/assets/request.auto-rig.json)、[mesh-watertight 请求示例](../.dependency-mdf-call-source/assets/request.mesh-watertight.json)、[RunSpec 模板](../.dependency-mdf-call-source/assets/run_spec.template.json)、[批清单模板](../.dependency-mdf-call-source/assets/batch_manifest.template.json)和 [AI 元数据](../mdf-api/agents/openai.yaml)均随工具包交付。模板中的 example 值须按任务替换；批清单是记录格式，不是自动调度器。`.gitignore` 只排除 Python 缓存。

标准库原子兼容 Python 3.7+；HTTP 文件型 CLI 使用 Python 3.7+，SDK 模式使用目标完整 MDF3 SDK 支持的 Python（本包离线测试使用 Python 3.9+）。数组契约需要 NumPy。来源、配置和独立运行方式只在 [通信运行时](../.dependency-mdf-call-source/references/wire-runtime.md) 维护。`inspect_runtime` 查询 Git 时需要本机 git，否则对应信息为 null。

依赖方向为 业务/诊断入口 → HTTP 或 SDK 适配器 → 对应网络/codec、`mdf_gateway` / `mdf_endpoint` / `online_service_atoms`，原子模块不导入业务项目。调用脚本将当前工具包的 `scripts/` 加入进程模块搜索路径即可导入；不依赖仓库根目录、工作目录或其他 skill。Python 运行时不读取本页；入口及引用资料仍按打包约定完整提供。

## 原理与状态契约

从三个不变量组织实现：一次授权请求只提交一次；不把未知执行结果当作未执行；成功必须有产物和必要副作用的验证证据。RunSpec 固定事实，单次适配器记录发送与终态，后续验证器决定是否达到业务完成标准。

契约字段、审计事件、恢复和副作用的唯一操作说明分别见 [契约与 RunSpec](../.dependency-mdf-call-source/references/contract-and-runspec.md)、[执行与恢复](../.dependency-mdf-call-source/references/execution-and-recovery.md)、[业务验收](../.dependency-mdf-call-source/references/validation-and-side-effects.md)；最小 Python 调用见 [HTTP 适配器](../.dependency-mdf-call-source/references/mdf3-generic-forward.md) 与 [SDK 适配器](../.dependency-mdf-call-source/references/mdf3-service-invoke.md)。

- `call_once` 返回值仅证明当前业务成功谓词返回了字面量 `True`，不自动验收文件或 required 副作用。
- `AuditReport.ok` 检查调用记录结构及已知结果；`allow_incomplete=True` 时可在仍有 open 调用时为 true，必须同时看 `complete`，不可据此声明 `VALIDATED`。
- 适配器无跨进程去重、异步轮询或自动恢复重发；相同 ID 的服务端幂等语义须来自实际契约。
- `stable_digest` 是脱敏、截断摘要的指纹，不是精确数据指纹。checkpoint 的三个指纹由调用方对完整确定性数据计算，例如 `sha256_bytes(serialized_input)`；文件使用 `sha256_file`。

## online_service_atoms 接口

无特别注明时，下列函数不访问网络。纯计算与文件 I/O 分离，错误交由调用方分类；不打印传入数据。

| 函数或类型 | 输入、输出与边界 |
| --- | --- |
| `utc_now()` | 返回带 UTC 时区、秒精度的 ISO 时间字符串。读取系统时钟。 |
| `sha256_bytes(content)` | bytes → 64 位十六进制 SHA-256；完整字节内容摘要。 |
| `sha256_file(path, chunk_size=1048576)` | 路径、正整数字节块大小 → 文件完整 SHA-256；只读，I/O 错误向上传播。 |
| `_normalize_key(value)` / `_is_sensitive_key(key, extras)` | 将字段名规范化，再判断已知凭据名、后缀或额外敏感字段；不识别任意文本中的秘密。 |
| `summarize_for_audit(value, *, extra_sensitive_keys=(), max_depth=4, max_items=16, max_string=256)` | 数据 → JSON 安全摘要。已知敏感字段替换为 redacted，bytes/BinaryFile 内容变为大小和摘要，Path 只保留文件名及绝对路径标志。限制深度、序列长度和长字符串；映射保留全部键。未知对象只记录类型。 |
| `stable_digest(value, *, extra_sensitive_keys=())` | 对上述摘要排序键、JSON 编码再 SHA-256；相同摘要可能对应不同完整输入，不用于 checkpoint。 |
| `OnlineCallError(message, *, call_id=None)` | 带 call_id 的异常基类。派生类型：`DefinitiveRejection` 确定未受理；`BusinessFailure` 明确业务失败；`AmbiguousOutcome` 执行结果未明；`ContractViolation` 契约错误；`ArtifactValidationError` 文件验收失败。 |
| `RunSpec` | frozen dataclass；必要字段为 run_id/case_id/environment/endpoint_alias/protocol/operation/trace_id/timeout_sec/retry_policy/success_predicate。validators、side_effects 默认空 tuple；摘要、运行时来源与幂等键默认 None；schema_version=1。内部 dict 仍可变，不等于深度冻结。 |
| `RunSpec.validate()` | 验证非空字符串标识、有限正超时、schema=1、明确重试策略及副作用策略；无返回值，错误抛 ContractViolation。它不执行授权校验、字段 schema 或重试。 |
| `RunSpec.to_dict()` / `RunSpec.from_dict(mapping)` | 验证后在 dataclass 与字典间转换；from_dict 将 validators/side_effects 转成 tuple。未知或缺失构造字段会抛类型错误。 |
| `CallIdFactory(prefix='call')` / `.next(operation)` | 清理 prefix/operation 中的字符，用实例内线程锁生成递增编号字符串；不保证跨实例、跨进程唯一。 |
| `AuditWriter(path, *, extra_sensitive_keys=())` / `.write(event, **data)` | 创建父目录；追加单行 UTF-8 JSONL，含 schema/time/event 与脱敏数据，返回实际记录。使用实例锁、flush/fsync；新文件权限 0600，已有文件权限不修改。不是多进程日志事务。 |
| `atomic_write_bytes(path, content, mode=0o600)` | bytes → 目标 Path；创建父目录，同目录排他临时文件写入、flush/fsync、replace，尝试目录 fsync 并清理临时文件；会替换现有目标。 |
| `atomic_write_json(path, value, mode=0o600)` | JSON 可序列化数据 → 目标 Path；排序、缩进、UTF-8 编码，拒绝 NaN，复用 atomic_write_bytes。 |
| `validate_file(path, *, min_size=1, expected_size=None, expected_sha256=None, parser=None)` | 文件路径及可选断言 → validated 报告，含路径、大小、摘要、parser、assertions、validated_at。默认要求非空，指定预期大小/摘要时严格比较。parser(Path) 可注入；解析异常向调用方传播。 |
| `load_jsonl(path)` | 读取非空行 → 字典列表；非法 JSON 或非对象行抛 ContractViolation，文件 I/O 错误直接传播。 |
| `verify_audit_records(records, *, trace_id=None, allow_incomplete=False)` | 按 trace 选择记录，以 call_id 核对恰好一次 request_sent、retries=0、至多一个终态及 trace/service/operation 一致性；返回 AuditReport。无调用记录、重复事件、失败、歧义或未允许的 open 调用不能通过。 |
| `AuditReport` | 保存所选记录数、发送/成功/失败/歧义计数、相关 call_id 和错误列表；`structure_ok` 表示无结构错误，`complete` 表示无 open 调用，`ok` 按上述规则判断；`.to_dict()` 同时输出这些派生字段。 |
| `evaluate_checkpoint(checkpoint, *, input_digest, contract_digest, parameter_digest, parser=None)` | 核对 validated 状态与三个指纹，要求产物 path、正整数 size、64 位十六进制 sha256，再重新执行文件/解析验证；返回 CheckpointDecision，不匹配则列 reasons。不会提交任务或仅凭文件存在放行。 |
| `CheckpointDecision` / `.to_dict()` | 结果包含 reusable、reasons、validation；验证器异常转成不复用理由，仅记录异常类型。 |

`AuditWriter` 的默认脱敏只针对已知字段名。字段值中出现的凭据、URL、项目自定义秘密须由调用方使用额外敏感键或白名单 hook 处理；不要把 raw response 传入审计。注入 parser、模块和回调属于调用方代码，其副作用需单独确认。

## MDF3ServiceInvokeCaller 接口

构造函数全部为命名参数：

| 参数 | 契约 |
| --- | --- |
| `config_path`、`endpoint_alias`、`environment` | `config_path=None` 按显式值、`MDF3_CONFIG_PATH`、随包 test 配置解析；别名/环境非空。配置存在不替代对目标部署身份的确认。 |
| `audit`、`success_predicate` | AuditWriter 与 callable(dict)；成功谓词必须返回字面量 True，否则判失败，抛异常则为契约错误。 |
| `caller_service_name='mdf-call'` | 传给 SDK session，出现在服务端日志中。 |
| `session_factory=None` | 默认使用官方 `ServiceInvokeSession`；可注入无网络假 session 做离线验证。 |
| `extra_sensitive_keys=()`、`input_audit_summarizer=None`、`output_audit_summarizer=None` | 扩展脱敏键或输入/输出白名单 hook；默认审计只保留字段名与摘要指纹。 |

- `_mapping_audit_summary(value, hook)`：调用可选摘要 hook 后再次脱敏；无 hook 时仅记录键和摘要指纹。
- `call_once(*, service, input_data, trace_id, timeout_sec, run_id, case_id, call_id=None)`：先校验配置，再写 request_sent 并执行一次 `session.invoke`；成功返回业务字典。未指定 call_id 时使用当前实例计数器。

结果判断：SDK 超时/`ServiceCallFailed`/传输异常为 AMBIGUOUS；返回非 dict 或成功谓词异常为 ContractViolation；谓词非 True 为 BusinessFailure。业务 `success=False` 的 dict 仍会交给谓词。

默认 session 工厂在 `start()` 部分失败时也会执行 `stop()`，清理已创建的本地 TCP 服务。配置缺失或队列地址非法在创建 session 和写发送审计前拒绝；非 test 环境必须显式提供配置，不能回退随包 test 队列。

适配器会保留原异常链供程序排障，但调用方不得把可能包含敏感响应的原始异常堆栈放入用户报告。文件写入、业务验证、副作用检查由原子函数和项目 hook 完成。

## 本地 CLI 与运行时检查

三个 CLI 的 `main(argv=None)` 接受显式参数列表，省略时读取进程 argv；导入模块不会自动启动 main。

- `inspect_runtime.capture_runtime(*, modules=(), repositories=(), environment_keys=(), labels=None)` 返回来源字典；不写文件。内部 `_module_info(name)` **实际导入模块**并读取来源、摘要与版本，必须只选择已确认初始化无线上副作用的模块；`_repo_info(path)` 用 `_command(args)` 读取 Git，命令超时为 10 秒、不可用时返回 None；`_env_info(name)` 只读取显式指定环境键，并按敏感名称隐藏值。`main` 解析 label、可原子写 `--output` 并输出 JSON。
- `validate_artifact.parse_json(path)` 用标准 JSON 解析器读取，返回顶层类型；不是业务 schema 验证。CLI 校验失败退出 1，成功退出 0。
- `verify_audit.main` 读取 JSONL 并输出 AuditReport，report.ok 为 true 时退出 0，否则退出 1；`--allow-incomplete` 不会抹除 open 调用。

最小本地验证命令，变量由当前环境解析：

```bash
"$PYTHON" "$SKILL_DIR/scripts/inspect_runtime.py" --module json \
  --output "$RUN_DIR/runtime_provenance.json"
"$PYTHON" "$SKILL_DIR/scripts/validate_artifact.py" \
  "$RUN_DIR/runtime_provenance.json" --json
"$PYTHON" "$SKILL_DIR/scripts/verify_audit.py" \
  "$RUN_DIR/invocation_audit.jsonl" --trace-id "$TRACE_ID"
"$PYTHON" -m unittest discover -s "$SKILL_DIR/tests" -v
```

这三个 CLI 只做本地来源、文件和审计检查；配置检查和在线诊断使用下述入口，业务调用使用 `mdf_call.py` 或上述 Python 适配器。`verify_audit` 的输入必须是真实记录，不能制造成功事件代替调用。

## 配置解析和在线诊断接口

调用命令、配置优先级和副作用的唯一说明见 [部署与诊断](../.dependency-mdf-call-source/references/deployment-and-probes.md)。服务清单记录当前收录的 12 个下游名及源码归属，不持久化每次在线状态。exposure_status 为用户确认的 exposed 或待确认的 pending_confirmation，只记录露出范围，不选择传输或改变 CLI 准入；用户列出的 pcg-function-call-service 因尚无请求契约未注册。业务与诊断 CLI 只接受当前清单中的服务名，未收录名称在参数解析阶段拒绝；`--all-services` 只遍历当前清单。业务输入输出速查在 [服务总表](mdf_list.md)，效果与详细契约默认由独立 [service-select](../.dependency-service-select/REFERENCE.md) 随包维护；[mesh-watertight 完整契约与调用用法](../.dependency-mdf-call-source/references/mesh-watertight.md) 由本工具唯一维护，服务选择包按 package.json 物化。

| 原子 / 入口 | 契约 |
| --- | --- |
| `mdf_call.materialize_request(value, *, base_dir, binary_factory, field_name="")` | 递归读取显式 $file 引用并构造 BinaryFile，保持普通 JSON 和 None 槽；文件路径相对输入 JSON 解析。 |
| `field_equals(result, field, expected)` | 按点分隔读取字段，严格比较类型与值；缺失返回 False。 |
| `save_binary_outputs(result, *, directory, binary_type)` | 导出嵌套 BinaryFile/bytes，净化文件名并加唯一序号，忽略已知凭据字段；返回字段位置/大小/SHA-256，不做业务解析。 |
| `redact_summary_urls(value)` | 在已脱敏摘要中递归移除含 HTTP URL 的文本；不是完整响应编码器。 |
| `mdf_call.main(argv=None, *, session_factory=None, binary_factory=None, post=None)` | JSON 业务 CLI；默认 HTTP，仅预检所选传输依赖，使用对应适配器，输出 trace、真实状态、摘要和产物；无自动重试，已有输出目录拒绝提交。 |
| `mdf_endpoint.validate_config_path(path)` | 校验存在的 YAML 文件；错误不回显文件内容。 |
| `resolve_config_path(config_path=None, *, environment='test', environ=None)` | 显式值优先；否则读 `MDF3_CONFIG_PATH`（文件或目录），再回退随包 test 配置；空设置报错。 |
| `validate_queue_url(endpoint)` | 校验 TaskQueue HTTP(S) URL，不含凭据/query/fragment；允许空 path。 |
| `load_config_mapping(path)` / `inspect_config(path)` | 解析 YAML 并核对 `task_queue.endpoints`；报告不含密钥。 |
| `check_config(config_path=None, *, environment='test', environ=None)` | 解析并预检配置；下游状态保持 unverified。 |
| `load_service_names(path=CATALOG_PATH)` | 读取随包 JSON，验证版本、非空名字及去重；不导入业务模块。 |
| `mdf_endpoint.main(argv=None)` | 默认 HTTP 健康检查，显式 SDK 配置检查；可写报告，成功/失败分别退出 0/1，参数错误退出 2。 |
| `probe_service(service, *, config_path=None, run_dir, run_id, timeout_sec=60, environment='test', session_factory=None, transport='http', endpoint=None, post=None)` | 只提交诊断字典，复用所选 HTTP/SDK 适配器。真实业务失败仍记录为 BusinessFailure；可解码下游字典另记可达。 |
| `mdf_probe.main(argv=None, *, session_factory=None)` | 选择清单内单个/多个/全部服务；先检查所选 HTTP 网关或 SDK 配置，再运行 1–4 个并发任务，默认 1；要求新运行目录。未确认项退出 2。 |

客户端单次提交不保证服务端绝无重派发：框架可按 task_hash 重新投递尚未取走的任务。网络超时也不取消后台任务。在线诊断报告、具体请求 trace ID 和离线测试记录保存在仓库外的任务目录。

## 验证方法与边界

使用上面的 unittest 命令运行离线测试；各测试文件的职责见目录表。测试覆盖请求构造、文件处理、单次提交、结果分类、脱敏审计和 CLI 退出状态。独立分发时，按打包约定在仓库外物化完整分发目录，检查资源引用、模块导入和代表性入口。

离线假 session 不能证明下游业务成功或所有线上 SDK 版本兼容。实际调用仍需按目标部署、服务成功条件、产物格式和副作用验收；配置预检、下游响应和业务成功分别判断。

完整 SDK 可用时，同一测试命令还运行真实 `ServiceInvokeSession` 与 loopback TCP 的集成测试：使用仅含 `task_queue` 的临时配置，模拟队列与 worker，禁止 HTTP 外联；验证 BinaryFile 经 TCP 返回并由 CLI 保存、业务失败仍可确认往返、超时保持单次提交，以及部分启动失败的资源清理。缺少 SDK 时这些用例明确跳过，不能据此报告 SDK 兼容性已验证。运行配置依据 [MDF3 3.3.0](http://172.31.0.3:8099/TangPei/mdf3/-/tree/28f0983a99f40cb73a226611c3a04ca55812d4f5) 的 API；已有 SDK 仍须通过运行时和集成检查。

## 运行时原子

- `mdf_runtime.load_codec(transport="http")` 返回已有 `mdf3.mdf_tool`；未安装时 HTTP 启用独立搜索路径的 wire 子集，SDK 则要求完整模块存在。不会替换已安装但导入失败的实现，也不自动切换网络。
- `check_runtime.check_runtime(require_numpy=False, transport="http")`：执行本地 BinaryFile 往返，仅 SDK 模式确认 `ServiceInvokeSession` 可导入；记录解释器、实际模块位置和可选 NumPy 可用性。返回 ready 或异常类型，不提交业务或读取认证信息。
- `check_runtime.main(argv=None)`：支持 `--transport`、`--require-numpy` 和 `--output`；ready 退出 0，缺少/不兼容依赖退出 2。
- 业务入口在新目录保存 `runtime.json`，调用中保存 `IN_PROGRESS`，终态补充带时区完成时间与单调时钟客户端耗时；业务失败和未知结果仍使用现有分类，不能根据中间文件存在重提。

## HTTP 原子与参数

- `MDF3GenericForwardCaller` 的 `call_once` 参数与 SDK 适配器一致，传入业务 service、input_data、trace、有限正 timeout 和审计关联 ID。构造函数接受 endpoint、入口别名、environment、audit、success_predicate，可注入 post、dumps_fn、loads_fn、传输异常类、headers 与摘要 hook。完整示例与 envelope 见随包 HTTP 适配器说明。
- `mdf_gateway.validate_endpoint` 拒绝含凭据/query/fragment 的地址；`resolve_endpoint(endpoint=None, environment=None)` 按显式值、MDF_ENDPOINT、默认地址选择；存在但为空拒绝。
- `gateway_health_url` 返回同前缀 `/health`；`get_health_json` 单次 GET，超时默认 10 秒，响应上限 1 MiB；`check_gateway` 核对 HTTP 200、服务身份与健康，返回有限分类，不输出原响应。以上函数也从 mdf_endpoint 重导出，保留旧 Python 入口。
- `mdf_http.post_json` 接收 endpoint、headers、json、timeout、allow_redirects=False、max_response_bytes（默认 512 MiB），返回 `JsonResponse(status_code, body)`；其 `json()` 返回已解码值或抛出已保存异常。`encode_json` / `decode_json` 处理 UTF-8 JSON；连接始终关闭，不读取环境代理。
- wire 子集的 `BinaryFile` 保留 field_name/file_name/content/file_size 与 getstate/setstate；dumps 固定 protocol 4，loads 只面向可信 MDF 部署。只加载其中的传输定义，不启动服务、读取配置或更改网络。
- CLI 对 HTTP 的 SDK 配置参数、SDK 的 HTTP 地址参数在提交前拒绝。运行记录新增 transport；旧记录保留原 trace 和入口别名。HTTP 超时、连接中断、不可解码结果仍按 AmbiguousOutcome 保存，不创建 SDK 会话或自动重发。

身体服务结果的本地骨架校准、权重回迁与动作适配交接给独立 [rig-retarget](../rig-retarget/SKILL.md)；本工具的传输、状态与服务参数契约保持不变。

## 账号公开 mesh/invoke

Runtime 自动提供当前调用的对话与轮次；共享 hi3d_client 将其附加为 `X-Session-Id`、`X-Turn-Id` 请求头，标识约束与失败边界见 [Hi3D 账号传输契约](hi3d-api.md#账号-runtime-backend)。原有请求体 sessionId/turnId 保持兼容，任务指纹不包含这些关联字段。

[scripts/runtime/mdf_api.py](../mdf-api/scripts/mdf_api.py) 是受管账号模式，内部 HTTP/SDK 客户端继续保留。[完整公开能力、参数、NPZ 结构、LOD 字段与成功判定](../mdf-api/references/mesh-invoke-api.md) 和 [运行入口](../mdf-api/SKILL.md) 是唯一协议资料。

validate 校验 SCHEMA 的 14 项能力、扁平参数、文件格式/头部与大小；integer/BOOL/CHOICE 不把 bool 当 int。multipart 返回临时流/类型/长度，显式 JSON part 与图片 MIME，并以规划哈希校验实际发送字节。execute 先排他保存 UNKNOWN 意图，client.send 仅 POST 一次；HTTP 200 + 整数 code=0 + SUCCEEDED 才成功，普通2100秒、LOD7500秒。dry-run 只做离线校验。

原响应用显式物化的 hi3d_storage 私有缓存接口保存于宿主状态目录；工作区记录仅 public_record 脱敏值。download/summary 使用同一账号/环境及输出目录，仅续下载已成功的结果；LOD 用 lods 解析动态字段指针并匹配目标顺序与 actual_faces。下载逐文件保存哈希，改动/缺失不覆盖；UNKNOWN/中断从不自动重发，无公开 query。retopology 只有 model_obj 可接受 ZIP；extract-centerline/check-printability 允许纯 JSON 结论。上传变化、下载失败及缓存缺失均保留原记录；不向 CDN 附带 Cookie。

共享客户端仅在工具层通过 package.json.files 与 profile 显式物化，不做相邻 hi3d 目录导入，不物化进业务工作流。Python 3.10+ 标准库；测试用假客户端/本地合成文件验证，不调用真实服务。
