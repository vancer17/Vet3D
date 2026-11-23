# Grease Pencil 二维动画契约

入口：[脚本](../scripts/hi3d-stroke-animate.py)；最小输入：[示例](../examples/hi3d-spec.json)。运行依赖：Python 3.10+、Blender 4.3+ Grease Pencil 新 API。

## 公共契约

JSON 字段以 `validate`/`edit` 的白名单为准，未知字段报错。外部路径通过显式参数或 JSON 输入传入。生成输出放全新目录，输入不覆盖。`hi3d-result.json` 提供 schemaVersion、status、fingerprint、artifacts（相对路径/bytes/sha256）与 checks。状态为 running/completed/failed/interrupted，未完成任务不复用为成功。

预算、运行记录及校验复用 [通用编辑任务](../../.dependency-run-tools/references/hi3d-edit-job.md)。成功缓存指纹包含声明素材和安装包的实现；改脚本或输入后必须另开输出。软件升级需新输出验收，不把旧缓存当新软件测试。

产物：hi3d-project.blend、frames、hi3d-review.json。只对实际实现的功能声明成功，未安装软件不伪造文件。

## 本能力边界

从明确二维笔划创建 Grease Pencil 图层、逐帧画稿和对象变换关键帧，保留可编辑 BLEND 并重开验证。

测试需在独立物化包运行，以免仓库相邻文件掩盖依赖缺失。纯参数测试不能替代软件运行；输出真实打开和视觉检查由调用者完成。

## 画稿、坐标与关键帧

width/height/fps/frames为正整数。viewWidth默认10，为正交相机逻辑宽度，笔划点采用 XY 平面逻辑单位，不是毫米工程尺寸。layers每项id唯一，color为0..1 RGBA；drawings包含唯一正整数frame与strokes，stroke.points至少2个二维点，radius默认0.03，cyclic默认false。

可选 keys 为 `{frame,x=0,y=0,rotation=0,scale=1}`，rotation单位度，scale>0；Blender 默认关键帧插值。可选 source 打开既有 BLEND，仅重建指定同名 Grease Pencil 对象，其他对象保留。render默认true，budgetSeconds默认180。

`validate` 负责纯结构检查；`execute` 调度；`hi3d-stroke-kernel.py` 使用 Blender 4.3+ 新版 drawing/strokes API 写笔划，插入对象变换关键帧，保存重开核对画稿帧、笔划/点数量、点坐标及关键帧位移，再输出透明PNG序列。依赖 Blender 和 Python侧 Pillow。没有完整手绘笔刷模拟、骨骼二维绑定或 AI 补帧。
