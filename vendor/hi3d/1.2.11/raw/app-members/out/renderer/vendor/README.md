# DataFinder Web SDK

`collect-rangers-v5.2.6.js` 是网页端当前使用的火山引擎 SDK 原始文件，未经修改，随 Electron 包一起发布，不在运行时下载远程脚本。

- 来源：https://lf6-data.volccdn.com/obj/data-static/log-sdk/collect/5.0/collect-rangers-v5.2.6.js
- 版本：5.2.6
- SHA-256：`503bae0033b22d402dff1d71685db202a96fc5b5ad5a82ee9e616aa690a15edd`
- 获取日期：2026-09-13

升级时同时更新此文件、`track/trackInit.ts` 中的路径及 SDK 集成测试中的版本断言。采用本地副本是为了保持与网页端版本一致，并保留 `script-src 'self'`。

例外：内测包启用埋点悬浮球时，SDK 会另外从 `https://lf-static.applogcdn.com` 加载 DataFinder devtool 渲染脚本，由 `electron.vite.config.ts` 的 `desktop-track-devtool-csp` 插件在内测包放宽 CSP。正式包不加载该脚本，CSP 保持 `script-src 'self'`。
