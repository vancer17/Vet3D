# `file:resolveImagePreview`

## 接口名称与注册来源

`file:resolveImagePreview` 是 Hi3D Agent 1.2.11（Windows x64）的桌面 Electron IPC。渲染进程通过 preload 暴露的 `window.sparc3d.files.resolveImagePreview(request)` 发起调用，Electron 主进程在 `ipcMain.handle` 中处理。该接口为一张已知工作区图像生成本地预览地址。

## 模型可见描述

该版本的注册链路通过 Electron IPC 暴露，未找到对应的 LLM Tool 注册或模型可见 `description`。**接口概述。** 根据已知工作区和图像路径解析桌面可用的预览地址。

## 参数与结果

| 字段 | 类型与条件 |
| --- | --- |
| `assetId` | 必填非空字符串，最多 256 字符。用于定位工作区。 |
| `path` | 必填非空字符串，最多 4096 字符。支持工作区相对路径、仍位于该工作区内的绝对路径，以及可转换为本地路径的 `file:` URL。 |

两项均无默认值，未定义可选字段。扩展名检查忽略大小写，支持 `.png`、`.jpg`、`.jpeg`、`.gif`、`.webp`、`.bmp`、`.avif` 和 `.svg`。检查使用规范化的本地路径，并在判定扩展名前截去 `?` 或 `#` 之后的部分。最终解析结果须指向普通文件。

成功返回 `{url, fileName}`。`url` 的格式为 `sparc3d-asset://workspace/<assetId>/<relativePath>?v=<mtime>-<size>`。路径各段独立编码，`v` 由整数化的文件修改时间和文件大小构成，用于区分预览 URL。`fileName` 是解析后的真实文件的基本文件名。预览 IPC 读取目录绑定和文件属性，工作区解析可填充主进程内的路径缓存。图像字节在后续读取 `url` 时通过本地协议提供。该调用不写入素材文件或登记产物。

发送方不受信任、请求非法、工作区未知、`file:` URL 无法解析、路径越界、扩展名不受支持、文件缺失或目标为非普通文件时，主进程返回 IPC 错误。缺失目标和真实路径越界可能共用 `The image does not exist or its path is outside the workspace`。后续访问本地协议时，主机名或路径参数不合法可返回 `400`，文件不可解析时可返回 `404`。

## 实现伪代码

**根据安装包重建的伪代码。** 主进程校验调用来自受信任窗口的主渲染框架，再按 `assetId` 从缓存或 `workspace/open` 取得 `cwd`。路径先做词法检查，再做真实路径检查。符号链接只有在最终真实路径留在工作区内时才可能通过。渲染进程请求返回的预览地址时，桌面协议处理器会再次解析路径。

```javascript
async function resolveImagePreview(sender, request) {
  requireTrustedMainRenderer(sender);
  const { assetId, path } = requireImagePreviewRequest(request);
  const cwd = await requireWorkspaceCwd(assetId);
  const local = path.startsWith("file:") ? fileUrlToPath(path) : path;
  const candidate = resolve(cwd, local);
  const relativePath = requirePathInsideWorkspace(cwd, candidate);
  requireSupportedImageExtension(candidate);

  const realPath = await requireResolvedAssetPath(assetId, relativePath);
  const info = await stat(realPath);
  requireRegularFile(info);

  const cacheKey = `${Math.floor(Number(info.mtimeMs))}-${info.size}`;
  const encodedPath = encodeRelativePathSegments(relativePath);
  return {
    url: `sparc3d-asset://workspace/${encodeURIComponent(assetId)}/${encodedPath}?v=${encodeURIComponent(cacheKey)}`,
    fileName: basename(realPath),
  };
}

async function serveAssetUrl(request) {
  const target = parseWorkspaceAssetUrl(request.url);
  if (target === null) return new Response("bad host or path", { status: 400 });
  const { assetId, relativePath } = target;
  const realPath = await resolveAssetPath(assetId, relativePath);
  if (realPath === null) return new Response("not found", { status: 404 });
  return net.fetch(pathToFileUrl(realPath), { headers: request.headers });
}
```

## 调用示例与核查依据

**根据已核查接口重建的请求。** 假定 `asset_example` 已登记，且该工作区中已有对应图像。

```javascript
const preview = await window.sparc3d.files.resolveImagePreview({
  assetId: "asset_example",
  path: "inputs/sample image.png",
});
```

**示例响应。** 修改时间与文件大小为演示值，真实调用以磁盘属性为准。

```json
{
  "url": "sparc3d-asset://workspace/asset_example/inputs/sample%20image.png?v=1700000000000-1024",
  "fileName": "sample image.png"
}
```

- 核查版本为 Hi3D Agent 1.2.11（Windows x64）。读取的 `app.asar` 位于 `D:/install/Hi3DAgent.__hi3d-transaction/resources/`，SHA-256 为 `71cc584505ab56eb7dfbd542d54941308c9b629ebae4f84785e4f546d9e0e09a`。包内 `package.json` 和同目录 `runtime/manifest.json` 均注明版本。
- `out/preload/index.js` 的 `files.resolveImagePreview` 定义预加载桥接。`out/main/index.js` 的 `L`、`sl`、`cl` 和 `fileResolveImagePreview` 处理来源校验、入参、解析及返回。`resolveAssetPath` 校验真实路径，`kr` 和 `Ir` 分别构造和读取本地协议 URL。渲染器对已知图像路径的消费见 `out/renderer/assets/index-CDPCug_K.js` 的 `files.resolveImagePreview` 调用。
- 接口、路径校验和返回分支来自安装包静态核查。对提取的参数解析、本地路径解析和协议处理函数使用模拟工作区与文件属性，离线核对了相对路径、`file:` URL、返回地址编码、词法越界、缺失文件及 `400`、`404`。未运行真实 Electron IPC 或预览加载。实际图像能否解码由读取方确认。
