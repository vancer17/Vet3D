# 本地工具与原子契约

按入口打包约定生成的完整分发目录独立提供，脚本从自身路径解析随包资源，不从作者机器或相邻技能导入。`LAMP_SKILL` 指本工作流实际绝对目录，`LAMP_RUN` 指包外任务目录，所有输入/输出路径由执行者提供。日志、模型、媒体、计时和服务 job 不写回技能目录。

## 依赖与局部能力

| 脚本 | 可独立复用能力 | 副作用与失败边界 |
|---|---|---|
| `experience.py` | `brief_from_selection(data, catalog)` 纯校验/生成需求；`recommended_brief(catalog)` 返回标记为助手默认的完整流程需求；`read_catalog(assets)` 读随包目录 | `serve(output, port, assets)` 为 loopback HTTP 适配层；CLI start/status/recommend/stop 编排进程与本地记录。只接受目录/场景/范围枚举，补充最多 1000 字。不生成模型、不读取 Hi3D 密钥。重复相同提交复用 revision，改变选择递增；recommend 不伪造提交。 |
| `make_coupons.py` | `ring_mesh` 纯生成闭环网格；`stl_bytes` 纯三角化与二进制序列化；`write_coupons` 输出配合销、4 个间隙环及 4 个透光片 | Python 标准库，毫米坐标；拒绝已有 STL/试片说明目录。半径/高度须有限有效。样件只校准所列圆形配合及平片，复杂锁环另做同构试片。 |
| `stl_to_3mf.py` | `decode_stl` 解析索引网格；`model_xml` 构造含毫米单位的模型；`package_3mf` 序列化 OPC 包；`convert` 为文件适配 | 拒绝空/截断/长度不符、非有限数、顶点合并后塌缩的三角形与已有输出；不修网格，不证明水密、切片或机器兼容。3MF 只有几何，没有机器/材料配置。 |
| `preflight.py` | `check_nominal(data, existing_files)` 纯名义校验；`referenced_files` 提取声明路径；`check(data, root)` 检查这些路径是否为文件 | 检查毫米单位、硬件/安装包络、径向配合、床面和声称通过的证据文件存在。未读网格或证据内容，不能证明其真实或完整。CLI 0 表示所列名义项通过，可仍有 warnings；2 表示阻塞/输入错误。 |
| `generate_pleated_lamp.py` | Blender 例子：`build_materials`、`build_shade`、`build_base_and_hardware`、`export_parts`、`setup_studio`、`save_scene`、`render_preview`；底层 mesh/boolean/metrics/STL 函数可独立组合 | 创建场景、灯罩/底座、示意硬件、GLB/STL、工程与光效配置。CLI 会清空当前内存场景，仅用后台工厂环境；输出目录须为空。固定几何例子，仅 `--wall` 可调；硬件包络是示例，不是选定器件或 DIY 连接生成器。 |
| `render_states.py` | `configured_sources(cfg)` 校验命名灯/材质；`configure_render` 设置 Cycles；`render_states` 输出同轨迹 OFF/ON PNG 序列与场景/统计 | Blender 场景适配，需要相机、实际灯、有效三维目标；只切灯具自身源及配置发光材质，保持曝光、摄影光和几何。拒绝非空输出目录。是转台工具，不是装配动画或热仿真；渲染中断保留已有帧，重试用新目录。 |
| `encode_video.py` | `sequence_names` 纯序列检查；`encoder_command` 纯 argv；`encode` 编码、解码检查与 sidecar | Python + ffmpeg（libx264），不经 shell；要求从 0000.png 连续编号且无额外 PNG。拒绝已有 MP4/sidecar；失败可能留部分视频，换新输出路径重试。实际解码通过后才写报告。 |

Python 工具使用 3.10+ 标准库。Blender 脚本在 Blender 的 Python 中运行，使用 `bpy`/`bmesh`/`mathutils` 与支持 Principled `Emission Strength`、Cycles 和 GLB 的版本（4.x 或后续兼容版本）；按实际宿主验证，不声称全部版本均兼容。模型阅览器和 Draco 解码器随入口附带，其许可证保存在 `assets/experience/vendor/`。

## 调用

```sh
python3 "$LAMP_SKILL/scripts/experience.py" start --output "$LAMP_RUN/intake"
python3 "$LAMP_SKILL/scripts/experience.py" status --output "$LAMP_RUN/intake"
# 偏好时间已到且用户没有明确要求等待时，由执行者采用该输出继续设计。
python3 "$LAMP_SKILL/scripts/experience.py" recommend --output "$LAMP_RUN/intake"
python3 "$LAMP_SKILL/scripts/experience.py" stop --output "$LAMP_RUN/intake"

python3 "$LAMP_SKILL/scripts/make_coupons.py" --output "$LAMP_RUN/coupons"
python3 "$LAMP_SKILL/scripts/stl_to_3mf.py" "$LAMP_RUN/part_mm.stl" "$LAMP_RUN/part.3mf"
python3 "$LAMP_SKILL/scripts/preflight.py" "$LAMP_RUN/lamp-manifest.json" --output "$LAMP_RUN/preflight.json"
```

需要固定程序例子作为局部开发起点时才运行：

```sh
blender --background --factory-startup --disable-autoexec --python-exit-code 1 \
  --python "$LAMP_SKILL/scripts/generate_pleated_lamp.py" -- \
  --output "$LAMP_RUN/pleated-example" --wall 1.2
```

该例子输出 `pleated-lamp.blend`、`pleated-lamp.glb`、`print/` 下的毫米 STL、`geometry.json` 和 `light-states.json`；`--preview` 额外渲染两张 960px 静帧。例子不是入口四款样机的生成器，不是对任意新概念的自动建模器，不自动产生采购 BOM、完整网页、装配动画或全打印锁环。新设计在任务目录编写自己的几何配置和构建脚本。

双状态渲染/编码命令见 [渲染](rendering.md)，实际输出需打开图像、回读模型、解码视频；同时验证未执行的步骤如实标注。完整业务计时遵守 [阶段统计](timing.md)，`render-manifest.json` 的局部单调时钟耗时不能冒充全部任务耗时。

## 可复用验收方法

按入口打包约定在仓库外物化完整分发目录后，检查主入口及相对资料链接；在没有原目录/仓库邻居参与的条件下运行 recommend、入口提交、试片、转换和预检。用合成场景运行低分辨率 OFF/ON，检查帧数、光源状态、相机路径及固定曝光，再编码与解码。拒绝错误选项、异常 STL、缺帧、非空输出和缺失相机/光源。实际报告保存在包外，不将模拟测试当真实 Hi3D 或实物验证。

`render_states` 的 Python API 和 CLI 默认 `frames=1`，生成 OFF/ON 各一张静态图。多帧转台必须显式传入帧数，且在业务层确认视频已请求；编码器仅在可选视频分支需要。

试片公共实现见 [fit-coupon 契约](../../.dependency-fit-coupon/references/contract.md)，通过 package.json 物化。既有报告字段保留；新增配对记录中的 physical_test=not_run 仅表示尚无实际反馈。

目录资产读取公共实现见 [asset-page 契约](../../.dependency-asset-page/references/contract.md)，按 package.json 物化。概念选型、浏览器交互与本地服务保持本工作流实现；生成网页后仍需实际打开并检查下载。

网格拓扑测量通过物化的 [mesh-audit 测量核心](../../.dependency-mesh-audit/references/mesh-measure.md) 执行；本工作流保留旧字段、单位、面积阈值与通过条件。

STL 提取/序列化复用物化的 [print-export 核心](../../.dependency-print-export/references/blender-stl.md)。保留本品类的 raw、坐标系、摆盘、精度、法线阈值与头部适配；不重新实现二进制编码。

基础形体复用物化的 [shape-build 原语](../../.dependency-shape-build/references/primitives.md)，网格链接委托 [blender-tools](../../.dependency-blender-tools/references/scene-io.md)。保留本入口毫米/场景单位换算、集合、曲线/网格类型、材质、倒角与法线 profile；品类形状仍由此工作流编排。

基础材质复用 [blender-tools 节点构造](../../.dependency-blender-tools/references/material-nodes.md)，灯罩透光混合与实际光源材质仍由此示例显式建立。

放射竖片使用 [专项配方与检查](radial-lamp.md)，不把 `generate_pleated_lamp.py` 的连续褶皱壳体当独立竖片实现。任务构建脚本继续复用已有原语、STL 与测量接口；本次专项为执行指引，不声称已提供通用自动建模/Logo 检测脚本。

涉及无界布尔、重网格或离线渲染时，上述 Blender 命令交给物化的 `process_run.run_budgeted` 启动，按入口档位和 [预算契约](../../.dependency-run-tools/references/budget-run.md) 写预算/心跳；这些局部建模与渲染脚本自身不自动配置该保护，不能直接运行后宣称已受预算限制。
