# 两版最终交付，每版三项

完整建模流程固定完成 **外购配件版（hardware）** 和 **全 3D 打印版（printed）**。分别存于 `hardware/` 与 `printed/`，每版具有自己的 plan、参数、BOM、试片和验证；不可让同名文件覆盖另一版。用户只修改其中一版时保持另一版已有交付，不能用此次局部修改替换整套结果。

外购版写明采购件类型、尺寸/螺纹标准、数量、材料或等级要求、是否需要工具/后加工与安装方法；不得自动下单。装配 GLB 和展示页应有其真实安装包络/位置的独立参考节点并标记“外购，不打印”，STL 打印包只收录该版应打印的零件，采购件列入 BOM。供应商简化几何可用尺寸包络表示，但不能靠它宣称螺纹啮合或精密接触已经验证。

全打印版必须实际提供替代销轴、螺母/螺纹件、楔键、锁片、止挡、连接环和必要释放工具等文件；按所选结构取用，并非每种都必须出现。所承诺的机械装配中外购紧固/连接件数量为 **0**，不用胶，保持原定功能；不能把固定件省掉、运动件粘死或把金属件改名为打印件。两版的连接参数和装配路径分别验证，兼容的主体可共用参数源码。

灯具、电动或循环水产品的灯源、导线、电机、泵等若仍须外购，必须明确称为“全打印机械结构版（功能件另购）”并列依赖，不能称整机全打印。用户要求连这些功能件都不可外购时，说明当前不可打印的具体功能并保留未满足项，不能暗中改成无功能摆件或宣称全打印完成。

流程结尾按版分组，**每版**主动提供以下三个独立、可点击的入口（共六个），按此顺序呈现，不只给一个总文件夹：

1. **装配 GLB**：`assembly.glb`，保留独立零件节点、正确数量与装配变换，单位 m，用于整体查看。
2. **分部件 STL 打印包**：`parts-stl.zip`，内含独立零件 `parts/*.stl`（mm、打印姿态）、数量清单、打印条件和装配说明。重复件可只放一份 STL，数量必须明确。参数源码、所需随包工具、已生成的试片与验证记录一并装入相应子目录。
3. **效果展示页**：`viewer.html`，支持旋转/缩放、装配与拆解切换、拆解距离、打印摆盘、零件显隐和单件 STL 下载。有运动定义时可展示其功能端点；不要把端点预览叫完整动画。页面顶部必须有“下载装配 GLB”和“下载分部件 STL 打印包”两个醒目按钮。

每版三项必须来自该版最终零件。GLB 和网页的装配坐标、打印件与外购节点数量一致，ZIP 里的每个 STL 与预览使用的原始字节一致。模型修改后重做该版三项，不能留旧下载链接。页面标题、BOM 和文件说明写明版本；两个下载按钮指向当前版的 GLB 与 ZIP。可增加两版入口总览，但不能省掉每版三项。整体装配 STL 不能代替分件打印包。

## 打包与页面生成

随包 `package_delivery.py` 是**单版打印零件**打包原子工具，模型部分沿用 `kit.json` 的字段，不自动设计两版或验证免胶保持。分别对两版运行并使用独立输出目录，不能拿一次结果重命名充作两版。展示解析器使用二进制 STL；其他 CAD 输出 ASCII STL 时，先转成二进制、更新 plan 摘要并重验：

```bash
python3 /path/to/print-kit/scripts/package_delivery.py /path/to/hardware/kit.json \
  --out /path/to/delivery/hardware \
  --source /path/to/model.py \
  --source /path/to/print-kit/scripts/kitlib.py \
  --source /path/to/print-kit/scripts/requirements.txt \
  --coupons /path/to/hardware/coupons

python3 /path/to/print-kit/scripts/package_delivery.py /path/to/printed/kit.json \
  --out /path/to/delivery/printed \
  --source /path/to/model.py \
  --source /path/to/print-kit/scripts/kitlib.py \
  --source /path/to/print-kit/scripts/requirements.txt \
  --coupons /path/to/printed/coupons
```

`--source` 可重复，显式选择重建所需源码与依赖说明；同名文件会被拒绝，按实际项目结构命名后交付。`--coupons` 可省略，但已生成的试片必须随打印包提供。工具不猜测用户目录，也不递归打包整个项目。未实测的实体反馈保持未验证。

将 [连接记录模板](../assets/connection-record.md) 填成每版 `coupons/connection-record.md`，随 `--coupons` 收录。关键连接与采购/全打印状态另写入 plan 的 `notes`、`joints.retention`、`hardware` 和 `assembly_steps`，工具会把这些说明带到页面与 PRINTING.md。模板和文本不是自动验证结果。

**工具覆盖范围**：现有 `parts/instances` 全部视为打印件，`hardware` 是说明文本。工具不会把外购配件变成 GLB/网页参考节点，也不做外购件碰撞；不要把外购节点混进打印清单。需要完整外购装配显示时，由任务源码扩展场景/页面，或使用满足本契约的其他打包实现。扩展后必须同步更新展示页内嵌的 GLB 下载字节并复核节点与 ZIP 过滤。弹性/旋拔/螺旋接口也需匹配的任务验证，不能跳过失败的通用验证或伪造报告。两版完成条件由实际产物与证据决定，不由此 CLI 是否退出 0 决定。

默认仅用实际 STL 实时绘制。若已审查同版的 `assembly.png`、`exploded.png`、`plates.png`、`operation.png`，可加 `--include-renders` 将现有图片嵌入效果区；脚本不会证明这些图片是否仍对应当前几何，执行者须先核对。参考图可另外加在页面中并注明来源，不混同为实物照片。

页面内嵌展示脚本、STL 和两个下载文件，可单独移交而不丢下载功能，不依赖 CDN、原案例目录、localhost 或开发服务器。浏览器需要 JavaScript 和 WebGL 才能操作 3D；下载初始化与 WebGL 分开，3D 初始化失败时仍保留文件下载。体积随零件增大，特别大的制作包可改用完整目录中的本地资源与相对下载链接，但必须整目录交付并重验。需要网页托管时按用户授权与宿主能力执行，不把发布设为固定前置条件。

## 原子契约与依赖

`package_delivery.py` 使用本工作流的 `kitlib.assembly_geometry`、`verify_kit.verify` 和已声明 Python 依赖，不依赖别的 skill。沿用 [阶段耗时](timing.md)，将打包、页面生成、下载复查计入交付阶段；脚本不自动采集整个业务流程。

| 函数/资源 | 契约及副作用 |
|---|---|
| `read_parts(plan_path)` | 读取 plan/STL，检查相对路径和文件摘要，返回 plan、字节字典与网格；文件变更或路径逸出时失败。 |
| `json_bytes/printing_notes/parts_csv` | 从内存数据生成 JSON、打印说明、数量 CSV，纯计算；非有限 JSON 数值失败。 |
| `zip_bytes(entries)` | 名称→字节生成 ZIP 字节，拒绝绝对路径和父目录跳转，不读写磁盘。 |
| `read_supplements(sources, coupons)` | 只读取显式源码文件和试片目录中的 STL/JSON/Markdown；同名附件或不存在的试片目录失败。 |
| `image_gallery(root)` | 读取指定目录内四种已审查 PNG，生成内嵌图片；不生成图像、不证明图片版本。 |
| `render_page(...)` | plan、STL、GLB、ZIP、说明、报告与已加载资源 → 自包含 HTML，纯计算；转义用户文本及 JSON 的 HTML 边界。 |
| `build_delivery(...)` | 编排几何验证、STL 复读、同版 GLB、ZIP 与页面；仅在 `out` 写入/覆写三个同名文件，错误向上传播，不切片、打印或发布。输出目录不得指向 skill 包。 |
| `assets/viewer/page.html` | 响应式页面模板和三项交付中的两个下载入口。 |
| `downloads.js` | 将内嵌字节转成 Blob 下载 URL，按页面生命周期清理；不使用网络。 |
| `viewer.js` | 输入是 `window.PRINT_KIT` 和配套 DOM；`loadSTL` 将二进制 STL 字节解析为网格，`mat/modeMatrix` 计算显示矩阵，`update/draw` 更新场景和画布。回调处理当前视图、旋转缩放与显隐状态；交互不修改制造文件。 |
| `vendor/three.min.js` | 随包 Three.js r160 浏览器构建，MIT，来源 [Three.js r160](https://github.com/mrdoob/three.js/tree/r160)。完整许可在 `LICENSE-three.txt`，随独立 HTML 保留。 |
| `scripts/test_delivery.py` | 在临时目录验证三项字节一致、GLB 节点/单位、ZIP 清单与失效输入；不模拟浏览器已完成验收。 |

## 交付前复核

- 两版各自解压检查数量、毫米单位、文件完整性和说明；外购件规格齐全且不混入打印清单，全打印版无遗漏的机械连接件。重新加载 GLB，检查打印件及外购参考节点数、实例位置与单位。比对每页内嵌 GLB/ZIP 与当前版独立文件字节一致，防止跨版串包。
- 实际打开页面，检查初始装配、拆解、摆盘、零件开关及移动端布局；点击两个下载按钮，检查所得文件可打开且内容正确。浏览器或自动化环境受限时完成可运行的文件/脚本检查，明确 UI 或点击行为未验证，不能把静态链接检查说成浏览器验收。
- 最终答复按“外购配件版”“全 3D 打印版”分组，各给“装配 GLB”“STL 打印包”“效果展示”三个真实链接，并主动打开效果页（宿主允许时）。用简短对照说明采购件、打印件数量、连接结构和实测状态。不要因为用户还未实际试打印而省略数字交付，也不要虚填实物装配成功。
