# 实现与资源契约

输入、输出和边界以 [入口](../REFERENCE.md) 为准。物化文件不另维护实现；原文件名到唯一源的映射见 [package.json](../package.json)。

| 维护文件 | 函数/类入口 |
| --- | --- |
| [scripts/template_defaults.py](../scripts/template_defaults.py) | `resolve_template_config` |

参数默认值和返回字段见对应函数签名；argparse 入口可读 `--help`；位置参数适配脚本按入口中列出的格式调用。执行依赖按所选接口加载，不能在普通 Python 中导入含 `bpy` 的模块。运行产物写包外路径。

固定耳部映射：[`sapiens2_ear_mapping.json`](../assets/taro/sapiens2_ear_mapping.json) 保存模板三角形/重心权重与零基顶点索引；同目录 manifest 记录模板与映射版本。运行时读取，不执行模板检测。

`assets/taro` 的文本资源按 manifest 逐字节校验，仓库 `.gitattributes` 固定其 TXT、JSON、OBJ、MTL 为 LF；Windows 启用 `core.autocrlf` 时也必须保留这些字节。物化与宿主打包直接复制资源，不修改 manifest 来适配换行符。验收时在启用 CRLF 自动转换的独立 checkout 中生成分发包，再验证 manifest 的全部文件哈希。
