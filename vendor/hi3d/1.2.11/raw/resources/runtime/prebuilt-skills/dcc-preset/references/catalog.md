# 预制清单

机器可读清单在 `scripts/catalog.py`。本页只说明每条预制实际做什么、版本门槛和不能当成完成的事。插件名对照 Unreal Directive 对 UE 5.7 的插件索引，以及 Epic 5.7 Water System 文档中的启用步骤。本机没有安装虚幻、Houdini 或用来验收的 Blender 工程，因此没有打开编辑器核对 `.uplugin` 原文。

## unreal.water

- 最低版本：5.7.0。5.6 及更低直接拒绝，不改工程。
- 写入 `.uproject` 的 `Plugins`：`Water`、`Landmass`，`Enabled` 设为 true。
- `Water` 是水体系统本体，默认不启用。`Landmass` 是配套的地形编辑插件，同样默认不启用。编辑器启动时仍可能按其自身依赖再打开别的插件。
- 插件成熟度在索引中仍是 Experimental。启用只表示下次打开工程时加载这些插件。
- 不创建 Water Body，不生成网格，不重启编辑器。

## unreal.water-samples

在 `unreal.water` 的名单上增加 `WaterExtras`。索引说明它提供示例和测试地图，不直接用于发行。只有用户要示例内容时才选这条。

## unreal.water-simulation

在 `unreal.water` 的名单上增加 `WaterAdvanced` 和 `Buoyancy`。二者都是实验插件：前者是基于 Niagara Fluids 的水体模拟集合，后者给 Water 生成的水体提供浮力工具。启用后仍然没有浅水河流或浮动物体。

## houdini.ocean-spectrum

- 最低版本：20.5.0。调用时用 `--version` 声明本机 Houdini 版本。
- 操作是新建 HIP，并创建内置 SOP 类型 `oceanspectrum`。这不是要打开的插件。
- hython 若报告该类型不存在，命令失败，不留下声称已建好的 HIP。
- 不生成海洋谱缓存，不跑 FLIP。

## blender.fluid-domain

- 最低版本：4.2.0。调用时用 `--version` 声明本机 Blender 版本。
- Blender 的液体是修改器，不是可开关插件。操作新建 BLEND，加入名为 `FluidDomain` 的域和名为 `FluidInflow` 的液体流入。
- 不烘焙，不设置分辨率预算，不把它当成溪流场景。

## 版本来源

虚幻以 `.uproject` 的 `EngineAssociation` 为准。它是 `5.7` 这种版本号时，不再接受另一套 `--engine-version`。它是自定义引擎 GUID 时，必须另给已安装引擎的版本；结果里记为调用方声明，不是文件自证。Houdini 和 Blender 的预制文件本身没有引擎版本字段，版本只来自调用参数。
