# 完整资产载入

在独立后台 Blender 的物化 scripts 路径导入 `asset_scene.open_asset(path, *, frame=None)`。输入已有 `.blend` 或 `.glb` 路径，输出当前场景对象列表；不做单位转换、对象合并、测量、修复或文件写入。

BLEND 使用 open_mainfile 打开完整工程，保留场景、父级、动作与当前帧，禁止内嵌脚本自动执行且不加载窗口布局。它与 [scene_io.import_objects](scene-io.md) 的 BLEND 对象追加不同。GLB 复用该导入器的 reset=True 分支；原场景会被替换。`frame=None` 保留载入后的帧；显式整数帧则切换后更新依赖图，不接受布尔或小数帧。

缺文件、不支持的后缀或非法 frame 在替换场景前失败；实际导入错误传播，可能留下部分场景，不承诺回滚。只能在专用后台进程使用，不能对未保存的前台工程调用。所有源文件保持，API 不保存工程或报告。

完整模块说明及 [测试入口](../tests/test_asset_scene.py) 见 [工具文档](../../.dependency-doc/blender-tools.md#scriptsasset_scenepy)。测试在合成工程上验证全场景与帧恢复、GLB 动作、路径失败前场景保持及原文件哈希。
