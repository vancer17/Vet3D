# SVG 矢量编辑契约

入口：[脚本](../scripts/hi3d-svg-edit.py)；最小输入：[示例](../examples/hi3d-spec.json)。运行依赖：Python 3.10+、Pillow、Inkscape 1.2+。

## 公共契约

JSON 字段以 `validate`/`edit` 的白名单为准，未知字段报错。外部路径通过显式参数或 JSON 输入传入。生成输出放全新目录，输入不覆盖。`hi3d-result.json` 提供 schemaVersion、status、fingerprint、artifacts（相对路径/bytes/sha256）与 checks。状态为 running/completed/failed/interrupted，未完成任务不复用为成功。

预算、运行记录及校验复用 [通用编辑任务](../../.dependency-run-tools/references/hi3d-edit-job.md)。成功缓存指纹包含声明素材和安装包的实现；改脚本或输入后必须另开输出。软件升级需新输出验收，不把旧缓存当新软件测试。

产物：hi3d-artwork.svg、PNG/PDF。只对实际实现的功能声明成功，未安装软件不伪造文件。

## 本能力边界

通过白名单操作编辑 SVG 节点、文字、样式、变换和路径布尔，并用 Inkscape 导出 PNG/PDF；保护原输入。

测试需在独立物化包运行，以免仓库相邻文件掩盖依赖缺失。纯参数测试不能替代软件运行；输出真实打开和视觉检查由调用者完成。

## 文档操作与导出

新建需正数 width/height；编辑需 source。operations 中 op 为 add/set/remove/duplicate：add 指定 id/tag/attrs，可选 parent/text；set 指定 id/attrs/text；remove 指定id；duplicate仅支持叶节点，需newId。支持安全 SVG 子集：基础形状、path、g、text/tspan、渐变、clipPath。属性以脚本 ATTRS 为准，禁止脚本、事件处理、外部URL、DTD/实体和非局部url引用；不是通用 SVG 清洗服务。已有 Inkscape 文档仅剥离非渲染 namedview 及编辑器命名空间属性；其他不支持内容明确拒绝。

boolean 为顺序 `{op:union/difference/intersection,ids:[...]}`，动作名与id经过白名单，调用Inkscape路径操作，保留首个对象的颜色/描边。实际顺序依照 Inkscape 选择与层级语义；复杂差集先用简单夹具验证。formats 为 png/pdf 子集，默认两者；budgetSeconds默认120。

`attributes/identifier/inspect/edit` 为输入与XML操作核心；`strip_editor_metadata` 仅删除明确非渲染编辑器字段；`execute` 另存SVG，调用CLI并解析SVG、解码PNG、将PDF重新导入导出PNG。成果须查看确认路径和文字，字体替换不能由PNG解码证明。没有将任意复杂插画布局自动理解为编辑配方。
