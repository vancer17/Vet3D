---
name: api-demo-service
description: 将用户自己的可运行算法封装成单任务本地 HTTP 演示服务和测试页；校验失败与执行失败分开，不把请求拼进命令行，面板不索取密钥。
---

# 算法演示服务

把用户**已经能跑**的一个算法封成本地单任务 HTTP 演示：测试页上传样例、填参数、提交、看结果或错误。不读取或封装宿主内部算法，也不做成 MDF 常驻部署。

## 宿主执行模式

在 desktop 中先读 [Runtime 执行约定](../.dependency-run-tools/references/desktop-runtime.md)。本入口不提交 Hi3D/MDF，不消费 `HI3D_AK`/`HI3D_SK`。

## 独立工作流与依赖

按 [打包约定](../.dependency-package-tools/references/usage.md) 和 [依赖清单](package.json) 在仓库外生成完整分发目录。通过 `$api-demo-service` 或显式读取本文件调用。Python 3.10+。运行目录必须在包外。[统一计时](../.dependency-run-tools/references/stage-records.md) 与 [阶段计时](references/timing-and-revision.md) 一起使用。先读 [检查点](pcg/routes.yaml) 与 [阶段及产物](pcg/architecture.yaml)。

## 共用交互

状态为等待输入、就绪、执行中、待预览、修改中、完成、失败、已取消。缺入口脚本时提示用附件提供。取消保留已生成服务目录。公开发布另行确认。测试页不出现密码或密钥字段。

## 输入与规划

同步/后台说明见 [modes.json](references/modes.json)。样例能短时完成时默认同步；已知会超过同步窗口则用带状态查询的后台任务。不能单凭偏好忽略已测到的超时。限额为文件大小、执行超时和并发；涉及外部费用或设备可用性时单独询问。

```bash
"$PYTHON" "$SKILL_DIR/scripts/plan_demo.py" \
  --brief "$RUN_DIR/brief.json" --modes "$SKILL_DIR/references/modes.json" \
  --output "$RUN_DIR/plan.json"
"$PYTHON" "$SKILL_DIR/scripts/build_demo.py" \
  --plan "$RUN_DIR/plan.json" --algorithm "$RUN_DIR/algorithm.py" \
  --skill-dir "$SKILL_DIR" --output "$RUN_DIR/demo"
"$PYTHON" "$SKILL_DIR/scripts/serve_demo.py" --root "$RUN_DIR/demo"
```

只复制用户给出的入口文件。请求体经 `contract.py` 校验后再交给固定 argv 的 `runner.py`；禁止把字段拼进 shell。用户若提供 `argv`，必须是不含插值的字符串列表。

## 预览、修改与交付

用户用测试页提交正常样例、错误参数、无法处理的文件；执行中禁止重复提交；后台任务可查询状态。输入校验失败 `kind=validation`，算法失败 `kind=execution`，超时 `kind=timeout`。失败不自动重跑收费服务。公开部署、密钥面板、多算法路由、MDF 队列标为未实现。

资源加载用 `scripts/check_http.py` 对测试页、plan 与服务脚本做 loopback GET。交互步骤显式调用独立 [game-browser-check](../game-browser-check/SKILL.md)，传入本次 URL 与提交/失败提示步骤；缺少 Playwright 时记录未做浏览器交互，仍须用 HTTP 实际调用 `/run`。成果页显式调用独立 [asset-page](../.dependency-asset-page/REFERENCE.md)，接收本轮 HTML 与服务源码，只生成本地页面，不隐含发布。交付核对显式调用独立 [delivery-review](../.dependency-delivery-review/REFERENCE.md)，输入成果页与真实下载文件，输出清单和实际打开范围。

交付：服务源码、测试页、接口说明、依赖及启动说明、调用示例。默认本地演示。

最小验收：正常样例、错误参数、无法处理的文件、超时和连续请求；实际启动服务并从测试页契约调用成功，检查返回对象及失败提示。

<!-- managed-by: sparc3d-runtime -->
