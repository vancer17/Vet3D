# Vet3D
Agent-powered pipeline for generating animatable 3D animal assets from images, built for veterinary and animal-science workflows

## Development

Vet3D 的目标是供 BFF 调用的后端服务。当前已完成 [L0-01 最小应用入口与装配骨架](docs/vet3d/implementation/work-items/L0-01.md)，采用独立 CPython 3.14 环境、uv 和 Hatchling；运行命令、当前范围与验证记录见实施卡。M0 尚未完成。

[宿主与装配决策](docs/vet3d/adr/0001-service-host-and-composition.md)记录技术选择及边界。Hi3D 参考工具与产品实现分别维护。

## Documentation

[Hi3D Agent workflow and Vet3D handoff](docs/hi3d/README.md)

[Vet3D Agent 分层架构与实施路线](docs/vet3d/implementation/README.md)

[Hi3D 1.2.11 reference archive](vendor/hi3d/1.2.11/README.md) · [Debian portability and verification](docs/vet3d/reference-portability.md)
