# 显式编辑任务

[scripts/hi3d-edit-job.py](../scripts/hi3d-edit-job.py) 提供参数检查、环境版本探测和不可覆盖的本地编辑任务。文件/进程副作用与领域计算分离。

- `number(value,name,minimum=0,strict=False)`：有限数检查，拒绝 bool。
- `local_file(value,base)`：仅本地存在文件，返回真实路径；不读取 URL。
- `probe(executable,args=("--version",),timeout=10)`：显式可执行程序版本，不扫描账户配置、不安装软件；available 不代表许可/所有操作可用。
- `digest(path)`：流式 SHA256；`dump(path,data)`：同目录临时写入后替换，仅适用于任务自有文件。
- `EditJob(output,spec,inputs,package_root,budget=120)`：校验输出不与输入/包重叠；新任务先写预算及心跳；已有任务仅允许完成状态且指纹与全部产物哈希匹配时复用。未完成任务必须使用新目录。
- `run(argv,phase)`：复用 process_run.run_budgeted，不执行 shell；每个直接子进程预算，KeyboardInterrupt/超时停止直接子进程。继承进程环境但不枚举或记录。POSIX 下启用进程组，超时/中断停止同组子孙进程；显式脱离会话的守护进程不在保证范围。Windows 保持直接子进程清理，需要平台另验。主线程上下文临时接管 SIGTERM 为取消，并在退出恢复原处理器。
- `finish(files,checks)`：核对源哈希、输出在根内且非空，写产物清单和 completed。领域解析/解码/尺寸验证必须先完成；不能用这个函数代替业务验收。
- 上下文管理器把未捕获异常记录为 failed/interrupted，不写成功。中断后不自动重试；源文件和旧完成目录是回退依据，不操纵前台编辑器撤销历史。

新输出目录避免硬链接覆盖；路径预检复用 path_safety，不作为防恶意并发文件系统变更的沙箱。代码指纹纳入包内 Python/JS/JSON 源；不扫描 node_modules，Node 依赖用调用者显式 lockfile 固定。字体、插件、设备及外部软件版本变化须新建任务重新验收。日志和预算属任务记录，不写回源仓库。

CLI：`python scripts/hi3d-edit-job.py --probe /explicit/software --version-arg=--version`，输出版本探测JSON；不会认证或安装。EditJob上下文仅支持主线程（SIGTERM处理）；服务多线程调用须放在独立工作进程。
