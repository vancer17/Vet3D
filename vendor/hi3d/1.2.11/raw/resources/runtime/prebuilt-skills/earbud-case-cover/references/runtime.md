# 运行、输入与配置

按入口打包约定在仓库外物化完整分发目录后，以其中 `workflows/earbud-case-cover` 为命令起点，或将 scripts 改为该工作流包内的明确绝对路径。Python 3.12+安装requirements.txt；Blender 5.2命令路径由调用者提供，需可用glTF importer/exporter。文件读写均指向当前任务out/work，不能放进Skill目录或源目录。新Hi3D任务另行由独立hi3d-api负责；以下命令全部离线，只接收本地输入。

先读 [代码契约](code-contract.md)。CLI的`--help`显示完整参数。例中路径是调用者准备的任务路径；数值只是说明契约的示例，不能替代当前设备/身体/形体数据。不要使用Python优化模式（`-O`会关闭几何assert）。默认关闭视频仍是完整基础流程；`--skip-stills` 或只有 geometry 阶段仅适用于局部恢复，最终仍须图片、3D 和网页。明确请求视频后才启用视频分支。

## 输入与显式设备配置

对象是入耳式耳机的**充电盒外套**。输入实际GLB需大体紧凑、内有足够空间容纳设备与壁厚。原设备品牌/型号/代数/充电版本保持用户指定；官方宽厚高只定义名义外包络，圆角、盖线/铰链、接口和操作区要单独取得。缺实测则标“待校准数字版”，不能自动换同品牌其他款。

```bash
python scripts/run.py --input ./input/art.glb --output ./result --work-dir ./scratch --blender /path/to/blender --config ./cover.json
```

必要配置：`height_mm`、`outer_width_mm`、`outer_depth_mm`为艺术外体拟合尺寸；`device_mm:[width,depth,height]`为设备本体，全部毫米；`profile`为同版本设备文字标识，`key`为输出子目录名；`led_center_z_from_bottom_mm`为LED相对于设备底部的实际/名义高度。所有来源在任务说明记录，数字值不会由CLI认证。

`device_corner_radius_mm`、`device_lid_split_mm`（相对底部）、`device_bottom_mm`（场景Z）、`device_y_mm`、`clearance_mm`、`seam_gap_mm`和`opening_degrees`必须在当前构型检查。`rear_depth_scale`和`rear_transition_mm`只压艺术体后侧；`rear_relief_mm:[dimensions_xyz,location_xyz,corner_radius]`按实际源与铰链扫掠设置；LED当前固定为半径1.6mm贯穿观察孔，不支持伪造触控操作窗开关。未知具体版本不从默认值推断兼容。下方列配置字段的实现缺省，仅说明代码行为，任务仍要明确选择。

`lid_rear_clearance_mm` 缺省/null 时不增加上盖后口，明确设置时接受 `[dimensions_xyz,location_xyz,corner_radius]`：前两项为有限毫米三向数组，圆角为正有限数，三个尺寸均须大于两倍圆角以形成有效切体。该负空间只额外作用于上盖，不改变数字设备、下壳或原内腔；位置和大小必须根据实际干涉选择，不自动扩大所有外套的后口。原有 `rear_relief_mm` 仍只作用于下壳，两者独立。

`opening_degrees` 必须为 0–360 范围内的有限数，这只是旋转输入边界，不代表设备支持任意角度。建壳在原壳对壳姿态检查之外，增加闭合到该角度的 116 个等间距上壳—固定下设备交体检查；最大角度为 115° 时对应逐度姿态。新增检查失败会阻止有效 construction 交付，但不擅自改变旧几何或缩小用户要求的开盖角度。离散姿态不等于连续碰撞证明，完整动画及关键间隙仍要复核。

当前适配器采用单一圆角长方体名义设备、Y后侧铰链、底部插口、前侧LED、水平上下盖线及局部后窗。接口示例仍限定为：14×9×18mm外套底部通道、10×3.4×10mm数字设备插口、12×7×15mm插头外壳、8.2×2.3×6mm金属头，以及41×22×11mm后窗（后窗圆角2mm）。这些固定示例尺寸不是接口标准；其他插头、准确铰链/操作窗需在任务目录替换负空间参数并重新检查。源必须完全包含内腔以及1.5mm的预开孔壁厚包络，否则assert失败。自由造型可以重新拟合，但不能为使检查通过而悄悄缩小设备。其它铰链、非底部口、多装饰穿插、或准确OEM曲面需先单独构建并校验。

运行阶段：源归一化→`fit_vertices`拟合→明确启用时外形减薄→精密负空间/两壳→场景/动作→STL及fresh-import/开盖/插线/安装/图像依赖检查→实际媒体。`--stage geometry`只做源/几何及STL；`--skip-source-views`不渲源图；`--skip-stills --no-video`为显式局部重放选项。恢复媒体可用`render_video_chunks.py --case ./result/<key> --work ./media-work --blender /path/to/blender --spec "$SKILL_DIR/assets/render-spec.json"`，之后调用encode_review，读CLI帮助的实际位置参数。

生成按key分目录，包含parts/print、construction、model/exploded/motion/installation等GLB和native。动画中上盖跟随原设备只是目标运动，不证明外套固定成功。当前代码不生成DIY卡笼/柔性保持组件，需按diy-printing.md在任务工作目录设计实现；产品/BOM与网页不能称它们已存在。

## 实现中的可覆盖缺省值

这些是几何/显示起点，用户目标与实测优先；未列出的下标读取字段需要调用者提供。

| 字段 | 代码缺省表达式 |
|---|---|
| `clearance_mm` | `0.6` |
| `device_bottom_mm` | `3` |
| `device_corner_radius_mm` | `9` |
| `device_lid_split_mm` | `34.2` |
| `device_y_mm` | `0` |
| `opening_degrees` | `115` |
| `rear_relief_mm` | `None` |
| `lid_rear_clearance_mm` | `None`（关闭额外上盖切口） |
| `seam_gap_mm` | `0.6` |

## 可选外形减薄

只有用户明确要求减薄、当前任务已明确采用参数时才启用，先读[减薄说明](thin-wall.md)。配置 `thin_enabled` 缺省或 `false` 时完整保留原流程，即使存在两个数值也不暗中启用；flag 只接受 JSON 布尔值。为 `true` 时以下字段必须显式提供：

| 字段 | 含义与边界 |
|---|---|
| `thin_excess_fraction` | 厚大区的超额距离收缩比例，有限数且 `0 ≤ 值 < 0.6`；无缺省值。不是整壳厚度百分比，也不是总成比例。 |
| `thin_preserve_offset_mm` | 相对名义圆角内腔的受保护偏置，有限数且 `1.5 ≤ 值 ≤ 3` mm；无缺省值。不是成品全表面最小壁厚保证。 |
| `device_mm`, `clearance_mm`, `device_corner_radius_mm`, `device_y_mm`, `device_bottom_mm` | 与原结构相同的明确内腔字段。设备三维正值、圆角正值且不大于最小半边、间隙非负，全部有限。此阶段不替调用者填入名义设备参数。 |

`thin_source.contract_excess` 使用固定 0.6 mm 的 C1 起始过渡；其余区间按超额距离收缩，内腔近处受保护，仍须检查鳍根、孔口和轮廓。主入口把结果写入 `work-dir/thinned`，使用它继续现有建壳与校验；1.5 mm 预开孔包络检查不变。数值例如 `0.35` 和 `1.8` 仅是一组可选择的候选，不自动保存为通用默认，也不声称正好减轻 35%。

已有拟合源可直接调用此阶段，避免重跑 Hi3D 或源拟合：

```bash
python scripts/thin_source.py --source ./fitted --output ./thinned --config ./cover.json
python scripts/build_solids.py ./thinned ./result ./cover.json
```

输入 `source.npz` 与 `source.blend` 必须齐全。新 NPZ 保存实际变换顶点及原 faces/逐角 UV/material_index；复制的 blend 仍是原材质库，不是已减薄原生工程。`thinning-transform.json` 是未裁切源的顶点距离/包络摘要，不能替代最终 STL 的壁厚、内腔、干涉和体积检查。后续 `build_scene` 以同一 thinned 路径生成真正的成品工程和媒体。此可选阶段按[阶段计时](stage-timing.md)记录；直接调用 CLI 不自动替代执行者的完整业务计时。

## 写入前路径边界

`run.py` 在任何 mkdir 前调用 `config_runtime.resolve_file_request`：输入为 `--input` GLB 和 `--config` JSON，写入根为 `--output`/`--work-dir`，包根为本工作流目录。两份输入均受保护；配置必须在两个写入根之外，不能放在 result 或 scratch 中。路径判定和失败语义见 [本地路径契约](../../.dependency-run-tools/references/local-runtime.md#写入根与受保护输入)。

已有 output/work-dir 可重用且允许互相包含，同名派生产物会更新。路径、JSON、height_mm 和减薄参数预检先于 mkdir；后续拟合、建壳或检查失败仍可能留下局部输出。修正后从必要阶段续接，不能仅凭目录存在跳过验收。

独立拟合、减薄入口的源目录保护与输出文件限制见 [代码契约](code-contract.md#写入前路径边界)；主入口的配置预检不能冒充所有单阶段函数的自动保护。

## 视频默认与显式启用

`run.py` 默认执行几何、静态图片、GLB 动作与检查，不渲染视频。仅在用户明确请求视频后加 `--render-video`；`--no-video` 保留兼容并与 `--render-video` 互斥。已有场景追加视频优先使用随包分段渲染/编码入口，不为追加视频重建模型。直接使用 `build_scene.py` 也默认不渲连续帧，只有明确设置 `ASTRA_SKIP_VIDEO=0` 才启用；`studio_preview.animate_video` 的 `render_now` 默认 False。
