---
name: dcc-preset
description: "按软件和版本检索 Blender、Houdini、UE 的水体类内置预制，并执行这一条操作。UE 5.7 及以上只改 .uproject 的插件启用项；Houdini 新建海洋谱 HIP；Blender 新建流体域。不搭建场景，不烘焙模拟。"
---

# DCC 预制检索与操作

按目标软件、版本和主题找出一条内置预制，并只执行这条预制写明的操作。当前主题是水体。场景、网页和离线包仍由相应工作流编排；本入口不制作溪流。

## 输入与完成结果

- 输入：`unreal`、`houdini` 或 `blender`，可选主题 `water`、版本，以及要执行的预制 id。虚幻写入时还要已有 `.uproject`。Houdini 要 hython，Blender 要可执行文件。
- 输出：检索结果，或一次操作的 `result.json`。虚幻操作改插件启用项。Houdini 另存 HIP。Blender 另存 BLEND。

完成只表示清单命中，且所请求的文件改动已经按结果状态发生。插件已启用、HIP 已保存或 BLEND 已保存，都不能代表水面、浮力或流体已经可用。

## 调用

先按 [打包约定](../.dependency-package-tools/references/usage.md) 物化 [package.json](package.json)。读取 [预制清单](references/catalog.md) 和 [阶段及产物](pcg/architecture.yaml)。

```bash
"$PYTHON" "$SKILL_DIR/scripts/dcc_preset.py" lookup --app unreal --topic water --version 5.7
"$PYTHON" "$SKILL_DIR/scripts/dcc_preset.py" apply --preset unreal.water --project "$PROJECT.uproject"
"$PYTHON" "$SKILL_DIR/scripts/dcc_preset.py" apply --preset unreal.water --project "$PROJECT.uproject" --write
```

默认不写文件。确认宿主允许覆盖工程后才加 `--write`。Houdini 与 Blender 还要 `--version` 和 `--output`；真正创建文件时再给 `--hython` 或 `--blender`。

```bash
"$PYTHON" "$SKILL_DIR/scripts/dcc_preset.py" --output "$RUN_DIR" apply --preset houdini.ocean-spectrum --version 20.5 --hython "$HYTHON" --write
"$PYTHON" "$SKILL_DIR/scripts/dcc_preset.py" --output "$RUN_DIR" apply --preset blender.fluid-domain --version 4.2 --blender "$BLENDER" --write
```

退出码 0 表示检索成功、预演成功或写入成功。退出码 2 表示版本、工程或未知预制被拒绝。退出码 3 表示 Houdini 或 Blender 的程序路径没有给出。命令失败不创建替代几何。

## 边界

三条软件的水体入口形态不同，清单不把它们写成同一种插件：

- UE 5.7 及以上改的是内置插件启用项。`unreal.water` 写 `Water` 与 `Landmass`。示例和浅水模拟分别使用 `unreal.water-samples`、`unreal.water-simulation`。低于 5.7 不改工程。
- Houdini 20.5 及以上创建内置 `oceanspectrum` SOP。没有对应的插件开关。
- Blender 4.2 及以上创建内置流体域。液体修改器随软件提供，不存在要先打开的水体插件。

不启动虚幻编辑器，不烘焙，不跑 FLIP，也不把这次文件改动记成场景验收。函数边界见 [代码契约](references/code-contract.md)。

<!-- managed-by: sparc3d-runtime -->
