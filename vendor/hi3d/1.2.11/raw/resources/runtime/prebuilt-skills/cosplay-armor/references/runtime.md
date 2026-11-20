# 运行、输入与配置

按入口打包约定在仓库外物化完整分发目录后，以其中 `workflows/cosplay-armor` 为命令起点，或将 scripts 改为该工作流包内的明确绝对路径。Python 3.12+安装requirements.txt；Blender 5.2命令路径由调用者提供，需可用glTF importer/exporter。文件读写均指向当前任务out/work，不能放进Skill目录或源目录。新Hi3D任务另行由独立hi3d-api负责；以下命令全部离线，只接收本地输入。

先读 [代码契约](code-contract.md)。CLI的`--help`显示完整参数。例中路径是调用者准备的任务路径；数值只是说明契约的示例，不能替代当前设备/身体/形体数据。不要使用Python优化模式（`-O`会关闭几何assert）。默认关闭视频仍是完整基础流程；`--skip-stills` 或只有 geometry 阶段仅适用于局部恢复，最终仍须图片、3D 和网页。明确请求视频后才启用视频分支。

## 输入与定位

两份实际GLB：身体部位和艺术护甲。先看正侧背，明确身体局部纵轴/朝向及艺术前后；运行内部分别焊接/归一化。身体长度与覆盖起止Z必须显式传入，来自用户测量、已标尺扫描或清楚标注的数字夹具假设，不提供偷偷替换真实人数据的默认值。

```bash
python scripts/run.py --body-glb ./input/body.glb --armor-glb ./input/armor.glb --out ./result --work ./scratch --blender /path/to/blender --body-region forearm --body-length-mm 560 --fit-start-mm 200 --fit-end-mm 410 --transverse-scale 1 --inner-clearance-mm 5 --pad-thickness-mm 8 --strap-skin-offset-mm 1.4
```

上述560/200/410仅演示显式参数，不是成人通用长度。前臂或护胫必须独立定位；`--body-region shin`不能复用前臂位置。允许`15<start<end<body_length-20`作为剖面采样边缘约束，余量/scale均正数；未满足即失败。`--body-yaw-deg`、`--armor-yaw-deg`分别调来源方向；`--armor-center-mode fitted|fixed`决定拟合中心，fixed另用center-x/y-mm。`--variant-name`小写英文数字短横线。

内部将艺术源归一化至230mm并采样，再映射到覆盖区，这是算法坐标规范，不是最终护甲高度。剖面需能由当前采样拟合为环绕肢体的连续截面，艺术壳应是可识别单侧甲片；其它身体部位/轴向折返/封闭互穿艺术体需另定采样法。椭圆包络余量不是皮肤间隙；附件用真实BVH跨Z全宽重新采样。

当前起点`transverse-scale=1`、`inner-clearance-mm=5`、`pad-thickness-mm=8`（上限）、`strap-skin-offset-mm=1.4`只是几何试制参数。垫受壳减.6mm、皮肤加1mm约束，不能把8mm都填满；15mm带/24mm垫检查全宽。数字身体非本人时输出持续标未校准，不宣称舒适或强度。

## 阶段与恢复

`run.py`编排两源inspect、profiles、build、finalize、STL/fresh-import/附件检查。配置写入当前work/config.json；单独恢复可调用：

```bash
/path/to/blender -b -t 2 --python-exit-code 1 --python scripts/finalize.py -- --config ./scratch/config.json
```

profile/build也接受相同`--config`，前提是同版本的inspection/剖面状态存在。变源或coverage后从对应依赖阶段重做，不能复用旧通过报告。`--skip-source-renders`略过源图，`--skip-renders`略过结果静图，不影响几何生成。

产物按variant目录有全模STL、配合试片、scene.blend、护甲/身体/穿戴GLB及量测；原始输入另在source保留。网页GLB另减面，不能用其替换高模打印件。native检查图像依赖。

穿脱使用`demonstrate_donning.py --help`的独立入口，必须明确先解除带/附件，再校验硬壳移出路径。长件用`split_for_printer.py --help`的显式scene/Z参数，之后validate_split回读STL检查表面/体积/人体；定位短榫需要胶，不是DIY锁。打印带、衬和无胶分段锁止未在此CLI实现，按diy-printing另建。动作关键姿态、产品/BOM与网页是执行者后续阶段，视频仅在交付后明确请求时追加，不把run.py成功当全业务交付。

## 写入前路径边界

`run.py` 在任何 mkdir 或业务写入前调用 `path_safety.validate_write_roots`：写入根为 `out`/`work`，受保护输入为身体 `--body-glb`（兼容 `--arm-glb`）与艺术 `--armor-glb`，包根为本工作流目录。具体重叠判断和通用限制见 [本地路径契约](../../.dependency-run-tools/references/local-runtime.md#写入根与受保护输入)。

本入口从 CLI 参数生成 `work/config.json` 并复制为 `out/parameters.json`；该配置是本次派生产物，可留在 work 供单独阶段恢复。已有 out/work 可重用且允许互相包含，同名派生产物会更新。源存在性、部位/覆盖参数和 Python 依赖检查通过后才创建目录；后续阶段失败可能留下配置、源副本、日志和局部几何，恢复须重验相关结果。
