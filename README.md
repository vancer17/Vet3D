# Vet3D
Agent-powered pipeline for generating animatable 3D animal assets from images, built for veterinary and animal-science workflows

## Development

Vet3D 的目标是供 BFF 调用的后端服务。当前已完成 [L0-01 最小应用入口与装配骨架](docs/vet3d/implementation/work-items/L0-01.md)、[L0-02 身份与关联](docs/vet3d/implementation/work-items/L0-02.md)、[L0-03 文件、来源、单位与视图契约](docs/vet3d/implementation/work-items/L0-03.md)和 [L0-04 独立事实、结果与交接守卫](docs/vet3d/implementation/work-items/L0-04.md)的原始条目，采用独立 CPython 3.14 环境、uv 和 Hatchling；运行命令、当前范围与验证记录见各实施卡。

[L0-05 最小生成端口与装配探针](docs/vet3d/implementation/work-items/L0-05.md)及本轮准备语义修订已完成，M0 按该卡的最小消费链范围放行。新的非交互 `vet3d-contract-probe` 与既有 `vet3d-demo` 的使用范围、命令及证据由该卡维护；探针不代表真实模型或 BFF 已接通。

[L1-01 受管工作区与持久注册](docs/vet3d/implementation/work-items/L1-01.md)已完成最小真实存储、宿主装配及当前 Debian 验收，按实施卡向 L1-02 放行。接口、创建恢复及后续执行隔离的边界由该卡维护，选择理由见 [ADR 0006](docs/vet3d/adr/0006-workspace-storage-and-execution-boundaries.md)。

[L1-02 受管文件保存与实际观察](docs/vet3d/implementation/work-items/L1-02.md)已完成当前 Debian 范围验收，真实文件、副作用和恢复范围由该卡维护；本项未前移产物登记或发布。选择理由见 [ADR 0007](docs/vet3d/adr/0007-managed-file-storage-boundaries.md)。

[L1-03 受管资源与固定快照读取](docs/vet3d/implementation/work-items/L1-03.md)已完成当前 Debian 范围验收，当前契约和验证记录由该卡维护；资源安装、解释器可执行性与业务验收分别交接。选择理由见 [ADR 0008](docs/vet3d/adr/0008-managed-resource-snapshots.md)。

[L1-04 单资产持久目录与真实 ArtifactAccess](docs/vet3d/implementation/work-items/L1-04.md)已完成本期范围，登记、重开对账及文件 I/O 与短元数据调用的并发边界由该卡维护；实际验证见该卡第 7 节，M1 尚未放行。选择理由见 [ADR 0009](docs/vet3d/adr/0009-single-artifact-catalog.md)。

[L1-05 统一配置、关联诊断与 Docker 宿主](docs/vet3d/implementation/work-items/L1-05.md)已完成本期范围。当前配置、读取与恢复契约见实施卡；[Docker 运行导航](docker/README.md)提供仅开发／生产两套编排及有限命令。选择理由见 [ADR 0010](docs/vet3d/adr/0010-settings-diagnostics-and-docker.md)，BFF 与通用脚本执行仍由后续条目接入。

[L2-01 固定资源要求与有限环境探测](docs/vet3d/implementation/work-items/L2-01.md)已完成本期范围；当前接口、恢复和实测范围由该卡维护。决定理由见 [ADR 0011](docs/vet3d/adr/0011-bounded-environment-probes.md)。

[L2-02 阶段 A](docs/vet3d/implementation/work-items/L2-02.md)已有有限实验实现和证据，当前实施范围仅验证模型、成熟运行时与任务环境组合的小型自主任务、原生反馈、连续性及运行边界；产品接入另行规划。基模家族已确定为 Qwen，`qwen3.7-plus` 直连样本仍有未完成任务，历史结果不因范围收敛改判。正式资产交接、真实动物质量和生产验收不属于阶段 A。决定理由及保留的原生唯一循环、撤销执行冻结／字节追溯边界见 [ADR 0012](docs/vet3d/adr/0012-native-agent-runtime-integration.md)。

[宿主与装配决策](docs/vet3d/adr/0001-service-host-and-composition.md)记录技术选择及边界。Hi3D 参考工具与产品实现分别维护。

## Documentation

[Hi3D Agent workflow and Vet3D handoff](docs/hi3d/README.md)

[Vet3D Agent 分层架构与实施路线](docs/vet3d/implementation/README.md)

[Hi3D 1.2.11 reference archive](vendor/hi3d/1.2.11/README.md) · [Debian portability and verification](docs/vet3d/reference-portability.md)
