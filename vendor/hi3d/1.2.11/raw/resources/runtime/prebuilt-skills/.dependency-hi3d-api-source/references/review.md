# Blender 原始产物检查

使用任务提供的 Blender 可执行路径和本 skill 的 `scripts/blender_review.py`：

```bash
"$BLENDER" --background --factory-startup --python-exit-code 1 --python "$SKILL_DIR/scripts/blender_review.py" -- --input "$MODEL" --metrics "$RUN_DIR/metrics.json" --weld-check
```

输入支持 GLB、GLTF、OBJ、STL、FBX、BLEND；GLTF/OBJ 的外部资源必须随输入提供。BLEND 加载关闭脚本自动执行。每次检查使用新进程与新 metrics 路径，禁止将输出覆盖输入或既有报告。只有需要可视化副本时添加 `--display-blend 新路径.blend`；显示 OBJ 等模型的顶点色时同时加 `--vertex-colors`。

报告记录源 SHA-256、原始网格的对象/顶点/面/三角数、局部坐标范围、对象尺寸/变换、UV、材质、颜色属性、图片尺寸/打包情况、骨架和 Action 数。面积退化阈值为局部坐标面积 ≤ 1e-12；边统计基于三角化索引，包含内部对角边。

`--weld-check` 只按单对象内**完全相同坐标**计算虚拟合并后的边指标，不修改几何。它帮助区分 UV 拆点和几何开放边；不同对象不合并，不使用距离阈值，不证明无自交、体积闭合、厚度或可打印性。

`--vertex-colors` 在单独显示副本中按颜色属性建立材质并替换网格材质槽，保留原始几何和变换；这不是原材质的无损替代，也不是纹理烘焙。默认检查不会保存 Blender 文件。副本打包可用资源，但缺失贴图仍需报告，不能伪造。

基础检查不自动修复模型，不分析求值后修改器，不建立动画或机械配合。按任务另行查看贴图、形态、多视图一致性；有装配/打印要求时补足实际尺寸、间隙、厚度等验收。

数值检查复用 [mesh-audit 的三角数组核心](../../.dependency-mesh-audit/references/mesh-measure.md#三角索引数组)，通过 package.json 物化；本工具保留原始对象元数据、导入、文件哈希与独立显示副本。必须使用完整包，不能单独复制 blender_review.py。
