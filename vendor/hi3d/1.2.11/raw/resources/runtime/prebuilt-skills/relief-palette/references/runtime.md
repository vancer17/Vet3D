# 配置与运行

## 入口

在命令中把 `SKILL_ROOT`、`BLENDER_BIN`、`TASK_ROOT` 替换为当前环境已确认的路径。所有任务目录在包及仓库之外。示例演示三格和一支双头涂抹器，数值只是合成测试参数，不是品牌或生产默认值。

```sh
python3 "$SKILL_ROOT/scripts/run.py" --describe
python3 "$SKILL_ROOT/tests/make_fixture.py" --output "$TASK_ROOT/fixture"
python3 "$SKILL_ROOT/scripts/run.py" check --config "$TASK_ROOT/fixture/job.json"
"$BLENDER_BIN" --background --factory-startup --python-exit-code 1 \
  --python "$SKILL_ROOT/scripts/run.py" -- build \
  --config "$TASK_ROOT/fixture/job.json" --output "$TASK_ROOT/attempt-01"
"$BLENDER_BIN" --background "$TASK_ROOT/attempt-01/palette.blend" --python-exit-code 1 \
  --python "$SKILL_ROOT/scripts/run.py" -- validate --report "$TASK_ROOT/reopened-check.json"
```

`--factory-startup` 只适合启动独立测试/生成进程；不要在用户现有交互场景中清空工程。`check` 校验 JSON、输入路径和 builder 语法，不执行 builder、不解码图片、不导入 STL，不能代替 Blender 检查。`build` 拒绝已存在的输出目录；失败后保留记录，下一次使用新目录，可传 `--previous-attempt-id` 关联之前 `timing_summary.json` 的尝试。`validate` 检查当前载入场景的持久化角色清单，报告路径必须不存在。

## JSON 契约（schema_version = 1）

生成的 `job.json` 是完整可运行样例。以下字段均必填，除非标为可选。

| 字段 | 类型与语义 |
| --- | --- |
| `task_id`, `builder` | 非空字符串；builder 是经审阅、提供 `build(ctx)` 的 `.py` 文件 |
| `pans` | 非空对象数组，长度就是粉盘数量，不固定为四格 |
| `pans[].id`, `variant_id` | 各自在整盘内唯一的非空标识 |
| `pans[].color` | 可带 `#` 的六位 sRGB 十六进制，不允许颜色重复；不代表真实销量或色差验证 |
| `pans[].image`, `relief` | 图像 `.png/.jpg/.jpeg/.webp` 与原始 `.stl` 文件；必须存在且非空 |
| `pans[].center_mm` | `[x,y,z]` 粉饼几何中心，Z 朝上，单位毫米 |
| `pans[].size_mm` | `[宽,深,厚]` 正数，本地 runner 生成圆角矩形粉饼 |
| `pans[].corner_mm` | 正圆角半径，小于最短水平边一半 |
| `pans[].margin_mm` | 浮雕相对粉饼矩形边界的正边距，小于半边长；圆角处仍需查看轮廓是否越界 |
| `pans[].relief_height_mm` | 原始浮雕完整 Z 范围映射到的正高度，非可见凸起高度 |
| `pans[].embed_mm` | 基线埋入粉饼顶面的正深度，小于粉饼厚度及浮雕高度 |
| `pans[].axes`, `depth_sign` | 三个源坐标索引组成的排列，例如 `[0,2,1]` 表示源 X/Z 为正面宽高、Y 为深度；深度方向为整数 `1` 或 `-1` |
| `hinge.pivot_mm`, `axis`, `sign` | 世界轴心三坐标、`X/Y/Z` 轴、开合旋转符号 `1/-1`；轴在闭合姿态定义 |
| `hinge.max_angle` | 最大开角，`0 < 角度 <= 180` |
| `keyframes` | 有序不同正整数帧号与角度对，如 `[[1,0],[24,105],[48,0]]`；首尾闭合并达到最大开角 |
| `check_frames` | 动画范围内显式非空整数帧数组；脚本额外纳入全部关键帧 |
| `resolution`, `samples`, `exposure` | 正整数宽高、Cycles 正采样数、有限曝光值；与微小产品尺度一起调灯，不沿用大场景灯光功率 |
| `shots` | builder 镜头键的唯一字符串列表；`[]` 可只导出模型与检查 |
| `powder_finish`（可选） | 对象：`grain_mm > 0`、`bump_mm >= 0`、`metallic/roughness` 各在 `[0,1]`；缺省使用原子函数的起始材质值，视觉上仍需调整 |

相对文件路径以 JSON 所在目录解析，与调用工作目录无关。位置尺寸必须有限；浮雕 XY 保持比例，Z 独立归一化。空或平面 STL 在真实导入时失败，不以方块替代。非圆角矩形、倾斜粉盘或自由曲面浮雕需扩展 task builder/适配器，不能宣称本 runner 已覆盖。

## builder 契约

从 [示例模型](../assets/example/model.py) 复制到任务目录，依据本次参考重写几何与灯光。`build(ctx)` 接收 `scene`、`collection`、已解析 `config` 和 `geometry` 原子函数模块。仅向给定 collection 添加本次对象，不删除其他场景，不从环境寻找输入。返回：

- `stationary`：底壳、固定件、在槽内附件的实际几何列表。
- `moving`：闭合状态的盖壳、镜面、活动轴节等实际几何；由控制器整体保持世界姿态绑定。不得另外设置会改变它们运动的动画/约束。
- `contents`：stationary 子集，用于闭合镜面间隙；粉饼和浮雕由 runner 自动加入。
- `studio`：不参加装配碰撞的地面/展台等实际几何；不能将产品碰撞物塞到此列表。
- `shots`：字典，每个值为 `{camera: Blender对象, frame: 整数, objects: 构图对象列表, margin: 可选且>=1}`。相机需正交类型，属于任务场景；按姿态使用投影包围盒取景。只包括镜头中应完整出现的对象。
- `mirror`（可选）：moving 中的实际镜面；省略时不会自动推断镜面或报告间隙。
- `contacts`（可选）：`[{objects: [moving对象, stationary对象], reason: 具体配合原因}]`；只排除这对表面碰撞，并原样列入报告，不能泛排整个铰链。

stationary/moving/studio 不重叠；每个 MESH/CURVE/FONT 必须登记，临时切割体使用后清理。灯、相机和空对象无需列为碰撞几何。模型保持静止形状；validator 缓存静态网格，只检测其矩阵变化，不支持被动画变形的 stationary。默认控制器扁平绑定 moving 列表，复杂层级/独立活动附件需另建控制逻辑与专门验证。

## 输出

`palette.blend`、按 shots 顺序的 `01_render.png` 等、`resolved_config.json`、`report.json`、`timings.jsonl`、`timing_summary.json`。保存采用独立 scene 及其依赖，恢复调用者当前场景，不把其他场景写进新文件。外部 builder 必须遵守此边界；输出目录也不得放仓库内，脚本仅自动阻止写入自身包内。

`report.json` 分开记录执行完成与 `checks.passed`。检查不通过仍保存候选文件供修正，并返回非零退出码；不是已验收交付。源图像不自动打包为纹理，也不随原始 STL 拷入输出，执行者交付时另保留输入目录和 builder。新开 `.blend` 后重跑验证并实际看图。
