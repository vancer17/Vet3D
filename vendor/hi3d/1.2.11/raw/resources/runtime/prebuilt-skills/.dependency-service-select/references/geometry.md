# 几何原子如何连接

适用于已有网格、多视图条件与 [geometry-v4-geo2-pass1-cfg-distill-quant](mdf/geometry-v4-geo2-pass1-cfg-distill-quant.md) 的交接。图像/bridge 约定依据 Geo 项目固定提交 [63dbc6cb349eab768da4a5a5b1441d7f75a7f7fb](http://172.31.0.3:8099/zhaoshengchu/geo3.0_service/-/tree/63dbc6cb349eab768da4a5a5b1441d7f75a7f7fb) 的调用方实现；不要求执行未收录的上游生成服务。

## 参考图准备

参考图去背景得到 RGBA，再准备对齐的 RGB/RGBA；若已有灰图和合格 mask，可直接进行本地准备。已有网格和完整图像条件跳过不需要的上游步骤。

`prepared_rgb` 是白底图，`prepared_rgba` 提供同一投影的真实前景 mask；两者必须来自同一次准备。转灰可能改变轮廓，不能无检查地沿用转灰前的 alpha。灰图不是 mesh、depth 或 CCM，不能把它当几何数组。

独立 geometry-input 的 `geometry_inputs.py prepare` 按 alpha bbox 裁方、加边距、等比缩放并生成对齐 RGB/RGBA。默认 1536 和 1.15 来自该 Geo 调用方，均可显式修改；只做图像准备，无模型推理。它拒绝空/全不透明 mask，并保留软 alpha，不执行中控的空 mask 回退或二次乘 alpha。

```bash
"$PYTHON" "$GEOMETRY_DIR/scripts/geometry_inputs.py" prepare \
  --input "$RUN_DIR/foreground.png" --out "$RUN_DIR/prepared"
```

## 已有网格与多视图 → 量化 Geo2

`multiview-service` 的 `reference_images` 与标准 bridge 视图索引使用 front / right / back / left 字面方位；保留 None 参考槽，不自动交换左右。已有渲染包须包含下述条件与相机，不能从任意 GLB 或预览图凭空组装。

rendered_views_zip 按 view ID 配对：normal_v*.png、ccm_v*.png、View*_CCM.exr、可选 View*_GrayMask.png、camera_info.txt。用于 multiview 的 CCM 是 PNG 条件图；用于 Geo2 的 CCM 是原始浮点 EXR，不能用 8-bit 图改后缀替换。

几何 multiview 的控制图还需要该调用方的通道/背景预处理：normal 以半径 2 像素的高斯核分别模糊前景信号与 mask，相除得到前景内归一化卷积，再按 mask 置黑底；CCM 做 R′=R、G′=B、B′=255−G 通道变换（保留纯白哨兵、纯黑先透明），再按相同前景 mask 置黑底。优先使用渲染 mask（L>127，尺寸不同时最近邻），缺失时才按对应版本算法恢复前景；不要随意把 texture-render 的图当作已经转换好的 Geo bridge 图。生成视图必须与控制图和相机逐位对应。

Geo2 `prep_zip` 的每个 View{i} 至少有 GrayColor 图与 CCM/BCCM EXR，按需要保留 mask 和 camera_info；mesh 通过 `stage1_mesh_glb` 单独传，不放 ZIP。geometry-input 的 bridge CLI 按 `--gray` 出现顺序组包，只组装标准四视图，拒绝非四视图、数量不一致、重复 view 和错误文件格式；它不执行控制图变换、图像生成或额外 face-view 编排。

```bash
"$PYTHON" "$GEOMETRY_DIR/scripts/geometry_inputs.py" bridge \
  --rendered-views "$RUN_DIR/rendered_views.zip" \
  --gray "$RUN_DIR/front.png" --gray "$RUN_DIR/right.png" \
  --gray "$RUN_DIR/back.png" --gray "$RUN_DIR/left.png" \
  --out "$RUN_DIR/prep.zip"
```

## 效果判断

几何生成解决总体体积与被遮挡部分的推断；后阶段可能增加细节，也可能改变造型，不用阶段数判断质量。水密与减面需要前后对照细杆、武器、耳缘、负空间、薄片和连接关系。成功返回可能走过跳过/回退，必须看实际网格及服务实际阶段结果。中控水密失败后的原网格回退不等于水密已完成。

完整服务参数、已忽略字段和版本差异见 [量化 Geo2 服务契约](geometry-v4-contract.md)。Geo 调用方传入的 guidance/步数不在 Geo2 MDF 白名单；蒸馏实际值由服务 profile 强制，postprocess=True 也会被覆盖为 False。

跨阶段还需重新核对包围盒、轴向和单位：Geo2 输出可能重新归一化，不保证继承输入网格的数值尺寸；未给物理标定时不要把坐标直接解释为毫米。高密度原始 mesh 可能产生很大的传输、解析与显示开销，分开记录服务计算时间与客户端总等待；简化预览须标明是派生副本，不能代替原网格拓扑验收。

图像与 ZIP 组装前显式提供 `GEOMETRY_DIR` 为已物化的 [geometry-input](../../.dependency-geometry-input/REFERENCE.md) 目录；服务选择包不含第二份实现。
