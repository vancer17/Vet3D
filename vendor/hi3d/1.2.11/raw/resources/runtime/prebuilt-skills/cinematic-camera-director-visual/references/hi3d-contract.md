# 统一镜头计划与轨迹契约

本文定义本 Skill 的本地数据结构，不冒充任一上游的原生协议。JSON 采用 UTF-8，数值必须有限。所有用户可见的新文件名以小写 `hi3d-` 开头。

## 坐标、尺度和时间

- `coordinate_system="blender_zup"`，世界右手 Z-up；相机局部 +X 右、+Y 上、-Z 前。
- `unit="meter"`；位置和 look-at 点均为绝对世界米制坐标，焦距单位毫米，角度字段以 `_deg` 明示度。
- `scale_m_per_blender_unit` 是实际 Blender 工程坐标到米的比例，不是任意目标尺寸。`scale_status` 只允许 `verified` 或 `unverified`；桥接器烘焙只接受已核实的比例。
- `fps` 为正数，可用 24 或 30 等实际需求；桥接器支持 1–240。逐帧轨迹从 `frame=1,t=0` 开始，连续至 `N`，`t=(frame-1)/fps`。最后样本时刻与视频编码帧数时长相差一帧，报告时不得混淆。
- 可选 `scene_frame_start` 指定相机样本首帧在原工程中的时间位置，默认 1；烘焙实际帧为 `scene_frame_start+frame-1`。动态场景应继承所需原始时间区间，不通过改动主体动画来配合镜头。
- 四元数格式 `[w,x,y,z]`，单位长度，表达 c2w 旋转；正负四元数等价，写入时保证相邻符号连续。

## 镜头计划 `hi3d-shot-plan.json`

以下只是合成坐标示例，不对应用户场景，也不证明轨迹无障碍。实际对象必须来自场景检查。

```json
{
  "schema_version": 1,
  "coordinate_system": "blender_zup",
  "unit": "meter",
  "scale_m_per_blender_unit": 1.0,
  "scale_status": "verified",
  "backend": "local_parametric",
  "camera_name": "Hi3D_Camera_Take01",
  "fps": 24,
  "resolution": [1280, 720],
  "sensor_width_mm": 36.0,
  "clip_start_m": 0.05,
  "clip_end_m": 1000.0,
  "initial": {
    "position_m": [0.0, -5.0, 1.5],
    "target_m": [0.0, 0.0, 1.5],
    "focal_mm": 35.0
  },
  "limits": {"max_speed_m_s": 2.0, "max_angular_speed_deg_s": 90.0},
  "segments": [
    {"id": "approach", "op": "dolly", "duration_s": 3.0, "target_m": [0.0, 0.0, 1.5], "end_ratio": 0.6},
    {"id": "reveal", "op": "orbit", "duration_s": 4.0, "center_m": [0.0, 0.0, 1.5], "angle_deg": 60.0},
    {"id": "finish", "op": "hold", "duration_s": 1.0}
  ]
}
```

### 本地编译器动作

所有动作继承前一段终点机位、旋转、焦距。所有段可提供正数 `end_focal_mm`。相机中心和主体相同、初始 look-at 不连续、非正持续时间和未知动作必须报错，不能猜测修复。

| op | 字段 | 语义 |
| --- | --- | --- |
| `move` | `end_position_m`；可选 `control1_m/control2_m`（必须成对）、`target_m`、`end_quaternion_wxyz` | 世界空间直线或三次 Bézier。无 target/末旋转则保持朝向；有 target 则全程注视同一点；target 与末旋转不能同时使用。 |
| `dolly` | `target_m`,`end_ratio>0` | 沿当前目标射线推拉；目标距离终值=初值×ratio，全程注视目标。适配 dolly zoom 时可同时指定匹配的终焦距。 |
| `orbit` | `center_m`,`angle_deg`；可选 `end_height_m` | 绕世界 Z 轴环绕，半径继承起点，正角度从顶视图看逆时针；高度字段相对 center。始终注视 center。 |
| `pan` | `angle_deg` | 固定位置，绕世界 +Z 旋转。左右语义由 Agent 根据初始视向映射，不靠上游标签猜角度符号。 |
| `tilt` | `angle_deg` | 固定位置，绕初始相机局部 +X 旋转。 |
| `roll` | `angle_deg` | 固定位置，绕初始相机局部 -Z 旋转；仅在导演意图允许倾斜时用。 |
| `zoom` | `end_focal_mm` | 位置与旋转不动，只变焦。 |
| `hold` | 无额外字段 | 保持位姿。默认焦距保持；若显式指定终焦距，效果相当于 hold 上叠加变焦，须在计划中说明。 |

本地编译器的 `u=6t^5-15t^4+10t^3` 用于段内进度，使每段端点速度、加速度归零。它不会自动寻路、调整节奏、跟随动态主体或保证不穿墙。

复杂连续通行、动态注视或外部轨迹可绕过 `compile`，直接生成以下标准采样格式；不能用未支持的动作名调用编译器。必须另记新轨迹的生成方式与实现，不能标成已调用 GenDoP。

## 统一轨迹 `hi3d-camera-trajectory.json`

保留计划中的坐标、单位、比例、相机名、fps、resolution、sensor-width、裁剪面、backend 与 limits。增加：

```json
{
  "schema_version": 1,
  "coordinate_system": "blender_zup",
  "unit": "meter",
  "scale_m_per_blender_unit": 1.0,
  "scale_status": "verified",
  "backend": "local_parametric",
  "camera_name": "Hi3D_Camera_Take01",
  "fps": 24,
  "resolution": [1280, 720],
  "sensor_width_mm": 36.0,
  "clip_start_m": 0.05,
  "clip_end_m": 1000.0,
  "limits": {"max_speed_m_s": 2.0, "max_angular_speed_deg_s": 90.0},
  "samples": [
    {"frame": 1, "t": 0.0, "position_m": [0.0, -5.0, 1.5], "quaternion_wxyz": [0.7071067812, 0.7071067812, 0.0, 0.0], "focal_mm": 35.0},
    {"frame": 2, "t": 0.0416666667, "position_m": [0.0, -4.99, 1.5], "quaternion_wxyz": [0.7071067812, 0.7071067812, 0.0, 0.0], "focal_mm": 35.0}
  ]
}
```

上面的两帧只演示格式，不是完整 8 秒轨迹。`samples` 至少两帧，不能伪造时间戳。多镜头分别生成，剪辑信息保存在镜头计划，不把不连续切镜塞进一条“连续”采样。

## 检查报告

`hi3d-camera-basic-checks.json` 是桥接脚本生成的基础报告；完整场景报告 `hi3d-camera-checks.json` 由执行者记录。每项应包含 `status`（`passed/failed/not_checked`）、方法、检查时刻/范围、阈值、实际值和失败样本。至少区分：

- 数值与时间契约；单位证据；速度/加速度与角速度/角加速度；焦距变化率。
- 几何碰撞与镜头体积间隙；相邻采样间扫掠；动态几何/实例覆盖。
- 遮挡、投影框、主体占比、近裁剪面、地平线；首中末与连接处真实预览。
- 原场景保留及交付副本重开；依赖资源完整性。

阈值是当前镜头的导演/安全约束，不是所有电影适用的固定标准。没有执行的项必须 `not_checked`。全局“通过”要求本次硬约束全部实际检查并通过，否则明确限制交付或停止。

## 视觉导演前置产物

`hi3d-scene-reading.json`、`hi3d-director-brief.md`、`hi3d-director-answers.json` 使用 [前置流程](hi3d-visual-brief.md) 的字段约定。它们是执行者维护的旁车文件，不直接传给 compile/bake。描述版本和确认来源必须相符，不能把偏好默认答案写成确认。

移动目标、主观视角交接和有界变化的环绕由执行者根据实际评估动画生成标准 samples；不能向本编译器添加未经实现的 op。切镜、镜头间衔接和分镜时长另存计划，不伪造连续轨迹。
