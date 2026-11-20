# 已有骨架与动画序列适配

先检查源角色、目标角色和动作来源，不从下载量、文件名或“已绑定”推断适配质量。复用目标已有蒙皮，操作另存候选；无绑定则先走 [新绑定](service-rig.md)。这里处理普通人形 FK 输出，不自动识别所有拓扑或替代脸部系统。

## 检查与骨轴校准

```bash
"$BLENDER" --background --factory-startup --python-exit-code 1 \
  --python "$SKILL_DIR/scripts/run.py" -- rig_adapter inspect \
  --input "$RUN_DIR/target.blend" --rig "$TARGET_RIG" --report "$RUN_DIR/rig.json"
```

报告包含骨名、父级索引、rest 矩阵、头尾、对象世界矩阵、动作与 NLA。用真实头点和父子链匹配肩肘腕、髋膝踝及手指；骨尾是导入器显示推导值时，不能用它计算腿长。骨尾只是显示异常而动作正常时无需改 rest。

只有需要修正骨轴时，建立与 `rig_sha256` 匹配的校准 JSON。`bones` 按实际骨名键控，每行给 `tail_at`（已确认的另一关节头）或显式 `tail`，以及与骨段不平行的 `roll_axis`；均为目标骨架静止空间。多分支的掌骨不能任取第一个子骨决定方向，末端骨尾需按手指/脚趾真实方向确定。

```json
{"calibrated":true,"rig_sha256":"来自本角色检查报告",
 "bones":{"upper_arm.L":{"tail_at":"forearm.L","roll_axis":[0,0,1]}}}
```

骨名/roll 示例不代表其他角色。`calibrated:true` 表示执行者已经完成几何核实，不是用户审批。

```bash
"$BLENDER" --background --factory-startup --python-exit-code 1 \
  --python "$SKILL_DIR/scripts/run.py" -- rig_adapter calibrate \
  --input "$RUN_DIR/target.blend" --rig "$TARGET_RIG" --spec "$RUN_DIR/axes.json" \
  --output "$RUN_DIR/calibrated.blend" --report "$RUN_DIR/calibration.json"
```

保持全部关节头、网格和权重。目标有动画时默认拒绝；本次确实要替换目标动作才传 `--replace-animation`，在候选中清除该 rig 的旧动画引用后重烘。未选对象的 Action 不动，旧数据块不主动删除。复杂约束/驱动、父对象、特殊继承或非刚体对象变换需要专门适配，命令拒绝直接处理，不能去掉约束绕过后声称行为保留。

## 将源动作求值成缓存

BVH 可用 [BVH 缓存](motion-and-hands.md)服务于原比例骨架 builder。对已有服务骨架推荐通用 `rig_adapter cache`：在独立 Blender 源工程中导入动作并确认它确实运动，记录来源/许可。

VMD 是动作数据而非可独立播放的完整目标 rig。需要匹配的 MMD 参考骨架及其控制骨/IK/上半身变体，先由当前可信导入器正确加载并求值；不能把脚 IK 通道直接复制给目标 FK 腿，也不能捏造缺失骨骼、表情或数据。MMD 工具只需在源导入/求值阶段可用，最终输出为本地 Action。FBX/GLB 的动作同样先在源工程检查坐标与时间。

```bash
"$BLENDER" --background --factory-startup --python-exit-code 1 \
  --python "$SKILL_DIR/scripts/run.py" -- rig_adapter cache \
  --input "$RUN_DIR/source-motion.blend" --rig "$SOURCE_RIG" \
  --start "$SOURCE_START" --end "$SOURCE_END" --fps "$OUTPUT_FPS" \
  --output "$RUN_DIR/motion.npz" --report "$RUN_DIR/cache.json"
```

读取场景 fps/fps_base，按目标 fps 取实际子帧；`--source-fps` 只在明确需要纠正源时间解释时使用。帧范围包含可达末帧，非整采样末端不额外拼入一帧。缓存包含 names/parents/rest/poses/fps/sample_frames、源文件和骨架身份、首采样世界矩阵。poses 在固定的首帧源骨架空间，包括源 NLA、约束/IK及对象运动，不能用基础 pose 属性代替求值。

## 建立本角色映射并烘焙

JSON 必须绑定目标当前 rest 的 `rig_sha256` 和真实缓存 `cache_sha256`。`source_to_target` 为把源坐标转到目标静止坐标的刚体 4×4；单位比例由 root 的对应关节链计算，不能在此同时缩放。默认矩阵为单位阵，仅用于执行者已核实坐标相同的情况。帧与源路径属于任务，不写进 skill。

```json
{
  "calibrated":true,
  "rig_sha256":"来自校准后目标",
  "cache_sha256":"来自缓存报告",
  "mapping":{
    "pelvis":{"source":"Hips"},
    "upper_arm.L":{"source":"LeftArm","target_end":"forearm.L","source_end":"LeftForeArm"},
    "index.1.L":{"source":"LeftIndex1","mode":"local","alignment_wxyz":[1,0,0,0]}
  },
  "root":{"target":"pelvis","source":"Hips",
          "source_chain":["LeftUpLeg","LeftLeg","LeftFoot"],
          "target_chain":["thigh.L","shin.L","foot.L"],
          "offset":[0,0,0],"in_place":false}
}
```

这是字段示例，实际 mapping 必须覆盖本次需要的身体、双侧手脚和手指。未映射骨随父骨保持 rest；不能把缺项当作成功跟踪。多个目标段对应同一源骨时明确如何分摊或跟随，不能沿手指链重复施加同一源关节转动。

- `global`（默认）：`Q_desired = Q_source_pose × inverse(Q_source_rest) × A × Q_target_rest`。A 由明确的 source_end/target_end 头点方向求得，或 `alignment_wxyz` 显式覆盖。方向对齐只确定摆向，roll/扭转仍需校准。T/A 差异大时不要假设 A=单位旋转。
- `local`：提取源父子关节相对 rest 的增量，换到目标骨局部轴后叠加在目标父骨姿态上，适合保留目标手指自然张开同时移入屈指。A 的语义同上，不是帧帧附加的任意修正角；数学契约见 [接口](retarget-api.md)。
- root 必须是真正无父骨的目标根。平移由源根相对 rest 的位移、对应链长度比例及显式 offset 构成；不自动用首动作帧重新归零。目标有控制根/骨盆双层结构时明确选根和映射，不能把父级世界位移算两次。in_place 清除目标空间 XY 位移，Z 保留。

root 的 offset 与 in_place 会同步作用于全部 IK 目标。IK 改变父骨后，未映射子骨继续保持中性局部姿态，local 映射保留本关节增量；global 映射继续保持所请求的绝对朝向。

可选 `limbs` 每项包含三关节 `target_chain`/`source_chain` 及目标空间的 fallback `pole`，用于固定长度的双骨 IK 后烘焙 FK；链必须直接相连。求源屈曲平面退化时才使用 pole，不复制固定膝盖方向到所有角色。鞋底补偿可增加 `sole_points`（实际鞋底在目标 rig rest 空间的点集）、`floor_z`、`preserve_flight`；没有鞋点就不推断鞋底。返回 `max_limb_reach_error`，不可达时按实际模型校准骨盆或步幅；clamp 并不等于脚部接触通过。

```bash
"$BLENDER" --background --factory-startup --python-exit-code 1 \
  --python "$SKILL_DIR/scripts/run.py" -- rig_adapter retarget \
  --input "$RUN_DIR/calibrated.blend" --rig "$TARGET_RIG" \
  --cache "$RUN_DIR/motion.npz" --spec "$RUN_DIR/mapping.json" \
  --action "$ACTION_NAME" --frame-start "$OUTPUT_START" \
  --output "$RUN_DIR/animated.blend" --report "$RUN_DIR/retarget.json"
```

输出每骨 quaternion 与根 location 的原生 layered Action，scale=1、相邻四元数符号连续、线性关键帧。时长 N/F 与首末采样差 (N−1)/F 分开。原始 rest 保留，不添加检查段、音乐、相机或渲染。已存在动作的替换仍需显式 `--replace-animation`；输出动作名必须新建。脚本不自动做音乐同步、循环闭合、cloth/hair simulation 或游戏状态机。

## 按动作反馈修绑定

在完整目标帧范围定位异常面→静止位置→权重及骨段。先排除 rest/T-A 对齐、父子空间和膝反折，再删已确认错误骨影响；最后才做局部连续性平滑。手指细小权重不能按全身强度平滑，裙片/长发不能仅按空间高度分给身体骨。

用同阈值与帧范围比较候选，保留较好版本。修权重需要 `service_rig inspect/repair` 的网格/骨架指纹和实际区域，与动画 mapping 的指纹是不同用途。按 [全段验收](validation.md)重开检查；报告残留而非把原型泛化为所有角色的全自动保证。
