"""Pure millimetre geometry for single-start screw bottles; no Blender or I/O."""
from dataclasses import dataclass
import math


def finite(value, name, minimum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(name + ' must be finite')
    if minimum is not None and value < minimum:
        raise ValueError(name + ' is too small')
    return float(value)


def integer(value, name, minimum):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(name + ' must be an integer >= ' + str(minimum))
    return value


@dataclass(frozen=True)
class Thread:
    root_radius_mm: float
    depth_mm: float
    pitch_mm: float
    crest_half_mm: float
    flank_half_mm: float
    radial_clearance_mm: float
    axial_relief_mm: float
    phase_mm: float = 0.0
    hand: int = 1

    def __post_init__(self):
        for key, value in vars(self).items():
            finite(value, key)
        if self.hand not in (-1, 1):
            raise ValueError('hand must be +1 (right) or -1 (left)')
        if min(self.root_radius_mm, self.depth_mm, self.pitch_mm, self.radial_clearance_mm) <= 0:
            raise ValueError('Radius, depth, pitch and radial clearance must be positive')
        if not 0 <= self.crest_half_mm < self.flank_half_mm:
            raise ValueError('Require 0 <= crest_half_mm < flank_half_mm')
        if self.axial_relief_mm < 0 or self.flank_half_mm + self.axial_relief_mm >= self.pitch_mm / 2:
            raise ValueError('Female grooves must leave a root between adjacent turns')


def thread_radius(spec, z_mm, theta_rad, female=False):
    """Continuous radial envelope. Female grooves expand both radially and axially."""
    phase = z_mm - spec.hand * spec.pitch_mm * theta_rad / math.tau - spec.phase_mm
    distance = abs((phase + spec.pitch_mm / 2) % spec.pitch_mm - spec.pitch_mm / 2)
    if female:
        distance = max(0.0, distance - spec.axial_relief_mm)
    fraction = max(0.0, min(1.0, (spec.flank_half_mm - distance) /
                           (spec.flank_half_mm - spec.crest_half_mm)))
    return spec.root_radius_mm + spec.depth_mm * fraction + (spec.radial_clearance_mm if female else 0)


def screw_lift(pitch_mm, angle_rad, hand=1):
    """World-axis displacement paired with an angle; left-handed opening is negative rotation."""
    if finite(pitch_mm, 'pitch_mm') <= 0 or hand not in (-1, 1):
        raise ValueError('Positive pitch and hand +/-1 required')
    return hand * pitch_mm * finite(angle_rad, 'angle_rad') / math.tau


def threaded_ring(spec, low_mm, high_mm, wall_radius_mm, *, female=False,
                  segments=128, rows_per_pitch=48, lead_mm=0.0):
    """Return vertices/faces of a closed annulus on local +Z.

    wall_radius_mm is the male bore radius or female outside radius. Leads taper
    only the male tooth. Sampling density is geometric resolution, not fit proof.
    """
    for key, value in [('low_mm', low_mm), ('high_mm', high_mm), ('wall_radius_mm', wall_radius_mm), ('lead_mm', lead_mm)]:
        finite(value, key)
    integer(segments, 'segments', 16); integer(rows_per_pitch, 'rows_per_pitch', 8)
    if high_mm <= low_mm or lead_mm < 0 or 2 * lead_mm > high_mm - low_mm:
        raise ValueError('Invalid axial interval or lead length')
    if female:
        if wall_radius_mm <= spec.root_radius_mm + spec.depth_mm + spec.radial_clearance_mm:
            raise ValueError('Female outside wall must exceed the groove radius')
    elif not 0 < wall_radius_mm < spec.root_radius_mm:
        raise ValueError('Male bore must be positive and smaller than the root')
    rows = max(2, math.ceil((high_mm - low_mm) / spec.pitch_mm * rows_per_pitch) + 1)
    if 2 * rows * segments > 2_000_000:
        raise ValueError('Mesh exceeds two million vertices; reduce resolution or split the operation')
    vertices, faces = [], []
    for side in range(2):
        for j in range(rows):
            z = low_mm + (high_mm - low_mm) * j / (rows - 1)
            for i in range(segments):
                theta = math.tau * i / segments
                if (female and side == 1) or (not female and side == 0):
                    r = thread_radius(spec, z, theta, female)
                    if not female and lead_mm:
                        fade = min(1.0, (z - low_mm) / lead_mm, (high_mm - z) / lead_mm)
                        r = spec.root_radius_mm + (r - spec.root_radius_mm) * fade
                else:
                    r = wall_radius_mm
                vertices.append((r * math.cos(theta), r * math.sin(theta), z))
    offset = rows * segments
    for side in range(2):
        off = side * offset
        for j in range(rows - 1):
            for i in range(segments):
                ni = (i + 1) % segments
                face = (off + j*segments+i, off + j*segments+ni,
                        off + (j+1)*segments+ni, off + (j+1)*segments+i)
                faces.append(face if side == 0 else tuple(reversed(face)))
    for j in (0, rows - 1):
        for i in range(segments):
            ni = (i + 1) % segments
            face = (j*segments+i, offset+j*segments+i, offset+j*segments+ni, j*segments+ni)
            faces.append(tuple(reversed(face)) if j == rows - 1 else face)
    return vertices, faces


def profile_points(profile):
    """Validate a positive-radius, strictly ascending (radius_mm, z_mm) profile."""
    if not isinstance(profile, (list, tuple)) or len(profile) < 2:
        raise ValueError('A profile needs at least two levels')
    result = []
    for row in profile:
        if not isinstance(row, (list, tuple)) or len(row) != 2:
            raise ValueError('Profile rows are [radius_mm, z_mm]')
        r, z = finite(row[0], 'radius_mm'), finite(row[1], 'z_mm')
        if r <= 0 or (result and z <= result[-1][1]):
            raise ValueError('Positive radii and increasing Z required')
        result.append((r, z))
    return result


def profile_radius(profile, z_mm):
    points = profile_points(profile)
    finite(z_mm, 'z_mm')
    for (r1, z1), (r2, z2) in zip(points, points[1:]):
        if z1 <= z_mm <= z2:
            return r1 + (r2-r1) * (z_mm-z1) / (z2-z1)
    raise ValueError('Z is outside the profile')


def revolved_solid(profile, segments=128):
    """Closed negative volume for a contoured reservoir, including flat end caps."""
    points = profile_points(profile); integer(segments, 'segments', 16)
    vertices = [(r*math.cos(math.tau*i/segments), r*math.sin(math.tau*i/segments), z)
                for r, z in points for i in range(segments)]
    faces = []
    for j in range(len(points)-1):
        for i in range(segments):
            ni = (i+1) % segments
            faces.append((j*segments+i, j*segments+ni, (j+1)*segments+ni, (j+1)*segments+i))
    faces += [tuple(reversed(range(segments))), tuple((len(points)-1)*segments+i for i in range(segments))]
    return vertices, faces


def profile_volume_ml(profile, lip_z_mm):
    """Volume of the continuous profile to a chosen lip, not rated liquid capacity."""
    points = profile_points(profile); profile_radius(points, lip_z_mm)
    volume = 0.0
    for (r1, z1), (r2, z2) in zip(points, points[1:]):
        high = min(z2, lip_z_mm)
        if high <= z1:
            break
        r_end = r1 + (r2-r1)*(high-z1)/(z2-z1)
        volume += math.pi*(high-z1)*(r1*r1+r1*r_end+r_end*r_end)/3
    return volume / 1000
