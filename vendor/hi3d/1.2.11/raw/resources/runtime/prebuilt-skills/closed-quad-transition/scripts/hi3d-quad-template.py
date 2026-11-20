import functools
import math
from collections import Counter, defaultdict

import numpy as np


def quadrangulate_polygon(points, normal):
    points = np.asarray(points, dtype=float)

    def quality(corners):
        quad = points[list(corners)]
        angles = []
        lengths = []
        for index in range(4):
            next_edge = quad[(index + 1) % 4] - quad[index]
            previous_edge = quad[(index - 1) % 4] - quad[index]
            next_length = np.linalg.norm(next_edge)
            previous_length = np.linalg.norm(previous_edge)
            if min(next_length, previous_length) < 1e-12:
                return None
            cross = np.dot(np.cross(next_edge, previous_edge), normal)
            if cross <= next_length * previous_length * 0.015:
                return None
            cosine = np.dot(next_edge, previous_edge) / (next_length * previous_length)
            angle = math.degrees(math.acos(np.clip(cosine, -1, 1)))
            if not 8 <= angle <= 172:
                return None
            angles.append(angle)
            lengths.append(next_length)
        edge_ratio = max(lengths) / min(lengths)
        if edge_ratio > 12:
            return None
        return sum((angle - 90) ** 2 for angle in angles) / 1000 + edge_ratio

    @functools.lru_cache(None)
    def solve(indices):
        if len(indices) == 2:
            return 0.0, []
        if len(indices) < 4 or len(indices) % 2:
            return None
        best = None
        for first in range(1, len(indices) - 2, 2):
            for second in range(first + 1, len(indices) - 1, 2):
                corners = (indices[0], indices[first], indices[second], indices[-1])
                cost = quality(corners)
                if cost is None:
                    continue
                results = (
                    solve(indices[:first + 1]),
                    solve(indices[first:second + 1]),
                    solve(indices[second:]),
                )
                if any(result is None for result in results):
                    continue
                total = cost + sum(result[0] for result in results)
                if best is None or total < best[0]:
                    faces = [corners] + [face for result in results for face in result[1]]
                    best = total, faces
        return best

    solution = solve(tuple(range(len(points))))
    return solution[1] if solution is not None else None


def boundary_edges(faces):
    counts = Counter()
    directions = defaultdict(list)
    for face in faces:
        if len(face) != 4 or len(set(face)) != 4:
            raise ValueError("Each face must contain four unique vertices")
        for index, first in enumerate(face):
            second = face[(index + 1) % 4]
            edge = tuple(sorted((first, second)))
            counts[edge] += 1
            directions[edge].append((first, second))
    if any(count > 2 for count in counts.values()):
        raise ValueError("Nonmanifold edge in candidate")
    for edge, directed in directions.items():
        if counts[edge] == 2 and directed[0] != directed[1][::-1]:
            raise ValueError("Inconsistent face winding")
    return {edge for edge, count in counts.items() if count == 1}


def validate_topology(faces):
    if len(faces) != 15 or tuple(faces[0]) != (16, 17, 18, 19):
        raise ValueError("Expected one center face and fourteen transition faces")
    if {vertex for face in faces for vertex in face} != set(range(24)):
        raise ValueError("Candidate must use exactly twenty-four vertices")
    expected_outer = {tuple(sorted((index, (index + 1) % 16))) for index in range(16)}
    if boundary_edges(faces) != expected_outer:
        raise ValueError("Original outer boundary changed")
    ring_edges = boundary_edges(faces[1:])
    expected_inner = {tuple(sorted((16 + index, 16 + (index + 1) % 4))) for index in range(4)}
    if ring_edges != expected_outer | expected_inner:
        raise ValueError("Transition ring has unexpected boundary edges")
    adjacency = defaultdict(set)
    for first, second in ring_edges:
        adjacency[first].add(second)
        adjacency[second].add(first)
    if any(len(neighbors) != 2 for neighbors in adjacency.values()):
        raise ValueError("Ring boundary branches or is open")
    remaining = set(adjacency)
    lengths = []
    while remaining:
        stack = [remaining.pop()]
        members = set(stack)
        while stack:
            for neighbor in adjacency[stack.pop()]:
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    members.add(neighbor)
                    stack.append(neighbor)
        lengths.append(len(members))
    if sorted(lengths) != [4, 16]:
        raise ValueError("Expected two independent closed boundary loops")
    return {"old_faces": 16, "new_faces": 15, "coarse_center_faces": 1,
            "transition_faces": 14, "closed_loop_lengths": sorted(lengths)}


def build_template(grid_points, normal):
    expected = {(horizontal, vertical) for horizontal in range(5) for vertical in range(5)}
    if set(grid_points) != expected:
        raise ValueError("Expected the complete 5 by 5 grid mapping")
    grid = {key: np.asarray(value, dtype=float) for key, value in grid_points.items()}
    if any(value.shape != (3,) or not np.isfinite(value).all() for value in grid.values()):
        raise ValueError("Grid coordinates must be finite three-dimensional vectors")
    normal = np.asarray(normal, dtype=float)
    if normal.shape != (3,) or not np.isfinite(normal).all():
        raise ValueError("Normal must be a finite three-dimensional vector")
    normal_length = np.linalg.norm(normal)
    if not np.isfinite(normal_length) or normal_length <= 0:
        raise ValueError("Normal must have a nonzero finite length")
    normal = normal / normal_length
    origin = grid[(0, 0)].copy()
    step = np.linalg.norm(grid[(1, 0)] - origin)
    if not np.isfinite(step) or step <= 0:
        raise ValueError("Grid step must have a nonzero finite length")
    normalized = {key: (value - origin) / step for key, value in grid.items()}
    outer_keys = [(horizontal, 0) for horizontal in range(5)]
    outer_keys += [(4, vertical) for vertical in range(1, 5)]
    outer_keys += [(horizontal, 4) for horizontal in range(3, -1, -1)]
    outer_keys += [(0, vertical) for vertical in range(3, 0, -1)]
    kept_keys = outer_keys + [(1, 1), (3, 1), (3, 3), (1, 3)]
    coordinates = [normalized[key] for key in kept_keys]
    radial_indices = (1, 6, 9, 14)
    offsets = (0.3, -0.3, 0.3, -0.3)
    for index, radial_index in enumerate(radial_indices):
        first = coordinates[radial_index]
        second = coordinates[16 + index]
        tangent = np.cross(normal, second - first)
        tangent_length = np.linalg.norm(tangent)
        if tangent_length < 1e-12:
            return None
        coordinates.append((first + second) / 2 + tangent / tangent_length * offsets[index])
    quads = [(16, 17, 18, 19)]
    for sector in range(4):
        start = radial_indices[sector]
        next_sector = (sector + 1) % 4
        length = (radial_indices[next_sector] - start) % 16
        indices = [(start + offset) % 16 for offset in range(length + 1)]
        indices.extend((20 + next_sector, 16 + next_sector, 16 + sector, 20 + sector))
        polygon_quads = quadrangulate_polygon([coordinates[index] for index in indices], normal)
        if polygon_quads is None:
            return None
        quads.extend(tuple(indices[index] for index in face) for face in polygon_quads)
    try:
        topology = validate_topology(quads)
    except ValueError:
        return None
    restored = np.asarray(coordinates) * step + origin
    restored[:20] = np.asarray([grid[key] for key in kept_keys])
    return {"coordinates": restored, "quads": quads, "topology": topology}
