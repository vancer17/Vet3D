# 圆口旋锁与双燕尾支座配方

本页是一个有限桌面框构型的可执行流程，先读[连接研究](connector-research.md)、[DIY判断](diy-printing.md)与[制作包完整性](delivery-completeness.md)。原标准压片/M3版本继续使用自己的构建器、配置和文件；本配方生成新公母接口，不把原金属螺钉换成塑料材质。

## 适用边界与四件分工

显式选择此家族才使用：圆作品口110mm、外圆R80mm、X偏心−14mm、82°桌面展示、纸卡113.9×0.4mm且不带玻璃。定位、锁止和变形采样区域依赖这些尺寸。不是任意相框转换器；用户指定其它尺寸、作品形状、玻璃或墙挂时保留其目标，另在任务目录设计相应结构。

- 主框有三段公耳的插入口/环形锁肩、背衬定位槽和支座母燕尾。正面浮雕来自显式真实高度场；原Hi3D高模另存，首击高度场不能表示倒扣。
- 静止背衬支承纸卡，以键限制旋转；其外盘/定位耳与框槽有不同径向余量。锁环旋转不要求照片随转，但纸张摩擦、翘曲和划伤仍需实物检查。
- 旋锁背环带三枚刚性耳，先轴向进入再旋转12°锁入；长侧舌限制反转，按入后才能解锁。保持面和止挡承担功能，预设释放形变不代表有限元、插入力或耐久证明。
- 一体支座由两宽燕尾承托，末端肩与可达释放舌限制滑出。装座需要完整入口行程；拆卸时捏住或勾起支座拨片，向自己拉起约1.5mm，再沿导轨向下退出，不是向框体按压。拿起相框时同样要检查保持，不靠重力或摩擦假装锁定。

正式机械件四件，外购螺钉/嵌件/胶为零。照片是被展示内容；打印材料、去支撑工具另列。没有玻璃、软脚垫、配重或墙体锚固的承诺。普通PLA、0.4mm喷嘴是可标注的试制起点，不是用户实测设置。

## 显式输入与配置

需要独立提供 Blender 5.2兼容程序、普通Python及本包requirements、真实高度场NPZ、作品图片、JSON配置。已有资产可跳过线上生成；新增自由纹样的Hi3D调用沿用独立工具契约，此本地CLI不调用网络、不读密钥。

```json
{
  "recipe": "circular-bayonet",
  "aperture_mm": [110, 110],
  "outer_radius_mm": 80,
  "eccentric_x_mm": -14,
  "frame_back_mm": -1.2,
  "bayonet_turn_deg": 12,
  "height_key": "height",
  "hi3d_relief_mm": 4.2,
  "source_boundary_fade_pixels": 18,
  "fit_clearance_mm": 0.25,
  "title": "本次圆口作品框"
}
```

这是该有限配方的调用示例，不是对新用户偏好的默认替代。未知键、非有限数、不同口径/外圆/偏心/旋角/背面坐标在写出前拒绝。`height_key`必须实际存在，数组至少8×8、二维实数且归一化到[0,1]；不接受空/复数/NaN数组，原件不修改。

可调值只包括浮雕幅度0–4.2mm、渐隐整数1–64像素、标题和配合偏置0.20–0.35mm。调整源场或幅度必须实看纹样/壁厚；调整配合必须重验插入和止退，不能拿区间表示每台PLA打印机都适配。燕尾偏置是X两侧各增`c`及+Z头部增`c`，斜面法向距离不能直接写`c`。旋锁径向/上下轴向间隙与背衬层叠分别记录；纸和背衬到前止面仍只有0.05mm名义余量，不称已校准或可自动适配其它纸厚。

## 调用与阶段

`SKILL_DIR`为独立提供的此技能目录，所有运行输出都放任务目录；这些是调用者变量，不是隐式安装路径。

```sh
python "$SKILL_DIR/scripts/run_diy.py" \
  --stage build --heightfield ./input/field.npz --artwork ./input/artwork.png \
  --config ./input/diy.json --output ./result --work ./run-work \
  --blender /path/to/blender --no-render
python "$SKILL_DIR/scripts/run_diy.py" \
  --stage coupons --output ./result --work ./run-work --blender /path/to/blender
python "$SKILL_DIR/scripts/run_diy.py" \
  --stage print --output ./result --work ./run-work --blender /path/to/blender
python "$SKILL_DIR/scripts/run_diy.py" \
  --stage verify --output ./result --work ./run-work --blender /path/to/blender
```

- `build`完成真实四件、两GLB和原生场景；`--no-render`只省图片，不省几何。直接Blender入口是 `build_frame_diy.py -- --output ... --heightfield ... --artwork ... --config ... --no-render`。
- `coupons`从**flat-assembly.blend**裁切六件真实接口，再生成三档燕尾公母六件；输出12件及manifest/native。不要给已倾斜的scene.blend，否则被拒绝。试片中的0.15/0.25/0.35mm仅为燕尾坐标偏置档位，不是整框其它接口的可用间隙范围。
- `print`把四正式件与12试片按实际配对方向另存到`manufacturing/parts`和`manufacturing/coupons`，写`print-orientation.json`记录从装配世界米坐标到打印世界米坐标的刚性矩阵。默认另产打印排布图与原生场景；`--no-render`省略排布图/场景，16件STL与矩阵仍生成。
- `verify`重新导出独立释放态、检验四件装配STL、12试片及16件制造STL的拓扑，逆变换制造件后与原装配坐标顶点双向比较，检查实际三档公母滑入路径、四件装卸/保持、四PLA实体的静态重心，并重新导入GLB。正式STL必须是**所有shape key归零并更新依赖图之后**的自由态；两类pressed文件仅作预设释放几何检查，不放进正式制造件。
- `media`制作该配方完整换片/装拆动作和图像；`all`编排build、coupons、print、verify、media。media还会重新导入真实GLB，与原生动作17个关键姿态的包络比较，并检查纹理打包、角色和单同步动作。GLB时间采用实际导出的frame/fps，与导入后的帧率换算，不额外加一帧。默认只生成选定本地阶段，脚本不会发布网页。`--no-render`可省静图；完整帧渲染需`--render-animation --ffmpeg /path/to/ffmpeg`，帧在work，MP4在output。保留原媒体序列的真实帧率，不凭标注改变动作速度。

阶段可独立重放，使用新的attempt-id，`--resume-of`关联上次；不覆盖同名attempt日志。输出与work可包含已生成派生文件，但不能包含本次原始NPZ/图片/配置，不能位于技能内或作为技能目录祖先。派生场景可在output内续跑，新文件不可覆盖输入本身。校验失败在创建输出目录前拒绝；运行中失败不保证回滚，保留日志再重跑受影响阶段。

## 数字与制造检查

公耳/母槽、背环舌/锁肩、支座舌/接收面都需存在；不能仅检查一侧。锁定态的故意退出探测应被实体阻挡，按压后整段离散装卸路径应无非预期交体。三档试片的母座底面要给公舌底座留出入口，拓扑闭合不证明配对能装。

装配坐标STL与摆放到打印板的文件分开；同一配对试片跟随正式配对件的打印方向。主框背面落台，锁肩下局部桥接/支撑需试切；背环外耳从离板处开始，不能宣称无支撑。支座按轨头落台方向安排支撑、清除梁下与释放缝；具体打印朝向以实际导出的orientation记录为准。不要用整套零件缩放来调间隙。

独立回读每件的单位、边界/非流形/零面积/连通、真实体积/包络；检查真实GLB的角色、自由/按压状态、单同步动作和关键帧。接地点与四PLA实体同密度假设下的重心只是数字静态稳定条件，此内置检查排除纸卡重量、不模拟填充率；加入玻璃、配重或其它介质必须重建质量假设。碰撞采样不覆盖所有连续运动、纸张变形、手指力、摩擦或柔性疲劳。实际切片、试印、支撑可拆、换片循环与抗推/抗滑未完成时逐项标待测。

## 完整交付与计时

最终还需主图/背面/接口图、完整装卸与落桌视频、真实交互模型、四件打印文件、12试片、BOM/方向/支撑/释放说明、native/配置/源码及保留的真实Hi3D原件；网页保留standard与DIY各自下载和物料状态。解压下载逐项核对，不能只用渲染完成来宣称制造包完成。`all`不是网页发布/实物验收命令。

`run_diy.py`为选定本地阶段自动写work/timing.jsonl（任务/attempt/阶段、带时区起止、monotonic秒数、失败/中断），每次新attempt保留结果和子进程日志；总墙钟取真实起止，不相加重叠项。其它研究、Hi3D、视觉审查、网页等阶段仍按[计时规则](timing.md)记录，真实token usage可选，不能用字符/耗时估算。日志和已执行报告不得写回技能包。
