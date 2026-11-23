import numpy as np, math, bmesh


def load_metric_heightfield(source):
    """Read explicit NPZ with no pickle, close archive, validate its numerical contract."""
    with np.load(source,allow_pickle=False) as data:
        A=np.asarray(data['height'],float);mask=np.asarray(data['mask']);bounds=np.asarray(data['bounds_xy_mm'],float)
    if A.ndim!=2 or min(A.shape)<2 or not np.isfinite(A).all() or A.min()<0 or A.max()>1:raise ValueError('height must be finite 2D normalized values in [0,1]')
    if mask.shape!=A.shape:raise ValueError('mask shape mismatch')
    if bounds.shape!=(2,2) or not np.isfinite(bounds).all() or np.any(bounds[1]<=bounds[0]):raise ValueError('bounds_xy_mm needs finite minimum/maximum XY rows')
    return A,mask,bounds

def apply_metric_relief(ob, source, profile_z, profile_r, config):
    A, mask, bb = load_metric_heightfield(source)
    A = A * (mask > 0)
    aspect = (bb[1, 0] - bb[0, 0]) / (bb[1, 1] - bb[0, 1])
    maxw = config['motif_width_mm'] / 1000
    maxh = config['motif_height_mm'] / 1000
    w = min(maxw, maxh * aspect)
    h = w / aspect
    center = math.radians(config['motif_angle_degrees'])
    zc = config['motif_center_z_mm'] / 1000
    depth = config['relief_height_mm'] / 1000
    der = np.gradient(profile_r, profile_z)
    mer = np.r_[0, np.cumsum(np.sqrt(1 + (0.5 * (der[:-1] + der[1:])) ** 2) * np.diff(profile_z))]
    mc = np.interp(zc, profile_z, mer)

    def coords(xyz):
        z = xyz[:, 2]
        rho = np.linalg.norm(xyz[:, :2], axis=1)
        r = np.interp(z, profile_z, profile_r)
        dr = np.interp(z, profile_z, der)
        theta = np.arctan2(xyz[:, 1], xyz[:, 0])
        delta = (theta - center + math.pi) % math.tau - math.pi
        u = r * delta / w + 0.5
        v = (np.interp(z, profile_z, mer) - mc) / h + 0.5
        valid = (u > -0.02) & (u < 1.02) & (v > -0.02) & (v < 1.02) & (abs(rho - r) < 0.0008)
        return (u, v, valid, r, dr, rho)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    xyz = np.array([v.co[:] for v in bm.verts])
    u, v, sel, *_ = coords(xyz)
    selected = set(np.flatnonzero(sel))
    edges = [e for e in bm.edges if all((q.index in selected for q in e.verts)) and e.calc_length() > config['subdivide_edge_threshold_mm'] / 1000]
    edge_count = len(edges)
    if edges:
        bmesh.ops.subdivide_edges(bm, edges=edges, cuts=config['subdivision_cuts'], use_grid_fill=True)
    bm.to_mesh(ob.data)
    bm.free()
    xyz = np.empty(len(ob.data.vertices) * 3, np.float32)
    ob.data.vertices.foreach_get('co', xyz)
    xyz = xyz.reshape(-1, 3)
    u, v, sel, r, dr, rho = coords(xyz)
    ids = np.flatnonzero(sel)
    if not len(ids): raise ValueError('Relief footprint contains no matching exterior vertices')
    U = np.clip(u[ids], 0, 1) * (A.shape[1] - 1)
    V = np.clip(v[ids], 0, 1) * (A.shape[0] - 1)
    i = U.astype(int)
    j = V.astype(int)
    i2 = np.minimum(i + 1, A.shape[1] - 1)
    j2 = np.minimum(j + 1, A.shape[0] - 1)
    du = U - i
    dv = V - j
    H = A[j, i] * (1 - du) * (1 - dv) + A[j, i2] * du * (1 - dv) + A[j2, i] * (1 - du) * dv + A[j2, i2] * du * dv
    fade = np.clip(np.minimum.reduce([u[ids] / 0.025, (1 - u[ids]) / 0.025, v[ids] / 0.025, (1 - v[ids]) / 0.025]), 0, 1)
    fade *= np.clip((0.0008 - abs(rho[ids] - r[ids])) / 0.00025, 0, 1)
    H *= fade
    ang = np.arctan2(xyz[ids, 1], xyz[ids, 0])
    normal = np.stack([np.cos(ang), np.sin(ang), -dr[ids]], -1)
    normal /= np.linalg.norm(normal, axis=1)[:, None]
    xyz[ids] += normal * (H * depth)[:, None]
    ob.data.vertices.foreach_set('co', xyz.ravel())
    ob.data.update()
    return {'source_npz': __import__('pathlib').Path(source).name, 'source_aspect_ratio': float(aspect), 'requested_box_mm': [maxw * 1000, maxh * 1000], 'actual_footprint_mm': [w * 1000, h * 1000], 'mapping': 'Horizontal arc length at each profile radius and vertical meridian arc length; preserve native aspect; local analytic normal displacement', 'center_angle_degrees': config['motif_angle_degrees'], 'center_z_mm': zc * 1000, 'height_mm': depth * 1000, 'actual_max_vertex_displacement_mm': float(H.max() * depth * 1000), 'local_subdivided_edges': edge_count, 'displaced_vertices': len(ids), 'undercuts': 'Not represented by first-hit heightmap; raw source retained'}


def ellipse_arc_coordinates(radius_x, radius_y, angles):
    """Pure per-row arc coordinates for elliptical mapping; inputs/output share length units.

    This is a mapping primitive, not an automatic elliptical teapot builder or equal-wall offset.
    """
    rx=np.atleast_1d(np.asarray(radius_x,float));ry=np.atleast_1d(np.asarray(radius_y,float));t=np.asarray(angles,float)
    if rx.shape!=ry.shape or t.ndim!=1 or len(t)<3 or np.any(np.diff(t)<=0) or min(rx.min(),ry.min())<=0:raise ValueError('Matched positive radii and increasing angles required')
    speed=np.sqrt((rx[:,None]*np.cos(t))**2+(ry[:,None]*np.sin(t))**2)
    arc=np.c_[np.zeros(len(rx)),np.cumsum((speed[:,1:]+speed[:,:-1])*.5*np.diff(t),axis=1)]
    origin=np.asarray([np.interp(0,t,row) for row in arc]);return arc-origin[:,None]
