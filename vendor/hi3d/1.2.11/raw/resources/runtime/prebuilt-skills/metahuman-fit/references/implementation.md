# 实现、速度与验收

## 算法取舍

参考 [BrushFit](https://github.com/rcc-cubAC/BrushFit) 的粗到细平滑笔刷思想，使用独立的 3D 实现：加权 Sim(3) 对齐 → 平滑目标 → 正向兼容表面/法线吸引与语义关键点残差 → 稀疏 Gaussian 空间控制场。旧 quad 目标用 Taubin；直接高模目标用按面积采样后的法线相容局部平面投影，细节原模另留作 bake。每步重新建立空间笔刷，限制邻近薄层的速度差，并回退会翻转局部三角形的步长。它是局部平滑优化器，不是已证明无交叉的微分同胚求解器。

皮肤几何追踪低频形状；高模细皱纹进入贴图。拟合 mask 负责去除内部表面和源耳。模板耳先随场移动，再按根部锚点做无缩放刚性恢复，仅在窄耳根带延伸修正位移，带外脸部保持不变。根带应由语义/拓扑圈确定并可视化；不能为消除接缝扩大到腮部和颈部。眼皮、内唇和薄层需要额外视觉/运行时审核。

颈部截断会将 cap/裁切边错误拟合成后颈台阶。分别标注颈部先验区域和面部保护区，以双调和能量最小化延伸模板相对位移；与保护区或语义关键点重叠时拒绝运行。区域外顶点从输入直接复制，逐值不变，并报告保护区最大位移。拟合度统计与烘焙排除颈部先验区域，避免投射截断面的黑线。单一模板高度无法区分颈部、下巴底部和下颌角，必须对照源模型审核分区；法线贴图只能补细节，不能补被改掉的下巴体积或侧脸轮廓。

DNA 分支保留拓扑、UV、蒙皮、关节命名、旋转和行为表：对 neutral mesh 用空间位移场，对原始 corrective delta 用局部 Jacobian，眼球/牙齿/唾液部件以平均位移平移；neutral joint world position 迁移后还原为局部平移。它不会重新训练行为表，也没有检查所有 LOD 的接缝与附件间隙。保留 target 数量不是驱动正确性的证据。

Epic 的 [From Template Mesh](https://dev.epicgames.com/documentation/en-us/metahuman/from-template-mesh) 对顶点语义与拓扑有要求。这里的 OBJ 是配套 DNA 的原生顺序结果，是否能直接用于用户选定的 Unreal 导入路径仍需在对应版本确认。

## 原子模块

| 模块 | 输入 → 输出/副作用 |
| --- | --- |
| `template_defaults.py` | 配置 → 以 skill 位置解析随包 Taro 模板和 atlas，返回配置副本；显式自定义模板不继承 Taro 贴图，不启用 DNA，缺随包文件报安装不完整。 |
| `image_pipeline.py` | 显式调用 hi3d-api CLI，固定 quality/几何纹理/500 万面，分段轮询并复用任务；组合高模准备、源绑定注释、注册与交付，记录父级计时。客户端、路径和配置显式传入；缺标注保存检查点。 |
| `prepare_high.py` | Blender 导入指定皮肤 GLB 对象 → 应用变换的完整烘焙场景、原始表面采样 NPZ、源三角/面/顶点对应、真实面数报告；不重拓扑。 |
| `surface.py` | 纯数组：确定性面积加权三角采样与重心坐标；32 邻域、法线点积大于 0.7 的局部平面投影，位移截断为设置半径。输出平滑点与单位法线，原几何不修改。 |
| `brush.py` | 纯数组：相似变换、邻接/法线/平滑、Gaussian 场、语义分组权重、鲁棒关键点残差、粗细拟合与统计；不读文件。 |
| `neck.py` | 模板、拟合顶点、明确颈部和面部保护索引 → 拒绝区域重叠，带固定边界的双调和位移延伸；检查有限值、位移上限和面部固定不变量。mask 校验仅需 NumPy，可在 Blender 烘焙入口复用。 |
| `skin_tone.py` | 模板皮肤纹理、原高模烘焙与真实命中 mask → Lab 肤色匹配、多尺度泊松颜色融合、法线边缘过渡及报告；只需普通 Python/Pillow/OpenCV。 |
| `fit.py`, `refine.py` | 校验哈希、光头与皮肤声明、索引/数组；分别执行原始笔刷和耳/颈局部修订，写分阶段 NPZ 与区域误差。 |
| `ears.py` | 完整模板耳核心、窄根带与根锚点 → 刚性耳形、双调和过渡、位移预算与区域外不变性；不切割输出拓扑。 |
| `eyes.py` | 模板眼 atlas 和显式 UV/虹膜/瞳孔参数 → 虹膜换色、瞳孔径向变形；眼白像素不变。 |
| `mesh_io.py` | 顶点/四边形/逐角 UV → OBJ；保持顺序。 |
| `collision.py` | Blender BVH 候选与精确 segment-triangle 交叉谓词；排除相邻、共面与切触。 |
| `contact_repair.py` | 仅对新增交叉尝试极小顶点位移；总位移限制为头部尺寸 0.0001，最多 1000 个候选，只接受新增交叉减少且局部三角方向保留的候选。无法修复时保留失败。 |
| `check_geometry.py` | 对齐模板与拟合 neutral → 有界接触修正、注册 NPZ/OBJ、baseline/current/new 对及退化检查报告。 |
| `transport.py` | 纯数组：局部 Jacobian、空间位移插值、关节局部/世界坐标往返。 |
| `dna_io.py` | 匹配 `dna` 库读取模板、校准完整 DNA；回读 neutral 并核对结构，输出静态 LOD0 装配。 |
| `blender_io.py` | 明确的高模导入、网格/材质、相机与灯光适配，不依赖同级 skill。 |
| `review.py` | 分离 bake / preview 模式，可靠外皮烘焙及 emission 射线命中 mask；可选肤色融合、原生眼/口腔贴图装配、12 视图和静态工程。 |
| `preview_export.py` | 导出嵌入贴图 GLB，检查所有已贴图材质保留、法线贴图、附件数量，回读双向最近点和头部三角数；不导出 RigLogic。 |
| `expression_smoke.py` | 匹配 OpenRigLogic 读取校准 DNA、指定 raw controls → 原生 quaternion/shape 输出；corrective 在蒙皮前应用，CPU linear blend skinning，检查 neutral 与注册头一致、未知控制和非有限结果。 |
| `render_expressions.py`, `contact_sheet.py` | 已求解的 LOD0 顶点与静态材质 → 相同相机的表情帧；`make_sheet` / `make_expression_sheet` 用物化的 image-sheet 组合真实图片格位，自身保留业务标题、模式/视角顺序与 JPEG 保存。 |
| `run.py` | CLI、进程管理、内容缓存和阶段统计；异常保留已完成阶段，重跑校验哈希。 |
| `test_core.py`, `test_geometry.py`, `test_appearance.py`, `test_parts.py` | 合成数据验证变换、输入边界、缓存损坏/恢复及有界接触修正的成功与失败、颈部与面部区域冲突、固定顶点不变量、泊松/口腔 UV 对齐、刚性耳形、眼白不变和瞳孔调节、关节层级/蒙皮及缓存分区，不读取真实模型。 |
| `test_image_pipeline.py` | 合成表面面积分布/重心回投/确定性、相反法线薄层分离、点云输入校验、源面 mask 映射与旧索引拒绝、模拟 pending/下载/原任务续跑；不访问网络或鉴权。 |
| `test_contact_sheet.py` | 合成图片验证模式/视角顺序、70 像素标题区、底部标签、表情部分行与空姿势失败，不代替真实人脸视觉验收。 |

## 缩短运行时间

先复用已完成的高模与注释；直接采样控制最近邻查询规模，避免为了注册再制作中间低模。已有 3D 几何时不重新预测 2D 法线；语义关键点仍由明确注释提供。模板仅提取一次；DNA 先写入 MemoryStream，再一次转储到文件，避免每个数值单独写盘。稀疏 Gaussian 控制场与 KD 查询避免密集顶点两两矩阵。笔刷按最少满足轮廓的粗细层级运行；不要用更细的笔刷追逐皱纹。颜色在 Lab 空间以亮度分位数排除极端暗/亮区域后匹配模板，保留模板本身色彩变化。该映射不等同于调用 [Creator Skin Tone U/V](https://dev.epicgames.com/documentation/metahuman/skin-material-tools?lang=en-US)。多尺度泊松只在较小 UV 图上解低频校正，再加回全分辨率源细节；边界窄带过渡保持 UV 对齐。法线在切线 XYZ 中独立混合并重新归一化。

默认生成 static review；指定 expression_presets 后运行少量真实表情。视频或完整表情扫查单独做。OpenRigLogic 原生求解与 CPU 蒙皮需分别理解：前者执行 DNA 的行为表，后者是本包的离线预览，未宣称 UE 引擎像素或变形一致。quaternion 合成按官方 Advanced 示例使用 neutral × delta，translation/scale 相加；以静态 neutral 回读校验坐标和层级。

主流程分 preflight、fit、refine、geometry、可选 dna、bake、review、overview、expressions、expression_review。bake 内 albedo/normal/coverage 与肤色融合是子耗时，已包含在 bake 和总墙钟中。眼睛参数只使 review 及使用其材质的 expression_review 失效，复用拟合、DNA、烘焙和求解姿势；耳根或颈部修订可复用 fit，改变源拟合候选则必须重做 fit。缓存键绑定输入、代码与输出内容；更换原生运行库版本使用新输出目录。每阶段记录任务与尝试 ID、状态、UTC 起止和单调时钟秒数；失败/中断与跳过保留，重试追加同一任务的新 attempt。硬终止留下 start 事件时，下次运行标记 interrupted，缺失耗时为 null 并解释原因。总墙钟按单次调用起止计算，不能把子项重复求和；缓存命中记录本次校验成本及原 attempt。

模板提取、环境构建和人工标注若在本次业务中执行，应另记其起止与耗时，不能把准备好的输入条件下的主流程时间宣称为 GLB 全自动冷启动时间。`dna_io extract` 提供独立提取耗时报告。token 未采集时省略；不从耗时或额度推算。

`test_template_defaults.py` 校验随包模型/贴图的可读性、拓扑范围和内容完整性，以及默认静态配置、自定义模板隔离和显式贴图覆盖。

## 完成条件

检查模板与输出顶点/quad/UV 数组顺序；原资产保持不变。拟合误差是配置外皮顶点到平滑目标顶点的最近邻距离，非连续面 Hausdorff、非全头身份相似度；同时看关键点、轮廓与局部最大误差。每笔刷阶段 history 使用原 fit mask；最终 initial/registered 使用扣除颈部与模板耳先验区域后的共同 mask，二者不可混作同一口径。fit_report 的误差在微小接触修正前测量，修正位移单独见 geometry_report.correction。RMS 改善不能替代眼耳检查。

neutral 检查要求有限坐标、无退化、无新增非相邻交叉。记录模板已有交叉，不能隐瞒，也不能把 current 总数减少当作无新增。比较同一 triangulation 下的交叉对；极近切触应检查局部图像，当前容差并不能检测全部穿透。几何失败仍输出候选供审核，`summary.quality_status=geometry_failed`，CLI 返回 2。

烘焙检查眼唇边界、下巴、下颌角、耳部、后颈和未覆盖 UV；多尺度近似需检查小岛/UV 接缝。颈部修订须同时与原高模和修订前的已拟合头部对比，分别确认身份相似度与局部改动范围；仅有区域外位移为零不足以证明保护区划分正确。不要将统一填充区域描述成成功还原的源贴图。装配预览显示原生眼球和牙齿的 neutral 几何；眼壳/睫毛等辅助层因没有原生透明着色而隐藏，但仍保留在 DNA/preview NPZ。眼球采用匹配 atlas 和独立虹膜/瞳孔参数；牙齿/牙龈/舌头使用模板 teeth atlas。口腔内侧由显式索引保护原模板颜色，避免肤色 Lab 偏移将黏膜漂白。缺失模板贴图时统一材质只可用于几何诊断，必须列为视觉交付缺项。主流程不自动接受视觉质量。

DNA 在匹配环境验证 neutral、单控和组合驱动，检查眨眼闭合、视线、唇接触、张嘴牙齿、耳颈接缝及各 LOD。未执行时标记 runtime_validation=not_performed；已采样时标记 openriglogic_sampled_poses，仍需人工审核闭眼、腮部体积、口腔材质与内唇、牙齿间隙、组合极值及 UE/目标引擎行为。结构保留、可反序列化或有限顶点都不等于 rig 可用于生产。

Sapiens2 模板校准与目标点交接见 [关键点映射](sapiens2-landmarks.md)：`calibrate_sapiens2_template.py` 离线反投影并匹配可见顶点；`sapiens2_landmarks.py` 校验模板/点名并组装新目标 landmarks。

`project_sapiens2_landmarks.py` 在 Blender 中校验源网格、渲染图、相机和旧 mask 的哈希，反投影新目标的 308 点并生成分组 fit settings；只支持单人、正方形正交渲染。

烘焙公共执行与状态恢复见 [texture-bake 契约](../../.dependency-texture-bake/references/contract.md)。本地材质与区域适配参数、常量通道跳过及模板融合仍按本工作流配置；共享代码纳入 bake 阶段内容指纹。

geometry 的 signature 除 collision.py 外，也绑定它使用的 [三角度量核心](../../.dependency-mesh-audit/references/mesh-measure.md) triangle_arrays.py。核心改变后重跑几何审查；不含该依赖的 fit/refine 仍按各自指纹复用。

`contact_sheet` 的公共格位复用 [image-sheet](../../.dependency-image-sheet/references/contract.md)，显式 LANCZOS 拉伸、底部 30 像素标签带与 `(12,4)` 标签偏移；70 像素标题区、列标题、模式/视角与文件对应、`expression_report` 读取及 JPEG quality=92 留在本工作流。缺图/坏图失败；空姿势以 ValueError 失败，不写出空表情图。返回格位相对共享画布，本地未对外输出移位后的映射。overview / expression_review 的 signature 同时绑定 contact_sheet.py 与物化的 image_sheet.py，不使 fit/bake 无条件失效。

`preview_export` 导出后调用 [glb-clips.read_glb](../../.dependency-glb-clips/references/contract.md) 读取完整容器，不合并动作。静态无动画 GLB 可读；损坏或截断尾块失败，嵌入贴图、法线、附件数量、双向最近点/三角数及回读临时对象清理仍由该脚本负责。review 的 signature 绑定 preview_export.py 与 glb_clips.py；解析变更不使拟合或烘焙重跑。

可选耳部注册由 `scripts/ear_run.py` 编排，`render_ear_views.py` 记录目标视图，`ear_check.py` 适配几何验收与归档。算法与反投影分别物化自 surface-fit、landmark-project；配置、输出和失败边界见 [耳部注册](ear-registration.md)。
