"""Export separate pin/slot gauges. Default pose is vertical bore + flat slot.
Replicate actual joint orientation/length before using results for production.
"""
from pathlib import Path
import argparse
import numpy as np
from kitlib import box,cyl,export_solid,sha,write_json

def gauge_shapes(gap, dots):
    """Return pin/bore/tab/slot solids for one radial/side gap in mm; no writes.

    Dot count 1..6 labels a calibration series. Geometry is fixed reference gauge
    stock, not a replacement for production-length or differently oriented joints.
    """
    if not np.isfinite(gap) or gap<0 or gap>1 or not 1<=dots<=6:
        raise ValueError('gauge supports gap 0..1 mm and 1..6 identification dots')
    pin=cyl(2,13)+cyl(5,3)
    bore=box((14,14,10))-cyl(2+gap,12,(7,7,-1))
    for j in range(dots):bore-=cyl(.5,1,(2+j*2,2,9.3),24)
    tab=box((18,18,3.2))+box((8,10,10.2),(5,4,3))
    slot=box((18,18,10))-box((8+2*gap,10+2*gap,12),(5-gap,4-gap,-1))
    if (pin.translate((7,7,0)) ^ bore.translate((0,0,3))).volume()>=.01:
        raise ValueError('pin gauge interferes')
    if (tab ^ slot.translate((0,0,3.2))).volume()>=.01:
        raise ValueError('tab gauge interferes')
    return {'pin':pin,'bore':bore,'tab':tab,'slot':slot}


def build(out):
    """Write the six reference gauge pairs and blank physical-fit record.

    Overwrites matching files; export validation errors propagate. The six gaps
    are a calibration ladder, not manufacturing defaults or physical results.
    """
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    gaps=[.15,.20,.25,.30,.35,.40]
    record={'units':'mm','gaps_per_side_mm':gaps,'items':[],'physical_test':'not_run',
            'caution':'Short gauges do not prove long-rail straightness. Replicate production orientation and local walls.'}
    for index,gap in enumerate(gaps,1):
        suffix=str(round(gap*100)).zfill(2)
        for name,s in gauge_shapes(gap,index).items():
            f=f'{name}-{suffix}.stl';export_solid(s,out/f)
            record['items'].append({'file':f,'gap_per_side_mm':gap,'sha256':sha(out/f)})
    write_json(out/'coupon.json',record)
    (out/'试配记录.md').write_text('''# 配合试片记录

孔片上 1–6 个小点对应径向 0.15 / 0.20 / 0.25 / 0.30 / 0.35 / 0.40 mm；文件后缀 15–40 同义。圆销 Ø4，孔径 4+2c；矩形榫 8×10，矩形孔 (8+2c)×(10+2c)。STL 单位 mm。

先打印一个 pin、一个 tab 和需要比较的孔片/槽片，不必把同样公件重复打印六次。孔片开口朝 Z、榫竖直；母件从上套下，底部靠公件肩部停止。这只是基础试片，实际横向孔、薄板舌或长滑轨需另取局部生产几何试打。

| 记录 | 值 |
|---|---|
| 打印机/喷嘴 | 待填 |
| 材料/批次/层高/线宽 | 待填 |
| XY 与象脚补偿 | 待填 |
| 公件实测尺寸 | 待填 |
| 选中间隙与母件实测 | 待填 |
| 是否手装到肩/是否卡滞 | 待填 |
| 晃动、拔出方式、重复次数 | 待填 |
| 最长正式接口复测 | 待填 |

先去毛刺、冷却后试配；不要强压脆性试片。回写 CAD 单边间隙后重建正式件，切片器不要再随意缩放单个零件。
''',encoding='utf-8')
    return record

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args();build(a.out);print(a.out)
