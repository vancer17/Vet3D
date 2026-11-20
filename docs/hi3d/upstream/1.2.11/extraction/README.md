# Hi3D 1.2.11 抽离清单

[抽离清单](extraction.json)由 Windows x64、`sparc3d` profile 的发行锁派生。清单保存相对 `resources/` 的实际交付路径。文件字节数、SHA-256、源码映射及 ASAR 成员位置继续从同一路径的发行记录查询。 [发行锁](../inventory/inventory.lock.json) · [发行文件索引](../inventory/inventory.jsonl)

## 优先级与 P0 核查

[P0 精确文件表](priority.md)覆盖 6 项基础能力的 30 个交付路径，其中 14 个原件候选、16 个证据引用。逐行记录直接本地依赖、纳入依据和待验证缺口。[机器可读优先级清单](priority.json)记录发行锁、抽离清单和核查输入的摘要，并关联到每个 P0 文件的大小、SHA-256 和已有源码映射。[核查范围](priority.scope.json)是入口选择及核查结果的编辑入口。

- **本地依赖。** 已从本机安装副本逐项核对 30 条 P0 路径、3 条 P1 试点路径及 15 条显式延期路径的大小和 SHA-256。P0 的 12 个 Python 原件候选已静态检查全部 import，确认 `config_runtime.py → path_safety.py`、`hi3d-edit-job.py → process_run.py / path_safety.py`、`artifact_refs.py → session_schema.py`。动态目标由 Blender 包装器或本地进程工具的调用方提供，后续按实际选用入口继续展开。此次覆盖静态闭包，单次运行、跨轮注入和真实取消等验证保留在对应条目中。
- **完整宿主边界。** 工作区、会话、模型登记、权限和工具注册的实现可追至 `runtime.mjs` 和 `app.asar`。宿主的 `gg` 在预置 Skill 安装前检查 `prebuilt.json` 与 `runtime/support/pcg_yaml.py`，因此两者纳入 P0 宿主证据。PCG 画板投影由独立入口按需选用。积分 Hook 同样按宿主证据记录，其启动还依赖受信任的 Codex 配置和 Runtime 本机确认服务。 [工作区初始化](../../../infrastructure/workspace/create-workspace.md) · [会话与模型可见上下文](../../../infrastructure/workspace/llm-context.md) · [模型登记](../../../infrastructure/workspace/import-or-register-model-version.md) · [执行权限与 Hook](../../../tools/exec-command.md)
- **归档与后续批次。** 既有四脚本试点中的 Blender 包装器随 P0 原件归档，材质和烘焙的 3 个文件进入 P1。其余候选按能力选取后展开。延期入口及触发条件见文件表。 [P0 归档收据](../archived-p0/archive.lock.json) · [独立资源说明](../../../resources/README.md)

在仓库根目录重跑时，命令从发行锁重建并核对现有抽离清单，校验 P0 入口及必需依赖的发行路径，随后写出 JSON 和 Markdown。输出字节相同可原样复用。变更核查范围时，使用新的输出目录生成并比较。 [派生命令](../../../../../scripts/hi3d/derive-priority.py)

```powershell
python -B scripts/hi3d/derive-priority.py `
    --inventory-dir 'docs/hi3d/upstream/1.2.11/inventory' `
    --extraction 'docs/hi3d/upstream/1.2.11/extraction/extraction.json' `
    --scope 'docs/hi3d/upstream/1.2.11/extraction/priority.scope.json' `
    --output-dir 'docs/hi3d/upstream/1.2.11/extraction'
```

## 优先级与 P1 核查

[P1 精确文件表](p1/priority.md)逐项记录照片审查、模型取证、材质、网格及蒙皮数值检查的交付路径、依赖、纳入依据和待实测缺口。供应商客户端、专项视角规则与人形绑定流程以安装包出处作为证据。 [机器可读清单](p1/priority.json) · [P1 范围输入](p1/priority.scope.json)

本批核查 58 条锁定路径，其中 15 个原件候选、43 个证据引用。大小和 SHA-256 按安装副本对账，选中脚本按实际部署目录检查导入。已执行的合成样本测试、仅经静态核查的行为和后续实测条件分别记在文件行内。 [安装包副本](<D:/install/Hi3DAgent.__hi3d-transaction/resources>)

原件已按此表归档并补齐独立说明。 [归档收据](../archived-p1/archive.lock.json) · [资源索引](../../../resources/p1/README.md) · [43 项证据](../../../resources/p1/evidence.md)

归档复核使用各批资源索引中的命令。P0 与 P1 分别验证归档的完整文件集合和逐件字节，归档输出目录须与锁定的盘点、抽离输入目录互不包含。 [P0 归档命令](../../../resources/README.md#复核或重建归档) · [P1 归档命令](../../../resources/p1/README.md#复核或重建归档)

- **视图。** 照片联系表使用调用方的原件、顺序和标签。本地 Blender 取证输出前、后、左、右、顶及展示视图。中心假设、顶视旋转和目标动物拍摄语义须分别验证。Hi3D 桌面提交的四槽组包和 `top` 拒绝经离线核查，所选服务的顶视输入和成品还需另验。 [多视图配对证据](../../../atomic-nodes/pair-multiview-inputs.md) · [模型取证](../../../infrastructure/workspace/acquire-model-visual-evidence.md)
- **文件与外观。** 锁定试点的材质、烘焙脚本和同目录设备模块纳入 P1，后台 Blender 启动包装器从 P0 复用。模型重开和导出按实际物化路径记录。窄格式 GLB 几何检查、Blender 求值网格、材质与烘焙分别记录各自的解释器、数据和验收范围。 [材质和纹理证据](../../../infrastructure/bundled-assets-and-script-tools.md#材质与纹理资源实例)
- **四足及供应商。** 蒙皮候选只提供对给定顶点、权重、骨骼索引和姿态的数值检查。骨架创建、真实动物形变、步态及远端输出仍待实测。API 证据覆盖参考图角色、预检与组包、同任务续查和产物下载。 [桌面工具契约](../../../tools/hi3d-api.md)

P1 采用独立补充清单。命令复核发行锁、抽离清单和 P0 清单的原始字节，核对三个既有试点文件均进入 P1，并拒绝重复选取 P0 原件。P1 清单保存 P0 发布摘要，可直接与既有归档收据核对。输出为 `priority.json` 和 `priority.md`。 [P0 归档收据](../archived-p0/archive.lock.json) · [派生命令](../../../../../scripts/hi3d/derive-priority.py)

```powershell
$release = 'docs/hi3d/upstream/1.2.11'
python -B scripts/hi3d/derive-priority.py `
    --inventory-dir "$release/inventory" `
    --extraction "$release/extraction/extraction.json" `
    --p0-priority "$release/extraction/priority.json" `
    --scope "$release/extraction/p1/priority.scope.json" `
    --output-dir "$release/extraction/p1"
```

## 清单范围

| 字段 | 本次范围 | 含义 |
| --- | ---: | --- |
| `candidates` | 2,757 条 | 2,751 条带源码映射的 Skill 文件和 6 条独立宿主文件。后续按选定入口复核各文件的引用、用途和来源。 |
| `origin_review` | 105 条 | 已发现第三方或混合来源的交付文件。此处保留精确路径，选用时按实际依赖和对应来源条款复核。 |
| `reference_only` | 4,878 条 | Codex、随包 Python、桌面包与其依赖、宿主协议、发行资料、上游测试及测试素材等。每组给出发行记录数和字节数，精确路径从发行索引按分组规则定位。 |
| `batch` | 4 个脚本 | 首批实际抽离范围，含三个独立入口或可调用模块、一个同目录模块依赖。四个文件均位于候选池。 |
| `external_references` | 1 项 | Blender 独立安装，提供 `bpy` 和 Cycles。 |

前三组覆盖发行锁的 7,740 条记录。分组字节数按记录加总，ASAR 文件与其成员各有记录。候选池包括其他专项工作流的交付文件；Vet3D 每次抽离选择确切入口，再展开该入口实际读取的配置、脚本及素材。六个候选宿主文件覆盖工作区指令模板、配置、Hook、程序环境启动、Skill 安装评审提示及 YAML 支持脚本。打包后的 Runtime 主模块和桌面宿主保留为实现证据。ASAR 内 `@sparc3d/contracts` 的 32 条记录属于 Hi3D 1.2.11 自有宿主协议，单列为 `desktop-host-contracts`。 [可执行分组规则](../../../../../src/vet3d/infrastructure/hi3d_inventory/extraction.py) · [宿主部署与调用证据](../../../infrastructure/bundled-assets-and-script-tools.md#runtime-安装与按需调用)

发行索引同时保留上游路径和真实的物化路径。同一源码和 SHA-256 的多份投放可以共用内容出处，调用方要求的交付位置仍须分别核对。同一源码路径出现不同 SHA-256 时，按实际调用路径保留对应版本。抽离以发行锁记录的部署字节校验，适用于 Windows 发行文件中的 CRLF。 [打包与部署证据](../../../infrastructure/bundled-assets-and-script-tools.md#源码映射与构建打包)

### 来源复核项

下表的路径相对 `resources/runtime/prebuilt-skills/`。

| 路径 | 记录数 | 已核实的来源 |
| --- | ---: | --- |
| 六个物化包的 `assets/taro/` | 58 | Epic MetaHuman Taro 模板、贴图及配套的派生映射。授权及版本见 `manifest.json`、`UPSTREAM_LICENSE.txt`。 [Taro 来源清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-head-template/assets/taro/manifest.json>) |
| `.dependency-head-hair-split/assets/viewer/` 中的 Three.js、OrbitControls 及许可证，`print-kit/assets/viewer/vendor/`，`lamp-design/assets/experience/vendor/` | 12 | 三套查看器的供应方依赖，包括 Three.js、model-viewer 与 Draco。相邻的业务 HTML 和脚本按各自来源归类。 [灯具查看器来源说明](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/lamp-design/assets/experience/vendor/NOTICE.txt>) |
| `rhino-control/references/official/`、`rhino-control/references/catalog.zip`、`roblox-api/references/hi3d-roblox-official-docs.zip` | 35 | 官方资料、本地镜像与从官方资料派生的目录。 [Rhino 官方资料索引](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/rhino-control/references/official>) · [Roblox 快照出处](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/roblox-api/references/hi3d-sources.md>) |

### 环境与宿主引用

| 环境或宿主 | 身份与出处 |
| --- | --- |
| 随包 Codex 0.166.0 | 发行索引 `runtime/codex/` 保留程序、版本清单及本地资源摘要。 [随包版本核查](../../../tools/exec-command.md#核查依据) |
| 随包 Python 3.12.14 | 本次安装副本中 `runtime/.runtime-python/python/python.exe` 的产品版本为 `3.12.14`，解释器与依赖均可查发行索引中的路径及摘要。 [已锁定文件索引](../inventory/inventory.jsonl) |
| 桌面宿主和依赖 | `app.asar` 为发行锚点，各成员身份见同一索引。可用成员内的 `package.json` 核对独立依赖的版本。 [发行锁](../inventory/inventory.lock.json) |
| 独立 Blender 4.5.16 LTS | 本机 `blender.exe --version` 实测，文件 SHA-256 为 `2cc9335813e9c015c006cdda64a976418bf8228d2945d8d90605d60df799f119`。该摘要来自独立环境观察。 [本机外部程序](<D:/install/blender/blender.exe>) |

## 首批文件及依赖

下表的脚本路径相对 `resources/runtime/prebuilt-skills/`。实际抽离文件集合为 `batch.entries` 与 `batch.local_dependencies` 中的目标路径并集。`batch.upstream_references` 是四份上游用法和契约的取证路径。

| 文件 | 已核实的调用关系 |
| --- | --- |
| `.dependency-blender-tools/scripts/material_nodes.py` | `principled_material()` 从 Blender 的 `bpy` 创建材质并设置 Principled 节点。调用方负责选择对象或面、绑定材质和导出。 |
| `.dependency-blender-tools/scripts/execute.py` | 通用 Blender 启动包装器，脚本自身使用 Python 标准库。使用时由调用方传入可信脚本或模块路径，包装器建立该入口的导入路径并用 `runpy` 执行。 |
| `.dependency-texture-bake/scripts/texture_bake.py` | 接收现成的 Blender 网格和材质对象，使用 `bpy` 执行 Cycles 烘焙。它从本包同目录导入 `cycles_device`。 |
| `.dependency-texture-bake/scripts/cycles_device.py` | 烘焙模块的本地依赖，在 Blender 内选择并恢复 Cycles 设备。保留其在该包内的实际位置。 |

已从安装副本重新计算这四个脚本和四份上游参考文件的大小与 SHA-256，并与发行索引核对。静态检查覆盖上述脚本的导入关系。`execute.py` 传入其他入口时，该入口的依赖另行核对。脚本被会话实际选用、其他候选的完整依赖，以及独立迁移后的执行结果属于后续验证。 [现有调用与隔离测试依据](../../../infrastructure/bundled-assets-and-script-tools.md#材质与纹理资源实例)

后续抽离按交付路径保存原件并验摘要，同时给每份抽出的资源写独立说明，记录来源、LLM 可见方式、参数、结果、副作用、执行权限及示例。运行时注册和 Vet3D 执行层接入由选用该资源的后续实现负责。 [资源约定](../../../infrastructure/bundled-assets-and-script-tools.md#vet3d-实现契约)

## 从发行锁重跑

从仓库根目录运行。派生命令读取现有发行锁和 JSONL，复核摘要、分区计数及锚点，再独占发布单份 UTF-8 / LF 清单。相同字节的成品可原样复用。摘要不符或成品内容冲突时返回非零退出码。运行只需仓库中的两份锁定输入。 [命令入口](../../../../../scripts/hi3d/derive-extraction.py)

```powershell
python -B scripts/hi3d/derive-extraction.py `
    --inventory-dir 'docs/hi3d/upstream/1.2.11/inventory' `
    --output-dir 'docs/hi3d/upstream/1.2.11/extraction'
```
