# 显式依赖与独立调用

仓库里的目录是唯一维护源。`package.json` 的 `files` 把原子能力中的 canonical 文件映射到调用方需要的包内位置；这些位置可能在源码目录中不存在。禁止直接执行未物化的工作流源码，或临时通过相邻路径导入来绕过依赖。

先指定本次实际仓库与新输出目录（输出必须在仓库外），再执行：

```bash
python3 "$REPO/tools/package-tools/scripts/bundle.py" --repo "$REPO" --entry surface-fit --output "$BUNDLE"
# 所有入口一起分发时使用 --all，不能与 --entry 同用。
```

`$BUNDLE/skills/surface-fit` 是已物化的入口；使用它的 `SKILL.md`、脚本和随包资源。工作流在 `$BUNDLE/workflows/<name>`，工具在 `$BUNDLE/tools/<name>`。完整分发目录还包含被引用的能力包和 doc；保留它们的相对布局，显式给 AI 入口的实际路径并读取后调用。文档引用带入的包不等于必执行阶段，真正的独立调用依赖由 `requires` 和当前任务分支决定。

本文中的“独立”指完整分发目录不再依赖源仓库。部分入口的文档链接仍指向分发目录中的其他包或 doc，不能只取一个子目录便宣称资料完整。宿主自动发现需按其实际安装机制处理；若移动入口或改变布局，须同时处理并验证资源、文档和依赖路径，再检查 `$<name>` 的发现与显式调用。文件存在、打包成功或脚本可执行均不能证明宿主自动发现成功。

物化副本是可丢弃的安装产物；所有修改返回 manifest 所指的 canonical 源，不能分别编辑多份安装副本再回迁。网络客户端只通过独立工具调用，不能把客户端物化到业务包。运行时外部依赖（Blender、Python 库、ffmpeg、MDF 服务）仍由各入口声明和检查，本工具不安装软件或启动业务任务。

`requires` 列出必须能独立调用的入口，按依赖顺序提供；`files` 是固定源文件到目标相对路径的映射。仅引用另一工作流作为可选扩展不使其成为必需阶段。已有输入满足当前阶段时跳过上游服务。工具拒绝缺失依赖、环、路径穿越、符号链接与覆盖本地文件；仅写全新的外部输出，失败清理本次临时目录。

## Desktop profile

CLI 和交互宿主统一直接写入最终目录，不使用目录 rename；宿主通过 JS API 的 `allowExisting: true` 显式复用已有安装目录；宿主负责冲突保留、安装中断修复及成功戳记。参数和失败边界见 [直接安装契约](../../.dependency-doc/package-tools.md#desktop-平面分发与子模块)。以下 CLI 仍只接受全新输出。

Node 22+ 执行 scripts/host-bundle.mjs --repo ROOT --profile sparc3d --output NEW_DIR。输出必须在源仓库外且不存在。profiles.<name>.files/remove 是 package.json 内显式模式覆盖；archiveBase=true 将未选协议实现归入隐藏参考目录，主动工具只保留当前模式；独立运行依赖仍由 files/requires 管理。分发根须整体安装，隐藏依赖的 REFERENCE.md 不作为宿主 SKILL.md 自动发现；实际展示入口与安装名由 tools/package-tools/profiles/sparc3d.json 定义。详细校验和布局见 [打包实现](../../.dependency-doc/package-tools.md#desktop-平面分发与子模块)。
