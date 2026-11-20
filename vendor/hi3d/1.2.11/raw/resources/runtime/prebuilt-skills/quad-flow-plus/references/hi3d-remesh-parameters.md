# 看完初版后，怎样把反馈翻译成调整

依据本次安装版本：QRemeshify 1.1.0、AutoRemesher 1.2.0、Instant Meshes 2026 扩展 1.0.0。本表翻译实际界面/公开参数，不把功能相近视为算法等效，也不声称每项参数都已做效果试验。

最有用的区分：**总面数**像决定一共用多少块瓷砖；**自适应**像把小砖多分给弯曲复杂处；**各向异性**像允许长条砖；**引导线**像指定砖缝走向。**硬边阈值**决定哪些折角应被当作棱；**平滑**决定怎样整理表面或网格，三者不能互相替代。

## 1. 相似功能放在一起看

| 用户想调整什么 | QRemeshify | AutoRemesher | Instant Meshes 2026 |
| --- | --- | --- | --- |
| 整体面更少、格子更大 | **Density 数值调大** | Target Quads 调小；Edge Scaling 是另一尺寸旋钮，通常先不动 | Target Faces 调小 |
| 整体更细、保留更多几何细节 | **Density 数值调小** | Target Quads 调大 | Target Faces 调大 |
| 总量大致保持，细节区更密、平面更疏 | 没有同名、直接等效的自适应滑杆 | Adaptivity 调大 | Curvature Adaptivity 调大 |
| 格子大小更均匀 | 没有直接等效滑杆 | Adaptivity 调小 | Curvature Adaptivity 调小 |
| 棱角更清楚，别把硬边磨圆 | 开启 Sharp Detect；酌情降低 Angle | 降低 Sharp Edge | 启用非负 Crease Angle，再酌情降低；不能把 -1 当作更强保边 |
| 网格更均匀顺滑 | Smoothing 是开关 | Smooth Normal 调整法线辅助的表面处理；不是同一种平滑 | Smoothing Iterations 控制平滑与回投次数 |
| 长管或长脊上的格子允许拉长 | 没有直接等效滑杆 | Anisotropy 调大 | 没有对应各向异性滑杆 |
| 让边沿着指定路径走 | 已有 sharp/seam/材质分界可提供影响 | 已有界面没有自由画布线参考的入口 | 使用用户的曲线/标注；不能拿加面代替引导 |
| 左右参考对称 | Symmetry X/Y/Z；先核对对称平面 | 本次公开界面/CLI没有对应对称开关 | Mirror X Symmetry；**本机 CLI 后端不传递此开关** |

角度阈值越小，通常越多折角被识别为硬边；过低也会把扫描噪声和细碎折面保下来。各软件实现不同，同样的“35°”不保证同样结果。

## 2. QRemeshify：主面板

定位：Blender 侧栏 **QRemeshify**。字段前缀：`QW = bpy.context.scene.quadwild_props`；`QR = bpy.context.scene.quadpatches_props`。

| 看到的英文（字段） | 直白翻译 / 怎么理解 | 调整方向与限制 |
| --- | --- | --- |
| **Density**（`QR.scaleFact`） | 面格尺寸倍率；标签叫密度，实际数值方向像“砖块大小” | 默认1；范围0.01–10。**增大→格子通常更大、更疏；减小→更细**。不是精确面数输入 |
| Preprocess（`QW.enableRemesh`） | 先清理、简化及重新采样输入 | 默认开。适合输入不均匀或有常见问题；也可能损失细节，不是保形保证 |
| Smoothing（`QW.enableSmoothing`） | 四边面生成后的平滑整理 | 默认开；只有开/关，没有强度滑杆。保留硬边仍要依靠特征设置和验收 |
| Sharp Detect（`QW.enableSharp`） | 启用特征边识别 | 默认开；利用角度及已有 sharp、seam、材质/面组边界等信息 |
| Angle（`QW.sharpAngle`） | 多大的折角才当作棱 | 默认35°，范围0–180°。降低→识别更多棱；升高→忽略较弱折角 |
| Symmetry X / Y / Z（`QW.symmetryX` / `QW.symmetryY` / `QW.symmetryZ`） | 沿指定轴切半并镜像结果 | 默认全关。先核对原点、轴向和实际对称性；不是“轻微偏对称”权重 |

### QRemeshify：Advanced 与 Callback Limits

这些主要是求解器设置。作者未完整说明部分高级项；下表只解释已知概念。不能从“更精细”“更像原图”直接推断一串高级参数，也不把求解最优程度当作几何误差。

| 英文（字段） | 简洁翻译与使用倾向 |
| --- | --- |
| Debug Mode（`QW.debug`） | 显示中间结果，方便诊断；不是质量档位。默认关 |
| Use Cache（`QW.useCache`） | 复用同一输入已完成的中间阶段。默认关；源网格、特征、对称或预处理变化后不能沿用旧缓存 |
| Alpha（`QR.alpha`） | 度量一致性与规则性之间的权重；默认0.005。提高会增加 isometry 项相对权重，不等于提高轮廓保真度 |
| Isometry（`QR.isometry`） | 启用度量一致性项，尽量减少划片度量变形；默认开。不是单位、体积或误差锁定 |
| Regularity / Quadrilaterals（`QR.regularityQuadrilaterals`） | 四边形区域的规则性约束；默认开。不是“所有面必须正方形” |
| Regularity / Non Quadrilaterals（`QR.regularityNonQuadrilaterals`）及 Weight（`QR.regularityNonQuadrilateralsWeight`） | 非四边形区域的规则性项与权重；默认开、0.9。按求解器区域定义，不是允许多少三角面的开关 |
| Align / Singularities（`QR.alignSingularities`）及 Weight（`QR.alignSingularitiesWeight`） | 尝试让不规则汇聚点的布局更协调；默认开、0.1。不是自动补眼口环或删除所有极点 |
| ILP Method（`QR.ilpMethod`） | 整数优化的目标形式：`LEASTSQUARES`=最小二乘，`ABS`=绝对偏差；默认前者。不是低/高质量档位 |
| Time Limit（`QR.timeLimit`） | 优化阶段时间上限，默认200秒、至少1秒。增加只是给求解更多时间，不保证更好，也不是整条流水线总时限 |
| Gap Limit（`QR.gapLimit`） | 求解器的最优差距停止阈值，默认0；较严格通常更费时。**Gap 指优化差距，不是模型破洞或毫米误差** |
| Minimum Gap（`QR.minimumGap`） | 另一求解 gap 控制，默认0.4；其与停止条件的组合没有完整说明，默认保留，不凭名称推断“补缝”效果 |
| Fixed Chart Clusters（`QR.fixedChartClusters`） | 内部划片簇的固定参数，默认0；不是独立部件数或目标面数。未验证具体语义时不自动调整 |
| Repeat Losing Constraints / Iterations（`QR.repeatLosingConstraintsIterations`） | 约束放宽重试相关的迭代开关，默认开；不是普通平滑迭代次数 |
| 同组 Quads / NonQuads / Align（`QR.repeatLosingConstraintsQuads` / `QR.repeatLosingConstraintsNonQuads` / `QR.repeatLosingConstraintsAlign`） | 分别控制对应规则的放宽重试；默认关/关/开。可能放松原约束，默认不由外观反馈触发 |
| Hard Parity Constraint（`QR.hardParityConstraint`） | 强制求解中的奇偶约束，默认开；不单独构成纯四边面、水密或保边保证 |
| Flow Config（`QR.flowConfig`） | 求解流程预设，`SIMPLE` / `HALF`；默认 `SIMPLE`。不是表面“边流顺滑程度”滑杆 |
| Satsuma Config（`QR.satsumaConfig`） | 后端求解策略：`DEFAULT`、`MST`、`ROUND2EVEN`、`SYMMDC`、`EDGETHRU`、`LEMON`、`NODETHRU`；默认 `DEFAULT`。缺乏效果证据时不自动试遍 |
| Callback Limits / Time Limit（`QR.callbackTimeLimit`）与 Gap Limit（`QR.callbackGapLimit`） | 8组阶段时间/求解 gap 策略；默认时间3/5/10/20/30/60/90/120秒，gap为0.005/0.02/0.05/0.10/0.15/0.20/0.25/0.30。属于求解停止策略，不是表面误差曲线 |

## 3. AutoRemesher：六个主要旋钮

当前安装为独立应用。名称对应其界面；括号内是供 AI 使用的 CLI 参数。

| 英文（CLI） | 直白翻译 / 类比 | 调整方向与范围 |
| --- | --- | --- |
| Target Quads（`--target-quads`） | 目标四边面总数＝总共铺多少砖 | 默认50000；增大通常更细，减小通常更疏。GUI范围1000–1000000；CLI已验证可用300，不能把GUI下限当成CLI统一限制。实际面数不保证命中 |
| Edge Scaling（`--edge-scaling`） | 参数化格子的边长倍率＝砖块再放大多少 | 默认1，范围1–4；增大通常格子更大、面更少。和目标面数会共同影响结果；通常先改目标面数，不同时乱拧两个旋钮 |
| Sharp Edge（`--sharp-edge`） | 硬边识别角度 | 默认90°，范围30–180°；降低→更多折角被保护，升高→只保留更明显的硬折 |
| Smooth Normal（`--smooth-normal`） | 重采样时的法线平滑角度＝按多平滑的表面来理解输入 | 默认0°，范围0–180°；0偏原始折面，增大可使曲面过渡更顺。会参与几何处理，**不等同于 Blender 的纯显示平滑** |
| Adaptivity（`--adaptivity`） | 按曲率重新分配面密度 | 默认1，范围0–1；0较均匀，增大→弯曲复杂处更多小面、平缓处相对更疏。不是全局加面，也不是任意指定区域加密笔刷 |
| Anisotropy（`--anisotropy`） | 允许面沿较平直方向拉长＝允许长条砖 | 默认1，范围0–1；0倾向近方形，增大允许沿管、脊等局部方向拉长。不是模型整体缩放，也不接受任意画出的方向线 |

输入/输出/报告路径（`--input` / `--output` / `--report`）是文件参数，不是外观调整旋钮。

## 4. Instant Meshes 2026：Retopo 面板

字段前缀：`IM = bpy.context.scene.retopo_props`。**当前本机使用扩展配套的 CLI 后端**；下面将界面能力与实际生效范围分开。

| 英文（字段） | 直白翻译 / 调整方向 | 本机情况 |
| --- | --- | --- |
| Target Faces（`IM.target_faces`） | 目标面数；默认5000，范围16–1000000。增大通常更细，减小更疏 | 可传递；实际面数近似 |
| Curvature Adaptivity（`IM.adaptivity`） | 曲率自适应；默认0.35，范围0–1。越大越向曲率复杂处倾斜面预算 | 可传递；与总面数旋钮分开 |
| Pure Quad Mesh（`IM.pure_quad`） | 尽量输出全四边面；默认开。关则允许四边面为主的混合面型 | 可传递；开启可能追加细分并改变实际面数，不能靠开关声明拓扑已通过 |
| Mirror X Symmetry（`IM.mirror_x`） | 将参考按世界X=0平面镜像；默认关；不是自动识别任意对称平面 | **当前CLI不传递**。要对称须检查用户提供的显式双侧参考，或先解决兼容原生后端；不能只勾选便报生效 |
| Singularity Filter（`IM.filter_singularities`） | 整理不必要的极点/螺旋流；默认开，不保证没有极点 | **当前CLI固定开启**，面板取消勾选不会关闭。没有可用的CLI切换参数时不能编造一个 |
| Intrinsic Cotangent Laplacian（`IM.intrinsic`） | 内蕴求解方式；默认开。像换一种计算邻域关系的方法，帮助处理不均匀三角网格 | 可传递；不是“增加细节”或“更光滑”的强度滑杆 |
| Align to Boundaries（`IM.align_to_boundaries`） | 让边流沿已有开放边界走；默认开 | 可传递；不表示自动封洞，也不等于边界坐标绝对锁死 |
| Smoothing Iterations（`IM.smooth_iterations`） | 平滑并回投到原表面的次数；默认2，面板范围0–10。增大＝多做几轮整理 | 可传递；回投后仍需检查细节和棱角，次数越多不必然更好 |
| Crease Angle（`IM.crease_angle`） | 硬折角识别阈值；默认-1关闭；范围-1–180°。设为非负才启用，启用后降低通常保护更多棱 | 可传递；-1不是最强保边 |
| Use Viewport Annotations（`IM.use_annotations`） | 把视口标注也作为布线参考；默认开 | 控制读取标注；**关闭后仍会读取符合条件的曲线**。本次实测的是曲线输入，标注兼容性需当场检查 |

**Draw Guide**=进入画参考工具；**Clear**=清空相关标注，属于修改参考数据的动作，不是强度开关。用户只是说“这一轮不要受参考影响”时，应在工作副本中排除对应参考，保留原参考，不直接清空。

曲线只要名字包含 `contour`（不区分大小写）或被选中，就可能参与求解；单纯隐藏不等于排除。当前面板没有“引导权重/作用半径”滑杆，CLI也未暴露这些调整；“更听这条线的话”应落到参考路径的明确修改与结果检查，不捏造 `guide_strength` 参数。

Quality Gates 中的 Purity（四边面占比）、Regularity（常规价数比例）、Topology（流形状态）、Distortion（局部变形）是**只读结果**。当前CLI分支不更新这些内存模块专属面板字段；不能依赖空白或旧值判断新结果，应另做实际网格统计。

## 5. 用户的一句话，译成怎样的动作

| 用户反馈 | AI先怎样理解 | 首选动作与应保留的条件 |
| --- | --- | --- |
| “面太多，再少一点” | 总预算下降 | Q：增大 `scaleFact`；Auto：降低目标quads；Instant：降低目标faces。其他参数先不动，检查轮廓/硬边 |
| “保留总面数，把面用在细节上” | 改密度分配，不是整体加密 | Auto / Instant：提高自适应并以实测总数核对预算。Q无直接同类滑杆，不假装有；局部目标需另定可支持的处理范围 |
| “格子别忽大忽小” | 面尺寸更均匀 | Auto / Instant：降低自适应；同时检查是否是长宽比问题，不能把密度与形状混为一谈 |
| “四边面太长，方一点” | 降低长宽比 | Auto：降低各向异性。Q的规则性项不直接等于长宽比旋钮；Instant无同类滑杆，需检视引导与局部网格，不能保证一钮解决 |
| “这条棱别圆了” | 指定特征保护 | 在目标部件上核对硬边标记/角度，必要时减少几何平滑；只降低显示光滑度不能恢复丢失轮廓 |
| “面绕眼睛/孔口走” | 明确边流路径 | Instant：取得或编辑用户指定闭环参考，再检查实际环线。Q可利用现有特征影响，但不承诺等效人工眼口布线 |
| “更顺滑一点” | 先区分轮廓、网格排列和高光显示 | 轮廓锯齿可能需更多面；网格排列需对应平滑；只有高光折线先检查法线/着色，不立即重拓扑 |
| “少一点极点、别打旋” | 优先处理边流和极点布局 | Instant先检查引导；本机过滤已固定开。Q可检查奇点对齐项；不能保证消除拓扑必需极点 |
| “左右一样，但耳饰别镜像” | 部件级对称，排除附属件 | 只对明确对称的主体设置对称或双侧参考；饰件保留，不对整件一刀切镜像 |
| “只改这里，其他别动” | 局部范围锁定 | 先确认后端能否真正局部处理。全局参数不能承诺局部影响；必要时在工作副本中分离可独立部件，或说明需换局部方法并收集新偏好 |
| “快一点” | 先判断是在等待还是要牺牲计算投入 | Q可在不改变源/特征的条件下复用缓存或减少优化时间；不是自动降低验收标准。其他后端不编造“速度/质量档” |

## 6. 给 AI 的调整指令契约

1. **先复用初版**：读取该版本实际参数、实际后端和面数，不重新生成输入、不重装插件、不重新选已经确认的方案。记录用户说的对象/部位与优先级。
2. **分清可见问题**：总面数、密度分配、格子长宽、特征棱、边流路径、对称、几何平滑、法线显示、求解速度分别判断。能从当前模型与话语明确推断就执行；歧义会改变主要形状或范围时用输入面板澄清。
3. **生成最小变更清单**：写清 backend、scope、goal、parameter、before、after、reason、保持项、验收项。before必须来自当前工程；没有实际值先读取，不用默认值冒充。一个明确反馈优先只改对应旋钮或必要的最小联动。
4. **识别不支持**：CLI固定/未传递项、没有局部能力、没有引导权重等情况，明确不能靠那个开关达成；给可执行替代。必要参考、改范围或换算法的选择按面板规则处理，不用超时伪造用户参考。
5. **只执行一版修订**：在保留初版的工作副本上重跑确有必要的阶段，输出新版本。一次调整后只检查受影响项及必要交付，不自动扫参数或反复试到“看起来不错”。失败保留记录，复用已有成果处理缺失步骤。
6. **报告实际变化**：例如“目标预算从A改到B，实际面数由C变为D”；说明轮廓、棱角、参考环线等是否达成。参数写入成功不能代替效果成功，目标预算不能代替真实面数。

**示例：用户说“用 AutoRemesher 再少20%的面，棱角和格子分配别变”。**

- 以初版实际输出四边面数 `F` 为基准，将 `--target-quads` 设为 `round(F * 0.8)`，作为本轮近似预算；不是对未实现的旧目标直接打八折。
- `--edge-scaling`、`--sharp-edge`、`--smooth-normal`、`--adaptivity`、`--anisotropy` 保持初版值，不同时改变密度分配。
- 重新输出一个工作区副本，统计实际面数及轮廓/硬边差异；如果未命中20%，报告偏差，不自动重复迭代或声称精确达到。

**示例：用户说“QRemeshify 只想细一点，别改边流规则”。**

- 读取当前 `QR.scaleFact`，向下小幅调整；保持硬边、对称、平滑与高级求解项。若用户只说“细一点”，明确采用一次小幅试调，不保证某个精确增面比例。
- 保留初版与原输入；缓存仅在同一输入和上游阶段完全未变、且缓存确实存在时可复用。核对真实增面量、细节与既有边流，不宣称边流绝对不变。

## 已有quad基线的大幅减面

反馈目标是“剩十分之一”等大幅减面，且用户已允许更换拓扑时，先按 [预算重建分支](hi3d-budget-rebuild.md) 判断是否复用可靠边链另建低面网格；不强行把此目标翻译成已失败后端的一个滑杆，也不批量试遍插件。没有重建允许时，继续保形模式或在实测冲突后收集必要取舍。

记录用户目标采用的原生quad/GLB三角面口径，分别报告几何基片数与最终quad数。仍然保留本表对真实参数、最小调整、参考保留和不支持项的规则；本分支不是任何插件新增的“边流权重”参数。

## 参数来源

参数名称、范围和默认值以本次发布包声明、UI绑定、公开CLI帮助和指定项目源码中实际传参为依据。QRemeshify高级项未完整文档化的部分已明确保留未知；不能把概念翻译当作这些策略已做效果对比。三个后端此前完成的合成网格冒烟验证继续有效，本次整理没有批量运行参数试验。

公开来源：[QRemeshify](https://github.com/ksami/QRemeshify)、[AutoRemesher](https://github.com/huxingyi/autoremesher)、[Instant Meshes 2026](https://github.com/MondRubberduck/instant-meshes-2026)。
