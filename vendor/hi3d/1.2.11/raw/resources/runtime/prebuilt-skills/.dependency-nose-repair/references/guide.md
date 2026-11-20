# 鼻部修复操作契约

直接调用 nose-repair，提供已有高模和同源 donor；不要求重跑图像生成或建模。

## 输入

- 原 highmesh GLB：单 geometry、Y-up、+Z 正面，先渲染确认。多 geometry 需明确目标和回装映射，不丢弃其他部件。
- 同源注册 donor：registered_glb_coordinates.npz，包含 vertices[24049,3]、Taro 同序 quads 和原 GLB 的 source_sha256。
- 只有 GLB 时，先读 [人像视觉分析](../../.dependency-portrait-analysis/REFERENCE.md)，按 [注册步骤](../../.dependency-face-fit/references/guide.md#注册步骤) 完成渲染、Sapiens2 分割/眼唇关键点、3D 投射、fit 与 donor 导出。带纹理模型使用带纹理渲染检测；不要硬用灰模上错误或低置信关键点。
- Python、NumPy、SciPy、trimesh、triangle 和 Blender 依赖见本 skill 的 requirements.txt。已有 donor 直接继续，脚本不隐式联网。

## 准备与运行

config JSON 含三个绝对路径字段：source、donor、全新 output。可选 landmark_settings 指向同源 face-fit 的 fit/observed_face_settings.json；prepare 按真实投射唇点自动约束下界，最多在原中心至鼻尖/鼻底中间的范围内检查 9 个中心候选，并按鼻翼跨度适当扩宽（不超过原水平半径的 1.5 倍），验证鼻尖、鼻翼、鼻小柱仍位于保留核心。lip_margin_fraction 默认鼻高的 0.04，不是物理毫米；坐标或来源不符、保护嘴唇与保留鼻部冲突时停止。未提供时保留原有启发式。

```bash
"$PYTHON" "$SKILL_DIR/scripts/nose_repair.py" prepare "$RUN_DIR/nose-config.json"
```

检查 output/profile.json 与原模、donor 鼻部。自动 ROI 是启发式，执行者需确认：

- 原鼻必须切除，保留 donor 的鼻翼、鼻小柱和鼻孔内部；仅平滑/投影原鼻不是移植。
- 默认椭圆可能碰上唇。优先提供 landmark_settings 自动保护；未提供时用当前 Sapiens2 投射唇点核对下界；GLB Y 对应 Blender Z，即 settings.landmarks[*].target[2]，不混用坐标系或其他人的点。
- 调整 nose.center、nose.radii、nose.min_z、nose.band_min_z 后同步 heightfield x/y 与 transition_spacing。网格可从中心 ±1.5 倍半径、间距最小半径/90 起调，不是所有案例的固定参数。
- 接缝通常延伸至椭圆约 1.13 倍半径；下界保护嘴唇，侧面应把鼻翼核心留在过渡带内。宽鼻翼可扩大水平范围后复查；不要裁平环带底边。
- 保留 source/donor 哈希绑定，改 profile 后重算 heightfield。

```bash
"$PYTHON" "$SKILL_DIR/scripts/nose_repair.py" run "$RUN_DIR/nose" \
  --blender "$BLENDER" --correct-small-contacts
"$PYTHON" "$SKILL_DIR/scripts/nose_repair.py" verify "$RUN_DIR/nose"
```

run 执行高度场、局部精确位置 UV 拆点焊接、切面/实体 donor 移植、Poisson 过渡、局部检查和来源核验。圆周边界保持拓扑顺序并限制角度跨度，不全局角度排序重连。

可省略 --correct-small-contacts。启用时仅处理 1–4 对局部相交，最多 1000 次尝试，位移预算为受检局部包围尺度的 1e-4；降至零才应用，保留原版本并重新审计。超出范围或失败需检查 ROI/注册，不扩大预算硬修。

## 输出与验收

- repaired.glb：真实移植后的灰色几何，拓扑变化，旧 UV 不迁移；纹理后续单独处理。
- repair_report.json、repair_provenance.npz、local_uv_weld.npz：面数与源顶点对应。
- geometry_validation.json、transplant-proof.json：当前哈希、局部检查、实际 donor 核心复制数量、区域外位置误差。
- workflow-timings.jsonl：总任务及子阶段、task/attempt/parent 标识、状态、带时区起止和单调时钟秒数；失败与跳过保留。总任务包含子阶段，不重复求和。算子自身 timings.jsonl 是嵌套明细，未启动阶段不虚构耗时，token 不可得时不估算。

每次尝试使用新目录，已有 repaired.glb 时拒绝覆盖。失败产物不作成功交付。重试关联原业务任务，保留旧记录和参数。

passed_local_checks 仅表示配置鼻部的有限坐标、退化、绕序、开放边、非流形、自交和来源检查通过，不认证整个 donor、人头、相切/共面接触或打印性。全 donor 有缺陷时须定位到局部依赖之外，不能以全脸平均误差宣称鼻部合格。

执行者仍需检查正面、斜侧面、鼻底及原/修复同步对比，确认辨识度、鼻孔、鼻翼和接缝。常规 ROI 的口唇保护和几何检查由代码执行；agent 仅检查输入方向、最终视觉和失败例外，不宣称任意 GLB 无人值守修复。

## 代码契约

nose_repair.run 编排现有算子；check_result 验证当前输出/来源并写证据；apply_contact 仅应用同一输出哈希的 delta。nose_contact.propose 在 Blender 提出有界修正，失败不改 GLB。算法唯一保留在 transplant_nose.py，上游注册与下游去噪由完整人头 workflow 编排。

## 底层算子与兼容入口

`prepare_nose.py config.json` 的配置为 `source`、`donor`、新 `output`。donor 必须满足上述注册导出契约，包含 source_sha256 与 Taro 同序 quads。适配器用已注册的鼻根/鼻尖/鼻底/鼻翼索引推导椭圆 ROI，保存 profile.json；这是待查看的启发式，不是新的检测模型。可在运算前调整 profile 的鼻部中心、半径和深度阈值，但必须保持源/先验绑定。

```bash
"$BLENDER" --background --factory-startup --python-exit-code 1 \
  --python "$SKILL_DIR/scripts/nose_heightfield.py" -- "$RUN_DIR/nose"
"$PYTHON" "$SKILL_DIR/scripts/transplant_nose.py" "$RUN_DIR/nose"
"$BLENDER" --background --factory-startup --python-exit-code 1 \
  --python "$SKILL_DIR/scripts/audit_nose.py" -- "$RUN_DIR/nose"
```

`nose_heightfield.run(root)` 读取源/先验实际深度，写局部 source/template 网格。`transplant_nose.main(root)` 验证源/donor 哈希，删除鼻部三角面，提取连续 donor 鼻部，通过保边界约束三角化连接；`nose_operators.poisson_reference` **原位修改**指定顶点高度，解混合参考梯度与固定 Dirichlet 边界；`regularize_band_xy` **原位修改**过渡带 XY。源/先验其余部分不作全局重建。失败保留中间文件，成功写新 repaired.glb 与原顶点到新顶点的 provenance。

`audit_nose.run(root)` 比较原/修复鼻部自交、绕序、退化、真实开放边及非流形边；开放边计数纳入区域顶点的全部邻面，避免把 ROI 裁面边缘算作洞，保存受检面索引。CLI 对修复区域失败非零退出。检查不包含相切/共面接触，也不构成打印认证。当前单 mesh 适配器会输出灰色几何，最终颜色来自后续 texture 阶段，不复用失效旧 UV。


模板来自 Epic MetaHuman DNA Calibration 的 Taro；见 [来源清单](../assets/taro/manifest.json) 和 [随包许可](../assets/taro/UPSTREAM_LICENSE.txt)，不重新许可为无限制开源素材。算子提取自既有局部鼻部修复实现，保留三维 donor 核心，仅过渡带采用单值高度场。
