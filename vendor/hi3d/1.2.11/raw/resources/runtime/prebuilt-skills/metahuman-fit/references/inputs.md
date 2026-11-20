# 输入与运行

## 依赖和版本

常规注册使用 Python 3.9+、NumPy 1.26+、SciPy 1.13+、Pillow 10.1+，检查/烘焙使用 Blender 4.2+ 的 Python API（代表性入口在 Blender 5.1 验证）。无需 Torch、图像关键点网络或在线服务。肤色融合和眼睛参数处理另需 OpenCV（已在 5.0 验证），由 `texture_python` 指向的解释器运行。DNA 适配器另需可导入 `dna` 的匹配 Python；本实现只接收 `DBName=DHI`，其他 rig definition 拒绝。

Epic 的 [MetaHuman DNA Calibration](https://github.com/EpicGames/MetaHuman-DNA-Calibration) 面向 UE 5.5 及更早版本；UE 5.6+ Creator 的新 DNA 需要对应的新工具。本包提供预提取的 [Taro 模板和配套 atlas](bundled-template.md)，不打包 DNA 运行库。macOS 可从官方源码编译其 Python 绑定，Python ABI 必须一致；运行时依赖和安装由目标环境提供。

可选表情测试另需 [Epic OpenRigLogic](https://github.com/EpicGames/OpenRigLogic) 的匹配 `dna`、`riglogic` Python 模块；与旧 DNA 写入器分进程运行，不能混用不同 ABI 的 `dna` 模块。驱动入口按 OpenRigLogic 的 quaternion joint-output 布局实现。依赖的构建时间不包含在主流程时间内；本包不执行 UE auto-rig。

## 模板、目标和注释

默认模板已在 `assets/taro/template.npz`，入口省略 `template` 即可自动使用；配套皮肤 atlas 也自动选择。模板侧区域和关键点索引见 `assets/taro/regions.json`，不含任何目标模型坐标。已有配置与标注必须匹配模板哈希。只有需要其他角色模板时才执行以下提取步骤。

用匹配的解释器提取一次模板，保存以供后续复用：

```bash
PYTHONPATH=/runtime/python python /skill/metahuman-fit/scripts/dna_io.py extract /assets/source.dna /work/template.npz
```

`template.npz` 的核心字段为 `vertices[N,3]`、`quads[F,4]`、`quad_uvs[F,4,2]`、`dna_sha256`；提取器还提供骨骼与权重以辅助标注。顶点/UV 来自原 DNA，不焊接、不重排。只有相同 DNA 的注册结果才能回写该 DNA。

`target.npz` 必须包含有限浮点 `vertices[M,3]`，并提供整数 `quads[K,4]` 或有限单位 `normals[M,3]`。前者接收已有 lowpoly，后者为直接高模表面采样，法线存在时优先采用点云分支，不运行 quad 平滑。图像/高模入口自动准备此文件，见 [图像管线](image-pipeline.md)。旧入口仍可接收独立 `head-lowpoly` 输出的 `lowpoly_data.npz`；不依赖其包。目标仅表示皮肤 neutral，眼球、牙齿和毛发不能并入。由操作者检查拆件与中性状态后声明 `target_parts=skin`，脚本不具备语义分割能力。

settings JSON 字段：

| 字段 | 契约 |
| --- | --- |
| `template_sha256`, `target_sha256` | 各 NPZ 文件的 SHA-256，必须完全匹配。重新导出后重新审核注释对应关系。 |
| `landmarks` | 至少 4 个非共线对应点；每项 `vertex_index` 为模板索引，`target` 为目标坐标 `[x,y,z]`，`weight` 为正数，默认 1。实际人脸应覆盖眼睑、唇线、鼻、前下巴和轮廓。可加 `name` 说明语义。 |
| `fit_indices` | 有观测的模板外皮索引，非空。排除眼球、牙齿、眼口内部和不可靠区域；不可靠耳部也排除。 |
| `target_fit_indices` | 可选、非空目标顶点索引；限制最近点候选，例如去掉源耳。先对完整目标计算平滑和法线，再过滤候选，避免删除拓扑造成边缘法线错误。 |
| `bake_indices` | 可选外皮烘焙索引，默认使用 `fit_indices`。独立标注可将唇面、耳部等可见区域用于烘焙，同时继续从拟合吸引中排除它们。 |
| `ear_regions` | 可选列表，每耳包含 `name`、`core_indices`、`blend_indices`、`anchor_indices`。核心保留模板耳形、窄根带做双调和过渡，至少 4 个非共线外侧根锚点。三类索引互斥，两耳活动区互斥；核心从 `fit_indices` 排除，根带可继续接收源表面观测。活动区不得与颈部修补或脸部关键点重叠，且自动从源烘焙排除。索引属于本模板，不能复制其他拓扑的耳部索引。 |
| `ear_max_fraction` | 默认 0.05；耳部恢复的最大位移占头部最大尺寸的上限。超限、退化锚点或奇异过渡直接失败。 |
| `bake_template_color_indices` | 可选模板索引，用于口腔内侧等区域。至少 3 个被选顶点的 quad 在 UV 上保留原模板颜色；从源投射、皮肤 Lab 调色与颜色融合中排除，法线保持平坦。需要 `template_albedo`。边界 3 像素过渡；外唇需保留源颜色时不能一并划入。 |
| `neck_fairing_indices` | 可选模板索引，仅标注不可靠颈部与过渡区域。双调和平滑延伸模板相对位移，区域外顶点保持逐值不变；此区域不参与最终外皮误差统计和原高模烘焙。与面部保护区或语义关键点有交集即失败。下边界保留固定锚点。 |
| `identity_protected_indices` | 启用颈部修补时必填、非空模板索引。独立标注需要保留的脸部，包含下巴体积、颏下轮廓、下颌角和源模型的其他身份特征；对照原高模确认分区。此约束只锁定颈部修补阶段，不替代拟合相似度审核。不得由错误的颈部 mask 简单取反来声称语义正确。 |
| `neck_fairing_max_fraction` | 可选，默认 0.2；最大位移除以拟合头部最大尺寸的上限，超过则失败。仍须几何和视觉检查。 |
| `mobility` | 可选 `[N]`，范围 0–1；控制颈底等区域移动并平滑过渡。陡变会造成折叠。 |
| `target_smooth_iterations` | 非负整数，默认 12；Taubin 平滑只作用于 quad 拟合目标。定向点云已在准备阶段平滑，此字段对它不生效。按皱纹尺度选择，不追逐高频扫描褶皱。 |
| `landmark_group_budgets` | 可选 group → 正数总权重；设置后每个 landmark 必须声明有效 group。密集眼唇推荐 left_eye/right_eye/lips 各 6，点数增加不改变组的总拉力。 |
| `landmark_strength`, `landmark_huber_fraction` | 默认 25、0（保持旧行为）。密集关键点建议 Huber 距离为目标包围盒最大跨度的 0.025；超过阈值的残差按距离降权，适用于非刚性迭代，不是异常检测器。 |
| `brush_stages` | 可选非空列表，每项 `sigma_edges>0`、`iterations>=1`。默认依次为 12/30、7/30、4/25；sigma 单位为对齐模板的中位边长。更小笔刷更易拟合细节，也更易破坏眼口。 |
| `ear_policy`, `provenance` | 可选说明实际策略和标注来源；`ear_regions` 才启用刚性耳恢复，`ear_policy=template_rigid` 必须同时提供区域。 |

拟合不固定模板坐标，3D 点使用目标坐标；Sim(3) 对齐模板。自动审核相机约定目标为 Z 向上、面朝 -Y；其他轴向应先对低模、关键点与高模应用一致变换，或修改相机方向。烘焙源应用 object transform 后必须与目标坐标一致。模板耳部应通过皮肤权重/语义区确定，不能把整个侧脸的包围盒当作耳朵。前下巴点要位于面部前缘，避免选到喉部。

## 工作流配置

以下字段描述通用脚本接口；默认业务流程使用随包模板 NPZ（可显式覆盖）、省略 `dna` 和 `expression_presets`，交付静态几何、贴图、原 Hi3D 高模和布线展示，见 [默认流程](head-workflow.md)。源 DNA 仅在需要提取模板时使用；已有 NPZ 不要求 DNA 运行库。

显式覆盖的路径均为调用方提供的绝对路径；省略 `template` 时使用随包资源。输出目录为空，或属于该工作流的可恢复目录。

```json
{
  "target": "/work/target.npz",
  "settings": "/work/settings.json",
  "hair_state": "bald",
  "target_parts": "skin",
  "blender": "/apps/blender",
  "output": "/work/metahuman-review"
}
```

```bash
python /skill/metahuman-fit/scripts/run.py /work/config.json
```

可选配置：

| 字段 | 作用 |
| --- | --- |
| `source_scene`, `source_object` | 启用贴图和 12 张对比图（原高模、源低模、注册几何、贴图结果各 3 视图）。输入原高模 GLB 或图片已打包的 `.blend`；多网格必须明确选中一个皮肤高模对象。保留原材质，以原始几何烘焙。外部图片依赖需先打包，否则不应复用内容缓存。 |
| `texture_size`, `render_size` | 默认 2048、800。贴图包含 albedo 和 OpenGL +Y 切线法线；normal 以 16-bit PNG 保存。 |
| `template_albedo` | 可选、与原 DNA 的 head UV 匹配的模板皮肤贴图路径，启用肤色匹配与泊松融合。模板贴图由调用方提供，不包含在包内。 |
| `texture_python` | 可导入 NumPy/Pillow/OpenCV 的解释器；主入口默认沿用自身 Python，直接调用 Blender review 时必须明确提供。 |
| `poisson_resolution` | 默认 512；在此分辨率解低频颜色校正，再叠回原分辨率细节。可提高至贴图分辨率做完整分辨率求解，耗时更长。 |
| `normal_feather_pixels` | 默认 24；法线在可信烘焙区域边缘的过渡宽度，与颜色泊松运算分开。 |
| `cycles_device` | 默认 CPU；可明确设为 `METAL`。设备不可用时失败，不偷偷改写为 GPU 已验证。 |
| `cage_fraction`, `ray_fraction` | 默认 0.012、0.06，乘高模最大包围盒尺寸；按遮挡与错投调整。 |
| `dna` | 请求将注册结果迁移回同一份 legacy DHI DNA。 |
| `dna_python`, `dna_module_path` | 匹配 DNA 绑定的解释器与 Python 模块路径；不填解释器时沿用调用方。运行库变化后使用新的输出目录，避免复用旧缓存。 |
| `template_eye_albedo` | 匹配模板眼 UV 的图像，需 DNA 装配数据。保持模板球体，仅改变纹理。未提供眼睛参数时直接使用原贴图。 |
| `eye_parameters` | 可选对象。提供参数时必须有 `center_uv:[u,v]`、`iris_radius`、`pupil_radius`；半径单位是归一化 UV，且 `0<pupil_radius<iris_radius<0.5`。模板 atlas 的中心与半径必须检查，不能跨模板硬编码。 |
| `eye_parameters.pupil_scale` | 默认 1，允许 0.3–2.5，缩放后瞳孔半径必须小于虹膜半径的 0.85；保持虹膜外缘和眼白逐像素不变。 |
| `eye_parameters.iris_color_rgb`, `pupil_color_rgb` | 可选 sRGB `[r,g,b]`，均为 0–1。前者保留虹膜亮度细节后换色，后者独立调瞳孔颜色。通常所谓“瞳孔色”指虹膜颜色；黑色瞳孔不必一起染色。 |
| `template_teeth_albedo` | 匹配模板 teeth mesh UV 的牙齿/牙龈/舌头贴图，嵌入预览 GLB/Blender；不使用头部皮肤颜色替代。 |
| `review_title` | 同相机总览和表情图的标题。 |
| `source_geometry` | 总览第二列标为 Source geometry；图像/高模管线自动开启。点云目标实际渲染源高模灰模，旧 quad 目标继续渲染源低模。 |
| `expression_presets` | 可选列表，启用真实原生求解；每项 `{name, controls:{完整raw-control名称:数值}}`，自动加 neutral。名称必须唯一，控制名必须存在于该 DNA，数值必须有限；控制范围由对应 rig 定义，调用方须选有意义的采样。空列表只测试 neutral，不配置则跳过。 |
| `riglogic_python`, `riglogic_module_path` | OpenRigLogic 解释器与模块目录；解释器默认主入口 Python。表情测试需 `dna` 输出；缺运行库时该阶段失败并保留上游结果，不虚构驱动测试。 |
| `expression_render_size` | 默认 640；有 `source_scene` 时，用真实求解姿势与已打包材质渲染表情图。无静态 review 时只输出求解数组/报告。 |

执行成功但几何检查失败时退出码为 **2**，候选文件照常保留；0 仍需视觉与运行时审核，异常为非零并记录失败阶段。相同目录重跑会校验输入、代码和产物哈希，只复用仍匹配的阶段。更换 Blender/DNA 原生运行库版本时选择新输出目录。

## 输出含义

- `brush_fit.npz` / `brush_report.json`：原始笔刷结果；`fitted.npz` / `fit_report.json`：局部耳/颈修订后的候选。几何阶段再产生 `registered.npz`，各阶段分别缓存。
- `registered.npz`：目标坐标的 `vertices`、对齐模板 `rest`、原模板坐标的 `native_vertices`、`quads`、`quad_uvs`、`linear`、`offset`、`dna_sha256`。
- `MetaHuman_Registered.obj`：原 DNA 坐标，保留顺序和 quad UV；不是新的任意拓扑 From Template 资产。
- `fit_report.json`、`geometry_report.json`：拟合区域误差和 neutral 三角交叉，完整说明统计范围。
- 可选 `MetaHuman_Review.dna` 及 JSON：原 RigLogic 行为表保留，neutral、几何与 corrective delta 迁移；写出报告只表明结构回读成功，实际驱动结果见独立 expression report。`.preview.npz` 是已装配 LOD0 的静态几何及逐角 UV。
- 可选 `textures/`、`renders/`、`overview.jpg`、`MetaHuman_Review.blend` / `.glb`：原高模/源低模/注册几何/贴图效果各 3 视图、标注总览和静态装配。GLB 自动回读核对头部坐标和嵌入图片；GLB/Blender 不含 RigLogic，不是经过 UE 验收的工程。
- 可选 `eye_report.json` / `textures/MetaHuman_Eyes.png`：眼睛纹理参数及结果。
- 可选 `expression_poses.npz` / `expression_report.json`：实际 OpenRigLogic 求解、corrective delta 与 CPU 蒙皮后的 LOD0 head/eyes/teeth 数组及分姿势统计；`expressions/` / `expressions.jpg` 是同相机正面采样图。仅证明列出的姿势已求解，不证明穿模/闭合/UE 引擎一致性通过。
- 可选 `skin_tone_report.json` 和 `textures/MetaHuman_*_Fused.png`：纹理侧肤色参数、UV 泊松融合/边界梯度与过渡后的法线；`MetaHuman_Template_Toned.png` 保留调色后的模板，原烘焙图不覆盖。
- `timings.jsonl`、`workflow.json`、`summary.json`：可恢复状态、阶段统计和本次运行结果。位于任务目录，不加入 skill 包。

可选 `ear_registration` 配置在 refine 后接入目标多视角耳部拟合；已有独立注册结果可直接调用 `ear_run.py`。字段、来源绑定和硬保护项见 [耳部子流程](ear-registration.md)。
