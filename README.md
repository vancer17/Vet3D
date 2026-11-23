# Vet3D
Agent-powered pipeline for generating animatable 3D animal assets from images, built for veterinary and animal-science workflows

## Development

Vet3D 的目标是供 BFF 调用的后端服务。当前已完成 [L0-01 最小应用入口与装配骨架](docs/vet3d/implementation/work-items/L0-01.md)、[L0-02 身份与关联](docs/vet3d/implementation/work-items/L0-02.md)、[L0-03 文件、来源、单位与视图契约](docs/vet3d/implementation/work-items/L0-03.md)和 [L0-04 独立事实、结果与交接守卫](docs/vet3d/implementation/work-items/L0-04.md)的原始条目，采用独立 CPython 3.14 环境、uv 和 Hatchling；运行命令、当前范围与验证记录见各实施卡。

[L0-05 最小生成端口与装配探针](docs/vet3d/implementation/work-items/L0-05.md)及本轮准备语义修订已完成，M0 按该卡的最小消费链范围放行。新的非交互 `vet3d-contract-probe` 与既有 `vet3d-demo` 的使用范围、命令及证据由该卡维护；探针不代表真实模型或 BFF 已接通。

[L1-01 受管工作区与持久注册](docs/vet3d/implementation/work-items/L1-01.md)已完成设计交接，产品仍未实施。身份关联、创建恢复及后续执行隔离的边界由该卡维护，选择理由见 [ADR 0006](docs/vet3d/adr/0006-workspace-storage-and-execution-boundaries.md)。

[宿主与装配决策](docs/vet3d/adr/0001-service-host-and-composition.md)记录技术选择及边界。Hi3D 参考工具与产品实现分别维护。

## Documentation

[Hi3D Agent workflow and Vet3D handoff](docs/hi3d/README.md)

[Vet3D Agent 分层架构与实施路线](docs/vet3d/implementation/README.md)

[Hi3D 1.2.11 reference archive](vendor/hi3d/1.2.11/README.md) · [Debian portability and verification](docs/vet3d/reference-portability.md)
