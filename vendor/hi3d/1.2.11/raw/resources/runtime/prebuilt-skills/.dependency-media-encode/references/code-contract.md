# 实现与资源契约

输入、输出和边界以 [入口](../REFERENCE.md) 为准。物化文件不另维护实现；原文件名到唯一源的映射见 [package.json](../package.json)。

| 维护文件 | 函数/类入口 |
| --- | --- |
| [scripts/encode_review.py](../scripts/encode_review.py) | `build_parser`, `execute`, `main` |

参数默认值和返回字段见对应函数签名；argparse 入口可读 `--help`；位置参数适配脚本按入口中列出的格式调用。执行依赖按所选接口加载，不能在普通 Python 中导入含 `bpy` 的模块。运行产物写包外路径。

[encode_sequence.py](../scripts/encode_sequence.py)：`sequence_names`、`encoder_command`、`encode_sequence`、`main`，输入与失败策略见 [序列契约](sequence.md)。

图片画布、标签与缩放复用 [image-sheet](../../.dependency-image-sheet/references/contract.md)，本入口保留来源选择、字号、采样器、标签格式及业务验收/归档职责。
