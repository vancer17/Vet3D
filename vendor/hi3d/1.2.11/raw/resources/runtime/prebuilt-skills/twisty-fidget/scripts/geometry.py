"""Mesh adapters and reusable geometry operations; all coordinates are mm."""
import math
import numpy as np
import trimesh
import manifold3d as mf
from shapely.geometry import Polygon
from shapely import affinity


def load_mesh(path, scale_to_mm=1.):
    if not math.isfinite(scale_to_mm) or scale_to_mm <= 0:
        raise ValueError('scale_to_mm must be positive')
    mesh = trimesh.load(path, process=True)
    if isinstance(mesh, trimesh.Scene):
        mesh = mesh.to_mesh()  # Applies scene-instance transforms.
    if not isinstance(mesh, trimesh.Trimesh) or not len(mesh.faces):
        raise ValueError('input has no triangle mesh')
    mesh.apply_scale(scale_to_mm)
    if not np.isfinite(mesh.vertices).all():
        raise ValueError('mesh has nonfinite vertices')
    return mesh


def metrics(mesh):
    return {'vertices': len(mesh.vertices), 'triangles': len(mesh.faces),
            'bounds_mm': mesh.bounds.tolist(), 'dimensions_mm': mesh.extents.tolist(),
            'volume_mm3': float(mesh.volume), 'watertight': bool(mesh.is_watertight),
            'winding_consistent': bool(mesh.is_winding_consistent),
            'components': len(mesh.split(only_watertight=False)),
            'zero_area_faces': int(np.count_nonzero(mesh.area_faces == 0))}


def require_solid(mesh):
    m = metrics(mesh)
    if not (m['watertight'] and m['winding_consistent'] and m['components'] == 1
            and m['volume_mm3'] > 0 and m['zero_area_faces'] == 0):
        raise ValueError(f'expected one closed positive-volume solid: {m}')
    return m


def to_solid(mesh):
    solid = mf.Manifold(mf.Mesh(np.asarray(mesh.vertices, np.float32),
                                np.asarray(mesh.faces, np.uint32)))
    if solid.status() != mf.Error.NoError or solid.is_empty():
        raise ValueError(f'manifold conversion failed: {solid.status()}')
    return solid


def from_solid(solid):
    if solid.is_empty() or solid.status() != mf.Error.NoError:
        raise ValueError('empty or invalid boolean result')
    result = solid.to_mesh()
    mesh = trimesh.Trimesh(result.vert_properties[:, :3], result.tri_verts, process=True)
    # Remove only exactly collapsed faces after float32 welding. Never discard islands silently.
    mesh.update_faces(mesh.area_faces > 0)
    mesh.remove_unreferenced_vertices()
    require_solid(mesh)
    return mesh


def section_loops(mesh, heights_mm):
    rows = []
    for z in heights_mm:
        if not math.isfinite(z):
            raise ValueError('section height must be finite')
        section = mesh.section(plane_normal=[0, 0, 1], plane_origin=[0, 0, z])
        rows.append({'z_mm': float(z), 'loops_xy_mm': [] if section is None else
                     [line[:, :2].tolist() for line in section.discrete]})
    return rows


def adapt_profile(points, source_count, target_count, radial_scale, inset_mm, sample_mm):
    """Resample before polar compression; inset changes all boundaries, including tongues."""
    if any(isinstance(n, bool) or not isinstance(n, int) or n < 3 for n in (source_count, target_count)):
        raise ValueError('source_count and target_count must be integers >= 3')
    if not all(math.isfinite(v) for v in (radial_scale, inset_mm, sample_mm)):
        raise ValueError('profile parameters must be finite')
    if radial_scale <= 0 or sample_mm <= 0 or inset_mm < 0:
        raise ValueError('positive radial_scale/sample_mm and nonnegative inset_mm required')
    p = np.asarray(points, dtype=float)
    if p.ndim != 2 or p.shape[1] != 2 or len(p) < 3 or not np.isfinite(p).all():
        raise ValueError('profile must be finite Nx2 coordinates')
    polygon = Polygon(p)
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError('profile must be a simple nonempty polygon without holes')
    if np.array_equal(p[0], p[-1]):
        p = p[:-1]
    sampled = []
    for a, b in zip(p, np.roll(p, -1, axis=0)):
        n = max(1, math.ceil(np.linalg.norm(b-a)/sample_mm))
        sampled.extend(a+(b-a)*t/n for t in range(n))
    p = np.asarray(sampled)
    angles = np.arctan2(p[:, 1], p[:, 0])
    center = math.atan2(np.sin(angles).mean(), np.cos(angles).mean())
    delta = np.angle(np.exp(1j*(angles-center)))
    if np.ptp(delta) >= math.pi:
        raise ValueError('profile must occupy one angular sector about the origin')
    theta = center+delta*source_count/target_count
    radius = np.linalg.norm(p, axis=1)*radial_scale
    mapped = np.column_stack((radius*np.cos(theta), radius*np.sin(theta)))
    polygon = Polygon(mapped)
    if not polygon.is_valid:
        raise ValueError('angular mapping produced an invalid profile')
    cs = mf.CrossSection([mapped]).offset(-inset_mm, circular_segments=16)
    loops = cs.to_polygons()
    if len(loops) != 1 or cs.area() <= 0:
        raise ValueError('inset removed or split the interlock; revise dimensions')
    final = np.asarray(loops[0])
    base = Polygon(final)
    copies = [affinity.rotate(base, i*360/target_count, origin=(0, 0)) for i in range(1, target_count)]
    clearance = min(base.distance(other) for other in copies)
    if clearance <= 0:
        raise ValueError('rotated profiles touch or overlap; provide a positive clearance')
    return final, clearance


def helical_parts(mesh, profile, count, k_deg_per_mm, step_mm):
    from motion import offsets
    offsets(count, 0, 'staircase')
    require_solid(mesh)
    if not math.isfinite(k_deg_per_mm) or k_deg_per_mm == 0 or not math.isfinite(step_mm) or step_mm <= 0:
        raise ValueError('nonzero finite twist rate and positive step required')
    if abs(k_deg_per_mm)*step_mm >= 180:
        raise ValueError('sweep step must rotate less than 180 degrees')
    lo, hi = mesh.bounds[:, 2]
    z0, height = lo-step_mm, hi-lo+2*step_mm
    sections = max(1, math.ceil(height/step_mm))
    cs = mf.CrossSection([profile])
    cutter = cs.rotate(k_deg_per_mm*z0).extrude(height, n_divisions=sections-1,
              twist_degrees=k_deg_per_mm*height).translate((0, 0, z0))
    solid = to_solid(mesh)
    return [from_solid(solid ^ cutter.rotate((0, 0, i*360/count))) for i in range(count)]


def measure_states(meshes, displacements, k_deg_per_mm, progress_values, overlap_tolerance_mm3):
    """Full solid pair intersections include complete containment; no proxy collision mesh."""
    from motion import screw_pose
    solids = [to_solid(mesh) for mesh in meshes]
    progress_values = list(progress_values)
    if len(solids) < 2 or len(solids) != len(displacements) or not progress_values:
        raise ValueError('at least two solids, one displacement per solid and nonempty progress required')
    if not math.isfinite(overlap_tolerance_mm3) or overlap_tolerance_mm3 < 0:
        raise ValueError('nonnegative finite volume tolerance required')
    from itertools import combinations
    from pose_math import axis_pose
    from solid_samples import sample_solids
    named = dict(enumerate(solids,1))
    def samples():
        for progress in progress_values:
            poses = {}
            for index,displacement in enumerate(displacements,1):
                z,angle = screw_pose(displacement,progress,k_deg_per_mm)
                poses[index] = axis_pose((0,0,0),(0,0,1),math.radians(angle),z)
            yield dict(value=progress,poses=poses)
    measured = sample_solids(named,samples(),combinations(named,2),
                             tolerance=overlap_tolerance_mm3,absolute_volume=True)
    return [dict(progress=row['value'],pair_checks=row['pair_checks'],max_overlap_mm3=row['max_overlap_mm3'],
                 collisions=[dict(parts=[hit['a'],hit['b']],overlap_mm3=hit['volume_mm3']) for hit in row['collisions']],
                 bounds_mm=row['bounds_mm'],dimensions_mm=row['dimensions_mm']) for row in measured['samples']]
