# MDF 服务契约

完整服务说明随 [service-select](../../.dependency-service-select/REFERENCE.md) 独立提供；[mesh-watertight](mesh-watertight.md) 的唯一正文及请求示例由 mdf-call 维护，服务选择包物化同一正文。

- [全部服务的功能、输入输出速查](../mdf_list.md)
- [按效果选择原子](../../.dependency-service-select/references/catalog.md)
- [共用 BinaryFile、数组、响应与部署约定](../../.dependency-service-select/references/mdf/README.md)

[mesh-lod](mesh-lod.md)、[auto-rig](auto-rig.md) 和 [sapiens2](sapiens2.md) 页面保留导航链接，完整正文只维护在 service-select 原子能力的 references 中；每页标明来源与契约覆盖范围。auto-rig 的底层版本已固定，但部署适配器尚未发布固定提交，其 SDK 队列/TCP 路径不能等同于默认 HTTP 网关路由。部署参数、本地文件 API 与 MDF 业务请求分开，不能互相直接传递。
