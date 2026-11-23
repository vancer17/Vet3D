# 来源与边界

- `brush.py`、`surface.py`、Sapiens2 模板映射/投影及先验几何检查最初来自 `metahuman-fit` 的本地实现；当前分别由 [surface-fit](../../.dependency-surface-fit/REFERENCE.md)、[landmark-project](../../.dependency-landmark-project/REFERENCE.md)、[head-template](../../.dependency-head-template/REFERENCE.md) 和 [mesh-audit](../../.dependency-mesh-audit/REFERENCE.md) 维护。按 [依赖清单](../package.json) 物化到本工作流所需位置，不另存业务版本，也不隐式导入相邻目录。`metahuman-fit` 保留光头、全模板与贴图的端到端编排；本工作流只对源高模的可见皮肤拟合先验。
- `fit_visible_face.py`、源相机与语义 target 适配器来自带发人头实验中的可见面部注册；`denoise_semantic_face.py` 提取自相同实验的受保护区域 Taubin 平滑。去除作者路径、固定网格名称依赖，增加独立函数、输入检查和来源约束。
- 鼻部算子由本地 `head-geometry-repair` 提取：保留真实 donor 鼻部几何，仅在鼻部边缘以单值高度场解 Poisson 过渡，不把整个鼻子拟合成高度图。当前由独立 [nose-repair](../../.dependency-nose-repair/REFERENCE.md) 维护。本流程不编排眼球修复，也未迁入眼球自动脚本或眼睑移植算法。
- [Taro 资源清单](../assets/taro/manifest.json) 记录模板来源与固定版本。模型数据来源为 Epic MetaHuman DNA Calibration 的 Taro，保留 [上游许可](../assets/taro/UPSTREAM_LICENSE.txt)。几何、区域及关键点映射随包提供；不包括贴图、DNA 运行时和绑定，不重新许可为无限制开源内容。

局部 fitting、语义去噪和鼻部移植有独立案例基础；当前按“图像处理→几何生成→几何后处理→纹理生成→几何拆分”组织，后处理中的修鼻与去噪分别可选。完整组合仍需业务回归，既有算子案例不代表全部可选组合已验收。打包验证不调用真实服务。Sapiens2 检测、隐藏面的图像生成、鼻部 ROI 和多视图一致性需要观察结果；模板平均距离与 Laplacian 能量不是人物辨识度评分。

鼻部适配器当前限定单 mesh、GLB Y-up/+Z-front 正面头部、Taro 顶点顺序及局部鼻子可形成一条外边界的情况。鼻孔及鼻翼由 donor 三维表面保留，过渡带要求在正面图表中单值；多层投影、非闭合切口或新交叉必须停止并调整 ROI，不能静默扩大裁切。

面部注册适配器现由 [face-fit](../../.dependency-face-fit/REFERENCE.md) 唯一维护，本 workflow 通过 package.json 物化兼容脚本；上游同源渲染由 portrait-analysis 维护。
