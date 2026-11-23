# 官方接口来源与离线资料

Engine API 以 [Creator Hub Engine reference](https://create.roblox.com/docs/reference/engine) 中对应类的参数、返回值、运行侧、Security、Deprecated 与继承链为准；Open Cloud 以 [Cloud reference](https://create.roblox.com/docs/cloud) 和 Place Publishing 指南为准。不能把普通 Script、插件、Command Bar 或外部 HTTPS 的权限混为一谈。

本次会话交付源码可证明使用了接口，但不能证明作者当时具体阅读了哪一页。这里列出的是整理时核对的官方来源，不虚构历史浏览记录。源码中的历史用法若与文档冲突，以当前受支持契约修正，保留版本差异说明。

## 完整相关文档快照

- 作者/维护者：Roblox / creator-docs contributors。
- 上游：[Roblox/creator-docs](https://github.com/Roblox/creator-docs)。固定 revision：`4fc8478587ee7c1a412403d76baff4d0ede578d4`。
- [完整文本快照 ZIP](hi3d-roblox-official-docs.zip)：选中页面的完整原始 Markdown/YAML 与原 LICENSE，未改写，保持上游目录。按用户要求保存完整相关文档；不是整个 Creator Hub 网站的离线镜像。
- [逐文件来源清单](hi3d-doc-sources.json)：列出各文件的固定版本 URL、许可证和未修改声明。ZIP 内含 CC BY 4.0 许可证，原作者署名与来源保留。新编写的本 skill 说明与上游原文分开。
- 上游文档的站内链接、图片、视频、特殊组件和其他类引用未全部随包下载；离线查原文时可读其文本，完整视觉展示和最新政策请用在线页面。不要把 ZIP 当作可直接运行的网站。

覆盖范围：实例/服务/层级、模型与变换、WorldRoot 射线查询、Parts/MeshPart、玩家/角色/工具、RemoteEvent/提示交互、容器与生命周期、输入/相机/GUI、灯光、TextChatService 与频道/界面、基础数据类型和 task；另含 Studio 导入与测试、建模/纹理规范、单位、流式加载、性能、客户端服务端安全、聊天、Place 文件与发布、API Key、内容问卷指南，以及 Universes API v1 的完整 JSON 接口定义。

## 按任务查阅

| 任务 | 官方入口 |
| --- | --- |
| 服务端/客户端与数据模型 | [Client-server](https://create.roblox.com/docs/projects/client-server)、[Data model](https://create.roblox.com/docs/projects/data-model) |
| 远程事件及不可信客户端 | [Remote events](https://create.roblox.com/docs/scripting/events/remote)、[Client-server boundary](https://create.roblox.com/docs/scripting/security/client-server-boundary) |
| 资产与单位 | [3D Importer](https://create.roblox.com/docs/studio/importer)、[Units](https://create.roblox.com/docs/physics/units) |
| 聊天 | [In-experience text chat](https://create.roblox.com/docs/chat/in-experience-text-chat)、[TextChatService](https://create.roblox.com/docs/reference/engine/classes/TextChatService) |
| 测试与性能 | [Testing modes](https://create.roblox.com/docs/studio/testing-modes)、[Performance design](https://create.roblox.com/docs/performance-optimization/design)、[Hardware testing](https://create.roblox.com/docs/performance-optimization/test-on-hardware)、[Streaming](https://create.roblox.com/docs/workspace/streaming) |
| 首次发布与公开 | [Publish experiences and places](https://create.roblox.com/docs/production/publishing/publish-games-and-places)、[Content maturity](https://create.roblox.com/docs/production/promotion/content-maturity) |
| 已有 Place 自动更新 | [Place Publishing](https://create.roblox.com/docs/cloud/guides/usage-place-publishing)、[API keys](https://create.roblox.com/docs/cloud/auth/api-keys)、[Universes API v1](https://create.roblox.com/docs/reference/cloud/universes-api/v1) |

## 更新规则

执行任务时只复核将用到的当前接口/政策，不每次下载全部资料。维护快照时固定新的上游 commit，完整保留相应原文件与许可，同步 ZIP、清单、接口地图和受影响模板/测试；不得仅修改 revision 而保留旧文件。上游原文件之间的引用不是本包执行依赖，按需在线补查。无真实服务验证时明确区分文档核对、离线模拟与线上实测。
