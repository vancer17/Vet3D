# 输入与配置

## 运行环境

- Blender 5.x，使用内置 `bpy`、`bmesh`、`mathutils` 和 NumPy。脚本调用带 `--python-exit-code 1`，异常返回失败。
- Instant Meshes 原生 CLI，支持 `-d -r 4 -p 4 -f N -S 2 -o output.obj input.obj`；显式配置可执行文件。
- Python 3.9+、NumPy 1.26+、Pillow 10.1+。外部 Python 与 Blender 的 NumPy 无须相同，不修改用户全局数值环境。
- 可选视频需要显式 `ffmpeg` 路径。GNM、MetaHuman 数据和网络服务均不是本工作流的依赖。

## GLB 与头发

主流程输入自包含高模 GLB，纹理应嵌入文件。当前眼口适配器使用 **前方 -Y、上方 Z、头部最大跨度约 1 单位**。其他坐标先生成定向/归一化 GLB 副本，保留原文件与变换记录；配置绑定实际参与处理的副本 SHA256。交付沿用这一工作坐标，需要原单位时再组合保存的逆变换。

推荐光头；有头发也可输入。单一网格可直接处理；若有多个网格，用 `source_object` 明确头部，并用 `hair_objects` 显式列出要保留的独立头发网格。未选中的附件不会被暗中并入头部。独立头发保留原 UV/材质，按每个对象的预算减面后刚性绑定到 Head；贴图仍来自其原材质，不宣称已烘进头部图集。融合的雕塑头发随头部表面减面和烘焙。发丝、发片过密或遮住眼口时先检查简化与遮挡，不能宣称恢复了不可见皮肤；groom/曲线须先转网格。

用户提供 GLB 后，执行者根据实际正面/侧面确定眼口边界、关节位置和局部位移参数。可以复用用户的关键点/mask/法线模块，但先核对坐标、语义和置信度；不要求用户手填所有字段，也不把人工标注时间伪装成自动推理耗时。

## config.json

路径可以是绝对路径或启动进程的相对路径；入口统一解析为绝对路径。输出必须在 skill 包外。

| 字段 | 契约/默认值 |
| --- | --- |
| source | 必填，高模 GLB |
| source_object | 多网格输入时选定头部的精确对象名 |
| face_config | 必填，本输入的眼口/骨骼/局部形态参数 JSON |
| output | 必填，任务产物目录 |
| blender / instant_meshes | 必填，可执行文件路径 |
| hair_state | `bald`、`hair`、`unknown`；默认 unknown，不作为拒绝带发输入的开关 |
| hair_objects | 保留的独立头发对象名列表，默认空；有值时 hair_state 必须为 hair |
| hair_face_goal | 每个独立头发网格的减面预算，默认 10000；与头部面数分别统计 |
| working_triangles | remesher 工作表面预算，默认 700000；不用于细节烘焙 |
| remesh_face_goal | remesher 请求值，默认 20000；pure-quad 的实际输出计数以报告为准 |
| texture_size | 贴图边长，默认 4096 |
| uv_method | 默认 CONFORMAL；可选 ANGLE_BASED、MINIMUM_STRETCH，需检查实际 UV 和贴图 |
| bake_pbr_extras | 默认 auto：同值且无贴图驱动的 roughness/metallic 保留为材质标量，否则正常烘焙；all 强制输出对应贴图 |
| cage_fraction / ray_fraction | 选中到活动烘焙的 cage/ray 距离相对高模跨度，默认 0.009/0.04 |
| surface_samples / seed | 高模面积采样量/种子，默认 250000/0 |
| review_size | 最终静态审核图边长，默认 640 |
| diagnostic_previews / preview_size | 中间重复诊断渲染，默认 false；开启时图像边长默认 900 |
| video_frames_per_control | 默认 0；开启时每个命名控制至少 2 帧 |
| ffmpeg | 开启视频时必填的可执行文件 |

默认运行输出必要的审核图，不制作配音、说话口型或宣传视频。已有烘焙材质的常量通道不通过生成常量图来消耗时间；有真实纹理变化时保留烘焙。

## 脸部参数

`face_config` 含 `source_sha256`、`coordinate_space`、`provenance`，以及：

- `front_depth`：眼口切割允许的最大 Y。`uv_back_depth`：后脑 UV 缝的最小 Y。
- `patches`：恰好两个 `kind:"eye"` 和一个 `kind:"mouth"`，保持稳定顺序。每个 patch 含唯一 `name`、`center:[x,z]`、`outer_radii:[rx,rz]`、`inner_radii:[rx,rz]`、正整数 `rings`。根据实际边界调整外椭圆；切割必须只产生一条闭合边界，否则脚本报错。
- eye 另含 `side:"L"/"R"`、`blink_seam_z`、`wide_amplitude`，可选 `blink_slope`、`lid_clearance`、`blink_clearance`。L/R 是模型自身左右，正面相机下正 X 是模型左。闭眼使用环线编号及弧长参数，检查中间值而不只检查端点。
- mouth 另含 `seam_z`、`corner_drop`。上下半环要在嘴角会合而不交叉，内半径 Z 保留正值，避免重复顶点。
- `controls.front_mask_start`、`front_mask_width` 确定前脸软遮罩。
- `controls.fields`：键为表情名，值为高斯项列表。每项含 `center:[x,z]`、`sigma:[sx,sz]`、`delta:[dx,dy,dz]`；可选 `radial_x`，或 `attract_to:[x,y,z]` 与逐轴 `attract_axes:[wx,wy,wz]`。眉下压/内外抬、笑、皱嘴、噘嘴、压唇和皱鼻由显式局部位移组合。避免把左右区域的符号跳变写成整脸位移。
- `controls.jaw` 含 `center`、`sigma`、`seam_z`、`transition`、`delta`，只影响下唇/下颌软区域。眼 patch 生成 eyeBlink_L/R 与 eyeWide_L/R，嘴 patch 生成 jawOpen。
- `weights` 含 `neck_start_z`、`neck_transition`、`jaw_center:[x,z]`、`jaw_sigma:[sx,sz]`、`jaw_seam_z`、`jaw_transition`、`jaw_strength`。头/颈/颌三组非负权重之和须为 1。
- `joints` 按父先子后的顺序给出 Root、Neck、Head、Jaw、Eye_L、Eye_R。每项为 `[head_xyz,tail_xyz,parent_name_or_null]`，头尾不能重合。眼球位置以眼眶和原始眼面确定，不能用头部包围盒中心代替。

这些数据由实际测量或用户模块产生，不在包内附带某个人头的硬编码参数。一次适配后保存在任务目录，可直接恢复运行。

## 重拓扑运行模式

`retopology_backend` 为 `instant_meshes` 或 `runtime`；独立包默认前者，desktop 分发默认后者。只有本地模式要求 instant_meshes 文件。Runtime 模式可指定稳定 retopology_job；输入/参数/输出目录必须与返回账本一致。--fresh 只使本地缓存失效，不授权重新提交远程任务。详见 [远程重拓扑](retopology-api.md)。
