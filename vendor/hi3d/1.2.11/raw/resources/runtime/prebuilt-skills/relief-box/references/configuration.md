# 收纳盒配方与布局范围

所有输入高度场及配置显式提供；不含旧纹样或历史运行数据。先按物品确定净空间。primitive/loft/height_mesh可独立调用，可据此重建新的轮廓/分区。

`build.py --heightfields FIELD.npz --config CONFIG.json --output WORK [--no-render]` 为基础矩形/圆形提盖配方。配置必需variants，每项为`[kind,width_mm,depth_mm,height_mm,x_display_offset_mm]`，kind=rect/circle，各平面尺寸>=70mm、高>=30mm；circle应宽深相等。必需relief_roles:{medallion:实际键,border:实际键}。浮雕尺寸依外廓和源宽高比计算，可调medallion_width_fraction（默认.72）。固定配方有3mm壁/底、3.2mm盖、定位裙、.4mm单侧裙间隙、20mm深可拆内托和矩形分隔/取托边；改变这些结构需适配代码。装饰为独立标准件，采用粘接必须列BOM；printed_only改为真正一体或配对打印连接。

`build_travel.py --heightfield FIELD.npz --config CONFIG.json --output WORK [--no-render]` 为显式`recipe:three-zone-travel`；当前固定172×104mm外廓、body_height_mm=34、height_key与relief_height_mm必填。戒指区、44×57×1.8mm带真孔耳卡、28×52mm项链芯、可拆三区内托和盖内衬已建模，位置仅对该布局成立。该输入限制明确拒绝把它当所有收纳物的可缩放万能模板；新尺寸需重排分区/锁位/动作后重验。标准版用两枚M3螺钉、泡棉/织物/弹力保持，不自动提供打印锁件或可直接替换的TPU文件。

两配方实际输出STL/GLB/native、measurements与图；no-render只跳过渲染。软衬整形STL和SVG是材料加工参考，不是已验证PLA或TPU缓冲件。travel_details生成盖底/内区图与1:1模板，animate_travel读取对应scene和measurements，展示真实提盖/取托/复位动作。基础矩形/圆形模型的通用提盖动画可用animate_lift，不能以旅行布局对象名套另一种盒。

extract_relief_stl以binary STL为输入，明确毫米/轴向，可配置axes/front-sign、分辨率及局部低谷修补。结果NPZ的height键可映射盖面。近边界四角、裙边和薄纹样要实际剖面复核，不把16位高度场当完全保留倒扣的高模。
