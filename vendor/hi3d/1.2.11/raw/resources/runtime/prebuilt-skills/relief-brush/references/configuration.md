# 输入与配置

所有几何/高度文件来自显式路径；包内没有历史图片或高度场。extract直接接收GLB/glTF；Blender导入后以场景米坐标采样，真实尺度仍须核对，随后独立赋物理毫米覆盖。负向/正向前面由axes和front_sign定义，先看实际视图。

`extract.py --source INPUT.glb --config extraction.json --output WORK/extracted`：配置必需`resolution:[width,height]`（各>=8）、`axes:[width_axis,height_axis,depth_axis]`（0/1/2排列）、`front_sign:-1|1`和`regions`。region如`motif:{crop:[0,0,1,1],mode:stamp,fade:[.06,.08]}`，模式stamp/tile/border明确选择；名称不可用raw/source，crop每轴至少8样本。ray_margin是源单位，默认.1；baseline_percentile默认6，height_percentile99.8。source_pit_threshold默认.004源单位，source_pit_kernel3、iterations1，需随源缩放核对，设iterations0可关闭；region repair默认5×5、归一化阈值.12、median_floor.2、最多3轮（tile1轮）。这些都是启发式起点，任何负空间不能仅按阈值认定缺陷。

`build.py --heightfields WORK/extracted/heightfields.npz --config build.json --output WORK/product [--no-render]`：同目录须有metadata.json及每个区域的16位PNG。必须显式brush_roles:{main:motif,tile:repeat,border:border}，并给每个region的stamp_dimensions_mm:[宽,高,浮雕深]。三角色是该组合构建器的范围；PNG-only只跑extract和读回检查。主要可选值：coverage_mm:[88,38]、relief_depth_mm:1.6、base_thickness_mm:2.4、cylinder_radius_mm:65、sphere_radius_mm:80、path_count:9、path_angle_step:.15。以上是演示尺度，非机加工标准；曲面覆盖角度过大时检查折叠/失真。路径块目前20×16mm独立实体，不是接合带。

可选grip_sleeve:{inner_diameter_mm,wall_mm,height_mm,relief_mm}只生成连续圆筒名义握套，需实际杆尺寸和装入/保持验证；没有分瓣锁环。build输出brush-library.blend与scene.blend、PNG/npz/元数据、几何印章、三曲面和路径GLB/STL、测量/渲染（no-render跳过图）。application_demo必须用相同config/heightfields和scene，避免不同拓扑形变。

单个数组可直接调用field_ops.prepare_regions；无需Blender、不写文件。高度场线性16位PNG应独立读回确认bit depth和方向，不能用8位preview替代最终输入。

## STL 预处理

STL 没有可靠的内置单位；本提取CLI不能直接传入STL。按用户/来源的单位换算为每个STL单位对应多少米：已知毫米用0.001、英寸用0.0254。未知时可采用明确标注的假设，记录unit_basis=assumed并保留待校准状态，不能自动称已知毫米。

1. 保留原STL不改写，将临时GLB和报告输出到本次工作目录。
2. 在Blender运行以下显式预处理；例中0.001/known只适用于已确认的毫米输入：

```sh
BLENDER -b -t 2 --python-exit-code 1 --python SKILL/scripts/prepare_stl.py -- --source INPUT.stl --output WORK/prepared/source.glb --meters-per-unit 0.001 --unit-basis known
```

3. prepare_stl会实际导入STL、导出GLB、清空场景后重读GLB，比较世界坐标bounds；source.conversion.json记录单位来源、前后毫米尺寸、误差和通过状态。默认1e-6米容差仅用于文件转换数值比较，不是打印配合/实物适配标准。失败不进入提取。另将这些尺寸与来源/实测尺寸对照；缺实测仍保留假设标签。
4. 再运行 `extract.py --source WORK/prepared/source.glb --config extraction.json --output WORK/extracted`；依据转换后的实际轴向/米尺度重新选axes、front_sign、ray_margin和source_pit_threshold。不要把原STL毫米坐标的阈值直接当米使用。GLB/glTF原输入可跳过此预处理，glTF的外部bin/贴图依赖须一起可读。
