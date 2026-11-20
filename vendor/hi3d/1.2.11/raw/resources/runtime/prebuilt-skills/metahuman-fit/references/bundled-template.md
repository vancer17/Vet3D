# 随包 MetaHuman 模板

直接查看用 [带皮肤贴图 GLB](../assets/taro/template.glb)；检查四边形布线用 [OBJ](../assets/taro/template.obj)，连同同目录的 `template.mtl` 和 `head_color_map.tga` 导入 Blender。GLB 内嵌贴图，可单文件打开；GLB 按格式要求三角化并在 UV 接缝拆点，OBJ 保留原始顶点顺序和四边形。两者都是头部皮肤模板，不含独立眼球或牙齿网格。

算法默认使用 [Taro template.npz](../assets/taro/template.npz)，包含 24,049 个顶点、24,002 个四边形及逐角 UV，保留原索引顺序。无需用户再次提供路径，也无需运行 DNA 库才能读取该 NPZ。

配套贴图：

- [皮肤](../assets/taro/head_color_map.tga)
- [眼睛](../assets/taro/eyes_color_map.tga)
- [牙齿、牙龈及口腔](../assets/taro/teeth_color_map.tga)

`image_pipeline.py` 的 registration、`run.py` 和 `fit.py` 可省略 `template`；`template_defaults.py` 从 skill 自身位置解析路径，自动选用配套皮肤 atlas。默认不启用 DNA/绑定。眼睛与口腔 atlas 已随包提供，可用于独立静态附件；只有显式 DNA 分支才自动填充其配置字段。贴图文件本身不是眼球/牙齿网格。

显式提供自定义 `template` 时不自动套用 Taro 贴图，需给该模板匹配的 atlas。已有标注必须与选定模板的 SHA-256 一致；随包模板不替代目标高模的语义标注。按入口打包约定物化完整分发目录后即可解析这些资源，缺文件时报包不完整，不要求用户重新购买/上传已有模板。

模板侧 [regions.json](../assets/taro/regions.json) 提供匹配哈希的外皮/烘焙 mask、耳根/颈部与身份保护区，以及 21 个命名关键点的模板索引。它不含目标坐标，不可用作另一高模的现成标注。

## 来源与使用范围

本机已有资源源自 Epic 官方 MetaHuman DNA Calibration 示例 Taro，模板由本包 `dna_io.py extract` 提取。原始来源版本、文件哈希见 [manifest](../assets/taro/manifest.json)，原随附条款见 [UPSTREAM_LICENSE.txt](../assets/taro/UPSTREAM_LICENSE.txt)。未打包 Epic 软件、运行库或源 DNA。

这是 Epic 示例角色数据，不是本项目原创或可任意再许可的公共素材；使用及共享遵循原许可和适用的 [Epic 内容协议](https://www.unrealengine.com/eula/content)。本包用于获授权的内部项目工作流；不要将这些源格式角色资产作为可自由下载的公共素材另行分发。

眼唇检测可复用 [Sapiens2 模板映射](sapiens2-landmarks.md)，含校准图、相机和原配静态眼球；算法默认使用 68 个眼唇顶点对应。

耳部使用同一模板的固定 `sapiens2_ear_mapping.json`，49 个默认点含三角形重心权重和顶点序号，按模板哈希校验；具体目标多视角流程见 [耳部注册](ear-registration.md)。
