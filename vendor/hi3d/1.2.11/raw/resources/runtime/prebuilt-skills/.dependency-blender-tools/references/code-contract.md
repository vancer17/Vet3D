# 代码契约导航

完整 [模块与接口](../../.dependency-doc/blender-tools.md) 由 doc 唯一维护；运行依赖和边界见 [入口](../REFERENCE.md)。分发时 package-tools 随包提供所链接文档。

## 后台环境与 Python 依赖

显式定位本次 Blender 可执行文件与已物化的调用包；不使用作者机器路径，不在未保存的前台工程中运行会改场景的脚本。典型 CLI 帮助调用如下，实际参数仍以目标脚本为准：

```bash
"$BLENDER" --background --factory-startup --python-exit-code 1 --python "$SKILL_DIR/scripts/<entry>.py" -- --help
```

`--python-exit-code 1` 让脚本异常成为进程失败；线程数如 `-t 2` 属于调用方的资源选择，工具不统一业务配置。Blender 版本、布尔求解器和 glTF 导出器 API 由所用能力明确；换版本须验证实际建模、导出与重新导入，不能把某工作流的版本要求推广为所有工具的最低版本。

Blender 的 bpy、mathutils 和自带 NumPy 在其嵌入 Python 中使用；普通数组、STL/实体、截面或图片检查所需 SciPy、manifold3d、Pillow 等按调用包的 requirements 在独立 Python 环境准备。需要在 Blender 内加载额外二进制库时，先核对其 Python 版本、平台与 ABI；不能盲装独立 Python 的 wheel 或用该环境路径补依赖。

模块导入与脚本路径按 [本地执行边界](../../.dependency-run-tools/references/runtime.md#显式本地执行) 处理。渲染图片/动画、保存工程与几何验收分别执行；命令成功不代表业务检查通过。
