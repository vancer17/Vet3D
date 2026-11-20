# 耳部多视角反投影

[project_ear_landmarks.py](../scripts/project_ear_landmarks.py) 在 Blender 中读取目标高模自己的正面与左右斜侧彩图、真实正交相机和对应 Sapiens2 pose。仅检测目标，模板使用 head-template 随包 `sapiens2_ear_mapping.json`；运行时不重新检测、重选或移动模板点。

```bash
"$BLENDER" -b --python-exit-code 1 --python "$SKILL_DIR/scripts/project_ear_landmarks.py" -- "$CONFIG" "$OUTPUT_JSON"
```

配置 JSON：`source`、可选 `source_object`、`template`、`mapping` 均为显式路径，`views` 是如下记录的列表。路径相对执行 cwd 解释，建议绝对路径；输出目录先由调用方创建。

```json
{"name":"left_oblique","image":"/run/left/color.png","camera":"/run/left/camera.json","pose":"/run/left/pose.npz","binding":"/run/left/binding.json"}
```

相机含 `projection: orthographic`、相等的 `width/height`、`ortho_scale`、刚性 `camera_matrix_world`、`source_sha256`、`image_sha256`；非正面视图必须含 `visible_ear: left|right`。只接受不偏移的方形正交相机，拒绝透视、缩放/反射矩阵。像素原点在左上，真实世界光线使用 `camera_ray.pixel_ray`，与眼唇投影共用同一计算。

`binding` 是检测调用时记录的 JSON，含输入渲染图的 `image_sha256` 和返回 pose 的 `pose_sha256`。调用方必须基于同一请求/结果建立绑定，不能给来源未知的旧 pose 事后补哈希冒充同源。pose 必须是单人 `keypoints: [1,308,2]`、`scores: [1,308]`。有旧的成功服务记录时核对实际输入图与返回文件哈希后可转为此本地绑定，无需再调用服务。仅凭检测文件存在不算绑定有效。

每视图只取光线第一个高模命中，分数低于 0.7、法线面向相机程度低于 0.08 或出界点被拒绝；斜视只收近侧耳，即使远侧检测分数高也不收。前视 `name` 固定为 `front`。相同 ID 的命中按朝向与侧视权重融合；三维分歧大于高模最大范围的 0.025 倍时不平均不相容表面，选可见性最好的观测并降至 0.2 权重；单观测权重 0.45，多视一致权重 1。融合后再贴回高模表面，输出 target、normal、权重、分歧和逐视图观测。

模板哈希、图/模型/pose 绑定不符、每侧少于四点时失败；不把检测遗漏自动补成模板点。产物包含 `source_sha256`、`mapping_sha256`、`records` 和 `rejected`，供拟合阶段二次验证。世界坐标追随源对象变换；目标采样也必须处于同一空间。

数组接口 [ear_projection.py](../scripts/ear_projection.py) 提供 `validate_mapping`、`orthographic_ray`、`fuse_observations`。它们可在普通 NumPy 环境中验证映射/相机/融合，不进行网格 IO 或服务请求。
