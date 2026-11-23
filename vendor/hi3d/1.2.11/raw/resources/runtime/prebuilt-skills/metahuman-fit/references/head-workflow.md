# 默认光头流程调用

本页由 AI 编排现有脚本；停止规则、额外交付清单与视觉验收是执行者职责，并非脚本已自动实现。

## quality 与注册交接

`SKILL_DIR` 表示已安装完整 metahuman-fit 目录。若输入是人头 GLB，先按 [GLB 预处理](image-pipeline.md#人头-glb-的图像预处理) 渲染，再图生图；图片输入直接图生图。按 [正面无表情彩图](color-reference-prompt.md) 准备 `bald_color_front.png`，使用 `image_pipeline.py` 的 `image` 入口；完整配置见 [图像管线](image-pipeline.md#入口与依赖)。

```json
{
  "image": "/task/images/bald_color_front.png",
  "hi3d_api_script": "/tools/hi3d-api/scripts/hi3d_api.py",
  "output": "/task/head",
  "registration": {
    "hair_state": "bald",
    "target_parts": "skin",
    "blender": "/apps/blender"
  }
}
```

```bash
python "$SKILL_DIR/scripts/image_pipeline.py" /task/pipeline.json --dry-run
python "$SKILL_DIR/scripts/image_pipeline.py" /task/pipeline.json
```

固定 quality / hi3dv3.0 / 2048quality / request_type=3 / pbr=1 / 请求 500 万面，同时获取几何与纹理；默认不使用只生成几何的 `parts_generation.py`。复用同一 `hi3d_job.json`，缺标注时保留请求检查点，再按来源补齐标注继续。已有高模用 `high_glb` 替换 `image`。

省略 `template` 时自动使用 [随包 Taro NPZ 与皮肤贴图](bundled-template.md)，保留原拓扑、UV 与来源标识；无需再次向用户索要模板。模板侧 mask 和关键点索引可复用随包 `assets/taro/regions.json`，目标 3D 坐标仍须在本次高模上确定。仅有源 DNA 时才用匹配库提取一次模板。默认配置不包含 `dna`、`expression_presets`，也不需要 DNA 写入器/绑定运行时；不能从旧配置无差别继承这些字段。模板耳/口腔回填使用匹配 atlas。

## brush 实现与阶段控制

用户指定来源是 `head-geometry-repair/src/head_geometry_repair/workers/brush.py`；本包 `scripts/brush.py` 基于该 worker，现增加密集眼唇关键点的分组总权重和 Huber 距离降权；未配置这些选项时保留原权重行为，入口为 `fit_brush(template, quads, target, target_quads, settings, guard=None, observe=None, target_normals=None)`。使用随包版本即可，不依赖作者机器的绝对路径，不新增第二套优化器；只有修改算法或排障才读取源码。

默认 `brush_stages` 为 sigma_edges/iterations：12/30、7/30、4/25。保留法线相容最近点、关键点约束、位移/速度梯度限制及翻面回退。`mobility` 控制移动区域，但不是语义 mask 或完整碰撞保证；局部修订须验证带外顶点不变、无新增交叉。不能把重跑 `fit_brush` 当作从当前解继续，它会从模板重新做 Sim(3)；耳/颈微调优先使用已有 `refine.py`，其他区域只在必要时显式保存当前解并编排局部位移。

`image_pipeline.py`/`run.py` 一次运行会串联注册、修订、bake 和 preview（显式配置 DNA 时另有该分支）；它们没有“等待视觉验收”开关。需要在首次 bake 前审核时，用现有原子入口依次准备高模/表面/注释、执行 `fit.py`、Python 函数 `refine.run(config)`（该模块没有 CLI）和 Blender `check_geometry.py`；几何冻结后才进入颜色和 bake。保持阶段配置/来源一致，最终几何和贴图必须对应最后冻结的顶点。

对已经准备好的注册配置，分阶段入口为：

```bash
python "$SKILL_DIR/scripts/fit.py" /task/registration.json
PYTHONPATH="$SKILL_DIR/scripts" python -c 'import json; from refine import run; run(json.load(open("/task/registration.json")))'
"$BLENDER" -b --python-exit-code 1 --python "$SKILL_DIR/scripts/check_geometry.py" -- /task/registration/fitted.npz /task/registration/geometry_report.json /task/registration/registered.npz
```

`registration.json` 的 `output` 对应 `/task/registration`；手动调用也记录阶段耗时。几何/视觉通过后沿用该配置调用 `review.py -- <config> bake` 等原子入口完成下游，不能改回未微调的 brush 结果。

## 颜色与 bake

直接使用本次 quality 高模自带的颜色与原始几何，向冻结的 MetaHuman UV 烘焙 albedo 和 OpenGL +Y 切线法线。保留原始高模和贴图；不调用额外 texture、texture-bake、四视图上色或 UV 服务。拟合采样的平滑点云不能作为 normal 源。

在本地 Blender 调用现有 `review.py` bake，检查 coverage、眼唇、耳颈和 UV 接缝；仅修缺陷区域或 cage。模板口腔/耳部回填与泊松融合见 [配置](inputs.md)。已提供的静态眼球/牙齿资产可在 Blender 装配，保持来源与坐标；现有 `run.py` 的 DNA 附件预览分支不作为静态交付的必需步骤。

高模贴图缺陷只做本地贴图修补、模板回填或 cage 调整；仍无法解决时保留结果并报告，不调用 `texture_pipeline.py` 或远端补色/bake 服务。注册和局部微调始终以 quality 原高模为对照，烘焙接收最终冻结的注册网格。

## 交付验收

默认交付静态 MetaHuman 几何资产，不包括 DNA、绑定或表情：

- 原始 Hi3D 高模 GLB（不覆盖、不用减面版代替）；如另有上色高模，分别命名并记录变换与来源。
- 保留模板顺序/四边形/UV 的 OBJ、NPZ，最终 albedo、normal，贴图嵌入的 GLB/Blender。
- 固定相机正面、侧面、斜侧面：原高模灰模与注册灰模对照、最终四边形线框；另给眼睑/唇环/鼻翼局部布线图。由真实网格渲染，线框取规范 OBJ/NPZ 的 quad 边，不用 GLB 三角线框冒充四边拓扑；仅展示副本可隐藏颈部以下，规范 MetaHuman 网格不得删顶点。
- 产物清单、几何/视觉验收状态与阶段耗时摘要；注明静态资产、未执行绑定/DNA。

现有 `image_pipeline.py` 的 delivery manifest 不包含原高模和额外线框图；执行者在脚本交付完成后将它们加入最终交付目录，按现有 `files` 结构补充相对/绝对路径、bytes 和 SHA-256，并复查文件可读及清单完整。`overview.jpg` 只有灰模与着色对照，不足以替代布线展示。若手动分阶段执行，按相同清单组织交付，不能声称脚本自动打包了全部内容。
