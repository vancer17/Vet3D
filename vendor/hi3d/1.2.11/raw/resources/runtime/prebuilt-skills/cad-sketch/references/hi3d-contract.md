# FreeCAD 约束草图契约

入口：[脚本](../scripts/hi3d-cad-sketch.py)；最小输入：[示例](../examples/hi3d-spec.json)。运行依赖：Python 3.10+、FreeCAD 1.x 命令行运行时。

## 公共契约

JSON 字段以 `validate`/`edit` 的白名单为准，未知字段报错。外部路径通过显式参数或 JSON 输入传入。生成输出放全新目录，输入不覆盖。`hi3d-result.json` 提供 schemaVersion、status、fingerprint、artifacts（相对路径/bytes/sha256）与 checks。状态为 running/completed/failed/interrupted，未完成任务不复用为成功。

预算、运行记录及校验复用 [通用编辑任务](../../.dependency-run-tools/references/hi3d-edit-job.md)。成功缓存指纹包含声明素材和安装包的实现；改脚本或输入后必须另开输出。软件升级需新输出验收，不把旧缓存当新软件测试。

产物：hi3d-project.FCStd、hi3d-solid.step、hi3d-review.json。只对实际实现的功能声明成功，未安装软件不伪造文件。

## 本能力边界

创建全约束矩形/圆草图、拉伸和直孔口袋，修改命名尺寸，另存 FCStd 和 STEP 并回读体积；单位毫米。

测试需在独立物化包运行，以免仓库相邻文件掩盖依赖缺失。纯参数测试不能替代软件运行；输出真实打开和视觉检查由调用者完成。

## 毫米配方与可编辑工程

unit必须mm，body默认Body，可选source为已有FCStd。operations按顺序：rectangle(id,width,height,x/y/z=0)；circle(id,radius,x/y/z=0)；pad/pocket(id,sketch,length)；dimension(sketch,name,value)。ID采用字母开头的字母数字下划线。尺寸必须有限正数。命名尺寸为矩形 Width/Height、圆 Radius；当前只支持这些已命名草图约束修改，不是任意CAD特征编辑器。

矩形通过端点重合、水平/垂直、原点及两尺寸约束达到全约束；圆用中心原点和半径全约束。草图placement决定局部平面位置；直孔pocket需要调用者把草图放在实体顶面并给合适深度，不自动猜测面拓扑。pad/pocket 使用原生PartDesign特征，保存真实参数工程，非三角网格替代。

`validate` 纯检查；`execute` 通过可信固定内核启动FreeCAD CLI；`hi3d-freecad-kernel.py` 负责原生建模/尺寸修改、求解、正体积/有效性检查、FCStd关闭重开、STEP导出再导入及体积误差检查（max(1e-5 mm³,体积×1e-7)）。budgetSeconds默认120。结果记录volume_mm3/bbox_mm/solids/版本。可重用原生工程，不包含装配工作台、图纸/BOM、网格逆向或完整拓扑命名修复。CadQuery配方仍由原 [brep-build](../../.dependency-brep-build/REFERENCE.md) 独立维护（仅比较，不执行该入口），本能力只补原生FreeCAD草图工程。
