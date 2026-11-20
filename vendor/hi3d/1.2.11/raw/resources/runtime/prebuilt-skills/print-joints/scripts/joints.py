"""Pure millimetre geometry for calibrated PIP ball joints, not anatomy detection."""
from dataclasses import dataclass
import math

import manifold3d as mf
import numpy as np


@dataclass(frozen=True)
class BallSpec:
    radius_mm: float
    gap_mm: float
    wall_mm: float
    stem_radius_mm: float
    stem_length_mm: float
    mouth_radius_mm: float
    lip_margin_mm: float
    # Optional paired rear access features; local +Y points out of the back.
    rear_flat_mm: float | None = None
    rear_port_radius_mm: float | None = None
    segments: int = 96

    @property
    def outer_mm(self):
        return self.radius_mm + self.gap_mm + self.wall_mm

    @property
    def lip_mm(self):
        return math.sqrt((self.radius_mm + self.gap_mm) ** 2
                         - self.mouth_radius_mm ** 2) + self.lip_margin_mm

    def validate(self):
        values = [self.radius_mm, self.gap_mm, self.wall_mm,
                  self.stem_radius_mm, self.stem_length_mm,
                  self.mouth_radius_mm, self.lip_margin_mm]
        if not all(math.isfinite(v) and v > 0 for v in values):
            raise ValueError("Joint lengths must be finite and positive millimetres")
        if not self.stem_radius_mm + self.gap_mm < self.mouth_radius_mm < self.radius_mm:
            raise ValueError("Require stem + gap < mouth < ball radius")
        if not self.lip_mm < self.outer_mm < self.stem_length_mm:
            raise ValueError("Require lip < outer radius < stem length")
        if not isinstance(self.segments, int) or self.segments < 32 or self.segments % 4:
            raise ValueError("segments must be a multiple of four, at least 32")
        if (self.rear_flat_mm is None) != (self.rear_port_radius_mm is None):
            raise ValueError("Rear flat and port must be supplied together")
        if self.rear_flat_mm is not None:
            flat, port = self.rear_flat_mm, self.rear_port_radius_mm
            if not (math.isfinite(flat) and 0 < flat < self.radius_mm
                    and math.isfinite(port) and 0 < port < self.radius_mm):
                raise ValueError("Rear flat and port must lie inside the ball radius")
            if port + self.lip_margin_mm >= self.lip_mm:
                raise ValueError("Rear port must remain below the retaining lip")
        return self


def unit(vector):
    value = np.asarray(vector, dtype=float)
    if value.shape != (3,) or not np.isfinite(value).all() or np.linalg.norm(value) == 0:
        raise ValueError("Expected a finite nonzero 3-vector")
    return value / np.linalg.norm(value)


def joint_frame(center_mm, distal_axis, rear_hint):
    """3x4 rigid transform; +Z distal, +Y rear projected perpendicular to +Z."""
    center = np.asarray(center_mm, dtype=float)
    if center.shape != (3,) or not np.isfinite(center).all():
        raise ValueError("Expected a finite joint center")
    z_axis, rear = unit(distal_axis), unit(rear_hint)
    y_axis = rear - np.dot(rear, z_axis) * z_axis
    if np.linalg.norm(y_axis) < 1e-8:
        raise ValueError("Rear hint is parallel to the joint axis")
    y_axis = unit(y_axis)
    return np.column_stack((np.cross(y_axis, z_axis), y_axis, z_axis, center))


def require_solid(solid, label):
    """Fail on empty, invalid, inward or disconnected physical parts."""
    if (solid.status() != mf.Error.NoError or solid.is_empty()
            or solid.volume() <= 0 or len(solid.decompose()) != 1):
        raise ValueError(f"{label}: expected one nonempty closed positive solid")
    return solid


def ball_tools(spec):
    """Return socket, ball+stem, parent cutter, child cutter in local coordinates."""
    spec.validate()
    r, g, outer = spec.radius_mm, spec.gap_mm, spec.outer_mm
    sphere = lambda radius: mf.Manifold.sphere(radius, spec.segments)
    cylinder = lambda height, radius: mf.Manifold.cylinder(
        height, radius, radius, spec.segments)
    outer_sphere = sphere(outer)
    shell = outer_sphere.trim_by_plane([0, 0, -1], -spec.lip_mm)
    cavity = sphere(r + g)
    opening = cylinder(spec.stem_length_mm + outer, spec.mouth_radius_mm)
    front_relief = sphere(outer + g).trim_by_plane([0, 0, 1], spec.lip_mm)
    parent_cutter = cavity + opening + front_relief
    ball = sphere(r)
    if spec.rear_flat_mm is not None:
        ball = ball.trim_by_plane([0, -1, 0], -spec.rear_flat_mm)
        # Starts at the center, inside the cavity; opens to the rear exterior.
        rear_port = cylinder(2 * outer, spec.rear_port_radius_mm).rotate([-90, 0, 0])
        parent_cutter = parent_cutter + rear_port
    stem = cylinder(spec.stem_length_mm, spec.stem_radius_mm)
    return {
        "socket": require_solid(shell - parent_cutter, "socket"),
        "ball_stem": require_solid(ball + stem, "ball and stem"),
        "parent_cutter": parent_cutter,
        "child_cutter": sphere(outer + g),
    }


def attach_ball_joint(parent, child, spec, center_mm, distal_axis, rear_hint):
    """Locally modify pre-partitioned solids; reject disconnected or overlapping output.

    This does not segment anatomy, add a stem fillet, recover UVs, measure walls,
    or certify release/capture. Caller retains source face provenance.
    """
    require_solid(parent, "input parent")
    require_solid(child, "input child")
    frame = joint_frame(center_mm, distal_axis, rear_hint)
    shapes = {name: shape.transform(frame) for name, shape in ball_tools(spec).items()}
    parent_out = require_solid((parent + shapes["socket"]) - shapes["parent_cutter"], "parent")
    child_out = require_solid((child - shapes["child_cutter"]) + shapes["ball_stem"], "child")
    if (parent_out ^ child_out).volume() > 1e-7:
        raise ValueError("Modified parts overlap; revise partition/envelopes")
    return parent_out, child_out


def pair_metrics(first, second, search_mm):
    """Exact-solid overlap and bounded min-gap query; upper bound is not exact gap."""
    require_solid(first, "first")
    require_solid(second, "second")
    if not math.isfinite(search_mm) or search_mm <= 0:
        raise ValueError("search_mm must be positive")
    overlap = float((first ^ second).volume())
    gap = float(first.min_gap(second, search_mm))
    return {"overlap_mm3": overlap, "gap_mm": gap,
            "gap_is_lower_bound": gap >= search_mm - 1e-9,
            "search_mm": search_mm}


def rotation_about(center_mm, axis, degrees):
    """Rigid transform of a part AND its descendants about a world-space anchor."""
    n = unit(axis)
    center = np.asarray(center_mm, dtype=float)
    if center.shape != (3,) or not np.isfinite(center).all() or not math.isfinite(degrees):
        raise ValueError("Non-finite rotation")
    cross = np.array([[0, -n[2], n[1]], [n[2], 0, -n[0]], [-n[1], n[0], 0]])
    angle = math.radians(degrees)
    rotation = np.eye(3) + math.sin(angle) * cross + (1 - math.cos(angle)) * (cross @ cross)
    return np.column_stack((rotation, center - rotation @ center))
