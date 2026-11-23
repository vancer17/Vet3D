# 初始重拓扑方案与插件交接

## 入口检查与推荐

读取本次实际对象、材质、变换、现有四边面工程、面数与保形目标。先复用已验收基线及同任务已选方案；只有需要新的初始拓扑时才弹四选一。不要为配置本 Skill 而对不存在的模型开跑。

已有可用quad基线、用户允许重建并要求显著减面时，转读 [可靠边链约束的预算重建](hi3d-budget-rebuild.md)。这是同一Skill的后续模式，不是初始选项5，也不要求重做已合格基线。缺少已验证边链时不能冒称已经按边流约束重建。

按顺序展示以下四项；推荐标记随情景变化，序号不变：

1. **QRemeshify**：硬表面、明确几何形状与边缘；低人工干预。若当前对象是这类资产且未要求人工指定边流，优先推荐。
2. **AutoRemesher**：一键自动初始重拓扑；低人工干预。希望直接自动跑、未指定人工边流时推荐。它是外部 macOS/Windows/Linux 应用，有命令行入口，不冒充 Blender 内置插件。
3. **Instant Meshes 2026**：用户在软件内提供布线参考；高人工干预。明确要求控制边流时优先推荐，并告知需准备曲线或标注。收到参考前不执行本分支。
4. **原四边通流程（兜底）**：插件不适用、输出未达到要求，或用户主动选择原方法时建议；完整保留原标准体/内腔分流和适用的基础、分区及闭合过渡条件。它需要相应输入与已安装依赖，不保证任意模型都能自动完成。

用户已选某方案则复用，不按推荐强行覆盖。无明确偏好的一般自动初始重拓扑，可推荐已验证可用的 AutoRemesher，并声明是按“少干预”目标推荐。要控制边流时不能以自动化更省事为由改成前两项。硬表面与引导控制同时存在时，用户明确的边流控制目标优先；说明选择第 3 项的原因。

实际不可用的项仍保留在四选一文案中，明确“当前不可用”和具体原因，不作为默认推荐。三个插件都不可用时，只有确认第 4 项对应输入/依赖满足才能推荐兜底；否则停在输入或依赖问题，不能凭空打通。

## 面板契约

用 `user_interaction`：kind=`preference`，title=`四边通：选择初始重拓扑方案`，question id=`initial_remesher`。四个 label 以 `1. QRemeshify`、`2. AutoRemesher`、`3. Instant Meshes 2026`、`4. 原四边通流程（兜底）` 开头，追加当次情景短建议，并只对推荐项追加 `（推荐）`。description 写当前对象适配理由、人工干预高低及必要限制；message 解释本次推荐理由。`defaultAnswer` 精确等于推荐 label；timeoutSeconds=`60`。

答案映射为固定内部标识 `qremeshify`、`autoremesher`、`instant_meshes_2026`、`legacy_quad_flow`，保存选择及来源。assistant_default 表示采用已公布偏好，不能当作用户新授权。自由文本出现不同方案或额外限制时按真实意思处理；多义时再询问，不能把任意文本映射成默认项。取消后停止依赖处理。

选择第 3 项但缺少用户参考：使用 kind=`input` 询问已有 Blender 曲线/标注的位置和控制目标，或提示通过聊天附件提供工程；input 不设默认答案或超时默认。没有参考时不得擅自画一条曲线并称为用户布线。仅作安装自检的合成引导测试须明确标为测试，不作为实际用户模型成果。

插件失败、输出不合格或用户拒绝高干预时，保留原件与当前结果，给出第 4 项等可行建议，收集新方案偏好后再继续。不能静默切换、自动覆盖已选方案或把失败输出当作已验收基线。

## 定位已安装后端

- 在 Blender 内通过 `bpy.context.preferences.extensions.repos` 的实际目录和 `addon_utils.modules()` 定位扩展，不把某台机器的账号路径写进流程。QRemeshify 扩展 id=`qremeshify`；Instant 扩展 id=`instant_meshes_2026`。常见用户安装位置为 `~/Library/Application Support/Blender/<版本>/extensions/user_default/`，以实际配置为准。
- AutoRemesher 搜索已授权的常见应用位置 `~/Applications/AutoRemesher.app/Contents/MacOS/autoremesher`、`/Applications/AutoRemesher.app/Contents/MacOS/autoremesher` 和 PATH。核对文件存在、可执行、架构及 `--help`，不能从 app 文件名推断功能。不要扫描整台电脑。
- Blender 用宿主提供的可执行文件，在要求时申请沙箱外运行；不要通过别的程序绕过宿主权限。启用插件前保留现有用户偏好；不覆盖其他插件或用户数据。只读探测不意味着授权升级、卸载或替换已安装项目。
- 缺的是这三项后端之一时，读取 [安装选项](hi3d-install.md)，把适用来源和建议全部交给用户。用户选定来源后才复制或下载；超时和算法选择都不等于同意安装。其他能力仍然不临时安装。

## 三项插件的实际调用

共同规则：先另存/复制源工程；只处理工作副本。冻结源对象集合、坐标、单位、部件名、材料/UV、保护边界和目标；不要把多个功能独立部件直接合并或让内部/背面凭空消失。插件改拓扑后另存结果，保留原件用于误差测量及属性转移。带蒙皮或形态键时另行确定支持范围，不直接替换其拓扑。

### 1. QRemeshify

来源：<https://github.com/ksami/QRemeshify>，使用与本机系统/架构匹配的已安装扩展。Blender public operator 为 `bpy.ops.qremeshify.remesh()`；场景参数为 `quadwild_props` 与 `quadpatches_props`。需要激活并选中工作副本且处于对象模式。

依据实际硬边/接缝/材质边界设置 sharp detection；对称轴必须有事实依据，不随意镜像非对称结构。没有同源缓存证据时禁用 `useCache`。`scaleFact` 等控制不等于承诺精确目标面数。评估依赖图中的修饰器可能被实体化，故必须保留原工程。松散部件按语义分开处理；面数不足或复杂折叠导致失败时报告具体原因，不以增加面数冒充形状提升。

operator 返回 FINISHED 不能单独证明成功：核对确有新的非空网格、真实四边面及有效坐标，再完成共同检查。QRemeshify 会改变显示/选择状态；只在工作副本上运行，最终稳定命名。

### 2. AutoRemesher

来源：<https://github.com/huxingyi/autoremesher>。导出工作副本为正确坐标/尺度的三角 OBJ，保留材料和高模参照于原工程。命令行示例用参数数组执行，禁止拼接用户输入进 shell：

```python
args = [executable, '--input', input_obj, '--output', output_obj,
        '--report', report_txt, '--target-quads', str(target_quads)]
subprocess.run(args, check=True)
```

输入、输出、报告都在工作区内，使用不覆盖旧结果的新路径与 `hi3d-` 文件名。其他公开参数有 `--edge-scaling`、`--sharp-edge`、`--smooth-normal`、`--adaptivity`、`--anisotropy`；只传当前版本 `--help` 确认支持的参数。使用 GUI 初始化的 macOS 版本时遵循图形程序沙箱规则。

目标四边面数是近似预算，报告实测面数和偏差。成功退出还需确认 OBJ 非空并可回读，按原坐标/单位导回 Blender，检查原部件分组。OBJ 不自动保留原 UV、蒙皮、形态键或贴图，应另行转移/烘焙并验证。

### 3. Instant Meshes 2026

来源：<https://github.com/MondRubberduck/instant-meshes-2026>，不可用同名旧版冒充指定项目。使用已安装 Blender 扩展的 Retopo 面板。接收用户现有曲线或 viewport annotations，并明确其对应主体、闭环和控制目标。当前扩展识别场景中名为 `Contour*` 的曲线或被选择的曲线；运行前只让本次授权参考参与，避免其他资产的引导混入。

public operator=`bpy.ops.mesh.instant_retopo_execute()`，场景参数=`retopo_props`。先设置目标面数、实际曲率适应与已确认对称约束，再在工作副本上执行。优先使用与 Blender Python ABI 匹配的 `pyretopo`；没有匹配模块时可使用扩展支持的同目录 `InstantMeshes2026CLI`。macOS arm64 源码编译的 CLI 是本机合法后端，不称为已安装 Python 原生内存模块。

CLI fallback 会导出工作网格及轮廓 OBJ，并通过 `--contour` 接收引导，再导入新网格。当前 fallback 未将曲线的 `mirror_x` 标记传给 CLI，不能仅开启面板镜像就声称获得镜像约束；需要对称引导时，须先取得并检查显式双侧参考，或确认兼容的原生模块可用。检查日志/参数证明参考被传入；检查实际边流和引导偏差后才能宣称符合用户布线，不能仅以“传入了曲线”替代语义验收。目标面数近似；纯四边面细分可能改变实际数量。不承诺自动动画级眼口环、精确面数或无翻面。

## 初版反馈与参数调整

用户已有初版并提出调整时，转读 [参数与动作对照](hi3d-remesh-parameters.md)，复用已选工具及真实配置；只有确需换算法才重新选路。本机CLI的镜像、固定奇点过滤及质量面板限制以该表为准。

## 进入后续流程与交付

第 1—3 项先检查新网格：真实 quad/tri/ngon、空/坏坐标、边界/非流形、退化面、法线、连通部件、源到结果的双向采样误差与实际保护结构。另行检查 UV/材料/纹理、引导与用户目标；离散采样不称连续误差上界。若用户未给目标，优先保形并报告实际结果，不擅自用统一面数标准判定。

通过的初始工程才可成为后续冻结基线。仅要初始重拓扑时，交付可编辑真实四边面 `.blend`、需要的不三角化 OBJ、三角化预览与检查报告；GLB 的显示三角数不代表可编辑 quad 数。需要后续减密/语义校准时，读取所调用能力现行要求，仅补缺失阶段，保留所有输入门槛和保护规则；插件输出不能替代面颈的独立验收。

第 4 项执行根入口保留的完整原流程；各阶段按适用条件调用，不强制把所有能力串行全跑。最终按宿主规则保留物理单位与稳定节点名，导出 GLB 后登记；将登记、预览和工程交付分别记录。失败仅补受影响阶段，已通过步骤不重跑。

## 本次已实测范围

macOS arm64 + Blender 5.1.1：QRemeshify 1.1.0 已完成硬边合成网格重拓扑；AutoRemesher 1.2.0 已完成自动 OBJ 输入/输出；Instant Meshes 2026 v1.0.0 已以本机源码编译 CLI 配合 Blender 扩展完成带闭合测试曲线的重拓扑。这些是安装冒烟验证，不证明任意资产、引导贴合精度、动画、UV 或打印要求已验收。
