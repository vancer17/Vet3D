# 动作与掌腕

## 来源与时间

核对动作来源、许可及文件实际内容，不把名称当品质保证。BVH 来源可查 CMU 等明确的数据提供方，保留作者、转换来源、许可及源文件身份；历史动捕不能作为近期流行程度证据。身体动捕与执行者另写的掌腕短句分开署名，动作二进制不捆绑到 skill。

检查源 fps、单位、朝向、roll。`cache_bvh.py` 通过 Blender 求值缓存 names/rest/poses/fps，同一 armature 空间。缓存 0 下标通常对应导入第 1 帧，不能把原始 120 fps 帧号当 30 fps 索引。

profile 中的动作示例，cache 路径相对于 profile，samples 为零基且右端不包含：

```json
{"fps":30,"inspection_frame":140,"animations":[
 {"name":"Run_Cycle","cache":"mocap/run.npz","samples":[1,23],"loop":true,"repeat":6,"timeline_start":1,"hand_style":"run","in_place":true,"ground":"source_flight"},
 {"name":"Street_Dance","cache":"mocap/dance.npz","samples":[45,405],"loop":false,"timeline_start":181,"hand_style":"dance","ground":true}
]}
```

采样范围仅适用于所述示例缓存，其他资源先查帧数。`[45,405)` 为 360 样本，在场景中是包含两端的 181–540；裁剪后可成为 0–359。N 个样本按 fps F 播放时长为 N/F，首末采样时刻差为 (N−1)/F。已有工程的裁剪、灯效压缩与帧重排见独立 hi3d-model-gpt-animation 的 stage_ops（按需另行提供该 skill），不要只修改场景起止值而留下旧 NLA。22 个跑步采样加闭合键为 23 键，NLA 重复 6 次为 1–133。ground=true 按实际最低顶点落地，会消除腾空；ground="source_flight" 在落地修正上保留源双脚最低点相对基线的腾空高度，循环动作默认使用它。ground=false 关闭自动高度修正。仍需检查足底滑动，必要时补足部接触约束或 IK，不能把高度修正称为完整足部锁定。

落地检测集合由 `profile.parts_collection` 指定，默认 `CharacterParts`；多人场景逐角色指定各自集合，允许集合内有骨架/Empty，但只对 Mesh 求值。`motion.ground_height` 将对象局部顶点变换到 rig 空间，再测量 rig 的 Z=0 平面；它不自动寻找世界舞台表面。倾斜 rig、独立地面高度或非均匀缩放须另行统一坐标。

## 重定向

源/目标坐标对齐后，常见旋转起点为 `Q_target_pose = Q_source_pose × inverse(Q_source_rest) × Q_target_rest`，再经父骨目标姿态转为局部 basis。仍需验证各 rig 的骨向；不能直接复制 Euler 或跳过 rest 修正。根位移按对应腿链长度缩放。

骨段维持单位 scale，校准 roll 和弯曲平面，不靠伸长骨头追源动作。刚性躯干可整体倾斜旋转，不能为迁就源脊柱改坏认可的蒙皮。

先在空 NLA 下烘焙全部 Action，再创建 strips，避免旧动作混入新烘焙。Blender 5.x 常用 `action.layers → strips → channelbags → fcurves`；不要假设 action.fcurves 总存在。相邻 quaternion 保持符号连续并归一化，循环同时检查姿态和接点速度。

## 掌腕直角问题

服务返回的骨名不一定具有左右/手指语义，先依据骨头位置与父子链映射。导入器合成骨尾不一定指向真实子关节；确认轴向后再编排屈腕和逐指弯曲。姿态正确但有尖刺时，按 [局部权重修复](service-rig.md#定位后修权重)检查跨侧影响，不用改骨轴掩盖错权重。

CMU 某些 Hand 是零长度点，BVH 导入器给它合成竖直尾点。目标掌骨实际沿指尖方向，直接复制会使掌腕持续约 90°。这是骨向问题，不应重新计算全身蒙皮。

以小臂作为目标掌骨中性方向：`Q_hand_pose = Q_forearm_pose × Q_wrist_offset`，再转回局部旋转。不同 roll 的 rig 不能套同一个局部四元数。跑步采用近中立、小幅随动，幅度与循环按当前角色校准；舞蹈应有停顿后释放、左右延迟及短句变化，不是持续同步正弦摆动。

编排可参考 [Darryl Tracy 的手部表达建议](https://thedancecurrent.com/article/handy-tips/)中的前臂旋转与掌腕表达，以及 [El Tiro 的 Arm Wave 教学](https://www.brambilabong.com/blogs/popping/how-to-dance-arm-wave)的关节依次传递，创作重音/回松和交替波浪。motion.hand_offset 是原创整掌短句种子，不包含独立分指，不声称音乐同步。无音轨时对齐身体运动变化，不虚构歌曲 BPM。

翻掌主要来自前臂长轴旋转，不把大幅旋前/旋后塞到腕部。改前臂时检查肘腕位置未变、原屈肘保留；只修手腕时不动前臂曲线。检查每个 Action，避免舞蹈修好但跑步遗漏。

局部修订从最新认可文件备份出候选，按 Action 与具体骨骼 data_path 修改。保存前后比对网格/UV/权重、其余曲线、肘腕位置、循环与拉伸；不要重跑整个 build 覆盖满意的结果。
