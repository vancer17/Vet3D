# 桌面构建与交付

## 前提与版本边界

原案例用 Unity 6000.3.26f1、Mono 后端完成 Windows x64 与 macOS Universal 构建。随包 C# 模板从成功构建脚本泛化，**本草稿中未在新工程编译或执行**；不保证任意 Unity 版本 API 完全兼容。使用不同版本时检查实际 API 与安装模块后再适配，不重复生成角色。

玩家不需要 Unity 或 Unity Hub；开发机器需要对应 Editor 与平台模块。检查当前安装，不把任意编辑器文件拷贝/二进制修改作为安装平台支持的通用流程。缺模块时说明所需模块，由用户通过受支持方式安装；不获取密码或绕过授权。

产品名、版本、Company/应用 ID 和持久数据目录有不同作用。产品名按用户拼写固定；已有项目不能随意改应用 ID 或 Company，否则可能造成存档位置改变。

## 运行模板前

1. 将 [hi3d-desktop-build.cs](../assets/hi3d-desktop-build.cs) 复制到工作副本的 `Assets/Editor/`，不覆盖已有同名脚本。此为静态 Editor 类，模板文件名不要求与类名一致。
2. 检查需要打包的场景已保存并启用；配置所有运行时资源与字体，无作者机器绝对路径。场景或资源缺失先修，不在 Build 前偷偷重建地图。
3. 确认产品名、版本、稳定应用 ID、统一图标，以及 `RELEASE_ROOT` 指向当前工作区中的一个全新导出目录。检查解析后的路径、符号链接和硬链接；模板的字符串路径范围检查不能替代实际文件系统检查。
4. 关闭占用同一工程的 Editor，再使用同一工作副本顺序构建。日志、报告、可执行文件均用新版本路径，不覆盖旧包。GUI/Unity 运行遵守宿主权限，构建模板不会代替这些授权。

## 命令形态

以下是说明模板，不是可直接粘贴运行的原作者命令。先把变量设置成当前机器真实、获授权的路径和当前简报中的产品值；变量值应正确引用，不把用户文字拼入未经转义的 shell 命令。

```sh
"$UNITY_EDITOR" -batchmode -nographics \
  -projectPath "$PROJECT_DIR" -buildTarget osxuniversal \
  -executeMethod Hi3dCozyDesktopBuild.Run \
  -hi3d-target macos \
  -hi3d-product-name "$PRODUCT_NAME" -hi3d-version "$VERSION" \
  -hi3d-identifier "$APPLICATION_ID" \
  -hi3d-release-root "$RELEASE_ROOT" \
  -hi3d-build-output "$RELEASE_ROOT/mac/$PRODUCT_NAME.app" \
  -hi3d-build-report "$RELEASE_ROOT/hi3d-mac-build.json" \
  -hi3d-app-icon "$ICON_ASSET_PATH" \
  -logFile "$RELEASE_ROOT/hi3d-mac-build.log"
```

`ICON_ASSET_PATH` 是工程内的 `Assets/...png` 路径，不是操作系统绝对路径。模板将该图片作为通用应用图标；先在工程设置中排除旧平台专用图标覆盖，再验证最终包的实际图标。

Windows 使用 `-buildTarget win64`、`-hi3d-target windows`，输出改为 `windows/<产品名>.exe` 并使用独立报告/日志路径。模板自行退出 Editor，不同时再用另一条构建任务打开该工程。

模板设置正式非 Development 构建、Mono 后端以及当前案例版本中 Mac Universal 的架构配置；切换 IL2CPP 或其他架构需要单独确认工具链与测试。BuildReport 的 Succeeded/零错误是构建条件，不是运行验收。

## Windows 免安装包

1. 检查主 EXE、`UnityPlayer.dll`、Mono 或实际选定后端的运行库、`<产品名>_Data`、Managed/资源/插件文件均完整。依据选定后端检查，不强求 IL2CPP 也有 Mono 目录。
2. 确认 Player 是目标 x64 PE；安装器本身可以是兼容 32 位引导程序，不应据此误判游戏架构。
3. 将 `*_BurstDebugInformation_DoNotShip` 等调试产物移到同工作区的留存目录，包内不含 Editor、Library、临时测试存档或源代码私密内容。
4. 放入当前版本说明，再把完整运行目录压为 ZIP。使用安全相对路径，检查 ZIP 可解压和内容完整，不只查看 ZIP 文件大小。
5. Windows 真机完整解压后启动，测菜单、字体、材质、输入与基本任务；没有设备就明确记录未实测，不能用 Mac 运行替代。

## Windows 安装器

可沿用案例已实践的 NSIS 路线，但需按当前版本重新生成脚本/文件清单，而不是携带原游戏目录表。

- 明确 `Name`、版本资源、主程序、应用图标与安装器图标；先从方图导出包含常用尺寸的 ICO。
- 建议 `RequestExecutionLevel user`，安装到当前用户 Programs 目录；使用当前用户的开始菜单与 HKCU 卸载记录。用户要求机器级安装时另行说明权限变化。
- 定义准确的安装文件白名单；卸载逐文件删除，再按深度倒序移除空目录，不对安装根或存档目录做无条件递归删除。安装目录校验失败就停止卸载。
- 带空格的卸载路径正确引用；不要把未转义产品名直接嵌入 NSIS 指令。标识符与路径特殊字符要验证。
- 在可信、已经安装且获准使用的编译器上以 `-WX` 编译，检查退出码与输出，不分发编译器本身。缺工具时可先交付已验证的 ZIP 并说明安装器未完成，不能拿 ZIP 改后缀冒充 EXE。
- 在目标 Windows 上测试安装、开始菜单启动、卸载、重装和存档保留。代码签名是独立步骤；未签名就说明，不索取或打包私钥。

## Mac 通用包与 DMG

1. 检查 Info.plist 产品名、可执行文件、版本、应用 ID、最低系统版本和图标。使用当前机器可用的 Mach-O 工具确认同时包含 x86_64 与 arm64。
2. 在本机实际启动最终 `.app`，检查菜单/图片/动作/移动/存档及日志；Intel 与 Apple Silicon 实机结果分别记录，不把二进制架构列表当两种机器均已启动。
3. 校验代码签名状态。临时/ad-hoc 签名不等于 Developer ID 签名或 Apple 公证；无证书时不得声称已认证。
4. 以新 staging 目录放入应用、安装说明和指向 `/Applications` 的安装入口；不跟随该入口复制系统应用目录。按宿主权限使用 hdiutil 或等效受支持工具创建 DMG。
5. 只读挂载 DMG，确认应用、版本、执行权限及安装入口，再卸载本次挂载。不反复重新构建已通过的应用只为确认 DMG 状态。
6. 安装文档说明拖入“应用程序”，确认来源后按系统提示处理未验证开发者；不要求关闭 Gatekeeper、删除系统安全数据库或执行不明脚本。

## 发布证据

报告分开记录：构建结果、架构、平台/运行库、资源完整性、Player 实测、安装卸载、签名、公证、设备及未测试范围。每个结论对应同一最终构建，不使用旧截图或历史完整流程测试充当新版本证据。

源码包只包括可编辑必需文件和已获分发许可的资产；依赖、来源和安装步骤另有清单。交付前检查输出确实位于工作区，再给相对文件链接；不以 Finder 定位替代下载。
