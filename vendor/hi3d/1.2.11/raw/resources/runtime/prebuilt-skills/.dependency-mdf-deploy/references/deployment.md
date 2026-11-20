# 本机 Docker 与 MDF3 部署

## 配置与网络前提

使用用户提供的专用配置文件路径，只检查文件是否存在及挂载权限；AI 不读其内容、
不从其他服务配置提取密码、也不在宿主打印环境变量。用户可在 AI 外按
[无凭据模板](../assets/service/config.example.yaml) 填写 Nacos/TaskQueue 的当前测试环境值。
配置存于服务/skill 仓库外、权限仅部署账户可读；以只读文件挂载供授权运行进程消费。
必须关闭 `feishu.enabled`，不要携带 TOS/Kafka 配置。仅关闭 failure_feishu_enabled
不足以关闭框架其他告警。模板 `config_check.py` 会拒绝不符合该测试策略的配置。

MDF3 3.2.1 用显式 `config_path=<文件>`；`ConfigManager.from_environment` 的目录发现
机制不是同一参数。用 `--config /config/mdf.yaml` 消除歧义；`--env` 与实际 Nacos namespace、
队列环境、group 必须一致。不要只改 env 字符串就认为已经隔离了生产队列。

```text
调用容器的 SDK/临时 Controller TCP ──push──> TaskQueueHttp
本机 ServiceBase                   ──pull──> TaskQueueHttp
本机 ServiceBase                   ──fetch/result TCP──> 调用容器
本机 ServiceBase                   ──register/heartbeat──> Nacos
```

两个方向都要可达：能连队列不等于服务能回连调用者。Linux `--network host` 是本机联调
的直接方式，但不是业务服务的 HTTP API；不需要中控 `/generate_model` 网关。
`ServiceInvokeSession` 会开放临时回调 TCP 端口，服务 TCP 是另一端口。多网卡/NAT 下核对
SDK 实际通告的 IP 与路由；不要仅发布固定服务端口却遗漏回调端口。
如果不能提供回调可达性，报告网络前提缺失；使用既有网关是另一种经确认的接入方案，
不能把 HTTP 健康页访问成功冒充真实 MDF3 队列调用。

MDF3 与某些算法 RPC 使用 pickle；只允许已确认的可信内网对等端，不能暴露到公网。
对指定队列可做只读 `GET /api/v1/healthz`；Nacos 列举使用当前版本 SDK 的只读查询并
仅输出本次服务的脱敏状态。不要探测全部未知服务或修改共享防火墙。

## 依赖收敛

构建前记录 Python、Torch/torchvision、CUDA、GPU 架构和编译扩展版本的组合。
已有本地父镜像能避免重新下载几十 GB，但需要验证镜像 ID/ABI；标签相同不保证内容相同。
稳定重依赖留在基础层，增补框架依赖尽量使用独立层，不让一次业务改动触发全部重装。
构建基础层只传本层必需文件；业务层排除真实权重、私有配置、日志、测试输出和 Git。

算法依赖先静态检查，再容器 import → 契约单测 → 带 GPU 内核测试 → 真实推理 → 输出回读。
`flash_attn` 能 import 不代表内核支持当前 GPU：须实际跑目标 dtype/shape，并与参考实现
比较；Hopper 专用分支在其他 GPU 上可能先 import 成功后 launch 失败。
不要硬编码某次使用的 CUDA/Torch/bpy 版本为所有算法要求。

普通 Docker build 没有 GPU；某些 demo import 就调用 `torch.cuda.get_device_name()`。
这种模块只在运行时检查，不把 build 的“无 GPU”误诊为依赖丢失。`pip check` 的真实冲突
应解决；若确定是官方 wheel 的错误平台元数据，记录影响并实测，不篡改元数据制造通过。

大 wheel 下载慢时，先比较当前授权代理/镜像与直连的可达性，不全局改代理配置。
可以把发布源校验过的 wheel 放在忽略的构建缓存，用 BuildKit bind mount 安装，
减少重复传输/缓存层；manifest 与校验规则保留，真实大文件不入 Git。
私有包源使用 secret，避免构建输出回显认证 URL；不得把缓存/模型凭据烘焙进镜像。

`# syntax=docker/dockerfile:...` 可能额外从 Docker Hub 拉取 frontend，即使父镜像已在本机。
受限网络中先核对失败的是 frontend 还是父镜像；本模板使用本机支持 `RUN --mount` 的
BuildKit frontend，不指定远端 syntax。若本机不支持，应准备受信任的兼容 frontend/构建器，
不能改为将秘密 COPY 进镜像来绕过。

## 启动脚本

以下变量必须由当前任务确定；秘密值不写入命令、skill 或报告。`MDF3_CONFIG` 是文件路径，
不是 YAML 内容；`MODEL_DIR` 和配置路径必须是绝对路径。CPU 无权重示例可以使用空模型目录。

```bash
# SERVICE_NAME / CONTAINER_NAME / TCP_PORT 必须是获授权且不冲突的测试目标。
# IMAGE_NAME、MDF3_CONFIG、MDF3_ENV、MDF3_GROUP、MODEL_DIR 同时通过环境提供。
bash "$SERVICE_DIR/deploy.sh"
docker inspect "$CONTAINER_NAME" --format '{{.State.Status}} {{.State.Health.Status}}'
docker logs --tail 80 "$CONTAINER_NAME"
```

GPU 服务设置 `GPUS=device=<宿主GPU索引>` 和 `DEVICE=cuda:0`；不默认 `--gpus all`。
只有 CPU 示例额外设置 `ALLOW_CPU_DEMO=1`。基础变量缺失、同名容器已存在、端口占用时
脚本失败而不替换。它不检查调度器资源预留、不核验 Nacos 同名实例，也不能防止端口探测
后的竞争；这些属于执行前的当前环境核对，不是脚本已实现的自动防护。

模板单 worker/puller，默认 shared memory 8 GiB、任务超时 1800 秒，均是可调整起点。
需要多 worker 时先实现设备/端口/内存隔离再放开数量限制。长请求不能使用无限 deadline；
caller timeout 包含排队与传输，需按任务预算设置并通常大于 worker 推理超时。
ready 等待时间、Docker start-period 应覆盖实测冷启动；heartbeat 的路径/文件名必须与
healthcheck 一致。`--tmpfs /tmp` 在重启时清除旧 ready；使用磁盘临时目录时要显式处理旧标记。

Docker 默认 entrypoint 启动 MDF3，离线 CLI 和 smoke 用 `--entrypoint python` 覆盖。
Docker `unless-stopped` 只重启已退出容器，不会因 health=unhealthy 自动重启。
任务超时/不可恢复 CUDA 的退出策略要真实接通；健康文件只证明模型曾 ready 且主进程
心跳正常，不能证明队列、GPU 和所有子进程持续可用。

## 官方 SDK 联调

`RUN_DIR` 须已存在并含输入；`/data/queue-check` 必须不存在。客户端不需要 GPU/模型挂载。
镜像必须与服务使用相同的完整 SDK；`smoke.py` 调用 SDK，不依赖相邻 mdf-call skill。

```bash
docker run --rm --init --network host --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$MDF3_CONFIG,dst=/config/mdf.yaml,readonly" \
  --mount "type=bind,src=$RUN_DIR,dst=/data" \
  --entrypoint python "$IMAGE_NAME" /app/smoke.py \
  --service-name "$SERVICE_NAME" --config /config/mdf.yaml --env "$MDF3_ENV" \
  --input /data/input.txt --options '{"uppercase":true}' --run-dir /data/queue-check
```

实际算法改成自己的文件/参数。脚本连续提交两次合法请求和一次缺输入请求；
检查输出 BinaryFile、相同 worker/session 以及结构化失败，只标记 `TRANSPORT_VALIDATED`。
最后必须运行独立业务验证器解码返回文件。保存每次提交前的 trace；中断标记
`AMBIGUOUS` 并停止，没有自动重试。SDK 内部可能对尚未 fetch 的任务按相同 task hash
容灾重推，这不等于业务 exactly-once；带外部副作用的算法必须自己按契约做去重。

## 停止/更新/交付

只对本次拥有且用户允许替换的明确容器停止/删除，先核对 labels、挂载和在途请求。
删除容器会丢失其可写层，模型及输出应已在外部挂载保存；不要清理共享镜像缓存或权重。
典型命令为 `docker stop -t <宽限秒数> <本次容器>`、`docker rm <本次容器>`，审阅新镜像后
再启动；脚手架不自动执行这一替换过程。有限故障检查无进展时停止重启循环并说明原因。

交付实际入口、环境/服务名、镜像、权重挂载与调用方式，说明 TCP 非 HTTP。
“只部署当前机器”不需要 registry push、CI、远端机器部署或业务工作流改动。
