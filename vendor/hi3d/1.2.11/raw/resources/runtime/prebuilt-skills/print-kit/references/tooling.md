# 可选本地工具

这些工具是轻量参照实现，可改用 CadQuery、FreeCAD、OpenSCAD 或 Blender 等建模工具；只需达到 skill 的实体、接口和装配验收目标。没有外部服务依赖。

## 环境

Python 3.11+，用当前可用解释器安装 `scripts/requirements.txt`。依赖范围由该文件声明。渲染另需 Blender，几何与验证不需要它。

```bash
python3 -m pip install -r /path/to/print-kit/scripts/requirements.txt
python3 /path/to/print-kit/scripts/verify_kit.py /path/to/kit/kit.json
python3 /path/to/print-kit/scripts/fit_coupon.py --out /path/to/coupons
python3 /path/to/print-kit/scripts/crop_coupon.py /path/to/kit/kit.json --instance part-id --bounds 0 0 0 20 20 12 --out /path/to/coupons/local.stl
python3 /path/to/print-kit/scripts/test_core.py -v
blender --background --factory-startup --python /path/to/print-kit/scripts/render_kit.py -- /path/to/kit/kit.json --render
```

`kitlib.py` 提供闭合实体原语、真正布尔并集、右手 Z-up 毫米坐标变换和 `Kit`。模型可在装配坐标建立，`add(..., print_rotation=...)` 会变换到贴床姿态并记录反变换。`instances` 为相同源件的多个装配变换；重复件只导出一份 STL。

`Kit(..., bed=(宽,深,高), profile={...})` 必须显式提供毫米打印空间；profile 来自当前任务，没有隐含材料、喷嘴或切片配置。未提供 profile 时保持空对象，由执行者补全或声明未知。`bed_margin=5` 与 `spacing=6` 是可调整的几何排版余量，需按裙边、支撑、逐件打印安全距离重新确定。`add()` 默认支撑状态为 `not_assessed`，不会默认为免支撑。

```python
from kitlib import Kit, box, translation
# 示例尺寸和工艺仅用于演示；业务任务传入自己的配置。
k = Kit('example', '两块试装片', {'gap_mm': 0.3}, bed=(120,120,120),
        profile={'material': 'PLA', 'nozzle_mm': 0.4, 'layer_mm': 0.2})
k.add('a', box((30,30,3)))
k.add('b', box((30,30,3),(0,0,3.3)), explode=(0,0,15))
k.path(['b'], [0,0,1], 40)
k.data['notes'] = ['演示坐标与检查器；不具备固定连接。']
k.export('/path/to/output')
```

此示例只演示 API，不能作为完整产品设计模板。真实任务应加入定位、保持、接口测量与操作顺序。

`crop_coupon.py` 从实际生产 STL 的装配坐标裁出指定盒形 ROI，保留原打印轴向并重贴床。公母件分别选择含完整接口和足够支承的连通区域。裁切改变热历史、支撑和底面，因此它证明局部几何配合，不代表最长滑轨、整圈翘曲或原始首层一定一致。

## 清单与检查器

`kit.json` 含 `parts`（独立文件与数量）、`instances`（4×4 变换）、`plates`（打印副本）、`joints`（接口与保持方式）、`features`（最终网格射线实测）、`disassembly`（逆向装配次序）、`motions`（运行行程）、参数/硬件/说明。矩阵为行数组保存，运算用列向量。

`features` 在指定中心沿轴线测邻近两壁的距离；适合孔宽、槽宽、销径与板厚。需选不会穿过旁边肋或边界的截面，并以明确部位定位；它不是全局壁厚证明。

`disassembly` 逐步把指定实例沿单位方向移出，步长由 `max_step_mm` 控制，剩余最多一个固定基件。多实例可以作为子装配一同移动，但**不得通过把全部件列成一个组绕开内部装配证明**；多件组本身应已有可执行的装配方式或由独立子装配检查覆盖。检查器不自动证明这一设计判断。

检查器重新加载 STL 并核对 SHA、几何、打印尺寸与数量、摆盘、刚体终态交叠、接口射线、分步移出和运行采样。体积阈值 0.01 mm³ 是数值容差，非真实打印配合公差。旋转通过角度采样验证；细小阻挡可能在采样间漏检，需减小步长、连续扫掠或局部补查。它不执行切片、不计算应力，不验证实物配合。

`export` 会立即复读 STL 拦截降为 float32 后出现的退化面/裂口。若失败，优先检查精确相切的布尔切口或仅共面的连接，改为跨越表面或有真实体积重叠；不要放宽水密判据。`retention` 是设计记录，非保持力证明；涉及五金时另保留安装/工具通路检查与实体固定测试状态。

各件的 `support` 与 `print_notes` 为设计声明；验证报告中的下向面面积只提醒后续切片检查。报告发现错误以非零退出码结束，不应改阈值掩盖实体相交。

## 独立使用与移交

完成两版最终零件后，按 [两版交付](delivery.md) 分别调用 `package_delivery.py`，每版输出装配 GLB、分件 STL ZIP 和含两个下载入口的展示页。工具只处理打印零件；外购件参考节点、特殊连接验证和两版制造完整性按该文补齐，不把同一套文件重命名充作两版。

将建模源码与输出一起交付，重建时仅通过 skill 的 `scripts` 导入工具，不依赖作者机器上的案例目录。输出包含 `assembly.glb`（米）与 `assembly-view-only.stl`（mm、多体，仅检查装配）；打印时使用 `parts/*.stl`。

相对路径方便把 skill 和案例一起移交。参考图片只作为用户本地验证输入保存，未经授权不要连同模型公开发布。

独立验证时按入口打包约定在仓库外物化完整分发目录，运行 `test_core.py` 和至少一个实际产品建模入口；脚本只在临时目录写测试产物。该检查覆盖实体导出、单位、公母间隙变化、干涉与路径失败、ROI 裁切和计时恢复，不等于目标 AI 的自动发现、切片或实体打印。宿主发现能力须在其技能目录中另行验证；显式文件路径调用与自动发现分别报告。

## 原子函数与副作用契约

以下几何计算均用毫米，除说明外不读写文件；无效参数、空实体或依赖库不支持的几何不能当作成功结果。CLI 只组合对应函数，生成失败可能留下部分文件，应修正后在新的任务输出目录重新导出。不要把输出目录设为 skill 包本身。

| 模块/入口 | 输入、输出与失败边界 |
|---|---|
| `kitlib.box/cyl/polygon` | 正尺寸/半径/高度或有效二维闭合轮廓 → Manifold 实体；`at` 是位置，`cyl` 的默认 96 段是曲面离散精度。非法几何由实体库返回错误/空体，导出阶段拒绝。 |
| `rounded_box/tray` | 宽深高、圆角、托盘壁厚 → 圆角块/开口托盘；执行者保证 `2r≤min(w,d)`、壁厚小于半宽深且底厚小于高度，数值为可调几何参数。 |
| `union` | 实体 iterable → 真正布尔并集；空输入返回空体，不能导出为零件。 |
| `translation/rotation` | 三维向量，或 x/y/z 轴、角度和 pivot → 4×4 右手矩阵；角度单位度，错误轴抛 ValueError。 |
| `transform/mesh/solid` | 实体+矩阵、实体、Trimesh → 变换实体或相互转换；`solid` 使用 float32，需重新验证细小/远离原点几何。`transform` 允许工程建模的镜像等仿射操作，打印/装配记录必须刚体。 |
| `is_rigid/valid_mesh` | 矩阵/Trimesh → 刚体布尔判据/单连通水密正向无退化判据；纯计算，不代表强度或打印成功。 |
| `export_solid` | 实体、已存在父目录中的 STL 路径 → 写入并复读的 Trimesh；非单实体或 float32 导出失效抛 ValueError，诊断文件可能保留。 |
| `assembly_geometry/pack_plates` | plan 和已复读的零件网格字典 → 米制预览 Scene+毫米装配网格/摆盘列表；纯计算，摆盘是无旋转的矩形货架算法，不做嵌套优化，超床抛 ValueError。 |
| `sha/write_json` | 路径 → 文件 SHA256；路径+JSON 数据 → UTF-8 JSON 覆写；只在这类明确 IO 适配函数中访问文件，IO 异常向上传播。 |
| `Kit.add/joint/path/probe` | 实体和实例、接口、逆装配路径、尺寸测量定义 → 更新内存中的 plan；add 返回零件 ID，重复 ID 或非刚体实例报错。方法不写文件。 |
| `Kit.export` | 输出目录 → `kit.json` 路径；编排 STL 复读、装配导出、摆盘和 JSON 写入，覆写同名输出。返回只表示导出完成，必须另跑验证和设计审查。 |
| `verify_kit.load_inputs` | plan 路径 → plan、网格和摘要字典；读取 JSON/STL，无文件写入。 |
| `check_parts/assemble/check_intersections/check_plates` | plan 与已加载几何 → 实测记录/装配实体/错误列表；依次检查零件、变换及数量、全部实体对、摆盘，每项可单独调用。`overlap` 先用 AABB 排除再算真实体积交集，包含关系也会被检测。 |
| `measure_features/check_paths/check_motions` | plan、装配实体 → 对应测量或采样记录+错误列表；无文件 IO，参数无效抛异常，不跳过为通过。路径终点须脱离剩余装配 AABB，是保守规则。 |
| `validate_plan/verify` | 内存 plan+网格+摘要 / plan 路径 → 验证报告；前者纯组合，后者为只读入口并将常见坏输入转换成 `status=fail`。CLI 写 validation.json，业务失败退出 1。 |
| `fit_coupon.gauge_shapes/build` | 单边 gap 0–1 mm 与 1–6 个标识点 → 四种量规实体；`build(out)` 导出六档参考试片及空白实体记录。档位是校准阶梯，不是机器的成功公差。复用 `export_solid` 的导出后检查。 |
| `crop_coupon.crop_solid/crop` | 打印网格+刚体装配矩阵+六个 ROI 边界 → 保持轴向并重贴床的实体；空/断开的 ROI 拒绝。`crop` 读取 plan/STL，写局部 STL 与来源记录，未知实例/IO 失败向上传播。 |
| `render_kit.author` | plan 路径、render 布尔 → 写 scene.blend 及可选 PNG/manifest；依次组合配置、STL 导入、实例姿态、相机、布景和渲染函数。必须在独立 Blender 进程运行，会清空当前场景。依赖 `bpy.ops.wm.stl_import`、AgX 和 Cycles。 |
| `render_kit.matrix_mm/camera` | mm 变换 → m 变换；网格包围盒、姿态、观察方向与画幅 → 正交相机及最低 Z；camera 创建 Blender 对象。 |
| `configure_scene/load_geometry/instance_poses/add_cameras/add_studio/render_views` | 显式 plan、目录、Scene 或网格姿态 → 对应 Blender 状态；每项只处理本名义阶段。前三帧是装配、爆炸、摆盘；可选第四帧只展示首个运动声明的端点，不是完整运动验证或装配视频。 |
| `timing` | `timestamp` 读时钟，`append_record/stage/skipped` 追加任务日志，`summarize` 纯计算摘要；完整计时契约见 [阶段耗时](timing.md)。 |
| `test_core.fixture` | gap → 内存肩销试装件，用于正常/失效的可复用回归测试；不依赖业务案例。所有测试文件由临时目录管理。 |

## 手工扩展 plan 时的字段

`schema_version=1`；`parts` 包含 id、相对 file、qty、color、print_notes、support，导出后补 sha256/size_mm/volume_mm3；`instances` 为 id、part、matrix、explode。`plates` 每个实例一条，含 instance、从 1 起的 plate 和 mm 变换。不同表中的实例 ID 必须对应。几何摆盘未计入切片器的支撑/裙边，切片后复核。

- `joints`：id/a/b/kind/clearance_per_side_mm/retention，可加 engagement_mm 等设计字段。保持说明非空只证明清单完整，抗拔、工具入口和五金通路需执行者另验。
- `features`：id/instance/center/axis/expected_mm/span_mm/tolerance_mm；center、axis 在装配坐标，axis 非零。span 为从中心向两侧的射线长度；从两侧各取最近交点，相距应在 expected ± tolerance。该截面必须适合目标特征。
- `disassembly`：instances/direction/distance_mm/max_step_mm，非空实例组、非零方向和正距离/步长；按顺序移除，剩余至多一个固定基件。多件组仍需单独证明内部装配。
- `motions`：id/type/instances/samples；至少两次含端点采样。translation 加 direction/distance_mm，rotation 加 axis（x/y/z）、pivot、start_deg/end_deg。多个运动逐个相对初始装配检查，不能声称组合动作已验证。
- `hardware/notes/assembly_steps/parameters/profile` 保存真实设计说明与任务条件；`evidence` 标明外部切片与实物状态。检查器本身总是将 physical_test 记为 not_run，外部反馈另存，不将几何结果升级为实物成功。

试片公共实现见 [fit-coupon 契约](../../.dependency-fit-coupon/references/contract.md)，通过 package.json 物化。既有报告字段保留；新增配对记录中的 physical_test=not_run 仅表示尚无实际反馈。

页面资产与模板公共实现见 [asset-page 契约](../../.dependency-asset-page/references/contract.md)，按 package.json 物化。离线查看器、装配/拆解/摆盘与制造打包保持本工作流实现；生成网页后仍需实际打开并检查下载。
