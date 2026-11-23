<!-- 文件信息：工作区持久注册与不可信执行边界的架构决策记录。
作用：保存采用理由、候选限制和未采用方案；字段及交接契约由 L1-01 实施卡维护。 -->

# ADR 0006：分离工作区持久注册与不可信代码执行

| 字段 | 内容 |
| --- | --- |
| 状态 | 已接受设计；产品未实施，当前契约和验证状态见 [L1-01](../implementation/work-items/L1-01.md)。 |
| 日期 | 2026-11-23。 |
| 范围 | L1-01 最小注册存储、身份交接和未来执行消费者必须满足的边界；保留 L0 成果。 |

## 背景

Vet3D 是面向 BFF 的后端，正常业务链由系统在预算内执行、检查和修订。后续多个 Agent 可能并行使用 Blender；目录、UUID、cwd 和虚拟环境只能组织数据，不能限制任意代码的进程、文件、网络和设备权限。逐命令人工确认不适合作为正常服务链的隔离机制。

L0 已把身份、内容、执行、验收和发布分开，未实现真实文件访问或通用执行器。L1-01 需要解决可恢复的目录创建和持久登记，但不应因此承接 L1-04 的全部持久化、L2 执行平台或多租户权限系统。

Hi3D 有值得借鉴的分层控制：[exec_command](../../hi3d/tools/exec-command.md#权限沙箱与前置-hook)区分有效权限、工作目录、Hook 和审批；[Runtime 分派](../../hi3d/tools/hi3d-api.md)核对调用上下文、工作区、参数与受管资源，按作业路径串行，代理侧消费凭证。服务端可以沿用这些可信入口机制，并由任务授权自动决策。

其证据也有限制：积分 Hook 不等于 OS 隔离，动态工具逐调用 Hook 覆盖并未全部实测；[Blender 包装器](../../hi3d/resources/blender-execute.md)明确面向可信包代码，本身不是沙箱；[进程预算夹具](../../hi3d/resources/process-run.md)还有异常窗口与回收限制。因此不把桌面样本或历史脚本成功升级为服务端隔离证明。

## 决定与理由

1. **本期建立最小真实注册存储。** 采用 SQLAlchemy 与本地 SQLite 作为 L1-01 设计基线，具体版本实施前验证并锁定。L1-01 若完全推迟持久化，将无法验证自己的创建恢复；反过来，先建立完整资产库又超出当前消费者。SQLAlchemy 满足已确认的数据层规范，SQLite 支持本地事务，限定单根单写入实例可控制首期并发范围。[SQLAlchemy SQLite 方言](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html)、[SQLite 隔离](https://sqlite.org/isolation.html)
2. **登记只有一处权威事实。** 复用 WorkspaceId，登记记录和目录观察分开；不为同一事实增加状态、模式和布尔值再以测试维持一致。原创建字段用于本地幂等，不用名称或路径推导身份。具体字段及关联只维护在实施卡。
3. **保留数据库与目录之间的失败窗口。** SQLite 原子提交并不包含文件系统 mkdir；按原身份对账实际残留，不能靠补造成功或删除现场掩盖部分完成。[SQLite 原子提交说明](https://sqlite.org/atomiccommit.html)
4. **短存储操作与建模执行分开。** 数据库 Session 限定在实际工作线程，异步取消只影响等待时不能释放仍在使用的资源。注册串行不扩展为模型全局串行。[SQLAlchemy Session 并发范围](https://docs.sqlalchemy.org/en/20/orm/session_basics.html#is-the-session-thread-safe-is-asyncsession-safe-to-share-in-concurrent-tasks)、[Python Future 取消限制](https://docs.python.org/3.14/library/concurrent.futures.html#concurrent.futures.Future.cancel)
5. **持久工作区、隔离执行和产物接收分别拥有职责。** 工作区保留身份与资产事实，执行器只取得最小输入和独立输出区。可信接收器核对实际字节，业务服务再消费独立验收与发布事实。WorkspaceId 不授予权限，不可信代码不得直接接触注册库或控制面。
6. **稳定能力与动态代码同时保留。** 常见预览、导出和检查使用结构化参数与受管脚本；复杂建模可以使用生成 Python，但需要真实隔离。Blender 官方说明 Python 不限制脚本权限，禁自动脚本不能作为通用沙箱。[Blender 脚本安全](https://docs.blender.org/manual/en/latest/advanced/scripting/security.html)
7. **平台选择不进入业务协议。** 环境配置、镜像、资源与隔离实现由 Bootstrap／Operations／适配器维护。缺少合格执行环境时明确不可执行，不增加业务 CapabilityMode、重复安全状态或架构切换开关，不改变动作参数和发布标准。

## 执行候选评估

以下为官方资料研究及工程判断，**没有选定、安装或验证任一执行平台**。当时环境观察由 L1-01 维护，后续选型必须按实际版本重新核实。

| 候选 | 文档支持与限制 | 本次判断 |
| --- | --- | --- |
| 加固容器 | namespace、能力裁剪、seccomp／AppArmor 和 cgroup 可限制权限及资源，仍共享宿主内核；daemon 控制权与挂载必须受信。默认容器没有完整资源限制。[安全说明](https://docs.docker.com/engine/security/)、[资源限制](https://docs.docker.com/engine/containers/resource_constraints/) | 作为打包及受控脚本验证基础；不能以默认 Docker 或仅设置 cwd 宣告任意不可信代码可开放。 |
| gVisor | Sentry 减少应用直接接触宿主系统调用面；仍依赖正确的挂载、网络策略及资源限制。systrap 适合 VM 内运行，不要求 KVM。[安全模型](https://gvisor.dev/docs/architecture_guide/security/)、[平台说明](https://gvisor.dev/docs/architecture_guide/platforms/) | 当前 VMware Debian 的 CPU 验证优先候选；需实测 Blender、插件、I/O 开销和生命周期，不能宣称已兼容。 |
| Kata／独立硬件虚拟机 | 独立客体内核需要虚拟化条件，并维护 VMM、客体镜像、设备和网络；VM 内 Kata 需要外层暴露嵌套虚拟化。Kata 不必绑定 Kubernetes。[安装前提](https://kata-containers.github.io/kata-containers/installation/)、[QEMU 安全模型](https://www.qemu.org/docs/master/system/security.html) | 当前 guest 未见 KVM；外层独立 worker VM 或其他宿主是条件候选，运维成本更高。不能把软件模拟当成已成立的安全替代。 |
| 远端 worker／执行服务 | “远端”只是部署位置，仍须核实其实际隔离、资源、网络、数据保留、终止和对账能力。 | 本机 GPU／虚拟化／兼容性不足时考虑；不预选供应商，也不把迁出当前机器当作隔离验收。 |

GPU 增加独立约束。gVisor 支持部分 NVIDIA GPU、驱动与 CUDA／Vulkan 等接口，但 nvproxy 仍将允许调用交给宿主驱动，不能消除其漏洞风险；不能从通用支持推断目标 Blender／OptiX 已验证。[gVisor GPU 限制](https://gvisor.dev/docs/user_guide/gpu/)

Kata GPU 路线需要相应 VFIO／IOMMU、客体驱动和镜像；直通与 vGPU 共享不是同一方案。[Kata GPU 说明](https://github.com/kata-containers/kata-containers/blob/main/docs/use-cases/NVIDIA-GPU-passthrough-and-Kata.md) Blender 的 GPU 后端也有设备与驱动要求。[Blender GPU 要求](https://docs.blender.org/manual/en/latest/render/cycles/gpu_rendering.html) 因此先以 CPU 后台操作验证；若目标效果或时延必须 GPU，先确定代表性任务再选择执行位置和平台，不自动降级为宿主裸执行。

## 未采用的方案

| 方案 | 原因 |
| --- | --- |
| 把工作区根挂载给任意代码，再依赖提示词限制路径 | 给出超过任务需要的实际权限；代码无需逃逸即可读写敏感对象。 |
| 将 UUID、注册时间或 cwd 当授权／隔离证明 | 混淆身份、存储、访问资格和执行机制。 |
| 通过关键词／模块黑名单、LLM 自审或持续人工命令审核隔离 | 无法替代操作系统边界，也不符合自主服务链。 |
| 为每个 LLM／工作区永久运行 Blender 并共享当前场景 | 放大状态泄漏与写冲突，现阶段没有持续进程消费者。 |
| 为并行放宽同 Job 的重复 Attempt 守卫 | 混淆独立候选与失败重试，破坏 L0 原尝试恢复约束。 |
| 生成脚本自行写 pass 后直接发布 | 报告、真实检查、验收和发布是不同事实；生成进程可控制自己的报告。 |
| L1-01 同时建立多租户权限、调度、通用沙箱端口及完整运维 | 没有当前消费者，提前增加状态与配置；只需保留必要边界和后续放行门槛。 |
| 环境模式同时控制工具参数、业务能力及发布资格 | 部署资源反向决定业务协议，产生重复事实与非法组合。 |

## 后果与后续决定

本次只完成设计文档，不改变 L0 已完成状态，也不发布 L1 API。当前契约、恢复、后续分工、真实验证条件和未决点统一见 [L1-01](../implementation/work-items/L1-01.md)。完整运维可以后置；首次开放不可信执行时所需授权、隔离、资源、回收和接收边界不能后置。
