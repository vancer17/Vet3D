<!-- 文件信息：L1-05／L2-01 两套 Docker 编排的操作导航。
作用：提供构建和有限探针命令；配置、环境观察与恢复契约由实施卡统一维护。 -->

# Docker 运行入口

当前支持范围、配置覆盖顺序、诊断读取及恢复边界见 [L1-05 实施卡](../docs/vet3d/implementation/work-items/L1-05.md)。本目录只维护开发与生产两套 Compose，使用同一 Dockerfile 的 `dev`／`prod` 阶段。

两套镜像提供 Linux x86_64 的 Python 与 Blender CPU 探针候选，具体观察范围和判定规则见 [L2-01 实施卡](../docs/vet3d/implementation/work-items/L2-01.md)。Blender 从官方发布目录下载，构建时核对 Dockerfile 固定的 SHA256；不使用 Hi3D Windows 二进制或宿主安装。模板中的解释器路径仅表示候选配置，安装成功不能替代实际检查。其他架构、GPU 和渲染质量未包含在当前支持范围。

默认命令是实际运行后退出的 `vet3d-operations-probe`。`--initialize` 显式建立空白存储；不带该参数只打开已有存储。当前没有 BFF HTTP 服务或健康接口，`compose up` 也不会保持一个常驻服务。镜像是可信宿主的运行环境，不是执行 LLM 生成脚本的沙箱。

以下命令从仓库根目录执行。宿主绑定目录必须事先存在，数据目录和日志目录须由容器 UID 拥有，权限为 `0700`。不要对已有数据递归更改所有者或放宽权限来规避校验；不同环境使用独立目录。

开发环境首次准备和运行：

```bash
export VET3D_DOCKER_UID="$(id -u)"
export VET3D_DOCKER_GID="$(id -g)"
export VET3D_DEV_ROOT="$PWD/.cache/docker/dev"
install -d -m 0700 "$VET3D_DEV_ROOT/data" "$VET3D_DEV_ROOT/inputs" \
  "$VET3D_DEV_ROOT/resource-source" "$VET3D_DEV_ROOT/logs"
docker compose -f docker/compose.dev.yaml config --quiet
docker compose -f docker/compose.dev.yaml build
docker compose -f docker/compose.dev.yaml run --rm vet3d \
  vet3d-operations-probe --config /etc/vet3d/config.yaml --initialize
docker compose -f docker/compose.dev.yaml run --rm vet3d
```

开发镜像保留测试工具，源码以只读方式映射到 `/app/src`，虚拟环境位于镜像的 `/opt/venv`，不挂载宿主 `.venv`。可以用同一编排运行 `python -m unittest discover -s tests/runtime`；测试使用容器临时目录，不覆盖现有数据。

生产镜像只保留非 editable 安装的 wheel 及运行依赖，用户固定为 `10001:10001`。以下目录准备命令仅用于新的空白位置；真实部署也可由已有运维流程创建同等所有权的目录。

```bash
export VET3D_PROD_ROOT=/srv/vet3d/prod
sudo install -d -m 0700 -o 10001 -g 10001 \
  "$VET3D_PROD_ROOT/data" "$VET3D_PROD_ROOT/inputs" \
  "$VET3D_PROD_ROOT/resource-source" "$VET3D_PROD_ROOT/logs"
docker compose -f docker/compose.prod.yaml config --quiet
docker compose -f docker/compose.prod.yaml build
docker compose -f docker/compose.prod.yaml run --rm vet3d \
  vet3d-operations-probe --config /etc/vet3d/config.yaml --initialize
docker compose -f docker/compose.prod.yaml run --rm vet3d
```

`VET3D_DEV_CONFIG`／`VET3D_PROD_CONFIG` 可以指定用户维护的 YAML 文件，只读挂载到 `/etc/vet3d/config.yaml`；仓库模板不被应用覆盖。Compose 的 `.env` 用于替换编排变量，并不会自动成为应用环境。应用环境覆盖须显式传入，例如 `compose run --rm --env VET3D_WORKSPACES__MAX_FILE_OPERATIONS=3 vet3d`。应用不自动搜索 `.env`，避免同一文件被 Compose 与应用重复加载。

检查已安装的固定资源时，在原存储重开命令中传入资源键和清单原指纹。以下三个值必须来自实际安装结果，不使用 `latest` 或从资源内容猜测：

```bash
docker compose -f docker/compose.dev.yaml run --rm vet3d \
  vet3d-operations-probe --config /etc/vet3d/config.yaml \
  --check-environment "$VET3D_RESOURCE_KEY" \
  --snapshot-sha256 "$VET3D_SNAPSHOT_SHA256" \
  --snapshot-size "$VET3D_SNAPSHOT_SIZE"
```

生产环境将 Compose 文件替换为 `docker/compose.prod.yaml`。有限命令完成后退出，不执行被检查的资源脚本，也不安装依赖。宿主机的观察不能作为容器内环境的通过证据；未来隔离执行环境也必须在其实际上下文重新核对。

两套编排当前不需要外部网络，所以使用 `network_mode: none`，并设置只读根文件系统、有限临时目录、CPU／内存／进程数限制和退出等待时间。未来网关接入时由对应条目设置所需网络；这些部署限制不改变业务协议。配置、输入和资源源目录只读挂载；数据及诊断目录可写。Docker `local` 驱动管理容器 stdout/stderr 的轮转，应用自己的诊断文件由单独的写入器管理，不对同一文件设置两个轮转者。

宿主当前尚未接入多副本存储，不能同时启动多个实例写同一个受管根。单实例的根所有权不限制后续不同执行环境的建模并行。

构建使用按摘要固定的官方 CPython、uv 镜像与 Blender 归档，身份统一维护在 Dockerfile；Debian 原生动态库通过官方仓库安装。升级由显式修改制品身份和重新验证完成。参考：[Blender 官方发布目录及校验文件](https://download.blender.org/release/Blender4.5/)、[uv 的 Docker 安装方式](https://docs.astral.sh/uv/guides/integration/docker/)、[Compose 绑定目录参数](https://docs.docker.com/reference/compose-file/container-spec/#volumes)、[Docker local 日志驱动](https://docs.docker.com/engine/logging/drivers/local/)。具体本机验证结果统一记录在实施卡，不将容器配置视为不可信代码隔离证明。

[L2-02 阶段 B](../docs/vet3d/implementation/work-items/L2-02-B.md)的 `vet3d-agent-probe` 当前从受信 Debian 宿主运行，按需创建有限任务容器，并使用明确的既有本地镜像与 Codex 发行目录。上述开发／生产 Compose 没有 Docker 管理接口及该入口所需部署资料，不能据其启动成功宣称 Agent 已托管；本期未增加第三套 Compose，也未把管理 socket 挂进应用或任务容器。
