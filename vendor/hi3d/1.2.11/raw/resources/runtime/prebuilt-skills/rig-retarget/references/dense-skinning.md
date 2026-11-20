# 高面数蒙皮与外部求解

## 何时使用

高面数原模需要参与动画、稀疏 LU 内存膨胀，或 Blender 内没有 ABI 匹配的 SciPy 时，使用外部 NPZ 求解流程。若用户允许动画代理，优先按其预算准备代理；不要自行把“500 万面原模”解释成“最终动画只需低模”。原始 GLB、导入后的有效三角面、工作网格、可见拆件和后补内衬分别计数。导入器丢弃退化面时记录差异，不修改原始文件凑数。

权重图覆盖同一连续蒙皮域。生成器把披风、尾巴、内背或裙片粘在一起，不代表它们应该共享扩散路径；先识别语义与独立域，再按域求解，域内先求权重后拆件。现有 build 脚本仍以一张准备好的统一表面为输入，不会自动切断这些语义连接。

## 两种求解路径

默认 `solver.method: "direct"` 保留稀疏 LU；`"cg"` 使用 Jacobi 预条件共轭梯度，逐骨求解以避免 LU 填充。两者都保持刚性锚点，检查非负和归一化。CG 记录每列迭代次数、退出码与相对残差，未收敛时拒绝导出可用权重。CG 仍需邻接图和全局权重表内存；先估计峰值，不把迭代法当作无限面数方案。

在 Blender 内运行时，`profile.solver` 可设置 `method`、`rtol`、`maxiter`。`radius`、`fidelity_length`、`edge_floor` 仍是身高 H 的比例，由 builder 转为模型单位。

无 Blender SciPy 时先导出校准输入，再用外部 NumPy/SciPy，最后回 Blender 构建：

```sh
"$BLENDER" --background --factory-startup --python-exit-code 1 \
  --python "$SKILL_DIR/scripts/run.py" -- build_character \
  --input "$RUN_DIR/prepared.blend" --profile "$RUN_DIR/profile.json" \
  --export-weight-input "$RUN_DIR/weight_input.npz"

# 三个长度变量必须等于 H × 对应 profile 比例；这里接收模型单位，不是比例。
"$PYTHON" "$SKILL_DIR/scripts/run.py" weight_graph \
  --input "$RUN_DIR/weight_input.npz" --output "$RUN_DIR/weights.npz" \
  --radius "$RADIUS_UNITS" --fidelity-length "$FIDELITY_UNITS" \
  --edge-floor "$EDGE_FLOOR_UNITS" --method cg

# 在 profile 加入 "weights_npz": "weights.npz"，路径相对 profile 目录。
"$BLENDER" --background --factory-startup --python-exit-code 1 \
  --python "$SKILL_DIR/scripts/run.py" -- build_character \
  --input "$RUN_DIR/prepared.blend" --profile "$RUN_DIR/profile.json" \
  --output "$RUN_DIR/weighted_candidate.blend"
```

外部流程不需要向 Blender 注入系统 Python 的二进制包。输入 NPZ 包含 `vertices/faces/initial/bone_names/mesh_sha256/calibration_sha256`；输出包含 `weights/fixed/bone_names/mesh_sha256/calibration_sha256`，并写 `.solver.json`。构建器验证静止坐标和三角索引、骨名顺序、骨点与区域校准摘要、锚点和权重合法性。改变坐标原点、拓扑、骨点、比例或初始权重区域后重新导出；改变求解参数后重新求解并更新缓存路径。`weights_npz` 存在时不会再运行 profile 内的 solver。

## 收敛后仍有拉伸

已绑定网格先用 [service_rig inspect / repair](service-rig.md#定位后修权重)定位错误归属；移除已确认的跨侧影响即可解决时无需图求解。共享点权重只在同一皮肤域保持一致，不扩大到独立衣物壳体。

残差小只证明线性系统求解成功。先看实际关节截面与种子：仅按高度覆盖 Head 会误把肩部披风分给头骨；给后补躯干内衬套用全身规则，会使内衬底环分别跟随左右腿。给内衬独立的骨盆/胸部过渡，不让辅助表面继承无关的四肢区域。

不均匀三角密度、很窄的自由带及刚性锚点边界可能使图解局部尖锐。检查沿真实弧长的权重剖面，再扩展有物理宽度的过渡区、校准种子；不要不停叠加 KNN/拉普拉斯平滑。必要时创作平滑的解剖坐标权重场，以受限图修正补局部细节，并重新做完整动作验收。某个模型的混合比例不是通用默认，脚本也不会自动选择此策略。

共享点使用同一份权重表，避免逐顶点 top-k 与低精度量化造成接缝。记录导出量化精度，做量化后的接缝检查。高面数检查按顶点的实际组成员遍历一次，避免“每根骨扫描整个模型”。数值初筛同时看倍率和绝对位移，见 [验收](validation.md)；不删皮肤面或细分面来规避阈值。
