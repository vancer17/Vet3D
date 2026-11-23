# RhinoMCP 安装与调用

依赖：已授权可用的 Rhino 8、外部 Python 3.10+、[uv](https://docs.astral.sh/uv/getting-started/installation/)、网络可达官方 Yak 与 PyPI。Rhino 授权由用户已有安装提供；本包不修改许可。上游为 [RhinoMCP](https://github.com/jingcheng-chen/rhinomcp)，插件和服务固定 `0.4.1.1`。升级前核对两端发行说明并重跑验收。

## 自动安装

```sh
python3 "$SKILL_DIR/scripts/rhino.py" detect
python3 "$SKILL_DIR/scripts/rhino.py" install-mcp --app "/Applications/Rhino 8.app"
# Windows 显式传 C:/Program Files/Rhino 8/System/Rhino.exe
```

安装器从实际安装定位 Yak，执行 `yak install rhinomcp 0.4.1.1`，再用 `uv tool install --python 3.11 rhinomcp==0.4.1.1` 安装服务；缺 uv 时按官方安装方式准备后继续。已有安装由包管理器检查，不删除其他包、不执行全局 killall。返回实际 server 路径。

[官方 Yak 文档](https://developer.rhino3d.com/guides/yak/installing-and-managing-packages/)说明新插件在 Rhino 下次启动时加载。检查当前文档，保存用户未保存工作；用 computer use 正常退出/启动 Rhino。打开目标模型或新空白模型，在 Rhino 命令栏输入 `mcpstart`。验证监听地址是 `127.0.0.1:1999`。如果插件已加载则无需反复安装/重启。

如没有命令行 Yak，用 Rhino 的 PackageManager 搜索准确包名 `rhinomcp`、安装官方登记版本、重启并执行 `mcpstart`；不要混装 `rhinomcp-mod` 等名字相近的包。安装/重启/启动是完整引导流程，不把下载成功当作连接成功。

## 连接并验证

宿主已经提供 Rhino MCP 时直接使用。否则可用本包的官方 SDK stdio 客户端，无需改写宿主配置或等待工具热重载：

```sh
# MCP_PY 是 uv tool dir 下 rhinomcp/bin/python，Windows 为 Scripts/python.exe。
"$MCP_PY" "$SKILL_DIR/scripts/mcp_client.py" --output "$RUN_DIR/tools.json"
"$MCP_PY" "$SKILL_DIR/scripts/mcp_client.py" \
  --request "$RUN_DIR/request.json" --output "$RUN_DIR/response.json"
```

`request.json` 为按序调用列表：

```json
[
  {"name":"describe_capabilities","arguments":{}},
  {"name":"get_document_summary","arguments":{}}
]
```

## tools/list / describe_capabilities / get_document_summary

先查实际 tools/list，不能假定旧插件具有新工具。服务目录可在 Rhino 未启动时列出，因此仍须 describe_capabilities 返回插件版本、核对 server/plugin 匹配，再读取进程内版本和文档。get_document_summary 用于文档概况，不能代替进程内 probe。入参按实际 tools/list；上述 request.json 的两个查询传空 arguments。

## get_rhinoscript_docs

参数为 `topic`、`include_examples`、`max_functions`，具体类型/默认值按本次 tools/list。先用离线两级索引读取目标函数契约；实际安装插件/包装版本不一致、离线缺项或需要核对现场接口时，再定向调用本工具，不重复获取全部函数文档。内核/SR 可用性仍由只读预检确认。

## execute_rhinoscript_python_code

参数为 `{"code":"..."}`；支持同一脚本批量建模。上游 ExecuteRhinoscript 实际用 `Rhino.Runtime.PythonScript.Create()`，当前路径是 IronPython；不能因为 Rhino 8 支持 CPython 就传 f-string 或 NumPy。需要 Python 3 时使用 ScriptEditor，并核实实际运行时。

探针和验收夹具先用 rhino.py prepare 生成，再将文件完整内容作为 code 提交；源文件中的包内 import 不保证存在于 Rhino 搜索路径。业务脚本按[共用 Python 约束](../python.md)的索引段编写。

## MCP 客户端、结果与超时恢复

`mcp_client.py` 使用官方 `mcp` 2.x SDK，不绕过 MCP 去直连自写 TCP 协议。环境固定 loopback；一次只运行一个客户端服务。调用按序留存已完成项；输出路径必须新建，超时/中断保留未决状态，绝不自动重发。MCP 信封成功后还检查工具正文 `success=false`，最终仍检查几何和产物。

`RHINO_MCP_TIMEOUT` 只限制等待，不能停止已进入 Rhino 的内核操作。断连后先查看已有对象、报告文件和活动命令，再决定恢复。服务只绑定本机；不开放公网或局域网端口。
