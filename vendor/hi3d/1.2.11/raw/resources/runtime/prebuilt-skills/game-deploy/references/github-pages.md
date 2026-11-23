# GitHub 发布与恢复

## 账户、仓库与 Git 推送

优先使用已有可用的 GitHub 连接器或 `gh`；只有浏览器已登录时，可由浏览器完成仓库创建和 Pages 设置，再由 Git 推送。浏览器会话与 Git 鉴权是两条独立通路，前者可用不能推导后者可用。不要导出 Cookie、读取私钥、运行 `gh auth token` 或打印凭据来连接两者。

检查仓库 owner、名称、公开/私有状态和默认分支。新建公开仓库需要本次相应授权；若同名仓库已存在，先核对内容，不能直接覆盖。已有本地 Git 历史时，新建空远端可避免自动生成 README 带来无关历史。保留原 `origin`；它指向其他托管平台时，可新增未被占用的 `github` 远端，明确更新命令。名称已占用时先检查，不覆盖原地址。

从项目规则确定发布分支。先完成本地候选与可公开文件范围检查，再提交和普通推送。保留用户改动；远端前进时 fetch 并按项目策略整合，不强推。公开仓库会公开推送历史中的文件，不能只检查当前 `dist`。授权发布不等于授权上传凭据、改其他仓库或开放其他服务。

### SSH 连接失败

使用现有 Git 鉴权检查可达性，不枚举凭据。SSH 22 端口受阻而 HTTPS Git 不可用时，GitHub.com 可尝试 `ssh -T -p 443 git@ssh.github.com`；该路径不适用于所有企业部署，见 [SSH over HTTPS](https://docs.github.com/en/authentication/troubleshooting-ssh/using-ssh-over-the-https-port)。

新主机密钥先与 [官方指纹](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/githubs-ssh-key-fingerprints) 核对；`ssh-keyscan` 返回值本身不是信任依据。按已验证 known_hosts 使用严格检查，不用 `StrictHostKeyChecking=no` 绕过。GitHub 的 SSH 成功欢迎消息表示认证通过，但不提供 shell，测试退出码可能非零。

优先用仅作用于本次 Git 调用的配置，或新远端的 `ssh://git@ssh.github.com:443/<owner>/<repo>.git` 地址；不要为单个部署重写全局 SSH/Git 配置。浏览器和 Git 显示的账号不同时，确认该 Git 身份对目标仓库确有写权限。

### 浏览器并发干扰

管理 GitHub 时使用当前工具支持的专用标签页/窗口与稳定 tab 标识。每次关键操作前确认 URL 中的 owner/repository 和当前页面；不要复用旧界面元素编号。出现被其他任务切走的页面时停止当前点击，重新定位本项目标签，优先改用可绑定标签的控制接口；无法隔离时串行处理必要设置，不在错误仓库继续。

## Pages 来源与工作流

有构建步骤的 Vite 游戏通常用 Actions 发布产物。在仓库 **Settings → Pages → Build and deployment → Source** 选择 **GitHub Actions** 并确认保存；仅上传工作流不代表 Pages 已启用。已有正确来源时复用，不另建一套发布。具体前提见 [自定义 Pages 工作流](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)。

[随包模板](../assets/pages.yml) 是 Vite/npm 项目的起点，复制前审阅已有 `.github/workflows/` 并合并必要变化。它不适用于不经构建的原生静态包或其他包管理器，后者沿用项目已有方式，仅适配 Pages 产物上传与部署。

模板契约：

- 源码位于仓库根目录，存在 `package-lock.json`、兼容 Node 版本的 `.nvmrc` 和 `npm run build`；按现有引擎版本生成或复用 `.nvmrc`，不复制案例中的 Node 版本。
- Vite 配置显式读取 `VITE_BASE_PATH` 为 `base`，输出为 `dist`。参数来自 `configure-pages` 的实际 `base_path`，构建前补齐结尾 `/`；若项目已采用经验证的 `base: './'`，删除无需使用的固定 base 参数即可。
- 示例发布分支是 `main`，使用前同步替换 `push.branches` 与 job 的 `if` 条件，并核对 `github-pages` 环境的分支限制。已有 PR 工作流只验证，不给未合入代码执行正式部署。
- 模板只提供安装、构建和 Pages 发布；将项目已声明的 lint、类型/功能测试、真实资产及静态路径检查接在安装后、上传前。不能因为模板没有这些步骤就省略必要验收，也不要虚构项目没有的 `verify` 命令。
- `contents: read` 用于源码读取，`pages: write` 和 `id-token: write` 用于部署；环境为 `github-pages`，交付 URL 取部署步骤的 `page_url`。拆成两个 job 时，部署 job 必须 `needs` 构建 job，上传和部署使用同一 artifact。
- 只上传实际构建目录，保留 `.nojekyll` 等已有适用文件；不要把源码目录当产物。模板按一个 Pages 站点串行发布，仅发布分支可执行部署；并行 CI 验证不应取消正式发布。

Action 使用固定提交，版本更新时核对官方仓库与目标 runner 支持；不要无条件升级项目依赖。`configure-pages` 的输出定义见 [官方实现](https://github.com/actions/configure-pages)。发布后记录实际 SHA、run URL 和部署输出 URL 到游戏任务产物；模板本身不保存这些单次记录。

## 跟踪和有界恢复

优先用 Actions UI、连接器或已有 `gh run list/view` 检查**本次 head SHA** 的构建与部署步骤；公开仓库也可匿名读取 GitHub API，但速率限制不等于部署失败。等待 queued/in_progress 结束，再按 [公开验收](static.md#公开游戏验收) 检查网站；不要连续制造空提交来轮询。

| 现象 | 下一步 |
| --- | --- |
| 推送成功但没有工作流 | 核对目标远端、发布分支、工作流路径/触发条件和 Actions 开关。 |
| `configure-pages` 提示找不到 Pages | 核对 Source 是否已启用、目标仓库及权限；配置修复后重跑原失败运行，无需重建仓库。 |
| 构建成功、部署失败 | 看部署日志、artifact 名称/依赖、Pages/OIDC 权限及环境分支限制，不重做游戏资产。 |
| 部署成功但公开地址 404 | 使用部署输出 URL，检查生效状态、`index.html` 所在层级和 Pages 配置；观察原部署的传播，不重复推送相同内容。 |
| 首页 200、开局失败 | 查 JS MIME、base、模型二进制、附属 URI、解码器和 CORS；回到静态检查，不把首页成功算完成。 |
| 页面仍是旧版本 | 对比当前部署 SHA、HTML 引用的编译资源和 Service Worker/浏览器缓存；用新上下文验证，不能仅添加随机查询参数就宣称已更新。 |
| 网络超时或上传结果不明 | 查远端分支和原 run 是否完成，再决定是否重试；复用候选。 |

同类错误在没有新信息或配置变化时停止重试，报告候选、失败步骤及当前有效线上版本。需要回退时使用此前已验证提交重新部署或按项目约定 revert，保留历史；破坏性重写历史和扩大可见范围不属于普通恢复。
