# MDF3 服务部署工作流

[独立 AI 入口](../REFERENCE.md)将现有算法封装成本机可测试的 MDF3 服务。
部署专属资源由 `workflows/mdf-deploy/` 维护，共享资源按 package.json 物化；本页记录实现映射，执行契约由下文链接的随包资料提供。
与 `mdf-call` 的边界：后者负责已部署服务的通用业务调用；本工作流负责服务实现、部署及
同 SDK 的直接队列/TCP 联调，不复制 generic-forward 客户端或其 wire 协议。

## 依据、前提与保留能力

从已实施的常驻推理服务封装和 `inference-service-scaffold` 提炼路径 API、BinaryFile
契约、模型生命周期、两层 Docker、权重外置、容器内测试、输出内容验收与依赖排障。
不迁入具体算法、个人路径、私有配置、内部地址、凭据、单次部署记录或隐式 CI/push 行为。
必要技巧已在随包参考中重述，使用时不依赖该来源 skill。

框架接口基线为完整 MDF3 3.2.1 的 `AlgoWorker/ServiceBase/ServiceInvokeSession`，
源码提交 `8af6e48ab048219ab61ecca9f87272624e15f674`。这是兼容性来源，不是“最新版”声明。
SDK 与算法/权重由使用者通过获授权来源提供；独立工作流不意味着不需要框架依赖、
Nacos/TaskQueue 或当前机器的 GPU/runtime。CPU 示例不代表真实模型适配已自动完成。

运行要求 Python 3.10+、完整 MDF3 和 PyYAML；部署为 Linux Docker，GPU 算法追加
匹配的 NVIDIA 驱动/容器运行时与算法依赖。SDK 安装/源码装配方式见
[脚手架说明](starter.md)，配置和回调网络前提见
[本机部署](deployment.md)。没有其他仓库 skill 的隐式依赖。

## 代码文件与原子契约

生成器不执行生成结果。模板在复制后的服务项目中运行，路径输入/计算/服务协议各自分离。

| 文件 | 原子接口与行为 |
| --- | --- |
| [scripts/scaffold.py](../scripts/scaffold.py) | `scaffold(output) -> Path`：将随包服务模板复制到不存在的目标；拒绝既有路径和模板 symlink，忽略缓存；无下载/配置读取/进程启动。`main()` 解析 `--output` 并提示下一步。复制 I/O 错误可能留下部分目标，必须审阅后使用新目录重试，不自动删除用户路径。 |
| [algorithm.py](../assets/service/algorithm.py) | `Session(model_dir, device)`：显式启用的 CPU 文本参考实现，真实项目唯一算法替换点。`validate_options(dict)` 严格解析 uppercase；`infer(source,target,options)` 读写 UTF-8；`validate_output(...)` 逐字比较返回字符数；`close()` 标记关闭。真实替换必须在构造器加载模型并在 close 释放自有资源。 |
| [API.py](../assets/service/API.py) | `infer(session,source,target,options) -> dict`：校验路径/后缀/非空和参数，在输出同文件系统临时导出，业务回读通过后原子发布，失败保持原正式文件；不创建模型、不依赖 MDF3。 |
| [run.py](../assets/service/run.py) | `main()`：输入/输出路径、JSON options、模型目录和设备 → 创建 Session → 共享 API → JSON 摘要，finally close。参数错误/推理异常非零退出；示例无权重，不据此声称完成真实模型检查。 |
| [service.py](../assets/service/service.py) | `validate_request(data,session,max_bytes)` 返回 BinaryFile 和规范 options；严格类型、字段名、basename、后缀及实际长度检查。`ServiceWorker.init` 常驻 Session，`process` 请求级临时文件与 API 转发，`shutdown` 幂等关闭。`main` 用显式服务/环境/group/端口/配置启动 ServiceBase，单 worker/puller、ready 等待、有限任务超时与不可恢复 CUDA 退出规则。 |
| [config_check.py](../assets/service/config_check.py) | `validate_config(mapping)` 约束专用测试配置：关闭通知、不含 TOS/Kafka、Nacos/队列存在、URL 不内嵌认证/query、heartbeat 路径/间隔匹配。`check_config(path)` 仅供授权运行进程读取配置，压制可能引用 YAML 私密行的解析异常，不输出内容、不复制文件；不是完整框架 schema 或秘密扫描器。 |
| [healthcheck.py](../assets/service/healthcheck.py) | `check(root='/tmp/mdf-health',max_age=30) -> bool`：ready 文件存在、heartbeat mtime 在 30 秒内；OSError 由 CLI 转为失败退出。反映初始化与主进程存活，不代表实时 GPU/队列全面健康。 |
| [smoke.py](../assets/service/smoke.py) | `require_result(dict)` 校验 success/status/BinaryFile/安全返回名；`save_record(path,record)` 临时文件原子发布 JSON；`invoke_checks(client,service_name,source,options,run_dir,timeout,repeat=2)` 注入官方 SDK 等价客户端，先持久化 trace，合法调用间插入一次缺参请求，检查同一 worker/session，保存输出和最少元数据，返回目录；超时不重试。`main()` 校验配置并在 ServiceInvokeSession context 中调用。 |
| [deploy.sh](../assets/service/deploy.sh) | 检查必填变量、路径、镜像、容器名、TCP 端口；按显式选择启动本机 host-network 容器，不停止/删除/替换既有容器。只读模型/配置、非 root UID、日志轮转、临时目录、restart 策略；不自动发现 Nacos 冲突或 GPU 调度预留。 |
| [tests/test_starter.py](../tests/test_starter.py) | `StarterTests` 在临时目录验证生成器/独立 CLI、真实 SDK 类型与签名、示例显式启用、请求边界、Session 复用、失败/输出清理、配置错误不泄漏、健康标记、模拟合法/负例/超时调用；不读取真实配置或连接线上服务。 |

模板中的文件读写是服务运行产物，不发生在 skill 目录；调用方可在测试中直接注入 Session/
客户端复用 API，不需要启动全套服务。完整请求/返回契约见
[架构与契约](implementation.md)。

## 构建资源与配置接口

- [Dockerfile.base](../assets/service/Dockerfile.base) 接收 `RUNTIME_IMAGE`，
  安装 [requirements-framework.txt](../assets/service/requirements-framework.txt)
  的 3.2.1 兼容框架依赖；可用 BuildKit `package_index` secret，不包办算法 CUDA ABI。
- [Dockerfile](../assets/service/Dockerfile) 接收 `BASE_IMAGE`，白名单复制
  运行文件和用户提供的完整 `mdf3/`；构建时检查 Python/SDK，默认启动 MDF3 并配置 healthcheck。
  真实算法新增模块时必须同步 COPY/PYTHONPATH。
- [.dockerignore](../assets/service/.dockerignore) 与
  [.gitignore](../assets/service/.gitignore) 排除配置、Git、缓存、日志与权重；
  前者额外排除 SDK 构建器/示例/部署配置。不是任意外部源码的完整保密审计。
- [config.example.yaml](../assets/service/config.example.yaml) 仅结构模板，
  地址为占位符、认证为空；真实测试配置由用户在 AI 外填写并在运行时只读挂载。
- [agents/openai.yaml](../agents/openai.yaml) 提供 UI 描述及 `$mdf-deploy`
  提示；自动发现仍由目标宿主安装机制决定，文件存在不等于已经安装。

部署脚本必填环境变量为 `IMAGE_NAME/CONTAINER_NAME/SERVICE_NAME/TCP_PORT/MDF3_CONFIG/
MDF3_ENV/MDF3_GROUP/MODEL_DIR`。可选 `GPUS` 默认不挂 GPU、`DEVICE=cpu`、
`ALLOW_CPU_DEMO=0`、`SHM_SIZE=8g`、`TASK_TIMEOUT=1800`。worker 的 `MAX_INPUT_BYTES`
默认 256 MiB，可在项目运行命令中显式注入；它不是 TCP 接收前的流量限制。
CLI `--model-dir` 默认 `MODEL_DIR` 或 `/models`，`--device` 默认 DEVICE 或 cpu，options 默认空字典。
服务 CLI 所有路由参数必填；workers 仅接受 1，扩展前先实现实际资源隔离。

smoke CLI 必填 `--service-name/--config/--env/--input/--run-dir`；options 默认 `{}`，
timeout 默认 1800 秒，repeat 默认 2 且至少 2；目标运行目录必须不存在。
记录状态为 SUBMITTING → RECEIVED → TRANSPORT_VALIDATED/EXPECTED_FAILURE，
调用异常为 AMBIGUOUS；保存原 trace、不自动新建任务重试。结果内容还需独立业务验证，
脚本不会写业务 VALIDATED。SDK 的同 hash 容灾重推及不确定状态边界见随包部署说明。

## 副作用、限制与维护验证

脚手架创建只写新目录；CLI 写指定产物；部署启动明确本机容器并经配置注册/拉取队列；
smoke 实际部署使用会提交多个测试任务、启动临时 callback TCP 并写新运行目录。
只有当前任务授权覆盖这些动作时执行，不能将 skill 维护测试变成真实线上测试。
默认无通知、失败转储、TOS/Kafka 上传或镜像/代码发布；不得修改共享基础设施。

协议和命令操作只在随包 [部署说明](deployment.md) 维护，
业务适配和资源回收在 [实现说明](implementation.md)，
分层验收与故障定位在 [验证说明](verification.md)。
不在此复制协议正文或保存具体运行报告。

维护时按入口打包约定在仓库外物化完整工作流分发目录，使用 Python 3.10+、完整 MDF3 3.2.1 和 PyYAML
执行随包 unittest、生成器 CLI、生成后的离线文本 CLI；Dockerfile 用同版本完整 SDK
构建/import 冒烟，Shell 做语法和目标边界检查。模拟客户端只验证适配行为，不能代替真实
Nacos/队列/GPU/业务质量验收。目标 AI 自动发现、其他 SDK 版本和任意用户算法需要在
其目标环境分别确认；不把静态元数据检查或已有案例表述成对所有环境的部署保证。
