---
name: flex-motion
description: 在 Blender 中为已绑定角色的柔性部位添加辅助骨，并把走动、转向和停止时的惯性随动烘焙成动作关键帧。识别头发末梢、衣摆、宽大袖口、披风、飘带、围巾和宽松裤脚等受气流与惯性拖曳的部位；保留网格、材质、身体骨架和已有身体动作。不是流体求解或逐三角形布料。
---

# 柔性部位惯性随动

在 Blender 里为已绑定角色的柔性部位添加辅助骨，并把走动、转向和停止时的滞后烘焙成动作关键帧。识别范围是全身会受气流和惯性拖曳的部位：头发末梢、衣摆、宽大袖口、披风下缘、飘带、围巾和宽松裤脚等。网格、材质、身体骨架和已有身体动作保留。

这是骨链弹簧的简化随动，不是流体求解，也不是逐三角形布料。真实布料缓存和披风 Surface Deform 仍由 hi3d-model-gpt-animation 维护，本流程不调用它。不生成角色，不默认减面、重拓扑或整身重绑，也不制作发片。

## 宿主执行模式

在 desktop 中先读 [Runtime 执行约定](../.dependency-run-tools/references/desktop-runtime.md)。本入口不提交 Hi3D，也不生成角色。

## 独立工作流

按 [打包约定](../.dependency-package-tools/references/usage.md) 和 [依赖清单](package.json) 提供本目录后，通过 `$flex-motion` 或显式读取本文件调用。Python 3.9+、NumPy；瞄准骨骼需要 Blender。运行目录在包外。阶段记录遵从 [run-tools](../.dependency-run-tools/references/stage-records.md)，由执行者记录真实起止、状态和耗时；本包脚本不自动采集计时。帧范围超过 600 时，用同一工具的 run_budgeted 包住这一次 Blender 进程，到点停止且不自动加时。

先读 [检查点](pcg/routes.yaml) 与 [阶段及产物](pcg/architecture.yaml)。弹簧与权重的纯函数在 [scripts/flex_motion.py](scripts/flex_motion.py)，骨方向写入在 [scripts/bake_flex.py](scripts/bake_flex.py)。

## 输入与缺项

必要输入是带骨架和蒙皮的 `.blend`，或含蒙皮与动作的 FBX/GLB，以及至少一个肢体角度真实变化的动作。转向和急停可以由同一动作的根旋转或路径驱动，不要求片段名字就叫转向。

没有有效身体骨架或没有包含肢体角度变化的动作时，交接 [rig-retarget](../rig-retarget/SKILL.md)，取回可走路的绑定工程后再从基线继续。已有合格绑定不重绑。

区域优先使用独立网格、语义顶点组、材质名或用户指出的部位。无法判断受影响区域时停止写权重，只问最关键的一项。

## 阶段

1. **基线。** 另存新的 BLEND，不覆盖用户原件。记录拓扑、身体骨名、休止姿态、材质和原始权重。关闭辅助骨后采样腿和手臂，确认动作里有角度变化。只有世界位移、没有肢体角度时，先回到绑定交接。
2. **柔性区域。** 按 [区域识别](references/regions.md) 标出每个自由端、锚骨和保护区。颜色、腰线高度或到腿骨的距离不能单独决定区域。
3. **辅助骨。** 按 [骨链](references/chains.md) 沿自由端加链。根挂在锚骨上，段数按轮廓决定。本流程创建的骨写入自定义属性 `flex_motion=1`。重复执行只复用这些骨，不删除同名前缀的用户骨骼。
4. **权重。** 锚点处保持身体权重，向自由端增加辅助骨影响。蒙版混合使用 `blend_auxiliary`。保护区域被误写入辅助权重、且该区域在已校准局部坐标里是轴向包围盒时，调用 [skin-weights](../.dependency-skin-weights/REFERENCE.md) 的 repair_regions 去掉指定骨骼影响。同拓扑基线则用 `restore_rows` 按索引恢复。减面或重拓扑之后禁止按索引回写。需要只读网格快照或按共享场景导入导出对象时，调用 [blender-tools](../.dependency-blender-tools/REFERENCE.md)。
5. **烘焙。** 按 [烘焙](references/bake.md) 逐帧读取身体姿态，用 `step_tip` 更新骨梢，再用 `aim_pose_bone` 只写辅助骨旋转。结果在 Blender 动作里。不另接运行时弹簧组件；导出的 FBX/GLB 只携带这些关键帧。
6. **验收。** 按 [验收](references/validation.md) 对比关闭和开启辅助骨关键帧。在锚骨局部空间里应看到加速滞后、转向偏移和停止后的衰减。世界坐标跟着根物体移动不算通过。

历史手部污染、空动作和坐标系错误的适用范围见 [案例边界](references/case-bounds.md)。那些毫米数不是新角色的默认容差。

## 参数起点

`SpringParams` 的时间常数对 24/30/60 fps 含义相同。下表只是起点，必须按当前角色的段长和动作重新看摆幅。

| 参数 | 起点 | 含义 |
| --- | --- | --- |
| `tau_return` | 0.28 秒 | 骨梢回到当帧目标方向的时间常数 |
| `tau_drag` | 0.05 秒 | 惯性速度的衰减时间常数 |
| `gravity` | `(0, 0, -9.81)` 米/秒² | 与骨梢同一坐标系，Blender 默认 Z 向上 |
| `gravity_scale` | 0.35 | 无量纲，避免按刚体自由落体 |
| `substep` | 1/120 秒 | 固定子步，不把每帧系数当成物理常数 |
| `dt_cap` | 0.05 秒 | 更大的时间间隔要重置状态，而不是一次积完 |

瞬移、切场景和读档时把骨梢与速度重置到当前目标。`dt == 0` 不推进。胶囊只推出骨梢一次，推出后再投影回休止段长，网格仍可能穿体。

## 产物

- 新的可编辑 BLEND：原身体骨架、`flex_motion=1` 骨链、区域权重和烘焙后的动作。
- 区域清单、骨链清单、权重审计和开关对照记录。
- 用户要求交换格式时，另存带关键帧的 FBX 或 GLB。只改参数时不导出无变化的模型。

## 本地检查

纯函数可在没有角色文件时运行。瞄准检查需要本机 Blender，并会新建一个空场景。

```bash
python3 -m unittest test_flex_motion.py -v
blender --background --factory-startup --python-exit-code 1 --python "$SKILL_DIR/scripts/test_bake_flex.py"
```

上述检查证明时间常数、段长、保护区权重和子骨瞄准。它不代替当前角色的动作对照。

<!-- managed-by: sparc3d-runtime -->
