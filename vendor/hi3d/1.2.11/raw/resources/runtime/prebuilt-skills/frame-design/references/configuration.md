# 相框配方与结构边界

先按作品尺寸/形状/厚度重建需求。包内不含历史高度场、作品照片或已执行配置。原子几何函数支持从显式点环/数组起步，独立调用无需跑全场景。

- `build_frame.py`：显式`recipe:flowing-foliage`、`aperture_mm:[W,H]`、`height_key:指定NPZ键`，W/H>=60mm。程序低频流动框加稀疏枝叶，叶表面用输入场；不是任意主题/厚度的通用设计器。默认固定标准层叠：后板2.95mm、纸卡.4mm、安装槽深3.4mm及M3压片/支座。改变层厚/玻璃/重量须适配并重验。
- `build_crescent.py`：显式`recipe:eccentric-crescent`、圆口`aperture_mm:[D,D]`、height_key、outer_radius_mm、eccentric_x_mm、relief_height_mm，并必传本次artwork图片。D>=80mm，outer_radius−abs(eccentric_x)须留至少D/2+3mm。上述3mm是此算法最小输入边界，不是承重标准。source_boundary_fade_pixels默认18，按源分辨率检查实际过渡；偏心轮廓、后承力环、后板/压片与拆座共同组成配方。

两构建器必传`--output --heightfield --config`，crescent另传`--artwork`；`--preview`仅限制若干主图，`--no-render`不出图但仍产真实几何。输出print毫米STL、model/exploded GLB、measurements、scene.blend与选定图片。M3外购硬件和部件位置属于配方，DIY需在工作目录适配代码而非传不存在的hardware_policy参数。

`extract_relief_stl.py`读取明确以毫米表示的binary STL。默认XY为纹面、+Z前面，可传`--axes 0 2 1 --front-sign -1`调整；`--resolution`、pit-threshold、median-floor可控。结果heightfield.npz包含height/raw/before/repair_mask与投射坐标bounds；首击不保留倒扣。先看源视图/掩膜，不把源修补当原高模修改。

动画入口读对应scene和同目录measurements；保留collection/assembly_role/pivot_mm语义。尺寸变体要重检固定的装入轨迹和镜头，不能只缩放总装。输出帧放工作目录，再用FFmpeg编码并核对视频首中末帧。

## 四件圆口旋锁 DIY 配方

已有标准构建器的 `hardware_policy` 不产生新接口。明确选择 **D110mm 圆口、R80mm 外圆、X=-14mm 偏心** 的桌面家族时，可使用独立的 `build_frame_diy.py` / `run_diy.py`；完整配置、四件角色、装卸顺序、打印朝向与验证见 [圆口旋锁配方](diy-recipe.md)。主框、静止背衬、旋锁背环、双燕尾支座均为真实打印零件，配套12件接口试片。其它口径、矩形作品、玻璃层厚、墙挂或不同偏心轮廓需另做结构适配，不能整体缩放或向此CLI传任意尺寸。

配置必须显式声明 `recipe:"circular-bayonet"`、`height_key` 与配方固定尺寸；高度场为所选键下归一化 `[0,1]` 的二维实数数组。浮雕幅度0–4.2mm、边界渐隐1–64像素和配合坐标偏置0.20–0.35mm可调，所有变化仍需重做配对/路径检查；范围是本地输入边界，不是用户打印机的校准结果。尤其燕尾 `fit_clearance_mm` 表示两侧X与头部Z坐标的偏置，**不等于45°斜面的法向间隙**。
