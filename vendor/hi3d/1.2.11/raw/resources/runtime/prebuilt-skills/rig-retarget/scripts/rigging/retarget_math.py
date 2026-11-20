"""Rest-aware rotations and fixed-length limb solving; no Blender scene mutation."""

import math
import numpy as np
from mathutils import Matrix, Quaternion, Vector


def rigid_matrices(values, label):
    a = np.asarray(values, dtype=np.float64)
    if a.shape[-2:] != (4, 4) or not np.isfinite(a).all():
        raise ValueError(label + ": expected finite 4x4 matrices")
    r = a[..., :3, :3]
    if (
        not np.allclose(a[..., 3, :], [0, 0, 0, 1], atol=2e-5)
        or not np.allclose(np.swapaxes(r, -1, -2) @ r, np.eye(3), atol=2e-4)
        or not np.allclose(np.linalg.det(r), 1, atol=2e-4)
    ):
        raise ValueError(
            label + ": scale, shear or reflection needs an explicit adapter"
        )
    return a


def hierarchy(names, parents):
    if len(set(names)) != len(names) or len(parents) != len(names):
        raise ValueError("Unique bone names and matching parents required")
    for i, p in enumerate(parents):
        if not isinstance(p, (int, np.integer)) or not -1 <= p < i:
            raise ValueError("Parents must precede children, with -1 for roots")


def unit_quaternion(value):
    a = np.asarray(value, dtype=float)
    if a.shape != (4,) or not np.isfinite(a).all() or np.linalg.norm(a) < 1e-9:
        raise ValueError("Expected nonzero finite wxyz quaternion")
    return Quaternion(a / np.linalg.norm(a))


def chain_scale(source_rest, target_rest, source_chain, target_chain):
    if len(source_chain) != len(target_chain) or len(source_chain) < 2:
        raise ValueError("Corresponding chains of at least two joints required")

    def length(rest, chain):
        return sum(
            (rest[b].translation - rest[a].translation).length
            for a, b in zip(chain, chain[1:])
        )

    a, b = length(source_rest, source_chain), length(target_rest, target_chain)
    if min(a, b) < 1e-8:
        raise ValueError("Degenerate scale chain")
    return b / a


def two_bone_ik(hip, goal, length_a, length_b, pole):
    """Return knee, clamped ankle and reach error; never stretch either bone."""
    hip, goal, pole = Vector(hip), Vector(goal), Vector(pole)
    if (
        min(length_a, length_b) <= 0
        or not np.isfinite([*hip, *goal, *pole, length_a, length_b]).all()
    ):
        raise ValueError("Finite points and positive limb lengths required")
    v = goal - hip
    if v.length < 1e-10:
        raise ValueError("IK target coincides with hip; choose an explicit fallback")
    axis = v.normalized()
    epsilon = min(length_a, length_b) * 1e-6
    distance = min(
        max(v.length, abs(length_a - length_b) + epsilon), length_a + length_b - epsilon
    )
    bend = pole - axis * pole.dot(axis)
    if bend.length < 1e-8:
        raise ValueError("IK pole is parallel to limb; calibrate a stable bend plane")
    bend.normalize()
    projection = (length_a**2 + distance**2 - length_b**2) / (2 * distance)
    radius = math.sqrt(max(0, length_a**2 - projection**2))
    return (
        hip + axis * projection + bend * radius,
        hip + axis * distance,
        abs(v.length - distance),
    )


def forward_heads(names, parents, rest, desired, root, root_position):
    positions = {}
    for i, n in enumerate(names):
        p = names[parents[i]] if parents[i] >= 0 else None
        if p:
            positions[n] = positions[p] + desired[p] @ rest[
                p
            ].to_quaternion().inverted() @ (rest[n].translation - rest[p].translation)
        else:
            positions[n] = (
                Vector(root_position) if n == root else rest[n].translation.copy()
            )
    return positions


def retarget_samples(source, target, spec):
    """Arrays + calibrated mapping -> local wxyz rotations/root locations and diagnostics.

    All output translations are in target rig units. Source object motion must
    already be baked in the cache. Does not modify any input arrays or a scene.
    """
    if spec.get("calibrated") is not True:
        raise ValueError("Inspect this character and mark its mapping calibrated")
    sn, sp = list(source["names"]), list(source["parents"])
    tn, tp = list(target["names"]), list(target["parents"])
    hierarchy(sn, sp)
    hierarchy(tn, tp)
    sr = rigid_matrices(source["rest"], "source rest")
    poses = rigid_matrices(source["poses"], "source poses")
    tr = rigid_matrices(target["rest"], "target rest")
    if (
        sr.shape != (len(sn), 4, 4)
        or tr.shape != (len(tn), 4, 4)
        or poses.ndim != 4
        or poses.shape[1:] != sr.shape
        or not len(poses)
    ):
        raise ValueError("Cache dimensions do not match skeletons")
    basis = rigid_matrices(spec.get("source_to_target", np.eye(4)), "source_to_target")
    if basis.shape != (4, 4):
        raise ValueError("source_to_target must be one rigid transform")
    sr = basis @ sr
    poses = basis @ poses
    S = {n: Matrix(sr[i].tolist()) for i, n in enumerate(sn)}
    T = {n: Matrix(tr[i].tolist()) for i, n in enumerate(tn)}
    sq = {n: m.to_quaternion() for n, m in S.items()}
    tq = {n: m.to_quaternion() for n, m in T.items()}
    rows = spec["mapping"]
    si = {n: i for i, n in enumerate(sn)}
    if not rows or any(n not in T or row["source"] not in S for n, row in rows.items()):
        raise ValueError("Mapping references missing bones")
    root_spec = spec["root"]
    root = root_spec["target"]
    source_root = root_spec["source"]
    if root not in T or source_root not in S or tp[tn.index(root)] != -1:
        raise ValueError("Root translation requires a real unparented target root bone")
    scale = chain_scale(S, T, root_spec["source_chain"], root_spec["target_chain"])
    offsets = Vector(root_spec.get("offset", [0, 0, 0]))
    if not np.isfinite(offsets).all():
        raise ValueError("Nonfinite root offset")
    align = {}
    for n, row in rows.items():
        mode = row.get("mode", "global")
        if mode not in ["global", "local"]:
            raise ValueError("Mapping mode must be global or local")
        if "alignment_wxyz" in row:
            align[n] = unit_quaternion(row["alignment_wxyz"])
        elif "target_end" in row and "source_end" in row:
            tv = T[row["target_end"]].translation - T[n].translation
            sv = S[row["source_end"]].translation - S[row["source"]].translation
            if min(tv.length, sv.length) < 1e-8:
                raise ValueError("Degenerate alignment endpoints")
            align[n] = tv.normalized().rotation_difference(sv.normalized())
        else:
            align[n] = Quaternion()
        if mode == "local" and sp[si[row["source"]]] < 0:
            raise ValueError("Local mapping requires a source parent")
    limbs = spec.get("limbs", [])
    for limb in limbs:
        a, b, c = limb["target_chain"]
        x, y, z = limb["source_chain"]
        if any(n not in T for n in [a, b, c]) or any(n not in S for n in [x, y, z]):
            raise ValueError("Missing limb joint")
        if tp[tn.index(b)] != tn.index(a) or tp[tn.index(c)] != tn.index(b):
            raise ValueError("Target limb must be a direct three-joint chain")
        if sp[sn.index(y)] != sn.index(x) or sp[sn.index(z)] != sn.index(y):
            raise ValueError("Source limb must be a direct three-joint chain")
        unit = np.asarray(limb.get("pole", [0, 0, 0]), float)
        if (
            unit.shape != (3,)
            or not np.isfinite(unit).all()
            or np.linalg.norm(unit) < 1e-8
        ):
            raise ValueError("Calibrated fallback pole required")
        sole = np.asarray(limb.get("sole_points", []), float)
        if sole.size and (
            sole.ndim != 2
            or sole.shape[1] != 3
            or not np.isfinite(sole).all()
            or not math.isfinite(float(limb["floor_z"]))
        ):
            raise ValueError("Finite sole points and floor_z required")
    output = np.zeros((len(poses), len(tn), 4), np.float32)
    locations = np.zeros((len(poses), 3), np.float32)
    previous = {}
    max_reach = 0.0
    for f, frame in enumerate(poses):
        P = {n: Matrix(frame[i].tolist()) for i, n in enumerate(sn)}
        pq = {n: m.to_quaternion() for n, m in P.items()}
        desired = {}
        for i, n in enumerate(tn):
            p = tn[tp[i]] if tp[i] >= 0 else None
            neutral = desired[p] @ tq[p].inverted() @ tq[n] if p else tq[n]
            if n not in rows:
                desired[n] = neutral
                continue
            row = rows[n]
            s = row["source"]
            A = align[n]
            if row.get("mode", "global") == "global":
                desired[n] = pq[s] @ sq[s].inverted() @ A @ tq[n]
            else:
                parent_s = sn[sp[si[s]]]
                source_local_rest = sq[parent_s].inverted() @ sq[s]
                source_local_pose = pq[parent_s].inverted() @ pq[s]
                delta = source_local_rest.inverted() @ source_local_pose
                conversion = tq[n].inverted() @ A.inverted() @ sq[s]
                desired[n] = neutral @ conversion @ delta @ conversion.inverted()
        parent_relative = {}
        for i, n in enumerate(tn):
            if n not in rows or rows[n].get("mode") == "local":
                p = tn[tp[i]] if tp[i] >= 0 else None
                parent_relative[n] = (
                    desired[p].inverted() @ desired[n] if p else desired[n].copy()
                )
        raw_displacement = (
            P[source_root].translation - S[source_root].translation
        ) * scale
        displacement = raw_displacement.copy()
        if root_spec.get("in_place", False):
            displacement.x = displacement.y = 0
        root_position = T[root].translation + displacement + offsets
        motion_offset = displacement - raw_displacement + offsets
        positions = forward_heads(tn, tp, T, desired, root, root_position)
        solved = set()
        for limb in limbs:
            a, b, c = limb["target_chain"]
            x, y, z = limb["source_chain"]
            goal = (
                T[c].translation
                + (P[z].translation - S[z].translation) * scale
                + motion_offset
            )
            sole = np.asarray(limb.get("sole_points", []), float)
            if len(sole):
                rotation = np.asarray((desired[c] @ tq[c].inverted()).to_matrix())
                low = float(
                    (
                        (sole - np.asarray(T[c].translation)) @ rotation.T
                        + np.asarray(goal)
                    )[:, 2].min()
                )
                lift = (
                    max(0, (P[z].translation.z - S[z].translation.z) * scale)
                    if limb.get("preserve_flight", True)
                    else 0
                )
                goal.z += max(0, float(limb["floor_z"]) + lift - low)
            axis = goal - positions[a]
            pole = P[y].translation - P[x].translation
            if (
                axis.length < 1e-10
                or (pole - axis.normalized() * pole.dot(axis.normalized())).length
                < 1e-7
            ):
                pole = Vector(limb["pole"])
            knee, ankle, error = two_bone_ik(
                positions[a],
                goal,
                (T[b].translation - T[a].translation).length,
                (T[c].translation - T[b].translation).length,
                pole,
            )
            max_reach = max(max_reach, error)
            for n, nextn, origin, end in [
                (a, b, positions[a], knee),
                (b, c, knee, ankle),
            ]:
                current = (
                    desired[n]
                    @ tq[n].inverted()
                    @ (T[nextn].translation - T[n].translation)
                )
                desired[n] = (
                    current.normalized().rotation_difference(
                        (end - origin).normalized()
                    )
                    @ desired[n]
                )
                solved.add(n)
            # Preserve local joint increments below changed IK parents. Global
            # mappings retain their explicitly requested absolute orientation.
            for i, n in enumerate(tn):
                if n in parent_relative and n not in solved:
                    p = tn[tp[i]] if tp[i] >= 0 else None
                    desired[n] = (
                        desired[p] @ parent_relative[n] if p else parent_relative[n]
                    )
            positions = forward_heads(tn, tp, T, desired, root, root_position)
        for i, n in enumerate(tn):
            p = tn[tp[i]] if tp[i] >= 0 else None
            q = (
                tq[n].inverted()
                @ (tq[p] @ desired[p].inverted() if p else Quaternion())
                @ desired[n]
            )
            q.normalize()
            if n in previous and q.dot(previous[n]) < 0:
                q.negate()
            output[f, i] = q
            previous[n] = q.copy()
        locations[f] = tq[root].inverted() @ (root_position - T[root].translation)
    return (
        output,
        locations,
        {
            "scale": scale,
            "max_limb_reach_error": max_reach,
            "frames": len(poses),
            "root": root,
        },
    )
