# 三项初始重拓扑后端的安装选项

用户选定算法之后，若该后端当前探测不到，先把下面适用的来源和建议全部摆出来，等用户选定来源再安装。未点名来源、超时、或只选了算法，都不表示同意安装。取消则停在该分支。

初始四选一仍是算法选择，按钮不表示安装来源。宿主若只能弹出本入口 `choices_example` 的四项重拓扑，那些按钮继续表示 QRemeshify、AutoRemesher、Instant Meshes 2026 和原四边通。安装来源写在同一次说明里，用用户的明确答复选定。

不安装 Blender 本身。包内没有 Blender。两个扩展都要求 Blender 4.2.0 或更高；更低版本不安装扩展，可改用 AutoRemesher 或原四边通。已有同 id 扩展或已有应用时，先报告路径和版本，只有用户选择“替换”才覆盖。不卸载其他插件，不改系统安全策略。

装完按 [初始方案](hi3d-initial-remesh.md) 重新探测。扩展要能按 id 找到并启用；AutoRemesher 还要 `--help` 成功。探测失败不进入重拓扑。

## 建议怎么选来源

已冒烟的组合是 macOS arm64、Blender 5.1.1，以及 QRemeshify 1.1.0、AutoRemesher 1.2.0、Instant Meshes 2026 扩展 1.0.0。本机系统、架构和 Blender 版本与该组合一致，并且用户手里有依赖备份时，优先建议用备份，不改用更新的未测版本。

系统不一致时，不要拷贝备份里的可执行文件。改建议官方发布里与当前系统匹配、且版本号与上表相同的包。没有匹配的官方包时，才把源码构建列为可选项，并写明本仓库没有验证过这次构建。

不要用 wjakob 的旧版 Instant Meshes 代替 Instant Meshes 2026。不要把 AutoRemesher 说成 Blender 扩展。

## 每个后端都有的四个来源

向用户列出当前适用的项，并标明推荐项和不能用的原因。不适用的项仍写出来，注明为什么这次不能选。

| 来源 | 做什么 | 何时建议 |
| --- | --- | --- |
| 依赖备份 | 使用用户指出的 `hi3d-quad-flow-dependencies` 压缩包或已解压目录 | 系统、架构、Blender 与冒烟组合一致，且备份里有对应文件 |
| 官方发布 | 下载下表中的固定版本发布包，不改用 latest 或 master | 备份缺失，或备份的系统与本机不一致，但官方有匹配包 |
| 源码构建 | 按该项目公开的构建说明编译 | 没有匹配的备份和官方二进制时才提出；构建成功不等于重拓扑已验收 |
| 不安装 | 改选已经可用的算法，或走原四边通，或停止 | 用户不愿安装、版本不匹配，或只想换路线 |

官方发布只从项目自己的发布页取得，对上文件名和版本后再装。不从搜索结果、网盘或来历不明的压缩包安装。

## QRemeshify

Blender 扩展，id=`qremeshify`。侧栏名称 QRemeshify。扩展声明支持 windows-x64、macos-arm64、linux-x64，最低 Blender 4.2.0。作者说明 Windows 是主要测试系统，Linux 和 macOS 仍在测试；本仓库的冒烟是 macOS arm64。

| 来源 | 具体文件 |
| --- | --- |
| 依赖备份 | `tools/qremeshify/`，含 `blender_manifest.toml` 与 `lib/*.dylib`。这份是 macOS 动态库，不能拷到 Windows 或 Linux |
| 官方 1.1.0 | <https://github.com/ksami/QRemeshify/releases/tag/1.1.0> 中的 `QRemeshify-1.1.0-windows.zip`、`QRemeshify-1.1.0-macos.zip`、`QRemeshify-1.1.0-linux.zip`。按本机系统选一个，不要解开展给 Blender |
| 源码构建 | 仅当上两项都没有匹配包。构建步骤以该仓库当时的说明为准，本入口不另写一套编译命令 |

安装：用当前任务的 Blender 执行「从磁盘安装」该 zip，或 `blender --command extension install-file <zip> --repo user_default --enable`。备份目录不是 zip 时，先去掉 `__pycache__` 和 `._*`，再复制到该 Blender 的 `extensions/user_default/qremeshify/`，然后只启用这个 id。macOS 官方 zip 的架构以包内二进制为准；与本机不一致就停止，不强行启用。

装完核对：扩展 id 可见且已启用，对象模式能找到 `bpy.ops.qremeshify.remesh`。不在安装阶段对用户模型重拓扑。

## AutoRemesher

独立应用，不是 Blender 插件。已冒烟版本 1.2.0。命令行入口名是 `autoremesher`。

| 来源 | 具体文件 |
| --- | --- |
| 依赖备份 | `tools/AutoRemesher.app`。这是 macOS 应用包，不能当作 Windows 或 Linux 程序 |
| 官方 1.2.0 | <https://github.com/huxingyi/autoremesher/releases/tag/1.2.0>。macOS 用该版本的 `.dmg`；Windows 用 `win32-x86_64` 的 zip，里面运行 `autoremesher.exe`；Linux 用该版本的 `.AppImage`，并 `chmod +x` |
| 源码构建 | 官方说明需要 C++14、Qt 5.15.2、TBB 和对应平台的构建工具。只在没有匹配发布包时提出 |

macOS 安装位置按用户选择：`~/Applications/AutoRemesher.app` 或 `/Applications/AutoRemesher.app`。默认建议用户主目录下的 Applications，避免改系统目录。第一次打开若被系统拦截，请用户在系统设置里允许这一次；不关闭 Gatekeeper，不清除全部隔离属性。Linux 的 AppImage 放在用户指定且可执行的工作目录，不假定包管理器。Windows 解压到用户指定目录，把该 `autoremesher.exe` 记为本次可执行文件。

装完核对：对实际可执行文件运行 `--help`，确认退出成功，并且帮助里有 `--input`、`--output`、`--target-quads`。帮助里没有的参数以后也不传。

## Instant Meshes 2026

Blender 扩展，id=`instant_meshes_2026`。最低 Blender 4.2.0。运行时优先用与当前 Blender Python ABI 匹配的 `pyretopo`；没有时才用同目录的 `InstantMeshes2026CLI`。这不是旧版 Instant Meshes 桌面程序。

| 来源 | 具体文件 |
| --- | --- |
| 依赖备份 | `tools/instant_meshes_2026/`，含扩展和 `InstantMeshes2026CLI`。该 CLI 是 macOS 可执行文件，不能拷到 Windows 或 Linux |
| 官方发布 | <https://github.com/MondRubberduck/instant-meshes-2026> 的发布页。只接受同时带有 Blender 扩展和当前系统 CLI、且能对上扩展 id 的包。发布里若只有更新的独立程序、没有这个扩展，不把它算作已安装 |
| 源码构建 | 仅当备份和官方发布都没有当前系统的 CLI。需要得到与本机 Blender 匹配的扩展，以及同目录 CLI。本仓库未验证从源码编出的 CLI |

安装扩展的方式与 QRemeshify 相同，目标目录名是 `instant_meshes_2026`。CLI 必须留在扩展目录里，不单独挪到 PATH 冒充另一个软件。装完核对扩展已启用，并确认 `pyretopo` 或 `InstantMeshes2026CLI` 至少有一个能被该扩展找到。没有用户提供的曲线或标注时，仍然不执行重拓扑。

## 安装时不做的事

- 不因为推荐了某一项就直接下载或复制。
- 不把三个后端一次全部装上，除非用户逐项同意。
- 不覆盖已有扩展、应用或用户偏好；替换要单独同意。
- 不用备份里的 macOS 二进制去配 Windows、Linux 或另一种 CPU 架构。
- 不把安装成功写成模型已经重拓扑通过。
- 源码构建失败时保留日志路径，不改走另一个算法，除非用户重新选择。
