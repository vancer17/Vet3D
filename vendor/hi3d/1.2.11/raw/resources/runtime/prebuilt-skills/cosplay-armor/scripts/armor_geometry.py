"""Shared explicit armor profile/mesh operations. No configuration, file, or Blender scene mutation occurs at import."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

import bpy, bmesh, numpy as np, sys, json, math, struct, os
from pathlib import Path
from mathutils import Vector
from stage_cli import cli_arguments, StageFinished, _finish_stage

def fit(z, *, FIT_SCALE, pf, zf):
    """Independently callable fit operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    z = np.asarray(z)
    return np.stack([np.interp(z, zf, pf[:, i]) for i in range(4)], axis=-1) * FIT_SCALE

def desired(z, th, extra=0, *, CLEAR, FIT_SCALE, pf, zf):
    """Independently callable desired operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    f = fit(z, FIT_SCALE=FIT_SCALE, pf=pf, zf=zf)
    a = f[..., 2] + CLEAR + extra
    b = f[..., 3] + CLEAR + extra
    rr = 1 / np.sqrt((np.cos(th) / a) ** 2 + (np.sin(th) / b) ** 2)
    return (f[..., 0] + rr * np.cos(th), f[..., 1] + rr * np.sin(th))

def mat(n, c, metal=0, rough=0.4):
    """Independently callable mat operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    m = bpy.data.materials.new(n)
    m.diffuse_color = (*c, 1)
    m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (*c, 1)
    p.inputs['Metallic'].default_value = metal
    p.inputs['Roughness'].default_value = rough
    return m

def mesh(name, v, f, m=None, *, S):
    """Independently callable mesh operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    d = bpy.data.meshes.new(name)
    d.from_pydata(np.asarray(v) * S, [], f)
    d.update()
    o = bpy.data.objects.new(name, d)
    bpy.context.collection.objects.link(o)
    if m:
        d.materials.append(m)
    bm = bmesh.new()
    bm.from_mesh(d)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    bm.to_mesh(d)
    bm.free()
    for p in d.polygons:
        p.use_smooth = True
    return o

def boolean(o, c, op):
    """Independently callable boolean operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    bpy.context.view_layer.objects.active = o
    q = o.modifiers.new(op + ' ' + c.name, 'BOOLEAN')
    q.operation = op
    q.solver = 'MANIFOLD'
    q.object = c
    bpy.ops.object.modifier_apply(modifier=q.name)
    bpy.data.objects.remove(c, do_unlink=True)
    print('boolean', op, len(o.data.polygons), flush=True)

def solid(name, low, high, extra, material=None, n=160, k=90, *, CLEAR, FIT_SCALE, S, pf, zf):
    """Independently callable solid operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    th = np.linspace(-math.pi, math.pi, n, endpoint=False)
    lo = np.broadcast_to(low, (n,))
    hi = np.broadcast_to(high, (n,))
    v = []
    for u in np.linspace(0, 1, k):
        z = lo * (1 - u) + hi * u
        x, y = desired(z, th, extra, CLEAR=CLEAR, FIT_SCALE=FIT_SCALE, pf=pf, zf=zf)
        v.extend(np.stack([x, y, z], axis=1))
    faces = []
    for j in range(k - 1):
        for a in range(n):
            b = (a + 1) % n
            faces.append((j * n + a, j * n + b, (j + 1) * n + b, (j + 1) * n + a))
    faces += [tuple(range(n - 1, -1, -1)), tuple(((k - 1) * n + a for a in range(n)))]
    return mesh(name, v, faces, material, S=S)

def annular_liner(low, high, n=160, k=90, *, CLEAR, FIT_SCALE, S, inner, pf, zf):
    """Independently callable annular_liner operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    th = np.linspace(-math.pi, math.pi, n, endpoint=False)
    v = []
    for ex in [3.5, -1.0]:
        for u in np.linspace(0, 1, k):
            z = low * (1 - u) + high * u
            x, y = desired(z, th, ex, CLEAR=CLEAR, FIT_SCALE=FIT_SCALE, pf=pf, zf=zf)
            v.extend(np.stack([x, y, z], axis=1))
    f = []
    N = n * k
    for side in range(2):
        off = side * N
        for j in range(k - 1):
            for a in range(n):
                b = (a + 1) % n
                face = (off + j * n + a, off + j * n + b, off + (j + 1) * n + b, off + (j + 1) * n + a)
                f.append(face if side == 0 else face[::-1])
    for a in range(n):
        b = (a + 1) % n
        f.append((a, N + a, N + b, b))
        f.append(((k - 1) * n + a, (k - 1) * n + b, N + (k - 1) * n + b, N + (k - 1) * n + a))
    return mesh('Regular annular liner with shaped end rims', v, f, inner, S=S)

def back_cutter(*, FIT_SCALE, S, Z0, Z1, pf, zf):
    """Independently callable back_cutter operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    z = np.linspace(Z0 - 50, Z1 + 60, 100)
    v = []
    for xz in z:
        c = fit(xz, FIT_SCALE=FIT_SCALE, pf=pf, zf=zf)
        v.extend([[c[0] - 180, c[1] - 5, xz], [c[0] + 180, c[1] - 5, xz], [c[0] + 180, c[1] + 180, xz], [c[0] - 180, c[1] + 180, xz]])
    f = []
    for j in range(len(z) - 1):
        for i in range(4):
            f.append((j * 4 + i, j * 4 + (i + 1) % 4, (j + 1) * 4 + (i + 1) % 4, (j + 1) * 4 + i))
    f += [(3, 2, 1, 0), tuple(((len(z) - 1) * 4 + i for i in range(4)))]
    return mesh('Continuous back opening', v, f, S=S)

def save(name, *, SAVE):
    """Independently callable save operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    bpy.ops.wm.save_as_mainfile(filepath=str(SAVE / name))

def check(o):
    """Independently callable check operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    d = {'vertices': len(bm.verts), 'faces': len(bm.faces), 'nonmanifold_edges': sum((not e.is_manifold for e in bm.edges)), 'volume_mm3': abs(bm.calc_volume()) * 1000000000.0}
    bm.free()
    return d
