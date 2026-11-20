# 静态构建与游戏验收

## 迁移边界

先识别浏览器入口、引擎初始化、静态资产与真正需要服务端的功能。GitHub Pages 托管静态文件，不能运行项目的 Node/SSR/Worker API 或提供共享数据库；保留必需动态服务的独立地址。参见 [Pages 能力边界](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)。

已有静态导出可用时复用它。需要迁移时，可将客户端页面接到 Vite 的 `index.html` 和浏览器入口，移除目标前端中不再使用的 SSR、Worker 绑定、服务端路由和构建插件；同步包脚本、锁文件与运行说明。不要删除仍被榜单服务使用的数据库代码，或为了部署重写游戏规则。

构建目录必须能由普通静态服务器运行，包含入口 HTML、编译后的 JS/CSS 和实际资产。上传该目录，不上传整个源码树、`node_modules`、私有配置、工作记录或仅供离线编辑的原始工程。浏览器可见的配置都是公开信息，不放 GitHub token、Hi3D 密钥或临时签名 URL。

## 选择 URL 基路径

保持一种明确策略，HTML、运行时加载器、CSS、动态图块与附属资源共用它。

| 目标 | 构建策略 | 条件 |
| --- | --- | --- |
| 固定项目站点 `/<repo>/` | Vite `base` 使用实际仓库前缀 | 可由 `configure-pages` 的 `base_path` 输出传给构建；不能假定就是本地目录名。 |
| 用户/组织站点或自定义域名根路径 | `base: '/'` | 以 Pages 配置及部署 URL 为准。 |
| 同一包在根路径与不同子路径使用 | `base: './'` | 适合单 HTML 入口、相对资源和页面内/Hash 导航；不要假定任意 History 深链也能刷新。 |

固定路径模式可在已有 Vite 配置中合并 `base: process.env.VITE_BASE_PATH ?? '/'`。`VITE_BASE_PATH` 是本模板约定的公开构建参数，需要配置显式读取；`import.meta.env.BASE_URL` 是游戏代码使用的构建基路径。官方说明见 [Vite Pages 部署](https://vite.dev/guide/static-deploy.html#github-pages) 和 [相对 base](https://vite.dev/guide/build.html#relative-base)。

例如运行时加载 `public/models/scene.glb`，可在资源解析函数中使用：

```ts
const modelUrl = new URL(
  `${import.meta.env.BASE_URL}models/scene.glb`,
  document.baseURI,
).href;
```

避免硬编码 `/models/...`、`/references/...`、`localhost` 或开发者文件路径。相对模式的页面入口应以 `/` 结尾；检查最终重定向及地址。History 路由需要静态路由输出或专门处理并实际刷新验证；开发服务器的回退不能证明 Pages 支持它。

## 游戏资产完整性

- 从加载器和模型文件建立实际请求清单，包含动态加载的模型、动画、碰撞/通道数据、音频、字体、纹理和运行时生成的 URL；只扫 HTML 会漏掉游戏主体。
- glTF 外部 `buffers[].uri`、`images[].uri` 相对 **模型 URL** 解析。检查字节长度和可解码性，不能只上传 `.gltf`；GLB 也检查实际外部引用。只有扩展契约明确允许时，才接受没有 URI 的解码器占位 buffer。
- Meshopt、Draco、KTX2 等依赖与加载器版本匹配。打包用到的 JS/WASM/worker，或逐项验证公开 CDN、CORS 与版本；模型文件可下载不等于可解码。
- 检查文件名大小写，避免本机文件系统掩盖 Linux 上的缺文件。大模型需检查 Git 及站点体积；当前限制按 [GitHub 大文件](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github) 与 [Pages 限制](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits) 核对，不把案例体积当预算。
- 如果使用 Git LFS，确认构建检出的是实际二进制且部署产物没有 LFS 指针；不能把指针文件当成公开模型。超出预算先处理传输压缩、资产拆分或已授权的资源托管，保留模型质量约束。
- 加载进度区分下载、解码和场景准备，失败要可理解并能恢复。分别检查首访和缓存后的加载；任何优化都以下载/解码/显存/帧时的实际瓶颈为依据。

## 本地候选检查

使用项目锁文件和兼容运行时执行已有检查；不要把案例的 Node 版本、测试数量或脚本名作为通用契约。验证构建输出时启动只服务真实文件、正确 MIME 的 HTTP 服务，不提供 API 或 SPA 回退。

固定路径模式按目标前缀构建和访问；如同时声称支持根路径，再单独构建验证根路径。相对模式把**同一份产物**分别挂到 `/` 和一个非根前缀检查。可在 `RUN_DIR` 创建带实际文件副本的静态根目录，再用普通 HTTP 服务测试；缺失资源必须返回 404，不允许返回 `index.html` 掩盖错误。

检查入口及全部运行时资源的状态、类型、有效内容和必要大小/哈希对应关系，尤其是模型和二进制 buffer。JS/WASM 返回 HTML、模型被截断或缺解码器都应失败。启动一次真实游戏，验证当前资产与核心交互仍匹配。

## 公开游戏验收

| 对象 | 完成条件 |
| --- | --- |
| 发布版本 | 部署运行的 SHA 与推送候选一致；线上 HTML/编译资源或版本标识对应本次构建，不能只看工作流名称。 |
| 匿名首访 | 不附账号、Cookie 或开发者本地存储依赖；首页、模型及附属资源公开可达，未借用本机服务。 |
| 启动和操作 | 实际点击开始并看见场景，执行项目的移动/转向/跳跃等关键操作，结果符合当前规则。 |
| 生命周期 | 覆盖项目具有的暂停、恢复、结算、重开；无重复循环、残留输入或无限加载。 |
| 可视内容 | 模型/贴图正确，无仅占位物；控制台无阻断错误，网络无缺文件/CORS 错误。 |
| 常显署名（如要求） | 使用用户给定原文，置于持续挂载的 UI 层；加载、菜单、游戏、暂停、结算均可见，层级足够且不拦截输入，考虑安全区和窄屏。 |
| 兼容性 | 按引擎声明并实测所需 WebGL/WebGPU、浏览器及输入设备；鼠标锁定、音频等需要用户手势的功能在真实点击后验证。 |

例如要求 `Powered by GPT6 and Hi3D` 时原样显示；这不是本工作流给所有游戏强制添加的署名。缺少某种设备或真实浏览器时明确未测范围，不能声称所有电脑均可用。若引擎依赖特定响应头或跨源隔离，先核对 Pages 能力并选择已支持的导出方式，不能用本地服务的头部配置冒充线上可用。
