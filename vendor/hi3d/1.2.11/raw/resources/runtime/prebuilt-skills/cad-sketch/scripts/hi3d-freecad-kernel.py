"""Runs only inside FreeCAD's Python runtime; inputs are validated declarative operations."""
import FreeCAD as App,Part,Sketcher,json
from pathlib import Path
spec=json.loads(Path(SPEC).read_text());out=Path(OUT)
doc=App.openDocument(spec['source']) if spec.get('source') else App.newDocument('Creative')
body=doc.getObject(spec.get('body','Body'))
if body is None:body=doc.addObject('PartDesign::Body',spec.get('body','Body'))
if body.TypeId!='PartDesign::Body':raise ValueError('target is not a Body')
for op in spec['operations']:
    kind=op['op']
    if kind in ('rectangle','circle'):
        if doc.getObject(op['id']):raise ValueError('existing object; use dimension edit')
        sk=doc.addObject('Sketcher::SketchObject',op['id']);body.addObject(sk)
        sk.Placement.Base=App.Vector(op.get('x',0),op.get('y',0),op.get('z',0))
        if kind=='rectangle':
            w,h=op['width'],op['height'];pts=[(0,0),(w,0),(w,h),(0,h)]
            for i in range(4):
                a,b=pts[i],pts[(i+1)%4];sk.addGeometry(Part.LineSegment(App.Vector(a[0],a[1],0),App.Vector(b[0],b[1],0)),False)
            for i in range(4):sk.addConstraint(Sketcher.Constraint('Coincident',i,2,(i+1)%4,1))
            for i in (0,2):sk.addConstraint(Sketcher.Constraint('Horizontal',i))
            for i in (1,3):sk.addConstraint(Sketcher.Constraint('Vertical',i))
            sk.addConstraint(Sketcher.Constraint('Coincident',0,1,-1,1))
            ix=sk.addConstraint(Sketcher.Constraint('Distance',0,w));sk.renameConstraint(ix,'Width')
            ix=sk.addConstraint(Sketcher.Constraint('Distance',1,h));sk.renameConstraint(ix,'Height')
        else:
            sk.addGeometry(Part.Circle(App.Vector(0,0,0),App.Vector(0,0,1),op['radius']),False)
            sk.addConstraint(Sketcher.Constraint('Coincident',0,3,-1,1))
            ix=sk.addConstraint(Sketcher.Constraint('Radius',0,op['radius']));sk.renameConstraint(ix,'Radius')
        doc.recompute()
        if sk.solve()!=0 or not sk.FullyConstrained:raise ValueError('sketch must solve and be fully constrained')
    elif kind in ('pad','pocket'):
        sk=doc.getObject(op['sketch'])
        if sk is None or sk.TypeId!='Sketcher::SketchObject':raise ValueError('sketch not found')
        if doc.getObject(op['id']):raise ValueError('feature id exists')
        obj=body.newObject('PartDesign::Pad' if kind=='pad' else 'PartDesign::Pocket',op['id']);obj.Profile=sk;obj.Length=op['length'];doc.recompute()
        if obj.Shape.isNull() or not obj.Shape.isValid():raise ValueError('invalid feature')
    else:
        sk=doc.getObject(op['sketch'])
        if sk is None:raise ValueError('missing sketch')
        ix=next((i for i in range(sk.ConstraintCount) if sk.Constraints[i].Name==op['name']),None)
        if ix is None:raise ValueError('missing named constraint')
        sk.setDatum(ix,App.Units.Quantity(str(op['value'])+' mm'));doc.recompute()
        if sk.solve()!=0:raise ValueError('dimension edit broke constraints')
doc.recompute()
if body.Shape.isNull() or not body.Shape.isValid() or body.Shape.Volume<=0:raise ValueError('valid positive solid required')
volume=body.Shape.Volume;b=body.Shape.BoundBox;bbox=[b.XLength,b.YLength,b.ZLength]
project=out/'hi3d-project.FCStd';doc.saveAs(str(project));name=doc.Name;App.closeDocument(name)
doc=App.openDocument(str(project));body=doc.getObject(spec.get('body','Body'));doc.recompute()
if abs(body.Shape.Volume-volume)>max(1e-6,volume*1e-9):raise ValueError('reopen volume mismatch')
step=out/'hi3d-solid.step';Part.export([body],str(step));loaded=Part.Shape();loaded.read(str(step))
if not loaded.isValid() or abs(loaded.Volume-volume)>max(1e-5,volume*1e-7):raise ValueError('STEP roundtrip mismatch')
report={'valid':True,'reopened':True,'stepRoundtrip':True,'unit':'mm','volume_mm3':volume,'bbox_mm':bbox,'solids':len(body.Shape.Solids),'version':App.Version()[:3]}
(out/'hi3d-review.json').write_text(json.dumps(report,indent=2))
App.closeDocument(doc.Name)
