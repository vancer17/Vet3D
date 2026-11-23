#!/usr/bin/env python3
"""Compute the fixed V5 interface and grid layout; no CAD or optical claims."""
from pathlib import Path
import argparse
import json
import math


def finite(value, name):
    if isinstance(value, bool):
        raise ValueError(f'{name} must be a number, not a boolean')
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f'{name} must be finite')
    return value


def frame_spec(width=150, height=100, edge_thickness=2.2, safety=1,
               gap_x=0, gap_y=0, columns=1, rows=1, light_gap=25):
    width, height, edge_thickness, safety, gap_x, gap_y, light_gap = [
        finite(v,n) for v,n in zip(
            (width,height,edge_thickness,safety,gap_x,gap_y,light_gap),
            ('width','height','edge_thickness','safety','gap_x','gap_y','light_gap'))]
    if not (100 <= width <= 500 and 100 <= height <= 500):
        raise ValueError('V5 UI width and height must be 100..500 mm')
    if not 1.5 <= edge_thickness <= 3:
        raise ValueError('mounting edge thickness must be 1.5..3.0 mm')
    if not 25 <= light_gap <= 60:
        raise ValueError('V5 light gap must be 25..60 mm')
    if min(safety,gap_x,gap_y) < 0:
        raise ValueError('safety and gaps must be nonnegative')
    for name,value in [('columns',columns),('rows',rows)]:
        if isinstance(value,bool) or not isinstance(value,int) or value < 1:
            raise ValueError(f'{name} must be a positive integer')
    b,o = 10.0,3.5
    vw,vh = width-2*b,height-2*b
    pw,ph = vw+2*o,vh+2*o
    if 2*safety >= min(vw,vh):
        raise ValueError('content safety consumes the visible window')
    count=columns*rows
    led=math.floor((max(width,height)-2*b-8)/10)*10
    return {
        'version':'frame_V5_interface','units':'mm','frame_outer':[width,height],
        'front_border':b,'panel_overlap_each_edge':o,
        'visible_image':[vw,vh],'finished_panel':[pw,ph],
        'slot_outline':[pw+.4,ph+.4],'slot_width':3.3,
        'mounting_edge_thickness_range':[1.5,3.0],
        'mounting_edge_thickness':edge_thickness,
        'content_safety_inside_visible_window':safety,
        'visible_bounds_on_panel':[o,o,pw-o,ph-o],
        'safe_bounds_on_panel':[o+safety,o+safety,pw-o-safety,ph-o-safety],
        'safe_content_size':[vw-2*safety,vh-2*safety],
        'layout_mode':'individually_framed_panels',
        'columns':columns,'rows':rows,'frame_count':count,
        'frame_edge_gap':[gap_x,gap_y],
        'panel_edge_gap':[gap_x+2*(b-o),gap_y+2*(b-o)],
        'visible_image_edge_gap':[gap_x+2*b,gap_y+2*b],
        'adjacency_exists':[columns>1,rows>1],
        'grid_pitch':[width+gap_x,height+gap_y],
        'grid_outer':[columns*width+(columns-1)*gap_x,rows*height+(rows-1)*gap_y],
        'frame_centers':[
            [(c-(columns-1)/2)*(width+gap_x),(r-(rows-1)/2)*(height+gap_y)]
            for r in range(rows) for c in range(columns)],
        'photo_plate_axes':'X right, Y photo up, Z thickness; flat print in XY',
        'lighting':{
            'max_panel_reference_thickness_mm':3,'reference_light_gap_mm':light_gap,
            'nominal_gap_at_selected_edge_thickness_mm':light_gap+3-edge_thickness,
            'gap_condition':'front seating plane fixed; varies locally with rear surface',
            'frame_body_depth_mm':3+3+light_gap+2-1+3.2,
            'body_depth_excludes':'rear hinges and stand',
            'placeholder_LED_lengths_mm':[led,max(10,led-20),led],
            'status':'layout only; actual strip cut pitch, power and optical tests required'},
        'hardware_for_complete_frames':{
            'M2x10_socket_head_screws':4*count,'M2_hex_nuts':4*count,
            'M3x8_socket_head_screws':4*count,'M3_hex_nuts':4*count,
            'M4x20_socket_head_screws':2*count,'M4_hex_nuts':2*count,
            'M4_flat_washers':2*count,
            'status':'B10 V5.1 nominal BOM; M2x10 geometric engagement verified at 1.5/3.0 mm panel edges'},
        'validation':{
            'scope':'dimension calculation only; not CAD, slicing, physical or optical validation',
            'source_revision':'V5.1 pressure head/key access repaired; B10 five presets at light_gap25 geometrically checked',
            'access_condition':'remove LED tray and four M3 screws before adjusting M2; new parameters need checks'}
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path)
    for key in ['width','height','edge-thickness','safety','gap-x','gap-y','light-gap']:
        p.add_argument('--'+key,type=float)
    p.add_argument('--columns',type=int,default=1);p.add_argument('--rows',type=int,default=1)
    p.add_argument('--out',type=Path)
    a=p.parse_args()
    try:
        cfg=json.loads(a.config.read_text()) if a.config else {}
        # The script implements the documented fixed contract, not arbitrary CAD.
        fixed={'border':10,'overlap':3.5,'panel_min':1.5,'panel_max':3,
               'slot_clearance':.3,'panel_xy_clearance':.4,'led_thickness':2,
               'led_recess':1,'back_thickness':3.2}
        for k,v in fixed.items():
            if k in cfg and not math.isclose(finite(cfg[k],k),v,abs_tol=1e-8):
                raise ValueError(f'{k} changes the fixed V5 contract; recalculate from the changed CAD')
        def choose(key,default,config_key=None):
            v=getattr(a,key)
            return v if v is not None else cfg.get(config_key or key,default)
        spec=frame_spec(width=choose('width',150),height=choose('height',100),
            edge_thickness=choose('edge_thickness',2.2,'preview_thickness'),
            safety=choose('safety',1),gap_x=choose('gap_x',0),gap_y=choose('gap_y',0),
            columns=a.columns,rows=a.rows,light_gap=choose('light_gap',25))
        data=json.dumps(spec,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
        if a.out:
            a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(data)
            print(str(a.out.resolve()))
        else:print(data,end='')
    except (ValueError,TypeError,OSError) as e:p.error(str(e))


if __name__=='__main__':main()
