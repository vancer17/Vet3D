# 地格、地图数据与环境生成

## 基础几何

- 标准正六边形外接圆半径 R=1m，边长也为1m。最早的单格模板厚0.1m；完整地形的柱高由海拔控制，不是每格恒厚0.1m。
- 两个独立部件：`HexTile_Top` 是上表面；`HexTile_Body` 是侧面、底面和上沿倒角。实例名称通常带 `_XX_YY`，格子根节点为 `HexTile_Base_XX_YY`。
- 地图是 pointy-top 的奇数行水平错位布局。早期单格模板局部朝向是 flat-top，实例存在旋转；不要只根据模板局部顶点推断世界方向。
- 每格 Body 从 Z=0 延伸到地表；Top 位于目标海拔高度。Body 不能只整体平移而留下悬空底部。
- 倒角宽0.03m、45°、一段，归属 Body。Top 随倒角内收但保持独立平面。高度变化只改直壁，不把倒角拉长。基线倒角后每格32三角面，100格3200三角面，仅计基础地形。

```text
x = (id.X + (id.Y % 2) * 0.5) * R * sqrt(3)
y = id.Y * R * 1.5
z_ground = altitude * height_step_m
height_step_m = 0.1
```

基线是10×10、100格、整数海拔范围19–64，对应1.9–6.4m。`altitude_max=1000` 是临时允许上限，不是当前地图已经达到100m。整体连续起伏，允许局部悬崖、地坑；`generation` 保存生成用相位、隆起、偏移等参数，`cells` 保存实际结果。

## 邻接与边索引

用同一套奇数行偏移邻接保证河流、城墙共享边一致。设p=Y%2，世界XY方向逆时针编号：

| 边索引/方向 | 相邻格(X,Y) |
| --- | --- |
| 0 / 0° | (X+1,Y) |
| 1 / 60° | (X+p,Y+1) |
| 2 / 120° | (X+p−1,Y+1) |
| 3 / 180° | (X−1,Y) |
| 4 / 240° | (X+p−1,Y−1) |
| 5 / 300° | (X+p,Y−1) |

相邻格对应入口边是(exit_edge+3)%6；越界表示地图外，不能创建不存在的邻格。这里编号是边的外法线方向，不是顶点角度。

## 原样例高程如何复现

完整复现时直接复用地图cells中的整数海拔。若需从初始生成记录重建，`hi3d-hex-terrain-grid_1.py` 的基线为：

```text
q = X + 0.5*(Y%2)
height = 36 + 12*sin(0.42*q + phase_a) + 9*cos(0.38*Y - 0.16*q + phase_b)
height += sum(amplitude_i * exp(-((q-column_i)^2+(Y-row_i)^2)/(2*width_i^2)))
if X>=7 and Y<=3: height += 19
if 3*(q-3)^2 + 2.25*(Y-6)^2 <= 3.01: height -= 15
altitude = clamp(int(round(height)), 0, altitude_max)
```

phase_a/phase_b以及5组bumps用地图generation中实际保存的数值。若从seed重新抽，原脚本依次用Python random.Random(seed)生成两相位[−π,π]，再逐个生成bump的column[0,9]、row[0,9]、width[2.2,4.5]、amplitude[−9,12]。随机调用顺序会影响结果。右上悬崖和中央地坑是这张10×10地图的显式样例特征，不是每张地图固定生成的位置。

## 数据职责与字段

| 层 | 内容 |
| --- | --- |
| 通用规则 JSON | 纹理映射、资产池、湿度×材质密度、碰撞、草坪、水和文明规则、规则版本 |
| 地图 JSON | 行列、半径、步长、种子、海拔、环境值、水位、文明度、河流路线、实际实例与版本引用 |
| 资产 manifest JSON | 模型 ID、根节点和 parts、地面原点、局部包围盒、米制尺寸、图集、已确认缩放 |
| GLB | 几何、材质、UV、变换、内嵌图片、必要单位标记，不放环境或游戏属性 |
| blend | 可编辑场景、生成所需结构、打包/相对路径纹理 |

每格基础字段：`id:{X,Y}`、`altitude`、`coordinate_m`、`temperature`、`humidity`、`surfaceMaterial`、`waterLevel`、`civilizationLevel`。连续环境值为 `humidityNoise/coverNoise/sandSourceNoise` 与 `humidityValue/fineCoverValue/sandinessValue`。显示结果可包含 `topTexture`、`surfaceState`、`decorationRuleKey`、`decorations`、`riverRefs`；草坪和文明结果随版本增补。

普通实例记录模型 variant、instance_name、parts、位置、朝向、scale、投影范围等；河流植物是独立层，记录在河流/河流生成数据中，不要并入文明建筑清理列表。`landSurfaceBackup`、`naturalSurfaceBackup` 是恢复自然状态的归档，不应与活动列表重复实例化。

属性变更只生成新 JSON，直到用户要求“贴上材质/生成GLB/摆放”才应用到模型。导出时剥离温度、湿度等语义 extras，保留 `sparc3dPhysicalUnits={version:1,unit:"meter"}`。

字段形状和真实实例示例见 [地图契约样例](../assets/baseline/hi3d-map-contract-examples.json)。样例有意截断格子/截面，只用于理解结构，不能作为完整地图输入执行。

## 枚举约定

| 维度 | 内部值 | 中文 | 文件中的值 |
| --- | --- | --- | --- |
| 温度 | hot / temperate / cold | 炎热 / 温和 / 寒冷 | 同内部值 |
| 湿度 | arid / moderate / humid | 干旱 / 适中 / 潮湿 | dry / moderate / wet |
| 地表 | soil / sand / gravel / rock | 土壤 / 沙子 / 砾石 / 岩石 | 同内部值 |

温度是三档，不是摄氏度。泥不单列为材质，由土壤+湿润表现。草地、森林属于植被覆盖，不进入四种地表材质。海拔保留独立连续数值，不把“山地/高原/平原”硬塞进材质枚举。

## 最终三个环境场及公式

全部噪声场值域0–1，独立种子，空间连续；在错位后的格心采样。基线全图温带。高海拔偏干、偏裸岩是当前地图的美术生成选择，可随新地图需求改变。

| 场 | 基线种子 | scale_cells | 特征 |
| --- | --- | --- | --- |
| humidityNoise | 20261131 | 1.7 | 较高频、小范围变化 |
| coverNoise | 20261232 | 1.4 | 较高频、小范围变化 |
| sandSourceNoise | 20261333 | 7.0 | 低频、大范围缓变 |

这些数字是 seed，并非日期，不能按日历纠正它们。

```text
h = clamp((altitude - min_altitude) / (max_altitude - min_altitude), 0, 1)
humidityValue = clamp(0.80 - 0.60*h + 0.30*(humidityNoise - 0.5), 0, 1)
fineCoverValue = clamp(1.175 - 1.19*h + 0.51*(coverNoise - 0.5), 0, 1)
sandinessValue = clamp(1/(1+exp(-12*(sandSourceNoise-0.885)))
                      + 0.08*(0.5-humidityValue), 0, 1)
```

当前 min/max=19/64；新地图用自身范围，不能直接除以1000。新地图全平时归一化分母为0；最初values脚本给h=0.5回退，但后续frequency迁移脚本直接除海拔差，复用时须保留回退。原样例没有全平输入的实际验证。

- 湿度 `<1/3` 干旱，`<2/3` 适中，其余潮湿。
- 覆盖度 `<0.25` 岩石，`<0.5` 砾石，其他进入土/沙候选。
- 仅在土/沙候选中，以 sandiness `<0.5` 为土，其余为沙。
- 不得恢复“湿度<0.5就是沙”的方案，否则干土和湿沙无法出现。
- 沙区过大时先查映射的分布和阈值，不要把低频沙源场随意改成高频噪点。最终 sigmoid 映射让沙源场保留7格尺度，同时降低大片沙区出现概率。

精确复现噪声时不能用任意Perlin/另一个库替代：原实现先以 `u=X+0.5*(Y%2)`、`v=Y*sqrt(3)/2` 作为单位格距坐标，再除各场scale_cells；不是直接用世界米制x/y除scale_cells。格点值为 `int.from_bytes(blake2b(f"{seed}:{ix}:{iy}",digest_size=8),"big")/(2**64−1)`，横纵插值权重均为smoothstep(t)=t²(3−2t)，四角双线性插值。三个场种子分别为map_seed+101/+202/+303。场值及派生数值存小数6位，分类采用已舍入字段；最后sandiness修订使用已存humidityValue，避免临界值和历史结果漂移。

环境生成结束时样本统计曾为岩23、砾22、土35、沙20；后续水域与文明是覆盖显示层，不能把此历史统计当成最终地表显示统计。
