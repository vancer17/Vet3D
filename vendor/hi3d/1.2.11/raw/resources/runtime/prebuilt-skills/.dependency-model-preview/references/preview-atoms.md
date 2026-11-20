# 展示原子接口

[preview_scene.py](../scripts/product/preview_scene.py) 接收当前 Blender 场景中的显式对象；坐标使用场景单位，不推断需展示哪些零件。

- `bounds_points(objects,evaluated,require_mesh=False)` 返回对象包围盒的世界坐标角点；evaluated 必填，选择原对象或求值对象的 bound_box/矩阵，不意味着逐顶点实体测量。require_mesh=true 要求非空求值网格。
- `fit_orthographic_camera(camera,objects,resolution,evaluated,margin=1.15)` 只移动相机平面位置并设置 ortho_scale。考虑 sensor_fit 与横/竖画幅，拒绝空对象、非正尺寸、退化投影和 margin<1。resolution 使用有效像素宽高（非方形像素先乘 pixel_aspect），调用方同步渲染画幅；不改镜头朝向或场景比例。
- `position_camera(camera,center,direction,scale,roll=0)` 保留显式目标、相对相机偏移、正交比例与角度制 roll；修改该相机。
- `projected_bounds(scene,camera,objects,evaluated,check_depth=False,require_mesh=False)` 返回 min/max x/y 和 all_in_front；check_depth=true 还要求所有角点严格位于 clip_start/clip_end 之间。默认仍只报告是否在相机前，不把包围盒在画面内解释成没有遮挡。
- `check_framing(scene,camera,objects,frames,evaluated,margin=.01)` 按 [姿态采样](../../.dependency-motion-check/references/scene-samples.md) 输出 all_bounds_in_frame/samples；边界严格落在 margin 与 1-margin 内且位于相机前，成功/失败恢复原帧。遮挡、构图美感和实际形变仍需渲染检查。
- `area_light(name,location,target,energy,size,color,collection,shape='DISK')` 创建并瞄准显式面积灯，物理参数与集合由调用方给定，不另设产品灯光配方。

[glb_export.py](../scripts/product/glb_export.py) 的 `export_glb(path,objects,convert_curves=False,unhide=False,exporter=None,**options)` 固定 GLB/use_selection，仅导出显式唯一对象；要求活动 view layer 与 Object mode。其余 Blender 导出参数原样传入，包括动画、强制采样、材质、Draco 与量化；不隐式减面。convert_curves 对静态曲线创建求值网格副本，保留属性并在成功/失败删除对象及 mesh。导出后恢复所有原选择、active、hide_set 与帧/子帧状态；不创建父目录、不决定覆盖策略，不修改源几何。字段/选项不兼容由当前 Blender 报错；exporter 可注入同签名调用函数，缺省为当前 Blender glTF operator。

基础 Principled 节点由 [blender-tools](../../.dependency-blender-tools/references/material-nodes.md) 创建；粉体颗粒、透光混合等特殊图仍在品类适配。产品 studio 的灯位/功率和护甲取景仍保留原配方；调色盘横幅结果保持，竖幅按 Blender AUTO sensor_fit 正确容纳投影。测试见 [test_preview_atoms.py](../tests/test_preview_atoms.py)。

`fit_projected_orthographic_camera(scene,camera,objects,evaluated,margin=.05)` 面向最终场景画幅，使用 Blender view_frame 和投影处理 sensor_fit、像素宽高比与镜头 shift；margin 是各边比例，须在 [0,.45)。只接受独立、无约束/动画的正交相机及非空网格，投影在严格深度区间内；修改平面位置/ortho_scale 并验证最后留边，失败不回滚相机。返回与 projected_bounds 相同的字段。它与原 fit_orthographic_camera 的倍率/显式有效分辨率接口不同，不能直接互换 margin；两者都不设置产品姿态或灯光配方。

比例留白接口先确定最终 ortho_scale，再按最终投影居中，避免非零镜头 shift 随比例改变导致留边验证失败；旧的零 shift 取景保持，非零 shift 可正确居中。
