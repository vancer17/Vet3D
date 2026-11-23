# 可运行工具与输入约定

Python 3.9+ 工具只用标准库。几何工具在 Blender Python 内运行，所用算子在 5.2 验证；不依赖外部 pip 包。先定位实际 Blender 可执行文件，不依赖作者机器路径。脚本相对于实际 `<skill>` 目录调用，输入和输出全部放包外任务目录。

按入口打包约定生成完整分发目录并按宿主规则安装后，通过 `$mask-design` 显式调用；按宿主要求重新加载。Hi3D 作为另行提供的独立工具，见 [安装与交接](hi3d.md)。本地辅助脚本并不自动完成图像理解、美术造型、全脸适配、网站或视频；这些由执行者按入口工作流组合工具完成。

脚本的原子函数、副作用与失败边界见 [实现契约](implementation.md)。计算和检查可独立调用，不要求先运行 Hi3D。

## 默认头型

拒绝上传或暂缺照片时可直接运行 `python3 <skill>/scripts/default_head.py --out /absolute/work/default-head`。只用 Python 标准库，无网络或个人输入；输出固定原创 `Default_Adult_Head_v1` 的 OBJ 和 JSON。OBJ 坐标为 mm，X 左右、−Y 脸前、Z 向上。常见 OBJ 导入器默认把 Y 当向上，导入时明确保持此 Z-up 坐标或记录并应用相应旋转，避免头型横倒。

JSON 包含真实边界尺寸、合成眼鼻口定位、来源、哈希和基本拓扑；导入后复查方向、毫米尺度和闭合性。它是非个人设计夹具，既不是 NIOSH 标准头，也不是人体平均或本人头雕。脚本拒绝覆盖已有输出；继续任务时复用已生成文件，不需要每阶段重跑。完整面具的外壳仍按 Hi3D 流程制作。

## 尺度拟合

输入 JSON 的一条测量形如：

```json
{"measurements":[
  {"name":"face_width","kind":"straight","model_distance":0.15,"measured_mm":150,"uncertainty_mm":1},
  {"name":"face_length","kind":"straight","model_distance":0.12,"measured_mm":120,"uncertainty_mm":1}
]}
```

这是合成演示数值，不是默认人脸尺寸。`model_distance` 来自头模两个已对应标志点的直线距离，`measured_mm` 是本人相同定义实测值。头围不能填进来。

```bash
python3 <skill>/scripts/calibrate.py /absolute/work/measurements.json --out /absolute/work/calibration.json
```

结果 `scale_mm_per_model_unit` 是每模型坐标单位对应的 mm，不直接等于 Blender 的对象 scale。若要转换成米制坐标应除以 1000；同时正确保留场景 unit scale，避免重复换算。脚本不修改网格，agent 应保存应用变换后的适配副本并核查实际包围盒和标志点。

数据冲突仍输出报告并返回 2，单尺寸拟合写 `single_dimension_only`。输入错误/输出冲突同样可能返回 2，须读实际状态，不仅看退出码。拒绝覆盖输入和已有报告；修订使用新路径。多尺寸拟合一致只是稀疏尺度检查，不是全脸认证。

## 从已准备的脸部曲面片建立内壳

准备 `.blend`：保留校准头体 `Head_Calibrated`，另做单个开口曲面 `FacePatch`，包含意图中的周边、眼孔和通气口边界。曲面已完成平滑/重拓扑，法线从脸向外；不能传完整闭合头体、未清理生成网格或带厚度的壳。可选顶点组 `NoseRelief` 权重 0..1 平缓过渡，不要硬切跳变。使用组时先应用修改器以保持顶点对应。

```bash
<blender> --background --factory-startup --disable-autoexec --python-exit-code 1 \
  --python <skill>/scripts/mask_geometry.py -- liner \
  --input /absolute/work/prepared.blend --patch FacePatch \
  --gap-mm 4 --wall-mm 2.8 --relief-group NoseRelief --relief-mm 2 \
  --out /absolute/work/liner-v01.blend
```

4 mm 与 2 mm 仅为命令演示，实际按分区空间预算修改；无顶点组时省略组和 relief 两个参数。产生 `Mask_Inner`（测量用隐藏曲面）及 `Mask_Shell`（外向加厚实体），保留输入文件与原头单位。该基础工具**不自动平滑、不倒圆、不处理自交、不加锚点、不转贴外观**。继续按结构文档完成这些工作；修改内表面后重建对应 `Mask_Inner`，不能用旧测量面审计新壳。

命令拒绝覆盖输入、已有输出文件和场景中的标准输出对象。其拓扑检查不能确认法线一定朝外，运行前后用侧面和偏置方向检查。偏置/加厚不是任意曲面都可行，剧烈凸凹应重拓扑或用距离场方法。

## 抽样审计

```bash
<blender> --background --factory-startup --disable-autoexec --python-exit-code 1 \
  --python <skill>/scripts/mask_geometry.py -- audit \
  --input /absolute/work/final.blend --shell Mask_Shell \
  --head Head_Calibrated --inner Mask_Inner --samples 5000 \
  --min-wall-mm 2.4 --out /absolute/work/geometry-audit.json
```

只查壳拓扑时同时省略 head/inner。脚本评估修改器及世界变换，再转 mm；不把 unit display 当长度。报告边界/非流形/不一致绕序/组件/退化面、局部射线厚度、内表面面积加权采样距离、近接触和最近法线负号风险。网格内外符号为局部启发式，不是全域碰撞证明；缺少闭合头体时符号无效。稀疏采样可能漏掉小薄壁，射线厚度可能高估。按 [验证文档](render-and-validation.md) 完成余下检查。

脚本退出 0 表示报告已生成，**不代表合格**；例如 `status=topology_repair_required` 仍产生报告。`self_intersection`、`global_collision`、`slicing`、`strap_root_strength` 和 `personal_wear_test` 保持 `not_tested`，不得改成通过而无证据。

## 穿线/织带公差样件

```bash
<blender> --background --factory-startup --disable-autoexec --python-exit-code 1 \
  --python <skill>/scripts/mask_geometry.py -- coupon \
  --hole-mm 4.6 --slot-length-mm 22 --slot-height-mm 3.2 \
  --out /absolute/outputs/strap-coupon
```

输出 80×30×4 mm 平板、圆孔与圆角槽，入口有倒圆；文件为 `.blend`、米制 GLB、数值为 mm 的二进制 STL 及审计 JSON。范围限制对应本样件布局：孔 2..8 mm、槽长 10..30 mm、槽高 2..6 mm。要测试更大规格应修改布局并验证余肉。

CLI 使用一次性空场景；独立函数 `build_coupon` 要求传入当前空场景环境，拒绝删除已有工作。输出已有文件时拒绝覆盖；文件写入中断保留部分产物，检查后换输出目录，不将半套文件视为成功。

初始孔径/槽高需要与实际绳带、折返层数和端头核对；多个补偿值用不同输出目录保存。该平板只检查穿线、尺寸公差和后处理触感，**不能证明面具锚点根部强度**。强度样件从当前设计的真实根部裁取，保持曲率/厚度/层向。

## 工具验证边界

本包的工具可在本地不联网运行。本人照片转头雕仍通过所选服务或本地重建工具；没有把云端凭据打包。`liner` 是工程建模辅助，不能单独完成高细节美术设计或真人适配。只有所有相关阶段完成后，才能交付对应阶段的最终面具。

## 网页交付清单检查

按 `assets/delivery-manifest.template.json` 建立本轮相对路径清单，为每项填写真实文件字节数、SHA-256 和源版本。完整基础网页至少包含 `image`、`description`、`model`；`video_requested` 为 true 时才要求 `video`，所有存在的视频仍须验证。

```bash
python3 <skill>/scripts/validate_delivery.py /path/to/delivery/delivery-manifest.json --root /path/to/delivery --report /path/to/work/web-integrity.json
```

脚本只做清单与文件完整性检查；通过不代表视频已经完整解码、GLB 几何正确、网页交互可用或访问权限正确。这些项目按 [网页与视频交付](delivery-web.md) 分别验证。

## 离线验证

按入口打包约定在仓库外物化完整分发目录，从无关工作目录执行：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 <skill>/tests/test_local.py
PYTHONDONTWRITEBYTECODE=1 python3 <skill>/tests/test_delivery.py
<blender> --background --factory-startup --disable-autoexec --python-exit-code 1 --python <skill>/tests/test_blender.py
```

测试覆盖默认夹具的闭合与连续曲面、重复输出保护、尺度冲突、非法清单/路径逃逸/文件变更，以及穿带样件的实际开孔、内壳偏置和 GLB/STL 单位回读。所有样件为合成测试数据，写系统临时目录并清理；无真实密钥或收费调用。CLI 帮助、显式脚本执行与宿主技能发现/调用分别验证，不能互相替代。阶段计时由执行者遵从 [计时契约](timing.md)，这些测试不证明全流程自动计时。

交付清单脚本兼容Python 3.9+，默认验收无视频网页，明确请求后才将视频列为必需；存在的视频不会因可选而跳过哈希/源版本校验。报告使用新路径，拒绝覆盖已有输入或报告。
