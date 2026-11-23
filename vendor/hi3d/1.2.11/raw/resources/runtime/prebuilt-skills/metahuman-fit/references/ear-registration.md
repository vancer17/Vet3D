# 耳部多视角注册子流程

用于已完成整头注册但耳朵大小、外展或位置不匹配的情况。保留原 Hi3D quality 高模；复用已存在的图像、检测、采样和注册结果。使用固定模板耳点，不在每个人头运行时标模板；计算阶段无需 agent 逐点介入，最终耳形仍需要同相机视觉验收。

## 输入准备

1. 源高模采用 X 水平、Y 深度、Z 向上，正面相机朝向与既有正面注册一致。复用高模正面彩图及其真实相机；不能使用最初照片的二维坐标。
2. 必要时补左右斜侧彩图，运行下面的 Blender 入口。它只渲染同一份带纹理高模，记录两个真实 1536 方形正交相机，不改原始文件。左右标签按模板坐标约定，先核对朝向；不适用的朝向必须先显式统一变换。

```bash
"$BLENDER" -b --python-exit-code 1 --python "$SKILL_DIR/scripts/render_ear_views.py" -- "$SOURCE_GLB" "$VIEWS_DIR"
```

3. 对每张彩图按 [Sapiens2 调用契约](sapiens2-landmarks.md) 使用独立 mdf-call 的已配置入口检测目标。复用成功记录，pending 按原记录恢复；模板不提交检测。保存实际输入图和返回 pose 的绑定，再按 [多视角反投影契约](../../.dependency-landmark-project/references/ear-projection.md) 给 `views` 列表。已有同源融合点可直接提供 `landmarks`，不重复渲染或检测。

## 本地 CLI 与配置

```bash
python3 "$SKILL_DIR/scripts/ear_run.py" "$CONFIG"
```

`CONFIG` 为 JSON，必填：

- `registered`：原整头注册 NPZ，含 `vertices/rest/quads/quad_uvs/linear/offset`；顶点顺序、四边形与 UV 对应模板。
- `source`：同一份 Hi3D 高模文件；可选 `source_object` 选择其中唯一头部。
- `surface`：同源世界坐标采样 NPZ，含 `vertices/normals/source_sha256`。
- `settings`：来源绑定的整头配置，含 `template_sha256`、`provenance.source_sha256` 与原眼唇 `landmarks[].vertex_index`。这些点是硬保护项，不用耳部损失重新拉动。
- `views`：前述图/相机/pose/绑定列表，或者 `landmarks`：已融合的 JSON，二选一。
- `blender`：实际 Blender 可执行路径；`output`：包外空目录或本子流程已拥有的恢复目录。

可选 `face_fit` 是局部面部优化后的 NPZ，读取 `vertices`；必须保留原眼唇点。省略则使用 registered 顶点。可选 `template/regions/mapping` 默认随包 Taro；自定义模板必须提供匹配资源，不能静默沿用 Taro 索引。所有路径从调用 cwd 解析，配置建议写绝对路径。

模板资源包含 49 个固定 Sapiens2 耳点，使用 triangle/barycentric 做亚顶点约束，vertex_index 供索引核对。映射与模板哈希绑定。模板改版或重排后必须离线重新校准并版本化，不能由运行脚本自动生成。

`ear_run.py` 复用 [landmark-project](../../.dependency-landmark-project/REFERENCE.md) 完成可选反投影；复用 [surface-fit](../../.dependency-surface-fit/references/ear-fitting.md) 的鲁棒仿射初始化、耳根过渡和共享体积变形；最后执行有界几何检查。拟合两侧使用相同固定参数，不按人物名选择超参。主要损失是法线相容双向表面距离和固定模板对应点误差，不是多视角法线图损失。

## 现有主流程接入

在 `scripts/run.py` 的配置中增加 `ear_registration` 对象，给出上述 source、surface、views 或 landmarks 及自定义 mapping/regions（如需要）。主流程在 refine 之后、最终 geometry/bake 之前调用子流程，自动传入本次 brush_fit、fitted、settings、template、blender 和输出子目录。未配置时保留原刚性耳恢复行为。最终 geometry 以只检查/导出模式保留耳部保护约束，纹理和展示使用耳部检查后的顶点，不能再从旧 fitted.npz 烘焙。

本地单独调用不自动运行图生图、Hi3D、Sapiens2、烘焙、DNA 或绑定。缺少已绑定的检测输入会明确失败，不自动更换服务地址、重提任务或索要新密钥。

## 输出、缓存与验收

输出 `initial.npz`、`candidate.npz`、`fit_report.json`；验收通过才写 `checked.npz`、`MetaHuman_Ears.obj`、`geometry.json`。checked 的 native 坐标按原注册逆变换重算，拓扑和 UV 保持一致。候选并不等于已接受结果。

每次执行在 output 下记录 `ear_config.json`、`workflow.json`、`timings.jsonl` 和阶段日志。Journal 自动记录 projection、fit、geometry 的任务/尝试、状态与单调耗时；缓存命中写 skipped。输入哈希、固定映射、实际参与的共享源码均纳入阶段指纹，恢复还核对输出内容。改耳部求解源码会重跑 fit/geometry，未变化的多视角反投影可复用。原先在上游完成的服务耗时不重复计入；不宣称本地耗时是模型推理耗时。

`ear_geometry_passed` 仅表示耳区通过当前离散穿越/退化与保护项检查。`whole_geometry_passed` 单独报告模板之外的整头穿越；旧眼唇问题不能因耳部通过就隐去。剩余失败项按 [几何检查契约](geometry-comparison.md) 处理，不能交付为整头验收通过。再看同相机正面、左右耳近景和侧面：耳轮厚度、上耳轮形态、耳垂和耳甲腔不能仅靠距离下降验收。归档与 OBJ 保留检查结果，GLB 与纹理沿用主流程已验证的后续交付入口。

恢复失败时旧 checked 文件可能仍在目录中；必须以对应阶段的成功状态、输入指纹和输出哈希判断其有效性，不能只按文件存在消费旧结果。
