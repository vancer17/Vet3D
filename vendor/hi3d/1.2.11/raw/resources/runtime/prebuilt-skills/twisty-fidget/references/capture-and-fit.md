# 闭合散架与忽松忽紧：捕获余量和配合验收

闭合就散架说明需要检查横向/径向脱出、倒扣余量、唇边和舌根；只补轴向末端止挡不能解决。保留用户确认的实际打印版本、瓣数、裁切和玩法。打印文件、缩放、材料、喷嘴、失效姿态一次性询问；缺项继续做数字诊断与试片，但将工艺标为 assumed，不能假称校准。实物失败优先于旧报告的通过结论。

## 修订顺序

1. 重读实际打印 STL。检查每瓣连通件，逐接口含首尾边取真实截面。区分导轨从槽口横向弹出、沿螺旋旋出、根部断裂和打印粘连；仅凭照片不推定材料、缩放或具体断裂原因。
2. 两侧倒扣余量分别测量，取较弱侧，禁止用平均头宽掩盖不对称。记录槽口宽、舌根宽、两侧松动空间、头部厚度、接收唇边、槽后壁和止挡承压位置。舌头变大可能把接收瓣削薄，必须同时验收。
3. 为本次尺寸与工艺声明制造损失、槽扩大、磨损/弹性让位预算和所需剩余捕获量。比较每侧实测余量减预算后的结果。预算不是已测弹性变形，二维刚体阻挡不是强度证明；实际试印失败后必须重做试配。
4. 增瓣后按毫米重定导轨尺寸，不能把参考截面角压缩、径向放大和全轮廓 inset 后直接沿用原验收。必要时用 `rail.t_profile` 生成圆角 T 轨候选，分别设置根宽、头宽、头厚、根部伸出、槽隙和半径。该函数不自动推断空间、强度、捕获或可打印性。
5. 跑动间隙与防脱倒扣分开调。常螺距径向切面上，同高 XY 间隙并非真实法向间隙；局部比例约为 `sqrt(1+(k_rad*r)^2)`。可依半径补偿径向缝隙，但 T 轨各面法向不同，最终仍测真实三维曲面最短距离。不能只统一减小间隙来修复“有松有紧”。
6. 给止挡保留独立材料带，避免槽切坏捕获唇边或舌根。按所有接口、常用玩法和每个止挡端点检查有效搭接；正搭接还需超过任务规定的最小值。
7. 生成真实匹配导轨的多间隙试片，沿用半径、旋转率、圆角、打印方向和尺寸。注明试片与整件在行程、止挡或外皮上的差异。试片不得用普通插销替代；诊断短轨不得冒充完整防脱成品。用户缩放整件后必须重算与重试配。

## 数字截面工具

```sh
python "$SKILL_DIR/scripts/run.py" measure-capture --assembly "$TASK_DIR/final/assembly.json" --spec "$TASK_DIR/capture-spec.json" --out "$TASK_DIR/capture-01" --task-id toy
```

`capture-spec.json` 必须含：

| 字段 | 内容 |
| --- | --- |
| schema | `twisty.capture-spec.v1` |
| maximum_section_step_mm | 本任务允许的最大取样间距，正有限数 |
| manufacturing | status 为 assumed/calibrated；basis 说明来源；extrusion_width_mm、male_loss_mm、female_growth_mm、wear_flex_budget_mm 为实际毫米参数，后 3 项可为零但须有依据 |
| thresholds_mm | residual_capture、maximum_neck_play、root、flange、front_lip、back_wall、minimum_engagement，均为任务阈值；将喷嘴/线宽、材料与打印方向的影响说明在审查中 |
| interfaces | 完整环，每条 owner/receiver 一次；angle_at_z0_deg、递增 heights_mm 至少 3 项、probes |

probes 在每条接口的局部 XY 坐标中定义：x_window_mm、x_center_mm、head_y_mm、neck_y_mm 指定头部、根部和槽口的横向探线；shoulder_x_mm 指定两肩的纵向探线；y_window_mm 与 flange_y_mm/front_lip_y_mm/back_wall_y_mm 分别定位头部、前唇和后壁的材料区间。先看剖面再选探线；窗口外延、选错区域、非闭合环或缺材料均失败。不能通过移动探线避开已知薄弱处；不适用于这种探线表达的机构需扩展测量适配器，不能填假数通过。

`capture.py` 从最终重导入网格取平面截面，逆转相应螺旋角，保存原始区间与各侧实测值。`accept` 强制要求 capture_measurement 文件引用，复算数值与原始区间一致性、制造预算、每接口/每高度覆盖、测量区间与搭接的一致性、全部声明玩法和双向止挡端点的最小搭接。缺数字报告时 `captured:true` 无法通过。

这是实际网格的有限平面采样。所测厚度为所选探线厚度，不能直接称全局最短法向壁厚。审查仍须覆盖探线之间、其他薄弱位置、止挡槽与外皮的材料，并保留足够采样/扫掠误差余量。

## 配合证据

最终 `reviews.fit` 强制包含真实三维间隙数据与试片引用。每接口记录 minimum_gap_mm、maximum_gap_mm、required_range_mm；artifact 中保留实际测点、测法、不同半径/高度/相对位移、异常/不可取样点及原因。不能拿单个 XY 最小距离或理想生成参数代替实测范围。模型更换后重测，不能引用另一版本的试片作为本版通过证据。

process_status 与 basis 明确工艺是 assumed 还是 calibrated；coupon_artifacts 指向实际试片 STL 和/或已测记录。生成了试片仅表示可以校准。未经用户实测不得称不卡、不散、丝滑、已修复实物或通过耐久测试；只能报告数字几何通过与待试配。出现已知不可打印问题时不能用 assumed 掩盖失败。

## 原子契约

| 函数 | 输入 → 输出 |
| --- | --- |
| rail.t_profile | 毫米尺寸、瓣数、旋转率、采样 → CCW 轮廓点和互锁舌轮廓；冲突/分裂/非法尺寸抛错 |
| capture.section_polygon / interval | 最终网格、平面与局部角 / 多边形、探线 → 保留孔洞的截面 / 单一有限区间；缺失或歧义抛错 |
| capture.measure_section / evaluate_row | 实际匹配截面、探线 / 实测行、工艺阈值 → 原始区间和两侧尺寸 / 失败项 |
| capture.validate_spec / measure_capture | 全环测量规格 / 最终网格、manifest、规格、摘要 → 合法规格 / 每接口每高度实测报告，失败保留 |
| capture.check_capture | 报告、manifest、摘要、区间 → 覆盖与数值审计；弱肩、薄壁、缺项、陈旧值、端点搭接不足抛错 |
| retention.check_fit_review | 配合审查、瓣数 → 完整环及实测范围审计；不重复三维距离计算 |

无文件副作用的运算保持在 rail/capture/retention 模块；读写、摘要和计时由 run 适配。参考原子脚本不自动调用切片器、不预测摩擦、不提供通用材料公差。
