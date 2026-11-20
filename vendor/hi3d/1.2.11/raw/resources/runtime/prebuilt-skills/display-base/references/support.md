# 展示底座支承适配

仅对已有静态 GLB/BLEND 的明确网格角色评估均质实体质量、水平地面与竖直重力；先检查闭合/一致绕序，主体/台座不得重复计质。实际填充、底座固定、摩擦或抗推倒仍需对应实测。材质渲染参数不是物理密度来源。

物化后在专用后台 Blender 中调用 `BLENDER -b --python-exit-code 1 --python PACKAGE/scripts/check_support.py -- --source ASSEMBLY.glb --config CONFIG.json --output REPORT.json`。`check(source, config, output)` 清空当前场景并导入源，按精确对象名取求值世界网格；不保存源文件。输出禁止包内、输入别名和已有文件；缺角色、非网格、无质量/接触、穿入地面超过容差、退化域失败。报告含每件体积/质量/重心、输入假设和 [核心报告](../../.dependency-support-check/references/contract.md)，CLI 严格正裕量返回 0，否则 1。BLEND 只导入对象及其依赖，使用静态装配保存的对象姿态，不复现整个场景的时间/物理求解环境。

配置键全部显式提供，无品类尺寸默认值；下列仅为格式示例，实际对象名/密度/单位/容差须按任务确认：

```json
{"unit_mm":1000,"ground_z_mm":0,"contact_tolerance_mm":0.02,"parts":[{"object":"Base","density_g_cm3":1.24},{"object":"Sculpture","density_g_cm3":1.24}],"contact_objects":["Base"]}
```

`unit_mm` 为每个 Blender 世界坐标单位的毫米数；地面/接触容差为毫米。`parts` 完整列出计质实体，不自动纳入场景道具。`contact_objects` 必须来自这些实体，仅取其满足 `abs(z-ground_z_mm) <= contact_tolerance_mm` 的真实顶点，不以包围盒代替接触。仅顶点采样不能发现没有落点顶点的曲面接触；遇到此类输入先细分/确认实际接触采样后再调用。
