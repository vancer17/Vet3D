# 架构与服务契约

## 从已有算法到唯一入口

先读算法的实际入口、安装脚本和默认权重解析；README 与代码冲突时以可运行实现核对。
找出隐式 cwd、相对配置目录、联网下载、临时端口和会在 import 时访问 CUDA 的模块。
外部源码固定提交并保持干净，优先在适配层改路径/加载函数，不改算法子模块。

分工如下，已有等价文件保留原名：

| 层 | 输入输出 | 资源职责 |
| --- | --- | --- |
| 算法 Session | 普通参数、本地路径、内容验证元数据 | 构造时加载；推理复用；close 释放自有模型/子进程 |
| API | Session + 路径 → 验证后的正式产物 | 临时导出、回读、原子发布；不感知 MDF3 |
| AlgoWorker | BinaryFile 字典 → 结构化结果 | init 创建 Session；process 暂存/转发；shutdown 关闭 |
| CLI / 联调 | 用户参数 → API / 官方 SDK | 生命周期、错误传播、保存产物和验收 |

随包 [algorithm.py](../assets/service/algorithm.py) 的 CPU 文本示例可执行，但不代表任意
模型已经适配。真实 Session 应先检查完整权重集合和设备，再构建 `.eval()` 模型；
构造中失败也要回收已启动的自有子进程/临时目录，不能等待未成功初始化的 worker 去 shutdown。
Torch 推理使用 `torch.inference_mode()`。如果 API 原本每次启动新进程加载模型，
保留该离线入口，同时增加可注入的长期 Session，不能让 MDF3 每个请求走原冷启动路径。

GPU 在容器内重新编号：宿主选择某一设备后，它通常是容器的 `cuda:0`。先用单 worker
验证显存峰值。多 worker 需明确映射、模型实例数、RPC 端口与算法并发安全；不要仅把
worker 数改成 GPU 数。MDF3 3.2.1 WorkerPool 用 spawn，因此主模块顶层不构建模型，
类应位于可导入模块；CPU 构建时也不要 import 会查询 GPU 型号的上游 demo。

## 路径与文件

请求默认字段为 `input_file` 和 `options`，返回 `output_file`。接入既有业务时可改名，
但必须同步 worker、CLI、调用方、测试和说明。二进制契约要求：

- `BinaryFile.field_name` 等于所属字典键，`file_name` 是安全 basename 且扩展名正确，
  `content` 是非空 bytes。拒绝路径穿越、NUL 和反斜杠目录，不相信声明的 file_size。
- 按实际字节数设上限；这只是算法入口限制，不是网络接收层的内存防护。大包会经过
  pickle/TCP/进程队列多次复制，应按可用 RAM 约束或在另行授权后使用对象存储引用。
- 暂存到每请求 `TemporaryDirectory`，使用自己生成的本地文件名；完整读取返回 bytes
  后再清理目录。可选 BinaryFile 省略时不传 `None` 冒充文件。
- 仅明确有共享挂载时接受调用方路径，并记录所有权；绝不删除调用方文件或共享权重。
  多文件 OBJ/纹理等依赖不能靠一个 BinaryFile 自动补齐，改用自包含格式或明确附件契约。
- 数值参数严格检查类型、范围、NaN/无穷；`bool("false")` 与 `isinstance(True, int)`
  不能用于服务入参校验。不要开放请求级任意 checkpoint 路径或任意文件写入位置。

成功必须是 `success=True, status="success"` 和有效 BinaryFile；失败必须是
`success=False, status="failed", error_type, error_message`，不能携带旧输出。
traceback 留在授权服务日志中，不把原始输入、配置或凭据塞入错误响应。
图片要解码，数组要核对键/shape/dtype/数值，网格要核对几何/拓扑/骨骼/权重等目标属性。
先在目标文件系统的临时文件导出，回读通过后原子替换；失败时保留此前有效产物，
不能先删除正式文件再尝试导出。缓存命中必须验证内容与输入/参数指纹，不只看文件存在。

## 权重与离线加载

集中管理模型目录、必需文件列表和缺失检查；不在 API/worker/CLI 分别写三套路径。
下载使用受信任发布源的固定 revision、预期大小和可得的校验和；`.partial` 文件只有
校验成功后才发布。记录模型清单，完整目录作为一组使用，不逐文件混用两套缓存。
模型缓存工具是可选外部依赖，不是 MDF3 必需组件；已下载的模型只读挂载即可。

HF 派生模型可能只需要架构 config，参数已在主 checkpoint；以实际加载路径确认，
不要机械下载整套语言模型。把 checkpoint 内的相对 VAE/编码器路径转为当前挂载目录的
绝对路径。下载完成后才启用 `HF_HUB_OFFLINE` 等离线开关，并用断网 CLI 验证没有隐式下载。
缺模型应在 init 清晰失败，不能悄悄联网补齐、使用随机权重或回退到另一套模型。

## 内部 RPC 与资源回收

host 网络下，上游 `0.0.0.0` 的 Blender/图像处理 RPC 会直接暴露到宿主网络；尤其
pickle RPC 必须改为回环监听。优先用上游参数，缺参数时用薄启动 wrapper，不复制服务端。
RPC 固定端口需启动前探测；文件锁只在同一文件系统命名空间生效，容器各自 `/tmp`
的锁不能解决跨容器端口冲突。当前无多端口支持时明确限制单实例。

创建子进程后轮询 `/ping` 或等价健康接口，设启动 deadline，检查提前退出。
关闭按 terminate → 有限 wait → kill → wait 回收。`atexit`/`shutdown` 不保证在 SIGKILL
执行：Linux 子进程可在 exec 后设置 `prctl(PR_SET_PDEATHSIG, SIGTERM)` 并检查父 PID
变化竞态；整个容器退出可依靠 cgroup 清理。不要在多线程父进程里用不安全的 preexec_fn。
离线进程树可用独立 process group，在超时/finally 清理；不要依赖杀一个 PID 回收全部后代。

不同请求间重置必要随机种子和临时状态，但不重建模型。若内部服务死亡或 CUDA 上下文
污染，记录错误并通过框架退出/容器重启恢复；不能长期返回失败却继续宣称 ready。
OOM 是否回收缓存后继续或重启，取决于算法是否可恢复，不泛化为所有 OOM 都杀服务。
禁止无差别清理整个 `/tmp`，只回收当前请求/会话拥有的目录。
