# 试片契约

## 几何与来源

[coupon_crop.py](../scripts/coupon_crop.py) 的 `crop_solid(solid,assembly_matrix,bounds,with_transform=False)`：Manifold 正实体、proper rigid 4×4 矩阵及六个 mm bounds → ROI 相交、逆回打印轴、按 min XYZ 平移后的单连通实体。with_transform 同时返回 coupon-to-assembly 矩阵；空/断开 ROI 失败。原始 mesh/solid 不修改，无隐式修复、缩放或间隙添加。

`crop_pair(paths,matrices,bounds,output,clearance_mm,definition)` 只接收两侧文件，使用 print-export 的精确焊接 STL 验收；先完成几何和契约校验再创建新目录，逐件导出后回读，最终写 coupon-pair.json。失败可留下未完成的输出目录，不报告成功、不自动覆盖重跑。main 仅解析下面的 JSON，文件路径相对 spec：

```json
{"files":{"male":"male.stl","female":"female.stl"},
 "matrices":{"male":[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]],"female":[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]},
 "bounds_mm":[-5,-5,0,5,5,10],"clearance_mm":0.2,"definition":"single-side radial clearance"}
```

以上仅是格式例，尺寸和 clearance 必须由本任务给定。报告含实际源与输出 SHA-256、共同 assembly ROI、各件返回装配矩阵、打印朝向、公差定义和 physical_test=not_run。

[blender_coupon.py](../scripts/blender_coupon.py) 的 `crop_object(source,cutter,name,intersect,prepare)` 复制双方且保留世界变换，取 basis 形态，调用显式 intersect(copy,roi) 与 prepare(copy)；原对象和原 cutter 不动，失败删除创建的临时对象，成功返回由调用者管理的 crop。intersect 可消费临时 ROI。该适配不自行选择 MANIFOLD/EXACT 或焊接尺度，也不声称连通验收完成；frame-design 保留自身 MANIFOLD、1e-9m 数值清理与 float32 STL profile。

## 系列与配对记录

[coupon_records.py](../scripts/coupon_records.py) 的 `clearance_series(values,definition)` 返回稳定 1-based index、clearance_mm、definition，拒绝空、重复、布尔、负数和非有限值。`source_record(path)` 只读显式来源，哈希复用 run-tools；`pair_record(id,files,clearance_mm,definition,orientation,source)` 要求至少两个独立文件和来源/朝向，支持额外 support 角色，生成待实测记录；不验证任意 caller 提供的 files 内容，导出者负责实际回读。

ball-joint 保留完整 BallSpec、back-down 球/窝/后支撑、5mm 摆盘距离、3MF 原位组织及 STL 回读；仅共用系列/配对记录。frame-design 保留真实旋锁/释放/支座裁切和 .15/.25/.35 坐标偏移燕尾，新增 coupon-pairs.json，原 manifest 不改。lamp-design 保留 20mm pin、.2/.3/.4/.5 径向系列并新增 fit-pairs.json；.8/1.2/1.6/2.0mm 透光片保持独立，不归机械 fit。print-kit 保留单件 crop API 及原来源报告，计算核心改用本能力。

验收：裁切前后 source 不变、装配重建一致、每侧单连通/正体积；空/断开 ROI/非刚体拒绝；Blender profile 成功与异常清理；系列拒绝无效值并保留机构自身定义。未切片或未试印时不可提升物理状态。
