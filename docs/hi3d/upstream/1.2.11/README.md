# Hi3D Agent 1.2.11 参考快照

这些文件取自 Windows x64 安装包的 `resources/runtime/prebuilt-skills/`，按原目录结构保存。归档时的安装根为 `D:/install/Hi3DAgent`，本机复核使用 `D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/` 中的事务备份。快照收录十二个 Skill 入口，以及相关的参考文档、流程配置、评审规则和桌面执行依赖。独立归档的 P0 与 P1 资源在下文列出。Git 属性保留原文件字节，使归档文件的 SHA-256 能与安装包核对。

全量文件盘点和发行锚点见 [JSONL 清单](inventory/inventory.jsonl) · [锁定记录](inventory/inventory.lock.json) · [重跑方法](../../infrastructure/bundled-assets-and-script-tools.md#只读盘点与锁定)。

抽离范围由同一发行锁派生，包含候选池、来源复核项、环境引用和 Blender 试点。优先级清单给出 P0 基础能力的精确路径、依赖及待验证行为。 [抽离清单与重跑方法](extraction/README.md) · [P0 精确文件表](extraction/priority.md)

P0 的 14 个原件按安装目录布局归档，另有 16 个证据引用。 [归档收据](archived-p0/archive.lock.json) · [独立资源说明](../../resources/README.md)

P1 的 15 个建模、取证及验收原件按安装相对路径归档，43 项安装包证据按路径引用。 [P1 归档收据](archived-p1/archive.lock.json) · [独立资源说明](../../resources/p1/README.md) · [P1 精确文件表](extraction/p1/priority.md)

| Skill 原文 | 与 Vet3D 节点有关的内容 |
| --- | --- |
| [hi3d](prebuilt-skills/hi3d/SKILL.md) | 通用图片工具、参考图角色、请求与异步任务规则。 |
| [head-reference](prebuilt-skills/head-reference/SKILL.md) | 四视图基准、相对方向、定向修订与版本化评审。 |
| [image-to-assembly](prebuilt-skills/image-to-assembly/SKILL.md) | 部件级视图规范、提示词模板、证据优先级和修订边界。 |
| [mdf-api](prebuilt-skills/mdf-api/SKILL.md) | 桌面已有网格处理、公开能力枚举、离线校验、结果下载及恢复。 |
| [quad-flow-plus](prebuilt-skills/quad-flow-plus/SKILL.md) | 初始重拓扑后端选择、保形减密、边链约束重建及共同验收。 |
| [head-lowpoly](prebuilt-skills/head-lowpoly/SKILL.md) | 人头高模到可编辑四边面、眼口重布线、绑定和本地烘焙。 |
| [metahuman-fit](prebuilt-skills/metahuman-fit/SKILL.md) | 人头模板注册、逐角 UV 复用、本地烘焙和可选分体扩展。 |
| [scale-aware-quad-rings](prebuilt-skills/scale-aware-quad-rings/SKILL.md) | 基于冻结尺度和误差预算的四边面分区减密。 |
| [closed-quad-transition](prebuilt-skills/closed-quad-transition/SKILL.md) | 规则 4×4 四边面片的 16→15 闭合过渡和局部验证。 |
| [lowpoly-quad-face-neck](prebuilt-skills/lowpoly-quad-face-neck/SKILL.md) | 从同源高低模建立四边面基线，校准人脸与面颈语义环线。 |
| [rig-retarget](prebuilt-skills/rig-retarget/SKILL.md) | 合格 LOD 复用、休止姿态源网格、绑定交接和动作验收。 |
| [hi3d-game-demo](prebuilt-skills/hi3d-game-demo/SKILL.md) | 游戏需求检查点、按用途设定分档预算、资产与目标设备验收。 |

快照还包含 [portrait-reconstruction 的分发入口](prebuilt-skills/.dependency-portrait-reconstruction/REFERENCE.md)及其执行契约，用于查证上层工作流怎样调用 `head-reference`。归档保留原件字节及其相对链接。未随快照收录的同目录或跨目录依赖、资源和脚本，可在上述安装包事务备份中按原相对路径查阅。

下列两份原文由 `image-to-assembly/SKILL.md` 的桌面分支直接引用，归档文件和安装包副本的 SHA-256 一致。

| 归档依赖 | SHA-256 |
| --- | --- |
| [桌面 Runtime 执行约定](prebuilt-skills/.dependency-run-tools/references/desktop-runtime.md) | `fceed0c4926403675541b6c071865bc643c5ac7f4cf7e20630f2a839f2f015d5` |
| [宿主编排提示](prebuilt-skills/.dependency-pcg-view/references/host-orchestration.md) | `91ab9ed0b69bd5b9b881ac364eb180857e79ef0303b0ad13672358f6a02bc500` |

MDF Skill 与其直接引用的公开接口契约均按原字节归档。

| 归档文件 | SHA-256 |
| --- | --- |
| [MDF Skill 入口](prebuilt-skills/mdf-api/SKILL.md) | `925135ef7dd9ddeedc9789263a3a79f31069b57ef4fae5b53bbbc3f6be3d502e` |
| [桌面网格接口契约](prebuilt-skills/mdf-api/references/mesh-invoke-api.md) | `fd5233d32594fb95df308055a1d319023466c268f1b6e8266ccdf00e4a1dd2b6` |

## 重拓扑与边流验收的随包证据

以下 Skill 入口、流程配置和直接相关参考文档均按原字节归档。后端探测、原生网格测量和业务验收的可执行脚本可在上述安装包路径中复核。

| 归档文件 | SHA-256 |
| --- | --- |
| [四边通 Plus 入口](prebuilt-skills/quad-flow-plus/SKILL.md) | `2e94be8dd6d126c987660fde87029c4e0175be56d96c199dc90ce6910f42df8d` |
| [四边通 Plus 工作流架构](prebuilt-skills/quad-flow-plus/pcg/architecture.yaml) | `931f1472e4752d8357be15efb52fd4d92051ce95148a08f1dd09a374ea49f38c` |
| [四边通 Plus 路线配置](prebuilt-skills/quad-flow-plus/pcg/routes.yaml) | `c867d258d5b40398b9b953babcac2f79a24459ca43e332b674d51d1dfb09192e` |
| [初始重拓扑方案与插件交接](prebuilt-skills/quad-flow-plus/references/hi3d-initial-remesh.md) | `b503c4a91e69fcdd037122f751fb4e8f729ffc6466ad2da5cf9d5bde353967f8` |
| [可靠边链约束的预算重建](prebuilt-skills/quad-flow-plus/references/hi3d-budget-rebuild.md) | `4fc3f7381a28b1cb27956d08bd2ea4eaeb0791bdf65f0dbcb2b18d37916cb9bc` |
| [人头低模入口](prebuilt-skills/head-lowpoly/SKILL.md) | `6045d89151b936ad46f727ca6cab91198688c04a966c90541843ffd95889052e` |
| [人头重拓扑与本地烘焙交接](prebuilt-skills/head-lowpoly/references/retopology-api.md) | `b6d33c74723ad25207943681df36cb539901b081a9c2877144f596b7ae71bfd5` |
| [尺度感知四边环带入口](prebuilt-skills/scale-aware-quad-rings/SKILL.md) | `7411d83b01b64bcc099e324468c4c95733fb0a62188b2ef6bb22b97bebff070f` |
| [闭合四边过渡入口](prebuilt-skills/closed-quad-transition/SKILL.md) | `86a19c54e79642507fc49dcaa7f783efdcb09c6046e52f75d5fb2b4860b6b5ac` |
| [基础四边面与面颈校准入口](prebuilt-skills/lowpoly-quad-face-neck/SKILL.md) | `20d342d1806562623dab0630e01866dd6d8d78efe73d94aa794cc2df4d6d0f62` |

## MetaHuman 的 UV 交接证据

默认流程沿用注册模板的 UV。明确选用分体扩展时，桌面交接参考说明缺少 UV 的网格怎样计划 MDF 预检及交接实际返回的 UV 网格。以下两份原文均与安装包副本的 SHA-256 一致。

| 归档文件 | SHA-256 |
| --- | --- |
| [MetaHuman 专项入口](prebuilt-skills/metahuman-fit/SKILL.md) | `0a942ac38ec682fbc60b259dcb14f04ad3c4be49a6b2e346d2efddebf8d5087a` |
| [桌面运行时交接](prebuilt-skills/metahuman-fit/references/runtime-handoff.md) | `924df06cccfa1198c55ecb36034aff5f00780d87d4d4f037c7e8f76240558a03` |

## 贴图迁移与烘焙的随包证据

下列原文覆盖带来源对应的贴图复用、面颈局部融合和 Blender 烘焙契约。执行脚本按文中的相对路径在安装包中复核。

| 归档文件 | SHA-256 |
| --- | --- |
| [本地烘焙依赖入口](prebuilt-skills/.dependency-texture-bake/REFERENCE.md) | `ffac12bf63bfe534be45eb01be61a7629be61c2427b5ffc0cef4edc01197106b` |
| [本地烘焙核心契约](prebuilt-skills/.dependency-texture-bake/references/contract.md) | `7aa4ea36fb5fee7fed74028dc21f07587e60e40bdfd757df7eb2d7a358564153` |
| [面颈局部处理与贴图融合规程](prebuilt-skills/lowpoly-quad-face-neck/references/method.md) | `8382af47ebaf20a0a32efbe767fb981db0dbb7c1deb306354964a1f30e73e2ad` |
| [头发与头部分件依赖入口](prebuilt-skills/.dependency-head-hair-split/REFERENCE.md) | `1f84e917b3b1896ecc28afe14c251a85cc3a17d926d4bf5e7ef53e4c83dc7696` |

## 人像已有网格贴纹理的随包证据

人像专项通过执行参考和 `texture_only` 路线声明，规定已验收正面图、冻结网格及纹理作业的交接。以下文件均与安装包副本的 SHA-256 一致。

| 归档文件 | SHA-256 |
| --- | --- |
| [人像重建入口](prebuilt-skills/.dependency-portrait-reconstruction/REFERENCE.md) | `198b96a8bb97efda7fd72909fca4a2147445482cb80540a4d7bcf038e29ac7ec` |
| [执行与纹理交接参考](prebuilt-skills/.dependency-portrait-reconstruction/references/execution.md#纹理生成) | `4a0f17879e659263aba9e2c628c152cf31aa4b769bcfb3d98e1b778a5f5ebd8f` |
| [人像重建条件路线](prebuilt-skills/.dependency-portrait-reconstruction/pcg/routes.yaml) | `01146efd84742fab7e056d98dc08de880d49b3f658ad86b5e3310203ccadb5e7` |

## 确定 LOD 源网格与分档预算的随包证据

以下原文覆盖已有 LOD 复用、新派生源网格、面数与贴图预算、设备与动作验收。桌面 Runtime 调用使用公开 MDF 契约。动画参考中的独立 `mdf-call` 示例属于非 Runtime 路线。每份归档的 SHA-256 均与安装包副本一致。

| 归档文件 | SHA-256 |
| --- | --- |
| [动画绑定与重定向入口](prebuilt-skills/rig-retarget/SKILL.md) | `8237ec25a4cf0b06a49723f21c168eee36f5848f64256fd357993d0a2b04f17d` |
| [桌面 LOD 调用与交接](prebuilt-skills/rig-retarget/references/runtime-mesh-lod.md) | `534be05e5826dada4ad5f64318c0115166a2efc432ff17a5a87fd501bd309ce8` |
| [独立 LOD 调用及本地处理](prebuilt-skills/rig-retarget/references/mesh-lod.md) | `76d1dab3449d71c205fb81b6c9f4f1d9a7eed3023334582df42efc0d530f2193` |
| [桌面绑定与服务代理](prebuilt-skills/rig-retarget/references/runtime-service-rig.md) | `eaef6f79f396d4f81e0f79c2ed1e2670e3f9eba5707c5c96add4c0c9082b630f` |
| [游戏角色资产交付](prebuilt-skills/rig-retarget/references/game-delivery.md) | `c68eabbef83a8aa5c8752d7a4854d92d93923b7e256e97548d8d6dfa9c19a369` |
| [绑定与动作验收](prebuilt-skills/rig-retarget/references/validation.md) | `1293d44603be48235d74f2c7bb0ae57241444234676160dcf50522d7f44ebcd2` |
| [游戏展示入口](prebuilt-skills/hi3d-game-demo/SKILL.md) | `009ee0e897d6a8c80ad9b14faccdd87c02ca7faa446bd6e3c6b9861b99bf9c74` |
| [游戏资产与运行时接入](prebuilt-skills/hi3d-game-demo/references/assets.md) | `ae26cbe6f272735c8eb47bf7e3114c1acdca3e21a8781c80efa8b6b1765d7509` |
| [游戏需求、素材与玩法约定](prebuilt-skills/hi3d-game-demo/references/hi3d-game-brief.md) | `34149ba60496575438a01c9f28f465337a862f1542154370befee067b8b9de39` |
| [游戏迭代、验收与交付](prebuilt-skills/hi3d-game-demo/references/validation.md) | `4691fa2f39f20a3f8034818ec63ac71ca7eefd94724899ef5bb1ba06f8b7c4b0` |
| [游戏检查点与资产复用路线](prebuilt-skills/hi3d-game-demo/pcg/routes.yaml) | `7868d23b28beb61aad35514adda2f2dc965ce7b5755d1f854fede60d6b60af3b` |

请求和实现示例见 [生成新视角](../../atomic-nodes/generate-new-view.md)与[编辑已有视角](../../atomic-nodes/edit-existing-view.md)。本目录用于保存逆向证据，Vet3D 的业务节点以各自的技术说明为准。
