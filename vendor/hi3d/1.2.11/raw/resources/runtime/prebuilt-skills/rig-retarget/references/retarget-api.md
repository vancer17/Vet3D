# 既有骨架适配接口

[rig_adapter.py](../scripts/rigging/rig_adapter.py) 是 Blender/文件适配器，[retarget_math.py](../scripts/rigging/retarget_math.py) 是仅依赖 NumPy/mathutils 的计算函数，导入后不改变场景；[run.py](../scripts/run.py) 仅分派命令、打印结果并按可选参数记录阶段。参数示例见 [适配流程](existing-rig.md)。

| 原子函数 | 输入 → 输出、影响与失败边界 |
| --- | --- |
| `selected_rig(name)` | 明确对象名 → 当前 Armature；缺失/非骨架拒绝，不猜首个对象 |
| `skeleton(rig)` / `skeleton_digest(data)` | 当前骨架 → 有序名字、父索引、rest/头尾数组；有序 names/parents/rest → JSON SHA-256；只读 |
| `protected_assets()` | 当前场景 → 所有非空 Mesh 的保护摘要及图片内容 SHA-256；复用 service_rig，不扫描凭据 |
| `require_preserved(before,frame)` | 在同一场景时间比较保护摘要，再恢复预览帧；骨骼挂接的道具保留局部变换/父级关系，允许随新动作移动 |
| `validate_target(rig, replace_animation)` | 目标 → 检查普通 FK、单用户数据、刚体世界矩阵及替换条件；父对象/约束/驱动/特殊继承不支持 |
| `calibrate_axes(rig, spec, replace_animation=False)` | 当前骨架、匹配指纹的 tail/roll 配置 → 新旧 rest 摘要与修改骨名单；编辑骨尾/roll，保留头；明确替换时移除该 rig 旧动画引用 |
| `cache_rig(rig, frames)` | 可见源骨架与有限帧列表 → 全骨 rest/pose/父级/源时间数据；求值 IK、NLA 和对象运动到首采样骨架空间；恢复原帧，拒绝 scale/shear/reflection |
| `bake_action(rig, names, quaternions, locations, root, frame_start, name)` | 校验后的单位 quaternion 数组及根位移 → 新 Action；替换所选 rig 的动画引用，设置 FK 旋转/scale=1，以 bulk F-curves 写入 Blender 5.x slots；不生成 NLA |
| `new_path(value, forbidden=())` | 路径 → 不存在的新路径；检查与输入/报告碰撞并创建父目录 |
| `execute(args)` | 已解析的 inspect/cache/calibrate/retarget 参数 → 报告；检查输入/缓存身份，另存打包候选并重开、核对保护项；失败不覆盖原件，保存失败产物不称通过 |
| `main(argv=None)` | CLI 参数 → 报告/输出位置摘要与退出码；完整数据写 JSON，不在控制台重复百万顶点信息 |

新缓存 schema 为 `rig-retarget-cache-v1`：`names (B,)` 字符串、`parents (B,)` 父前子后且根=-1、`rest (B,4,4)`、`poses (F,B,4,4)`、`fps`、`sample_frames (F,)`、`source_fps`、`source_world_at_first_sample (4,4)`、输入/骨架哈希。NPZ 禁止 pickle。旧 cache_bvh 的 names/rest/poses/fps 契约仍供原 builder 使用，不能不补父级/空间就冒充新 schema。

| 计算函数 | 契约 |
| --- | --- |
| `rigid_matrices(values,label)` | 有限仿射矩阵数组 → float64 视图；只接受正交、det=1、末行 [0,0,0,1]，拒绝尺度/剪切/反射 |
| `hierarchy(names,parents)` | 唯一骨名与匹配父索引 → 校验；父级须先于子级 |
| `unit_quaternion(value)` | 非零有限 wxyz → 单位 Quaternion；不改输入 |
| `chain_scale(source_rest,target_rest,source_chain,target_chain)` | 对应头点链 → 目标/源长度比例；拒绝退化链 |
| `two_bone_ik(hip,goal,length_a,length_b,pole)` | 同空间点、正链长、弯曲方向 → 膝、限制到可达范围的踝与误差；不伸缩；零目标方向或平行 pole 拒绝 |
| `forward_heads(names,parents,rest,desired,root,root_position)` | 目标 rest、绝对期望旋转与根位置 → FK 头点字典；无场景副作用 |
| `retarget_samples(source,target,spec)` | 身份由适配器检查的缓存/目标数组与已校准映射 → F×B×4 局部 quaternion、F×3 根位移、比例/帧数/最大腿部目标误差；不改输入或 Blender |

local 模式：源父子 rest 为 Ls，源父子 pose 为 Ps，局部增量 D=Ls⁻¹Ps。轴转换 C=Rt⁻¹A⁻¹Rs（Rs、Rt 为已统一空间的源/目标该骨 rest 旋转，A 把目标中性方向对齐源中性方向）。目标 local basis 增量为 CDC⁻¹，再按目标父骨姿态组合。global 模式则使用源全局相对 rest 的旋转；两者不能混用而重复继承父骨转动。

输出腿脚 IK 是几何重定向，不含接触状态估计、脚锁或碰撞。批量蒙皮/完整动作 QA 仍使用 service_rig/validate_blend。适配器 `pose_qa_pending:true` 明示保存之后还需要全段数值和视口验收。

IK 要求源与目标都是直接三关节链，root offset/in_place 同步移动关节目标。求解后重新继承未映射或 local 子骨的局部旋转，global 映射保持绝对旋转。回归同时核对平移不改变无地面约束时的相对姿态、local 子骨不反向补偿父骨，以及不连续源链被拒绝。

[record_stage](../scripts/rigging/timing.py) 记录命令/编排区间，契约见 [计时](timing.md)。[test_retarget.py](../scripts/rigging/test_retarget.py) 在小型合成源/目标骨架上验证 T/A 对齐、独立手指、源 IK/对象运动求值、链长、根比例、权重顺序、已有动画保护、保存重开及阶段失败记录；不调用服务或渲染。
