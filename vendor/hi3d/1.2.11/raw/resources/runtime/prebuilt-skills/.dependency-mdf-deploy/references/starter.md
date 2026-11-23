# 使用独立脚手架

## 文件与替换边界

`scripts/scaffold.py --output <新目录>` 只复制本包 `assets/service/`，不下载、不启动容器、
不读取配置、不覆盖已有目录。空目标也应使用新路径，防止误把真实仓库当成脚手架目录。
生成目录可以脱离 skill 包使用；既有项目只合并所需文件。

| 生成文件 | 用途 |
| --- | --- |
| `algorithm.py` | 唯一业务替换点：Session 加载/推理/参数及产物验证/关闭 |
| `API.py`、`run.py` | 可复用路径 API、独立 CLI；无 MDF3 协议依赖 |
| `service.py` | BinaryFile 校验、常驻 worker、MDF3 启动与超时保护 |
| `smoke.py` | 官方 SDK 的部署联调适配，连续调用/失败契约/会话复用检查 |
| `config_check.py`、`healthcheck.py` | 专用测试配置约束、模型 ready 与心跳检查 |
| `Dockerfile.base`、`requirements-framework.txt` | 已选运行时上安装框架依赖 |
| `Dockerfile`、`deploy.sh` | 装配代码/完整 SDK、显式本机目标部署 |
| `.gitignore`、`.dockerignore`、`config.example.yaml` | 排除运行状态/秘密，提供无凭据配置结构 |

CPU 示例契约是非空 UTF-8 `.txt`，`options.uppercase` 为布尔值，默认 True；
返回转换后的 `.txt` 并逐字比较。`ALLOW_CPU_DEMO=1` 且 `DEVICE=cpu` 才能启动。
真实算法接入后更改 Session 的 `profile/input_suffixes/output_suffix` 以及业务方法，
删去仅适用于文本示例的启用门槛，保留业务所需的设备/权重校验。不要让 GPU 请求静默走 CPU 示例。

Session 约定：`__init__(model_dir, device)`、`validate_options(dict) -> dict`、
`infer(source, target, options)`、`validate_output(source, target, options) -> dict`、`close()`。
模型只在构造器加载；`validate_output` 返回可序列化、无临时路径/敏感数据的业务摘要。
可转调已有稳定 API，但不能在 `infer` 内再次加载模型。若原算法输入输出不同，修改薄适配层
并保持真实契约，不强迫所有算法变成单文件。对多文件/可选输入按架构参考补 resolver 和测试。

## 获取完整 MDF3 SDK

模板按源码装配，要求生成目录的 `mdf3/` 是完整包，包含 `__init__.py`、`algo_worker.py`、
`service_base.py`、`worker_pool.py`、`service_invoke_tool.py` 及其运行依赖。此模板接口基线为
3.2.1；来源由用户提供并固定提交，不能以同名 PyPI 包或只有 BinaryFile 的通信子集代替。

```bash
# 以下变量来自当前任务；不在通用包中保存私有 URL。
git -C "$SERVICE_DIR" submodule add "$MDF3_REPO_URL" mdf3
git -C "$SERVICE_DIR/mdf3" checkout "$MDF3_COMMIT"
git -C "$SERVICE_DIR" add .gitmodules mdf3
```

已有子模块只初始化既定指针，不默认 `--remote/--force`。本地 clone 若已包含 SDK，先核对
位置/版本/dirty 状态，不再添加重复包。源码审阅限非敏感运行文件；不要运行发布/上传脚本
来“安装” SDK，也不要复制可能带凭据的构建器。模板已排除常见构建器/示例/配置，但不是
任意仓库的秘密扫描器；按当前源树补充白名单，确认运行 import 不会被误删。

如果用户使用已获授权的 wheel/index，将 Dockerfile 的源码 COPY 改成固定版本安装，
或使用已经安装完整 SDK 的基础镜像并移除重复 COPY；一次只保留一种 SDK 来源。
私有 pip.conf 由构建进程通过 BuildKit secret 消费，AI 不读取。不要把包源凭据放到 ARG/ENV。
不要求 SDK 一定有 setup.py；顶层就是包的源码可以通过 `/app/mdf3` + `/app` PYTHONPATH 导入。

## 构建与离线验证

先选择已有、ABI 合适且有 `python`/pip 的运行时镜像；GPU 模型还要包含其实际算法依赖。
`requirements-framework.txt` 是 3.2.1 的兼容性起点，不能代替算法依赖锁或 ABI 检查。
若基础镜像已满足框架依赖，可跳过基础构建；版本冲突时按当前项目收敛，不强行覆盖 Torch。

```bash
docker build -f "$SERVICE_DIR/Dockerfile.base" \
  --build-arg RUNTIME_IMAGE="$RUNTIME_IMAGE" -t "$BASE_IMAGE" "$SERVICE_DIR"
docker build -f "$SERVICE_DIR/Dockerfile" \
  --build-arg BASE_IMAGE="$BASE_IMAGE" -t "$IMAGE_NAME" "$SERVICE_DIR"

# 真实算法改成自己的格式/参数，GPU 算法追加经确认的 --gpus 选择。
docker run --rm --init --network none \
  --user "$(id -u):$(id -g)" -e DEVICE=cpu -e ALLOW_CPU_DEMO=1 \
  --mount "type=bind,src=$MODEL_DIR,dst=/models,readonly" \
  --mount "type=bind,src=$RUN_DIR,dst=/data" \
  --entrypoint python "$IMAGE_NAME" /app/run.py \
  --input /data/input.txt --output /data/output.txt --options '{"uppercase":true}'
```

上述 CPU 示例输入由用户准备在 RUN_DIR；读回内容应是原文本的大写，不只是文件非空。
目标算法必须另外有真实业务样本和独立验证器。业务 Dockerfile 故意白名单复制文件；
新增 `runtime.py`/`model_paths.py`/算法子模块等时同步 COPY/PYTHONPATH，不依赖宿主源码挂载蒙混过关。

部署环境变量和真实队列联调命令见 [本机部署](deployment.md)，异常定位见
[验收与排障](verification.md)。这两份说明随 skill 独立提供，不需要参考其他仓库。
