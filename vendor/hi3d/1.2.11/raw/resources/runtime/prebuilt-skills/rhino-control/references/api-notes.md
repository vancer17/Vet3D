# 按接口查询的建模注意事项

与接口契约一起按本版索引读取命中段；同组接口共用的几何前提保留在一段。共用语法、文档状态与失败处理见 [Python 编写清单](python.md#一次提交的编写清单)。这些经验不代替目标版本的签名、返回值和最低 SR。

## rs.AddPoint / rs.AddLine / rs.AddPolyline / rs.AddCircle / rs.AddArc / rs.AddInterpCurve

返回单 GUID；直线两点不重合，闭合多段线重复首点且至少 3 条非共线有效边；正半径、非退化角度；本夹具插值 degree=3、knotstyle=0 且至少 4 点，区分插值点与控制点；其它 knotstyle 另查次数/周期/切线限制

## rs.AddPlanarSrf / rs.AddLoftSrf / rs.AddSweep1

返回 GUID 列表；平面边界闭合且共面；放样按空间顺序，校准曲线方向/闭合接缝；单轨扫掠的截面按 rail 顺序放置，本夹具截面在起点与 rail 相交

## rs.AddBox / rs.AddSphere / rs.AddCylinder

返回单 GUID；Box 的 8 点须按底面周向再对应顶面排序；Sphere 正半径；Cylinder 用平面+数值高度，或基点+高度端点，不能混用；封口明确 cap=True

## rs.ExtrudeCurveStraight / rs.CapPlanarHoles

拉伸返回 GUID，起终点决定方向且不重合；封口返回 bool、修改原对象，不返回新 GUID；只封平面开口，之后检查闭合

## rs.AddRevSrf

曲线 GUID + 两点定义的非退化轴；默认 0–360 度，返回单 GUID；完整回转不代表自动封闭成实体

## rs.BooleanUnion / rs.BooleanDifference / rs.BooleanIntersection

参数为对应对象列表；返回新 GUID 列表且可多件，不能固定取首件；delete_input=True 会删除输入。实体任务先核验有效闭合、法向、容差及相交关系；相切/共面/缝隙不能套用夹具的单体积假设

## rs.CopyObject / rs.MoveObject / rs.RotateObject / rs.ScaleObject

返回对象 GUID；明确 copy 标志、中心、轴、比例及变换顺序；移动是向量，缩放是比例而非最终尺寸

## rs.AddMesh / rs.MeshVolume

AddMesh 返回 GUID；面为 0 起点的顶点索引，三角形 3 个、四边形 4 个，面朝向一致；测体积先验闭合。MeshVolume 返回 (网格数, 总体积, 误差)，体积取 [1]

## rs.SurfaceArea / rs.SurfaceVolume / rs.SurfaceVolumeCentroid

返回 (值, 误差)，取 [0]；实体体积/重心前检查 IsObjectSolid，不用有效但开放的曲面冒充实体

## rs.AllObjects

AllObjects 默认排除灯光、控制点、参考对象，不能单靠它保护空模型

## rs.Command / rs.LastCreatedObjects

只有 API 缺失才退到 `rs.Command`：每次只跑一个命令；英文命令/选项前加 `_`、抑制对话框用 `-`、带空格路径加引号。不要把按钮宏的 `! ` 放入 `rs.Command`；不要依赖当前预选或未完成的提示。单次命令返回 True 后仍验收几何；需要 LastCreatedObjects 时紧接该命令读取。跨平台不用 Windows COM/VBScript。
