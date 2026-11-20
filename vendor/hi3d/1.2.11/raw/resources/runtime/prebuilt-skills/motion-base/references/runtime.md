# 运行、输入与配置

按入口打包约定在仓库外物化完整分发目录后，以其中 `workflows/motion-base` 为命令起点，或将 scripts 改为该工作流包内的明确绝对路径。Python 3.12+安装requirements.txt；Blender 5.2命令路径由调用者提供，需可用glTF importer/exporter。文件读写均指向当前任务out/work，不能放进Skill目录或源目录。新Hi3D任务另行由独立hi3d-api负责；以下命令全部离线，只接收本地输入。

先读 [代码契约](code-contract.md)。CLI的`--help`显示完整参数。例中路径是调用者准备的任务路径；数值只是说明契约的示例，不能替代当前设备/身体/形体数据。不要使用Python优化模式（`-O`会关闭几何assert）。默认关闭视频仍是完整基础流程；`--skip-stills` 或只有 geometry 阶段仅适用于局部恢复，最终仍须图片、3D 和网页。明确请求视频后才启用视频分支。

## 标准四轮车

输入：一个实际GLB，艺术体具有可沿Z切出两个足部安全截面的厚脚，足底朝-Z，正面方向由读图归一化。`run.py`不是自动识别任意坐姿/薄翼的工具；足底剖面不足或内插榫外泄即停止结构阶段，在任务目录设计托盘/夹持替代，保留原角色。

```bash
python scripts/run.py --input ./input/character.glb --output ./result-standard --work-dir ./work-standard --blender /path/to/blender --config ./cart.json
```

config至少有`height_mm`（正数）和`boards`：每行`[variant_key, deck_length_mm, deck_width_mm, wheelbase_mm, wheel_radius_mm, palette_label]`。palette_label只随结构配置记录，场景脚本的中性/暖色示范配色需在任务中按用户偏好调整，不能说该标签已经控制全部材质。foot参数包括`sole_trim_mm`、`engagement_mm`、`radial_clearance_mm`、`depth_clearance_mm`；`axle_overhang_from_wheel_center_mm`需由外购轴/止退构造决定。脚底检测、CSG与碰撞仍会拒绝不适合的输入；参数化不表示任意数值有效。运行写construction、partsNPZ、毫米STL/原件、GLB、native、source-fit检查，完整模式还生成媒体。standard保留外购M3杆/螺母/止退的BOM，不假称可打印M3螺纹。

## 肩销DIY：明确的兼容输入适配器

`assets/diy/config.json`是一套局部机械夹具示例参数，必须由调用者显式传入，不能按用户只说开始就载入这个旧尺寸/主题。结构算法保留原脚底接口，将符合以下契约的车体换成四个桶形轮和四个双叉肩销。

```text
source-case/
  construction.json
  scene.blend
  print/character-with-blind-foot-sockets.stl
  print/skateboard-with-integrated-pegs-and-trucks.stl
```

- construction含board与joints；板100×62mm、topZ=29mm，wheelbase68mm、radius11mm、track72mm；两STL和native必须描述同一装配坐标/版本，STL毫米/native米。
- native含且仅含一个Mesh自定义属性`art=True`，它是待保留角色，已经位于与STL相同装配位置；贴图内置或可打包。没有该属性需先检查并明确标记，不以动物名字猜对象。
- 适配器会裁去旧底盘低于约21.65mm的轮组区并构建新座，要求原足榫/主体在保留区、支撑根连续。新布局不能删尺寸断言绕过；应根据本次目标改建适配器和独立验证。

```bash
python scripts/run_diy.py --source-case ./source-case --output ./result-diy --work ./work-diy --blender /path/to/blender --config ./assets/diy/config.json
```

输出10正式打印件（角色、底盘、四轮、四销），三档座+三档轮+完整销共7试片与1释放工具；NPZ、model/assembly/exploded/mechanism GLB、packed native、接口/运动/STL报告。输出的source-provenance只记录本次文件来源/哈希，不认证外部来源。`--stage verify`读取现有几何重新验证；`--stage media --render-video`读取当前assembly.blend渲帧/编码；全流程默认为all。媒体resume按实际scene SHA区分，不能用旧帧冒充更新。

每次实际检查销轴向两个极限、轮独立轴向极限及360度转动、双叉压缩/孔道/释放工具；报告范围是名义同轴离散位置，不是全部偏心/倾斜组合或物理试验。配置改变试片与主体必须一起重生。

## 当前可执行范围

CLI覆盖标准双脚四轮车和上面的限定DIY适配器。圆盘差动、自然托槽载具、可转膝机械支架属于业务设计能力，按SKILL独立设计轴耳、支承链、角限位/夹点及验证，再实现本次脚本，未提供现成CLI切换。产品介绍、当前BOM、包装、网页和发布由执行者继续完成，不能因脚本无网页命令而省略用户默认完整交付。

## 实现中的可覆盖缺省值

这些是几何/显示起点，用户目标与实测优先；未列出的下标读取字段需要调用者提供。

| 字段 | 代码缺省表达式 |
|---|---|
| `axle_overhang_from_wheel_center_mm` | `14` |
| `depth_clearance_mm` | `0.3` |
| `engagement_mm` | `5` |
| `radial_clearance_mm` | `0.25` |
| `sole_trim_mm` | `1.2` |

## 写入前路径边界

两个 runner 保留不同输入契约，共用 [本地路径契约](../../.dependency-run-tools/references/local-runtime.md#写入根与受保护输入) 的重叠判定。包根均为本工作流目录，已有输出/工作目录可续接且允许互相包含，同名派生产物会更新。

| 入口 | 写入根与受保护输入 | 配置与失败留存 |
| --- | --- | --- |
| `run.py` | `resolve_file_request` 在 mkdir 前保护 `--input` GLB、`--config` JSON；写入根为 `--output`/`--work-dir` | 配置必须在两个写入根之外；路径、JSON 与 height_mm 预检先于 mkdir，后续失败可能保留局部结果 |
| `run_diy.py` | `validate_write_roots` 在 mkdir 前保护整个 `--source-case`；写入根为 `--output`/`--work` | `--config` 不在根保护列表中；使用 all 阶段时应避开固定派生文件名，尤其不能直接用 `output/config.json`，否则复制配置时会同文件失败。可使用独立工作配置路径；缺少 source-case 必需文件是在 mkdir 后检查，可能留下目录 |

DIY 的配置规则不能用于标准入口。两条流程后续失败都可能保留日志或局部几何，恢复需核对当前输入版本及检查结果；独立阶段不自动获得 runner 的全部预检。

## 视频默认与显式启用

`run.py` 默认执行几何、静态图片、GLB 动作与检查，不渲染视频。仅在用户明确请求视频后加 `--render-video`；`--no-video` 保留兼容并与 `--render-video` 互斥。已有场景追加视频优先使用随包分段渲染/编码入口，不为追加视频重建模型。直接使用 `build_scene.py` 也默认不渲连续帧，只有明确设置 `ASTRA_SKIP_VIDEO=0` 才启用；`studio_preview.animate_video` 的 `render_now` 默认 False。

`run_diy.py` 同样默认不渲染视频；已交付 DIY 场景可用 `--stage media --render-video` 追加视频，`--stage verify` 不因该开关渲染。完整产品任务仍须完成 DIY 与网页；标准入口不是完整全打印交付。
