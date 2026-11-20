# 实现与资源契约

输入、输出和边界以 [入口](../REFERENCE.md) 为准。字段与缺口规则以 [简报契约](contract.md) 为准。物化文件不另维护实现；原文件名到唯一源的映射见 [package.json](../package.json)。

| 维护文件 | 函数/类入口 |
| --- | --- |
| [scripts/replace_brief.py](../scripts/replace_brief.py) | `image_size`, `validate_brief`, `request_gaps`, `annotate_image`, `crop_targets`, `build_output`, `main` |

参数默认值和返回字段见对应函数签名；argparse 入口可读 `--help`。需要 Pillow 解码 PNG/JPEG/WebP。不导入 `bpy`，无网络。运行产物写包外路径。
