# 布料交付与接触命令

## 适用边界

`embed_cloth.py` 和 `contact_check.py` 在 Blender 中运行，只需要其自带 NumPy。它们处理已创建的模拟/网格，不自动拆件、设计披风或修复碰撞。输入保留不改，输出使用新路径；这些脚本的行为已用 Blender 5.1.2 合成场景验证，其他版本先跑文末测试。

## 将已烘焙披风内嵌

先在原生工程完成 Cloth bake 并保存，再从这个文件捕获低模代理。保持原文件名与缓存路径有效，不要先另存到新名字再期待旧点缓存生效。`is_baked` 状态不是缓存视觉正确性的证明，应先抽查形状及动作。

```sh
"$BLENDER" --background --factory-startup --python-exit-code 1 \
  --python "$SKILL_DIR/scripts/run.py" -- --rig-skill "$RIG_SKILL_DIR" embed_cloth capture \
  --input "$RUN_DIR/native_baked.blend" --proxy CapeProxy \
  --start "$START_FRAME" --end "$END_FRAME" --output "$RUN_DIR/cape_capture.npz"

"$BLENDER" --background --factory-startup --python-exit-code 1 \
  --python "$SKILL_DIR/scripts/run.py" -- --rig-skill "$RIG_SKILL_DIR" embed_cloth embed \
  --input "$RUN_DIR/native_baked.blend" --cache "$RUN_DIR/cape_capture.npz" \
  --output "$RUN_DIR/portable_candidate.blend" --set-range
```

捕获连续整数帧的**求值后局部坐标**、世界矩阵、fps、源文件哈希与静止网格指纹。代理必须为非空三角网格、固定顶点和三角索引，至少两帧且在已烘焙范围内。只面向低模代理：每帧一个 shape key 的体积随帧数和顶点数增长，不对几百万面直接生成逐帧 keys。

embed 要求与捕获完全相同的源文件、fps、代理指纹和单用户 mesh。它保留代理对象身份及现有 Surface Deform 目标引用，移除播放代理已有的修改器和 shape keys（它们已包含在求值坐标里），写入局部坐标 shape keys、线性曲线和 NLA。对象父级/变换动画保留，避免 Armature 或世界变换应用两次。隐藏的原生备份保留配置以便重新烘焙；这不是可移植物理缓存。

输出打包图片、重开文件，逐整数帧比较代理坐标与世界矩阵，并检查已绑定 follower 引用仍在。`.cloth.json` 记录误差与哈希，失败非零退出。`--tolerance` 是场景坐标/矩阵分量误差阈值，默认 `1e-5`，按尺度确认。工具核验 follower 引用，不自动证明高模跟随质量；高模仍需单独检查。

`--set-range` 把时间轴设为捕获范围；省略时保留原时间轴，只在报告范围内承诺捕获对应关系。半帧线性插值不等于原生物理半帧解，需对内嵌后的最终高模重新做半帧穿模检查。改变动作后需重新模拟/捕获；不是把物理规则永久变成可适配任意动作的动画。

## 世界坐标接触检查

创建任务级 JSON（对象名按实际工程填写）：

```json
{
  "pairs": [
    {"a": "Cape", "b": "Tail"},
    {"a": "Cape", "b": "Body"},
    {"a": "Tail", "b": "Skirt"}
  ]
}
```

```sh
"$BLENDER" --background --factory-startup --python-exit-code 1 \
  --python "$SKILL_DIR/scripts/run.py" -- --rig-skill "$RIG_SKILL_DIR" contact_check \
  --input "$RUN_DIR/portable_candidate.blend" --spec "$RUN_DIR/contact_pairs.json" \
  --frames "$START_FRAME:$END_FRAME:0.5" --report "$RUN_DIR/contacts.json" --collect-faces
```

范围包含可达的末帧，可用逗号组合单帧或范围。每个网格必须预先三角化且求值拓扑不变；工具不会静默三角化后继续使用旧面号。坐标按各自求值后的 `matrix_world` 变换，再构建 BVH；不能直接把两个不同对象的 `BVHTree.FromObject` 当作同一坐标空间。

先运行无排除检查，读取报告 `objects.<name>.rest_mesh_sha256`，检查接触面心与图像后，仅对明确的固定连接区域设置 pair 内 `exclude`：

```json
{
  "object": "Cape",
  "reason": "经检查，此小片为肩部固定连接区",
  "mesh_sha256": "替换为当前 Cape 的静止网格摘要",
  "face_ids": [12, 13]
}
```

也可用模型**局部静止坐标** `rest_bounds: [[xmin,ymin,zmin],[xmax,ymax,zmax]]` 代替 `face_ids`，仅排除三个顶点都在框内的面。每条规则需理由、匹配的指纹和属于该 pair 的对象；不允许规则或组合规则覆盖整张网格。某角色的领口高度/尾根框不能照搬到其他角色。

报告分别给出原始、排除和剩余接触数，并输出少量接触面号与静止/世界面心。`--collect-faces` 收集每对对象在请求帧内的剩余接触面并集，只用于定位或设计有依据的开口，**不自动删面**。有剩余接触则保存报告并非零退出。

通过只代表已请求帧、已声明网格对、排除固定连接后的三角表面相交未检出。它不证明完全包裹穿入、自相交、连续时间无碰撞或艺术质量；采样步长也不能成为无条件保证。代理通过不代表高模通过，必须用最终可见对象另查。

## 离线回归

```sh
"$PYTHON" "$RIG_SKILL_DIR/scripts/run.py" test_weight_graph -v
"$BLENDER" --background --factory-startup --python-exit-code 1 \
  --python "$SKILL_DIR/scripts/run.py" -- --rig-skill "$RIG_SKILL_DIR" test_cloth_contacts --work-dir "$NEW_EMPTY_TEST_DIR"
```

数值测试核对 direct/CG 一致、锚点保持、无效输入、未收敛拒绝及 NPZ 指纹。Blender 测试包含不同父级/缩放、仅半帧碰撞、排除规则/拓扑变化拒绝、带上游变形的真实 Cloth bake、保留 Surface Deform 跟随和重开误差比较；最后移走原生缓存目录，确认内嵌动画仍可播放。只用合成小网格，不使用用户图像、密钥或收费生成。
