# 随包静态资源与脚本工具

本页属于基础设施层，说明 Hi3D Agent 如何把可复用脚本、文档、配置和实体素材从构建源带到本地执行环境。核查基准为 Windows x64 的 Hi3D Agent 1.2.11 和同版 Runtime，以下以 Blender 材质节点、纹理烘焙和专项模板为例。业务流程按任务选择资源，基础设施负责提供可定位、可核对的版本与执行入口。 [版本归档](../upstream/1.2.11/README.md) · [安装清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/manifest.json>)

## 职责与边界

| 类型 | 所在位置与调用方式 | 示例 |
| --- | --- | --- |
| LLM Tool | 模型通过当前会话开放的工具名和参数调用。Code Mode 可编排这些工具。 | [`exec_command`](../tools/exec-command.md) 启动本地程序，[`hi3d_api`](../tools/hi3d-api.md) 的 `generate_3d` 动作可提交远端仅贴图，[`view_image`](../tools/view-image.md) 读取实际输出图。 |
| Skill 与引用文档 | 公开 `SKILL.md` 提供任务入口和步骤。Agent 从已解析的路径按需读取 `references/`，以及兄弟 `.dependency-*` 目录里的 `REFERENCE.md`。 | [装配 Skill](../upstream/1.2.11/prebuilt-skills/image-to-assembly/SKILL.md) 指导何时按原图恢复局部标识，[Blender 工具参考](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-blender-tools/REFERENCE.md:19>) 说明怎样启动和引用脚本。 |
| 随包脚本与静态素材 | 随包文件由 Python、Blender 或 Node 加载。调用方使用入口文件或模块路径，脚本参数由该脚本契约定义。 | `material_nodes.py`、`texture_bake.py`、Taro 皮肤图集、模板和配置。 |
| 会话生成脚本与产物 | Agent 根据当前任务在工作区 `scripts/` 写入代码，可直接使用 `bpy`，也可显式复用随包模块。新资源和候选写入本工作区。 | 历史样本脚本为脸部修补新建材质、接入 PNG 并写入面材质索引，后续另行登记选定 GLB。 [工作区规则](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/templates/AGENTS.md:39>) · [实际脚本](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/scripts/hi3d-cat-face-repair_7.py:21>) |

基础设施的交接结果包括已安装根路径、实际资源路径和执行程序。对任务调用，还需保留输入与输出、命令终态和必要摘要。工具回包、脚本进程结束、候选资产验收和模型版本登记各有自己的完成条件。 [当前轮 Skill 发现与读取](workspace/llm-context.md#有效目录与选用) · [模型版本登记](workspace/import-or-register-model-version.md)

## 源码映射与构建打包

### 1. 在源码包声明物化文件

构建源采用 `tools/`、`skills/`、`workflows/` 下的命名目录。各包的 `package.json.files` 将**包内目标相对路径**指向**源码仓库相对路径**。对于跨包共享模块，构建器将源文件实际复制到消费包指定位置。`requires` 声明需要独立调用的入口，打包器会检查依赖名和环。脚本可以通过 `files` 取得本地导入依赖，即使所在包的 `requires` 为空。 [打包契约](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-package-tools/references/usage.md:3>) · [构建源码](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-package-tools/scripts/host-bundle.mjs:60>)

**源映射摘录。** 以下保留随包 `head-lowpoly/package.json` 中与材质和纹理有关的三条映射，省略其他文件。

```json
{
  "schema": 1,
  "files": {
    "scripts/cycles_device.py": "tools/blender-tools/scripts/cycles_device.py",
    "scripts/material_nodes.py": "tools/blender-tools/scripts/material_nodes.py",
    "scripts/texture_bake.py": "skills/texture-bake/scripts/texture_bake.py"
  },
  "requires": []
}
```

安装后的 `head-lowpoly/scripts/bake.py` 从同一包内导入烘焙模块，`texture_bake.py` 又从同目录导入 `cycles_device.py`。这两个 import 在已物化目录中解析。 [消费包清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/package.json:7>) · [业务脚本 import](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/bake.py:11>) · [烘焙模块 import](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-texture-bake/scripts/texture_bake.py:7>)

### 2. 生成桌面分发目录

随包的 `host-bundle.mjs` 实现桌面构建，输入为完整源码树、profile 和输出目录。它扫描命名包、验证路径及映射，结合 `sparc3d` profile 的白名单、别名和覆盖项计算输出位置。公开入口使用 `<名称>/SKILL.md`，其余依赖平铺为 `.dependency-<名称>/REFERENCE.md` 及各自脚本、资源。构建器先解析整个文件计划，并按输出布局重写 Markdown 相对链接，再写文件。CLI 要求输出为源码树之外的新目录。 [桌面构建源码](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-package-tools/scripts/host-bundle.mjs:45>) · [桌面 profile](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-package-tools/profiles/sparc3d.json>) · [桌面打包约定](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-package-tools/references/usage.md:20>)

构建结果的 `.runtime-profile.json` 记录各包的 profile 与源码目录。`.workflow-bundle.json` 记录公开入口以及 `[产物相对路径, 源码相对路径, 产物 SHA-256]` 三元组。以基础材质模块为例，`.dependency-blender-tools/scripts/material_nodes.py` 和 `head-lowpoly/scripts/material_nodes.py` 都指向同一个源码文件。构建来源可追至清单中的相对路径，Hi3D 工具源码仓库的提交在安装证据中仍未定位。 [写出清单的实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-package-tools/scripts/host-bundle.mjs:157>) · [材质模块的实际来源记录](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.workflow-bundle.json:335>)

## Runtime 安装与按需调用

### 3. 部署已构建的文件

本机包内源根为 `D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills`。打包桌面启动时由 Runtime 的 `Ij` 进入预构建资源部署，`fj` 使用安装包的 `prebuilt.json`。安装分支校验相对路径和符号链接、文件 SHA-256，以及公开 `SKILL.md` 或隐藏 `REFERENCE.md` 的受管标记。随后按相对布局写入 `CODEX_HOME/skills/buildin`。1.2.11 的部署清单列出 102 个公开入口、45 个隐藏条目和 3,168 个文件。构建侧的 `.workflow-bundle.json` 也随部署复制。 [实际部署清单](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/prebuilt.json>) · [Runtime 实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>) · [首次部署日志](<D:/download/.sparc3d-runtime/environments/prod/logs/desktop-20261111T032128Z-23156.log:23>)

Runtime 将安装结果写入 `.sparc3d-skills.json`。后续启动可校验 Runtime 版本、包指纹和已安装路径的元数据指纹，命中后复用已安装目录。该快路径的目标指纹基于路径、文件大小和修改时间。需要确认脚本字节一致时，另做内容摘要比对。留存生产环境的实际部署根为 `D:/download/.sparc3d-runtime/environments/prod/codex-home/skills/buildin`。 [本机安装戳](<D:/download/.sparc3d-runtime/environments/prod/codex-home/skills/buildin/.sparc3d-skills.json>) · [复用日志](<D:/download/.sparc3d-runtime/environments/prod/logs/desktop-20261115T032556Z-30688.log:23>)

| Runtime 中的复核锚点 | 实现 |
| --- | --- |
| `Ha`（`2437492`）、`fj`（`2438031`） | 部署路径检查、预构建清单和源文件校验。 |
| `Ij`（`2448254`）、`Tj`（`2453378`）、`e$`（`2456365`） | 打包桌面的异步部署入口、安装戳复用条件和目标元数据指纹。 |
| `l$`（`2482617`）、`oR`（`3023692`） | Blender 路径探测、模型可见 Skill 目录格式。 |

偏移均相对于 `resources/runtime/dist/runtime.mjs` 原文件的 UTF-8 零基字节位置。此版本的 Runtime SHA-256 为 `85f69d28261dd6ee3322e4cbd4a9a670ca60c80775ed6ebe322553424734de47`。 [原始 Runtime](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/dist/runtime.mjs>)

### 4. 定位选中入口及其依赖

Runtime 向模型给出有效 Skill 的名称、描述和入口路径。选用某个入口后，以实际 `SKILL.md` 所在目录为基准解析阶段要读的相对路径。文档中的 `SKILL_DIR` 表示这个目录。隐藏依赖可由路径访问，公开目录只列可选的 Skill 入口。模型读取入口后，根据任务需要打开某个参考文件，或选择其中声明的本地脚本。实际读过的文件以对应工具回包为证。 [有效目录与选用](workspace/llm-context.md#有效目录与选用) · [按需读取阶段依赖](workspace/llm-context.md#阶段依赖) · [Blender 脚本契约](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-blender-tools/REFERENCE.md:19>)

### 5. 进入合适的解释器并传递参数

材质节点与 Cycles 烘焙依赖 `bpy`，用 Blender 自带的 Python 执行。本机 Runtime 探测的 Blender 位于 `D:/install/blender/blender.exe`，实际路径由宿主注入工作区 `AGENTS.md`。独立的随包 Python 可用于文件和清单检查。对于已经选中的可信包入口，可通过 `exec_command` 启动后台 Blender，再调用可选的 `execute.py` 包装器。包装器把 `--script` 指定文件的父目录，或 `--module` 对应的 `--scripts` 目录加到 `sys.path`，设置目标参数并调用 `runpy`。结合 Blender 的 `--python-exit-code 1` 可将未处理异常传为进程失败。 [工作区实际解释器路径](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/AGENTS.md:50>) · [包装器源码](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-blender-tools/scripts/execute.py:8>) · [本地执行 Tool](../tools/exec-command.md)

若调用入口是会话生成的工作区脚本，包装器默认只加入该脚本目录。需要复用安装包模块时，由调用方显式选择已解析的包目录或模块路径。工作区样本也有直接编写 Blender 操作的例子。猫脸修补脚本自行创建材质和图像节点，再给面写入材质索引。样本只佐证该次调用，脚本库与可选路线以清单和源码为准。 [会话修补脚本](<D:/download/.sparc3d-runtime/environments/prod/workspaces/asset_04fbdc40/scripts/hi3d-cat-face-repair_7.py:21>)

## 材质与纹理资源实例

| 随包路径 | 能力与实现边界 |
| --- | --- |
| `.dependency-blender-tools/scripts/material_nodes.py` | `principled_material()` 接收线性 RGB/RGBA，RGB 补 alpha `1`。新建材质并设置 `diffuse_color`、Base Color、Metallic 和 Roughness，后两项默认 `0` 和 `.5`。`inputs` 最后合并，可覆盖节点值。未知 socket 会抛错并清理新材质。调用方负责分配到对象或面、连接图像及导出。 [源码](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-blender-tools/scripts/material_nodes.py:5>) |
| `.dependency-texture-bake/scripts/texture_bake.py` 与 `cycles_device.py` | 在已对齐网格间执行 Cycles selected-to-active。需要独立源和目标、目标 active UV 和独立节点材质。临时设 Image Texture 节点，运行 `DIFFUSE`、`EMIT` 或切线空间 `NORMAL`，保存并 pack PNG，返回图像与报告，恢复临时节点和设备。上层绑定结果并验收整组通道。 [烘焙源码](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-texture-bake/scripts/texture_bake.py:75>) · [本地烘焙契约](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-texture-bake/references/contract.md:3>) |
| `head-lowpoly/scripts/bake.py` | 复用随包烘焙模块。相同且未连线的粗糙度、金属度保留为常量，其余 PBR 通道按需经临时 Emission 烘焙。法线单独输出，随后恢复源连线，并将贴图接回目标。 [专项实现](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/head-lowpoly/scripts/bake.py:67>) |
| `.dependency-blender-tools/scripts/asset_scene.py` 与 `.dependency-model-preview/scripts/product/glb_export.py` | 重开确切 GLB/BLEND 候选，或按显式对象集合导出新 GLB。导出选项可透传给 Blender，包括材质与动画选项。此类脚本承载读写，实际业务验收另行执行。 [资产重开](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-blender-tools/scripts/asset_scene.py:7>) · [GLB 导出](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-model-preview/scripts/product/glb_export.py:6>) |
| `image-to-assembly/assets/` | 静态请求配置、清单样例与视图提示。局部贴花需要当前任务提供真实原图和可定位的表面。 [视图提示](../upstream/1.2.11/prebuilt-skills/image-to-assembly/assets/view-prompts.md) · [装配审查与修复](../upstream/1.2.11/prebuilt-skills/image-to-assembly/references/multiview.md#审查与修复) |
| `metahuman-fit/assets/taro/` | 专项人头模板，含 GLB、NPZ、OBJ/MTL、皮肤/眼睛/口腔 TGA、掩码与映射。资产清单记录 Epic Taro 示例的固定版本、`dna_io.py extract` 提取来源和随附许可。默认模板和皮肤图集按脚本位置解析，自定义模板需要相匹配的图集。 [资产来源](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-head-template/assets/taro/manifest.json:2>) · [模板解析](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/metahuman-fit/scripts/template_defaults.py:4>) |

## 只读盘点与锁定

从 Vet3D 仓库根目录执行以下命令。脚本需要 Python 3.12 或更新版本及可创建硬链接的输出文件系统。输入是留存安装包的 `resources/`，输出是仓库内独立的盘点目录。脚本读取并计算文件摘要，不调用包内脚本、桌面应用或远端服务。 [盘点入口](../../../scripts/hi3d/inventory.py)

```powershell
python -B scripts/hi3d/inventory.py `
    --resources-root 'D:/install/Hi3DAgent.__hi3d-transaction/resources' `
    --output-dir 'docs/hi3d/upstream/1.2.11/inventory'
```

清单逐项记录 Skill 文件、独立 Runtime 资源、资源根其他文件和 ASAR 成员。`path` 相对 `resources/`。ASAR 行用 `app.asar/<成员路径>` 表示，独立的 `member_path` 和 `offset` 给出成员名与归档内的零基字节偏移。Skill 的 `package` 表示物化归属，`source_path` 保留构建来源。相同来源的各个交付路径及摘要均保留。`execution_hint` 供归类和解析依赖。引用可达性、隔离执行和会话调用在发行锁中标为未知，后续资源说明可链接具体的旁证。 [全量清单](../upstream/1.2.11/inventory/inventory.jsonl)

发行锁固定清单的 SHA-256、发行元数据、分区计数和五个锚点。锚点为 `app.asar`、Runtime 版本清单与主程序、两份 Skill 清单。逐文件核对部署 SHA-256 和源码映射，并校验 ASAR 声明的成员摘要及分块摘要。当前读盘器支持内嵌成员，遇到链接或 `unpacked` 成员会返回错误。磁盘额外 Skill 路径保留供对账，Python 缓存仅在终端报告忽略数量。 [锁定记录](../upstream/1.2.11/inventory/inventory.lock.json)

输出采用稳定排序的 UTF-8 和 LF。先发布 JSONL，最后发布锁定记录。重跑命令会比较现有文件字节并复用一致结果。若上次只生成了匹配的 JSONL，可重跑补齐对应的锁。缺少锚点、校验失败或已有输出内容不同均返回非零，变更版本使用新的输出目录。

本次锁定包含 7,740 条记录，其中 1,043 条为已核对摘要的 ASAR 成员。Skill 子树核对了 3,168 条部署记录和 3,020 条来源映射。 [本次全量清单](../upstream/1.2.11/inventory/inventory.jsonl) · [发行锁](../upstream/1.2.11/inventory/inventory.lock.json)

抽离时以发行锁为输入，先确定候选池和环境引用，再为实际入口列出需要保留的文件。首批范围、依赖路径与派生命令见 [Hi3D 1.2.11 抽离清单](../upstream/1.2.11/extraction/README.md)。

已归档资源的原件、依赖和复核步骤分别见 [P0 资源索引](../resources/README.md)与 [P1 资源索引](../resources/p1/README.md)。

## 按安装包复核

**清单与文件对账示例。** 使用包内来源清单定位 `material_nodes.py` 的消费方，对包内源目录与当前已部署目录分别验 SHA-256。实际测试在这两个目录中验证了材质模块的 21 份副本、烘焙模块的 3 份副本与 Cycles 设备模块的 5 份副本。

```powershell
$packagedSkills = 'D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills'
$installedSkills = 'D:/download/.sparc3d-runtime/environments/prod/codex-home/skills/buildin'
$bundle = Get-Content -Raw -LiteralPath "$packagedSkills/.workflow-bundle.json" | ConvertFrom-Json
$source = 'tools/blender-tools/scripts/material_nodes.py'
$copies = @($bundle.files | Where-Object { $_[1] -eq $source })
if ($copies.Count -ne 21) { throw "Unexpected 1.2.11 material helper count: $($copies.Count)" }

foreach ($copy in $copies) {
    $relativePath = $copy[0]
    $expectedHash = $copy[2]
    foreach ($root in @($packagedSkills, $installedSkills)) {
        $actualHash = (Get-FileHash -LiteralPath (Join-Path $root $relativePath) -Algorithm SHA256).Hash
        if ($actualHash -ne $expectedHash) { throw "Digest mismatch: $root/$relativePath" }
    }
    $relativePath
}
```

**随包构建测试。** 沿用上面的 `$packagedSkills`。此用例在临时目录建立合成源码树，验证共享代码复制、公开别名、隐藏依赖和重跑时的清单一致性。执行正式构建需要完整源码树，可按打包契约传入 `--repo`、`--profile sparc3d` 和新的 `--output`。 [随包构建测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-package-tools/tests/host-bundle.test.mjs:37>)

```powershell
$bundleTest = "$packagedSkills/.dependency-package-tools/tests/host-bundle.test.mjs"
node --test --test-name-pattern 'host profile materializes shared sources' $bundleTest
if ($LASTEXITCODE -ne 0) { throw "Bundler probe failed with exit code $LASTEXITCODE" }
```

**根据源码编写的最小调用示例。** 在调用方已把已选包的 `scripts/` 放入 `sys.path` 的 Blender 进程运行。返回值可由外层脚本显式分配给目标槽位。

```python
from material_nodes import principled_material

material = principled_material(
    "Fixture",
    (0.2, 0.3, 0.4),
    metallic=0.6,
    inputs={"Roughness": 0.7, "Coat Weight": 0.8},
)
assert material.diffuse_color[3] == 1.0
assert material.users == 0
```

**实测过的本地执行命令。** 沿用上述 `$packagedSkills`，使用随包包装器执行随包测试。该测试从自己所在的包解析 `scripts/`，在临时目录生成 PNG，覆盖 CPU 上的 `DIFFUSE`、`EMIT`、`NORMAL`、16 位法线和临时状态恢复。 [随包测试入口](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-texture-bake/tests/test_device_context.py>)

```powershell
$blender = 'D:/install/blender/blender.exe'
$wrapper = "$packagedSkills/.dependency-blender-tools/scripts/execute.py"
$testScript = "$packagedSkills/.dependency-texture-bake/tests/test_device_context.py"
& $blender --background --factory-startup --disable-autoexec --python-exit-code 1 `
    --python-expr 'import sys; sys.dont_write_bytecode=True' `
    --python $wrapper -- --script $testScript
if ($LASTEXITCODE -ne 0) { throw "Blender probe failed with exit code $LASTEXITCODE" }
```

| 证据 | 核查范围 |
| --- | --- |
| 构建与安装 | 安装版本、源码路径映射、磁盘副本和安装戳已核实。用随包构建器对合成源码树复现了公开消费包、隐藏依赖和哈希清单的生成。生产日志记录首次部署及后续复用。 |
| 本地脚本 | Blender 4.5.16 LTS 实测共享材质 helper 的 socket 覆盖和失败清理，实测随包烘焙测试。会话脚本另有实际工作区证据。 |
| 待验证 | 已定位 `.workflow-bundle.json` 的生成和 `prebuilt.json` 的安装消费实现。生成 `prebuilt.json` 的发布脚本、完整发布所用的 Hi3D 源码提交、其他 OS 或 Blender 版本和 GPU 后端仍待核实。 |

## Vet3D 实现契约

1. **构建产物。** 为可复用模块保留唯一维护源，显式声明包内路径映射。发布清单记录包 ID、版本、公开入口、跨包依赖和文件摘要。对第三方静态模板另外记录来源版本、许可、提取方式及文件摘要。
2. **安装与发现。** 宿主校验并发布到可版本化的受管目录，对话内固定使用已经确认的版本。Skill 目录公开可选入口及路径，脚本和图集由调用方按契约定位。解释器、外部程序和设备能力由执行环境独立检查。
3. **执行和恢复。** 在执行记录中关联包版本、选中脚本或会话脚本摘要、解释器、输入版本、参数、执行句柄和输出位置。命令仍运行时按原 `session_id` 续查，Code Mode 单元仍运行时按原 `cell_id` 续查。脚本失败时保留原输入、日志和可复验的部分文件，后续执行从已确认的输出继续。 [本地命令续接](../tools/write-stdin.md) · [Code Mode 续接](../tools/wait.md)
4. **输出交接。** 本地执行器报告进程和文件结果，业务调用方选择验收范围和待登记候选。部署失败或资源缺失时在安装层报告明确的路径和版本，避免把错误交给业务节点当成资产验收失败。 [模型版本登记](workspace/import-or-register-model-version.md)
