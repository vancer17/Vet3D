---
name: source-prepare
description: "将明确选定的来源模型规范为指定高度、坐标与可回溯 NPZ/Blender 输入，保持 UV 和材质来源。"
---

# 模型来源规范化

将明确选定的来源模型规范为指定高度、坐标与可回溯 NPZ/Blender 输入，保持 UV 和材质来源。

## 输入与完成结果

- 输入：显式 GLB/GLTF/OBJ/PLY/BLEND 源文件、毫米目标高度、输出目录；位置参数依次为 source.glb、output_dir、height_mm。
- 输出：source.blend、毫米制 NPZ、来源哈希与指标；按配置可输出来源多视角检查。

## 调用与边界

Blender、NumPy。现有入口会重置场景、合并导入的全部 mesh、施加世界变换、居中落地并有限焊接；先保证文件只含目标对象，不能对多主体场景静默使用。只规范输入，不生成产品。

源码入口与安装依赖见 [package.json](package.json)；调用脚本前按 [独立打包约定](../.dependency-package-tools/references/usage.md) 准备完整包。函数和资源导航见 [代码契约](references/code-contract.md)。

调用格式：`blender --background --factory-startup --python-exit-code 1 --python "$SKILL_DIR/scripts/prepare_source.py" -- "$SOURCE_GLB" "$OUTPUT_DIR" "$HEIGHT_MM"`。此位置参数入口不提供 argparse 帮助；源规范化的成功提前结束通过 StageFinished(0) 传递，Python 直接组合时捕获该状态或调用 main。

<!-- managed-by: sparc3d-runtime -->
