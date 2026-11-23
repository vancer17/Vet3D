# Blender 后台脚本包装器 execute.py

## 资源身份与模型可见性

`execute.py` 是 Hi3D Agent 1.2.11 Windows x64 随包 `blender-tools` 的 Python 模块和命令行入口。模型选定可信包入口后，可在 `blender-tools/REFERENCE.md` 找到后台 Blender 的启动示例，再经宿主可用的本地命令入口执行。包装器没有独立 LLM Tool 注册或模型可见工具 `description`。下方文本是脚本传给 `argparse` 的本地 `--help` 描述。 [归档源码](../upstream/1.2.11/archived-p0/resources/runtime/prebuilt-skills/.dependency-blender-tools/scripts/execute.py) · [随包参考入口](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-blender-tools/REFERENCE.md>)

```text
Run an explicitly selected installed package script/module in background Blender.
```

## 参数、结果与副作用

| 参数或接口 | 行为 |
| --- | --- |
| `--script <file>` | 文件方式与 `--module` 二选一。解析目标路径，验证文件及父目录存在，并把解析后文件的父目录插到 `sys.path` 首位。 |
| `--module <name> --scripts <directory>` | 指定可导入的 Python 模块。CLI 要求同时给出存在的 `--scripts` 目录。将其绝对路径插到 `sys.path` 首位，以支持目标的包内相对导入。 |
| 目标参数 | 包装器使用第一个 `--` 后的命令参数，解析自身选项后将其余值传给目标。可以再次传 `--`，交给使用 Blender 参数约定的目标自行处理。 |
| `execute(*, script=None, module=None, scripts=None, arguments=())` | 将目标名或路径及其参数设为 `sys.argv`，用 `runpy.run_path` 或 `runpy.run_module` 以 `__main__` 运行目标。返回目标的全局命名空间字典。CLI 不序列化该字典，标准流和产物由目标决定。 |

CLI 参数不符时由 `argparse` 退出。脚本或目录缺失抛 `FileNotFoundError`，模块导入和目标代码异常向上传播。包装器不还原自己插入的导入路径及替换的参数列表。目标运行在同一个进程中，可按现有权限修改场景、写出文件或启动其他程序。

## 依赖、权限与前置 Hook

包装器只导入 Python 标准库。外部 Blender 由调用方启动。实际目标使用的 `bpy`、插件、本地文件和 Python 包由该目标的依赖决定。包装器使用调用方提供的显式路径与进程权限，未对目标实施沙箱、路径白名单或前置 Hook。由 `exec_command` 启动时，权限审批及前置 Hook 发生在外层命令调用。后台、工厂设置和 Python 错误退出码均由 Blender 启动参数决定。 [执行工具的权限与前置 Hook](../tools/exec-command.md#权限沙箱与前置-hook)

## 调用示例

**根据归档源码编写的 PowerShell 示例。** 令 `$blender` 指向已验证的 Blender 可执行文件，`$wrapper` 指向归档的 `execute.py`，`$trustedScript` 指向调用方准备的可信本地脚本。该目标按普通 Python 参数读取文件路径。

```powershell
& $blender --background --factory-startup --disable-autoexec --python-exit-code 1 `
    --python $wrapper -- --script $trustedScript 'inputs/sample.glb'
$LASTEXITCODE
```

## 核查依据与待验证项

源码映射为 `tools/blender-tools/scripts/execute.py`。已核对归档摘要，并用 Blender 4.5.16 LTS 验证归档副本的文件、模块模式均能转发参数。独立脚本导入 `bpy` 后仍能收到额外的 `--` 分隔符及标记参数，目标故意抛出异常时退出码为 `1`。上游安装副本曾作为隔离 Blender 烘焙测试的启动入口。实际目标的依赖、产物和宿主权限仍需按对应环境验证。 [本地执行证据](../infrastructure/bundled-assets-and-script-tools.md#按安装包复核) · [资源选择与摘要](../upstream/1.2.11/extraction/priority.json)
