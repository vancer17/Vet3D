# 局部面部注册执行契约

配置沿用已有分析目录：`source` 为 GLB 绝对路径、`output` 为分析目录绝对路径。目录内含 front.png、camera.json、surface_raw.npz、visibility.npz、service_binding.json 和 service/invocation.json。source_has_hair 应按实际输入设置；局部拟合对光头仍使用可见性筛选，因此上游需生成 visibility.npz。

```bash
"$PYTHON" "$SKILL_DIR/scripts/face_fit.py" "$RUN_DIR/config.json" --blender "$BLENDER"
```

入口对已有 fit 或 donor 拒绝覆盖。仅消费已有分析产物，不发起服务。已完成 fit 但检查/导出未完成时，显式加 `--review-fit`，核对 source/target/template 后只检查与导出；不会重新拟合，也不覆盖已有 donor。每个本地阶段由 process_run.run_budgeted 写预算心跳并执行，默认低档 180 秒；需要更高档时先按预算契约确认。阶段日志和 face-fit-timings.jsonl 写入任务目录。脚本异常、超时保留原始记录，不自动回退至重新检测或生成高模。

## 注册步骤

输入选择与分任务请求见 [portrait-analysis](../../.dependency-portrait-analysis/REFERENCE.md)。pose 使用带纹理渲染；seg/normal 可试灰模，当前联合注册消费同次 pose+seg。

所有本地适配器均有函数入口，CLI 只是组合；已有 target / settings 可直接执行 fitting。

1. 创建 config JSON：`source` 原始 highmesh GLB、`output` 新注册目录、`source_has_hair: true`，可选 `source_object`、`sample_count`、`render_mode`（默认 textured；gray 仅用于分割/法线尝试，不用于关键点注册）。模型须已确认正面朝向（GLB +Z）；不可猜测任意模型轴。以下渲染由独立 portrait-analysis 包执行，`ANALYSIS_SKILL_DIR` 为其物化目录：

   ```bash
   "$BLENDER" --background --factory-startup --python-exit-code 1 \
     --python "$ANALYSIS_SKILL_DIR/scripts/prepare_sapiens_registration.py" -- "$RUN_DIR/config.json"
   ```

   保存世界坐标表面采样、实际相机、front.png 和深度可见性。Blender 坐标为 Z-up/-Y-front；GLB↔Blender 变换明示保存在 camera.json。
2. 调用 Sapiens2，把其结果放到 config.output 下的 `service/`。在提交前保存 `service_binding.json`（`image_sha256` 绑定 front.png，可附 request_sha256），恢复时必须核对旧绑定，不能事后给未知来源的检测补写绑定。`prepare_sapiens_settings.py config.json` 验证 invocation 的成功、文件哈希、原模型与相机绑定；腐蚀语义皮肤边缘，去除眼唇投影内部，保留可见皮肤样本。生成 `target.npz`、`masks.json`、`project.json`、`registration.json`。
3. Blender 运行 `project_sapiens2_landmarks.py -- project.json`，以渲染相机向原高模 raycast。生成模板映射对应的 3D 眼唇 landmarks，自动点仍须查看投影；不要使用另一人物的点。
4. Python 运行 `fit_visible_face.py registration.json`。配置必须有 `hair_state: present`（带发）或 `bald`（光头）、`target_parts: visible_semantic_face_skin`、`source`、`source_sha256`、`target`、`settings`、新的 `output`。包位置自动解析。它检查模板/target/源哈希，再限制 observed fit_indices；原 mobility 保持空间连续，不能按面法线硬切 mobility。输出 `brush_fit.npz` 和报告，状态为待验收。
5. Blender 运行 `check_geometry.py -- brush_fit.npz geometry.json`；可选第三参数是经过判断后另存的 bounded correction NPZ。该函数返回报告且 CLI 退出 0 不代表 geometry_passed，必须读取布尔字段。全模板新增自交需定位；鼻部之外的局部失败只能明确标为局部 donor 使用，不能宣布全模板通过。
6. Python 运行 `export_sapiens_registration.py config.json`，其中 `export_fit` 显式指向刚检查的 NPZ；不要依赖旧 registered.npz。输出 GLB 坐标 donor、先验 GLB 和 landmarks.png。模板四边形/UV 顺序保持，原高模不变。

核心 `brush.fit_brush(template, quads, target, target_quads, settings, ..., target_normals=...)` 是纯数值运算：加权相似变换初始化，逐尺度空间 brush，法线相容点面吸引，landmark Huber，有限速度/邻域梯度和三角有向面积保护。返回 fitted、相似变换、rest、平滑 target、阶段指标。输入 settings 中 landmarks 绑定模板顶点，fit_indices 选择表面，mobility 为 [0,1] 数组；没有关键点时不能把它描述成自动无点注册。

## 输出与验收

`face_fit_report.json` 单列眼唇关键点残差、鼻部拟合点到同源皮肤采样的 RMS/P95 与归一化值，记录模型单位及来源；归一化分母为可见目标采样的包围尺度，可能包含颈部，不能当作鼻宽。另报告触及鼻部锚点包围盒（扩展 30%）的新增相交数，不能据此宣称完整接缝或基线接触通过。鼻部范围由随包模板固定位置推导，仅是诊断区；最近点距离不能验证鼻孔内部，也不能证明 donor 解剖正确。生成的 donor 保留模板四边形顺序，源 GLB 的字节保持不变。

`geometry.json` 是全模板比较，`geometry_passed=false` 不被局部距离覆盖。未观测头皮/后脑不作为拟合精度目标；发生几何错误必须定位是否涉及鼻部和接缝，未定位之前 donor 状态为待审核。初版不自动批准移植。

底层脚本与 CLI 均可单独调用；fit_visible_face 与 prepare_sapiens_settings 为此 skill 的唯一源，portrait workflow 通过 package.json 保留兼容路径。渲染准备仍由 portrait-analysis 维护，服务客户端仍由独立 [mdf-call](../../mdf-api/SKILL.md) 提供。模板来源和许可随 assets/taro/manifest.json 与 UPSTREAM_LICENSE.txt 交付。
