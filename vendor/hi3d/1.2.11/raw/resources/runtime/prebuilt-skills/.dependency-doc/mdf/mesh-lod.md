# mesh-lod

对 GLB 网格按目标面数渐进减面并重烘纹理/法线，生成多个 LOD；自交保护强制启用，每次 MDF 请求在独立子进程执行，完成后返回 GLB 字节及每档元数据。无神经网络推理模型。

输入、输出、默认值、别名、效果边界和本地 API 的唯一完整说明见 [service-select 服务契约](../../.dependency-service-select/references/mdf/mesh-lod.md)。

[服务速查](../mdf_list.md) · [共用格式](README.md)
