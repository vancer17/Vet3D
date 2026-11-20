# 水体预制

本阶段只调用 `dcc-preset`，不在这里维护第二份插件或节点名单。

| 宿主与版本 | 预制 | 得到什么 |
| --- | --- | --- |
| UE 5.7 及以上，只要水体系统 | `unreal.water` | `.uproject` 启用 `Water` 与 `Landmass` |
| 还要示例地图 | `unreal.water-samples` | 再启用 `WaterExtras` |
| 还要浅水或浮力插件 | `unreal.water-simulation` | 再启用 `WaterAdvanced` 与 `Buoyancy` |
| Houdini 20.5 及以上 | `houdini.ocean-spectrum` | 含内置 Ocean Spectrum 的 HIP |
| Blender 4.2 及以上 | `blender.fluid-domain` | 含流体域和液体流入的 BLEND |

先 `lookup`。默认预演。宿主确认本检查点的覆盖之后，才用 `--write`。版本低于门槛、工程版本冲突或没有给出宿主程序时，保持 dcc-preset 的拒绝或受阻结果，不改文件。

预制完成不等于溪流已经做好。插件启用后仍要在关卡里放水体。海洋谱 HIP 和流体域 BLEND 都没有细波、白沫、岸线接触和树木贴地。那些属于后续装配；做不到时标明未完成，不用一张滚动贴图或一块白沫代替。
