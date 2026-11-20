# 随包代码与调用契约

## 范围与依赖

脚本只实现已校准参数的球窝内核、局部装入、刚性变换、净空查询与背躺试片导出。人物语义切分、源面/角点 UV 回迁、壁厚、完整运动链、切片和真实试印由执行者按入口工作流处理；不能把试片 CLI 当作人物转换器。全部路径显式传入，不读取账户或调用服务。

Python 3.10+，安装本包 [requirements.txt](../requirements.txt)；Blender 由任务另行提供。版本范围以已使用 API 为基线，升级后跑随包行为测试；不用包管理安装代替几何验证。

```bash
python -m pip install -r /path/to/print-joints/requirements.txt
python /path/to/print-joints/scripts/coupon.py --spec /job/coupon-spec.json --out /job/coupon-attempt-1 --task-id figure-1
python -m unittest discover -s /path/to/print-joints/tests -v
```

`--out` 必须不存在；不会覆盖输入或既有产物。非法参数/无效几何抛异常，CLI 非零退出并保留失败产物和 timing.jsonl；重试用新目录。原子函数由任务脚本显式把当前 skill 的 scripts 路径加入模块搜索路径后 import，不依赖工作目录或相邻 skill。

## JSON 参数示例

以下是试片实例，不是固定人体比例或通用 FDM 设置。所有长度为毫米；gaps_mm 逐个替换 joint.gap_mm，其余参数保持一致。改变结构须重新校准打印与捕获性能。

```json
{
  "joint": {
    "radius_mm": 4.0,
    "gap_mm": 0.5,
    "wall_mm": 1.6,
    "stem_radius_mm": 2.0,
    "stem_length_mm": 12.0,
    "mouth_radius_mm": 3.35,
    "lip_margin_mm": 0.1,
    "rear_flat_mm": 2.4,
    "rear_port_radius_mm": 2.4,
    "segments": 96
  },
  "gaps_mm": [0.35, 0.5, 0.65],
  "support_gap_mm": 0.2,
  "support_radius_mm": 1.3
}
```

`BallSpec` 的七个基础长度必填且正数；rear_flat_mm / rear_port_radius_mm 同时省略表示不切背平面和清理口，试片 CLI 则要求两者存在。segments 为至少 32 的四倍数，默认 96 控制离散误差，仍需检查实际 gap。stem+gap < mouth < radius；lip 由 `sqrt((radius+gap)^2-mouth^2)+lip_margin` 求得，须小于 outer，stem_length 大于 outer；清理口须低于 lip 并留 lip_margin。外半径 outer=radius+gap+wall。

## 原子函数

| 文件 / 函数 | 输入、输出与失败边界 |
| --- | --- |
| [joints.py](../scripts/joints.py) / BallSpec.validate | 校验显式尺寸和捕获口关系，返回自身；非法/非有限长度拒绝，不自动修正。 |
| joint_frame | 中心、远端轴、后向候选 → 3×4 刚性矩阵；局部 +Z 远端、+Y 后向，平行轴候选拒绝。 |
| ball_tools | BallSpec → socket、ball_stem、parent_cutter、child_cutter 的独立 Manifold；无文件副作用。球杆无圆角，任务集成时补承力过渡。 |
| attach_ball_joint | 已分件近/远端实体、BallSpec、中心/轴/后向 → 新两实体；输入或输出不连通、无效或相交则拒绝。原分件未在局部退让区外互相接触是前提，仍需完整 gap/壁厚/外观验收。不直接处理 GLB/纹理。 |
| require_solid | 检查一个非空、有效、正体积连通实体；不证明自交缺陷全部消除、强度或可印性。 |
| pair_metrics | 两有效实体、search_mm → overlap_mm3、gap_mm、gap_is_lower_bound。命中搜索上限只说明距离至少为该值；体积为零不代表表面有净空。 |
| rotation_about | 中心、轴、度数 → 3×4 旋转矩阵；调用方把同矩阵施于该关节所有后代并更新子锚点/轴。 |
| [mesh_io.py](../scripts/mesh_io.py) / to_trimesh | Manifold → 不自动修复的 Trimesh，只导出位置和三角形，不含用户 UV。 |
| read_stl_solid | 实际 STL 路径 → 精确位置焊接后闭合、定向、无零面积、正体积且单连通 Manifold；非法文件拒绝。无自动修复或缩放。 |
| write_3mf | 新路径、名称到实体的映射、标题 → geometry-only 毫米 3MF；一个 mesh 保留全部实体的位置，拒绝覆盖。不设机器/支撑配置；调用方负责验证输入实体和实际 XML 回读。 |
| [coupon.py](../scripts/coupon.py) / coupon_geometry | BallSpec、支撑顶隙/半径 → 背躺 socket、ball、support 三独立实体；检查支撑可放入清理口、连通和零重叠。支撑不等于全模型免支撑。 |
| export_coupons | 解析后的配置与输出目录 → 3MF、逐实体 STL、coupon.json；实际回读每 STL，保留间隙→文件对应。候选沿 X 排列，同一候选不重排其捕获件。 |
| main | CLI 参数解析与调用编排，自动记录该调用起止 UTC/单调耗时和状态，失败保留记录。不会自动计量完整业务流程。 |

每一 gap 产生三实体；STL 保留共同位置，打印优先使用组合 3MF。coupon.json 包含名义参数、原位几何 gap、支撑顶隙实测、文件对应和未切片/未实测声明。支持柱仅覆盖球底平面，其他悬垂需切片检查。编号由文件名和报告对应，不在人物上自动添加文字。

## 可复用验证

[test_geometry.py](../tests/test_geometry.py) 以独立生成实体检查间隙变化、非零中心/A/T 轴向装入、连接失败、非法参数、运动干涉、支撑间距及真实 STL/3MF 往返；不依赖历史人物模型或用户资产。测试覆盖的是内核，不代表任意人物的解剖校准正确。完整业务按 [验收](validation.md) 做多视图、全模型运动和导出检查。
