# 几何筛查脚本

运行 `scripts/audit_geometry.py`，不要把它当作 SVG 解析器。脚本需要 Python 3 与 Shapely；使用当前环境可用的运行时，缺依赖时在任务目录建立环境。不要把某次任务、用户名或全局包位置写死到生成文件中。

```bash
python scripts/audit_geometry.py work/sheet-a.geometry.json --report work/sheet-a.audit.json
```

输入是一张加工排版的毫米制坐标。叠合预览里的不同深度层会互相覆盖，不要将叠合预览直接作为同一张加工排版验证。

```json
{
  "units": "mm",
  "sheet_mm": [40, 30],
  "min_part_gap_mm": 3,
  "parts": [
    {
      "id": "L1",
      "expected_components": 1,
      "screen_inset_mm": 1,
      "review_holes_below_mm2": 2,
      "polygons": [
        {
          "outer": [[3,3],[27,3],[27,25],[3,25],[3,3]],
          "holes": [[[8,8],[8,15],[16,15],[16,8],[8,8]]]
        }
      ]
    }
  ],
  "score": [
    {"part_id":"L1","points":[[5,20],[24,20]],"edge_clearance_mm":0.5}
  ],
  "engrave": [
    {"part_id":"L1","outer":[[20,8],[23,8],[23,11],[20,11],[20,8]],"holes":[]}
  ]
}
```

约定：

- `parts` 中每项对应一个设计零件或明确约定的零件组。`polygons` 为真实保留材料，`holes` 是扣除的废料孔。环必须显式首尾闭合。
- `expected_components` 默认 1。多个故意独立的零件宜分成独立 part；若作为一组，明确数量。不要为掩盖意外碎片而修改预期值。
- `screen_inset_mm`、`review_holes_below_mm2`、`edge_clearance_mm` 默认 0，即不启用对应筛查。阈值是当前设计的判断参数，不是通用制造规范。
- 点必须是有限数值；曲线先用受控误差采样。脚本不理解贝塞尔、样式、单位换算、变换或 SVG 复合路径规则。
- `score` 为线，`engrave` 为面，均明确指向 `part_id`；超出保留材料或落入孔洞属于错误。刻线与切边的允许关系若特殊，应在设计中明确处理。

退出码：`0` 为所实施的几何检查通过，`1` 为错误，`2` 为需要人工审视的筛查警告。警告需要分析和记录，不是无条件重设计或删除细节的命令。

检查覆盖：面域有效性、预期连通数量、重叠面、重复切边、范围、不同零件相交/间距、雕刻归属、可选的小孔/窄桥筛查。它不会自动修改几何。

用于格式回读时，先通过可靠解析器重新读取最终 SVG/AI/XCS，再转换成此结构。仍需独立比较回读结果与母版的尺寸、路径长度/面积和几何误差；脚本只判断输入 JSON 的几何是否符合约束。
