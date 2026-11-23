# Sapiens2 模板关键点映射

默认复用 [sapiens2_mapping.json](../assets/taro/sapiens2_mapping.json)：**36 个眼部点、32 个嘴唇点，68 个不同的头部顶点索引**。索引从 0 开始，绑定随包 Taro NPZ 的精确 SHA-256，以及 Sapiens2 308 点名称定义。只要模板文件和关键点定义不变，模板侧标注不用重做；换人只重新计算目标侧的 3D 点。

## 如何得到

用模板皮肤和原配静态眼球渲染正面彩图，保存相机矩阵；pose 检测得到原图像素坐标。将每点沿已知正交相机射线与头部外皮求交，再找最近的可见外皮顶点。眼唇孔口射线未命中或投影偏离时，仅允许在 6 像素内吸附可见外皮顶点；超限拒绝。不得用稀疏拟合 mask 代替完整外皮 mask，也不得取眼球、口腔内部或背面点。

首次空眼眶渲染使下睫毛线偏入眼眶，已改用同一 Taro DNA 的原配眼球并核对头部顶点一致。眼球仅用于校准图，不属于映射的顶点域，不执行绑定。随包保留 [校准图](../assets/taro/sapiens2_template_front.png)、[映射叠图](../assets/taro/sapiens2_mapping_overlay.png)、检测 NPZ、相机、眼球几何和关键点名称，可离线重算：

```bash
blender -b --python "$SKILL_DIR/scripts/calibrate_sapiens2_template.py" -- --output /work/recomputed.json
```

脚本不联网、不调用检测服务。重算输出是几何候选；正式映射还保存人工审核的使用策略。所有 84 个候选点投影距离最大约 2.7 像素，这只验证映射精度，不证明检测解剖语义的真值误差。

## 后续使用

1. 优先对目标高模的正面彩图运行 Sapiens2 pose，保留真实相机与原始分辨率。通过独立 mdf-call 调用，`task=pose, detect_persons=false, visualize=true, offload_cpu=true`；不需要每次重新检测模板。
2. 用目标相机将检测点反投影到该目标外皮，检查眼唇可见性和定位；射线失败或低分点剔除。原始照片没有已知相机时，先解相机，不能套用模板相机。Sapiens2 pointmap 也不是目标高模世界坐标。
3. `scripts/sapiens2_landmarks.py:build_landmarks(template, mapping, target_points, scores, names)` 接收按 308 点顺序排列的目标世界坐标，返回 fit 的 `landmarks` 列表。未命中点填 NaN；模板哈希和名称不匹配直接报错。目标标注仍须按 annotations 契约绑定新源哈希。
4. 默认只用眼唇。鼻梁、鼻尖及鼻翼外缘为可选低权重辅助，需看目标定位后才手动启用；鼻孔边缘和下巴仅作检查。308 点定义没有完整脸部轮廓线，不把耳部点当脸轮廓。轮廓继续通过高模表面与侧面视图约束。

原始 score 不是校准概率，可能略大于 1。模板侧一次校准不保证所有目标都准确，也不替代最终人工几何微调。

## 本次服务验证范围

2026-09-12，经 test 调用入口完成两次不同模板图的 pose 请求，均返回成功与有限 `[1,308,2]` 坐标、`[1,308]` 分数。首次往返约 14.5 秒、服务内约 6.35 秒。这里只验证 pose 和真实模板图往返，不声称 seg/normal/pointmap/matting 已逐项验收。网关 health 不暴露服务端环境，客户端 test 标签本身不会切换后端队列；运行审计保留实际 endpoint。

## 从检测到 brush 的直接交接

新增 `project_sapiens2_landmarks.py`，在 Blender 内读取高模、已检测 pose 和真实相机，一次输出 `settings.json`。配置字段：

```json
{
  "high_glb": "/work/high.glb",
  "image": "/work/front.png",
  "pose": "/work/pose.npz",
  "camera": "/work/front_camera.json",
  "target": "/work/target.npz",
  "settings": "/work/source_bound_masks.json",
  "output_settings": "/work/sapiens_settings.json"
}
```

`template` 可省略；自定义模板必须显式配套 `mapping` 和 `names`。`source_object` 仅多网格时填写真实皮肤对象名。camera 必须含 `projection="orthographic"`、`width=height`、`ortho_scale`、4×4 `camera_matrix_world`、源 GLB 的 `source_sha256` 与图片 `image_sha256`。坐标为 Blender 相机局部 +X 向右、+Y 向上、-Z 向前。相机元数据由真实渲染保存，不根据照片猜测。原始 pose 必须来自该图，执行者保存调用的输入/输出哈希；投影脚本不单靠 NPZ 验证检测来源。

```bash
blender -b --python-exit-code 1 --python "$SKILL_DIR/scripts/project_sapiens2_landmarks.py" -- /work/project.json
python "$SKILL_DIR/scripts/fit.py" /work/registration.json
```

registration 的 `settings` 指向新文件。脚本保留与当前 target 哈希匹配的外皮/耳颈 masks，将 landmarks 替换为新源眼唇点，默认按左眼/右眼/嘴唇分配相同总权重，再执行已有 refine → 几何检查 → 执行者局部微调 → bake。新高模必须重新建立 source mask，不得把旧 target 索引仅改哈希继续用。反投影后仍需看眼唇覆盖，几何交点不保证语义准确。

多视角法线可作为后续局部形状实验，但当前实现使用 3D 关键点、表面距离与法线相容性，**没有多视角法线图损失**；不要把已有 point-to-plane 项称作多视角法线拟合。若加入，须保留位置/轮廓约束并独立做前后对比。
