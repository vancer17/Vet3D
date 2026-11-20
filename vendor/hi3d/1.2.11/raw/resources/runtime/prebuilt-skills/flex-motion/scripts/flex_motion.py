"""Auxiliary-bone inertia for flexible parts. Pure NumPy; no Blender or engine runtime."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SpringParams:
    """Starting point in seconds and meters. Calibrate per character; not a look guarantee.

    tau_return and tau_drag are time constants, so 24/30/60 fps share the same meaning.
    gravity is m/s^2 in the same coordinates as the bone tips. gravity_scale is unitless.
    """

    tau_return: float = 0.28
    tau_drag: float = 0.05
    gravity: tuple = (0.0, 0.0, -9.81)
    gravity_scale: float = 0.35
    substep: float = 1.0 / 120.0
    max_substeps: int = 16
    dt_cap: float = 0.05

    def validated(self):
        gravity = np.asarray(self.gravity, dtype=float)
        if (
            gravity.shape != (3,)
            or not np.isfinite(gravity).all()
            or self.tau_return <= 0
            or self.tau_drag <= 0
            or not np.isfinite(self.gravity_scale)
            or self.substep <= 0
            or self.max_substeps < 1
            or self.dt_cap <= 0
        ):
            raise ValueError("invalid spring parameters")
        return gravity


def _vec(value, label):
    vector = np.asarray(value, dtype=float)
    if vector.shape != (3,) or not np.isfinite(vector).all():
        raise ValueError("expected a finite 3-vector: " + label)
    return vector


def project_length(origin, point, length):
    """Return the point on the sphere around origin with the given radius."""
    start = _vec(origin, "origin")
    end = _vec(point, "point")
    if not np.isfinite(length) or length <= 0:
        raise ValueError("rest length must be positive")
    delta = end - start
    dist = float(np.linalg.norm(delta))
    if dist < 1e-8:
        raise ValueError("tip collapsed onto the bone head")
    return start + delta / dist * float(length)


def push_capsules(point, capsules):
    """Push a point out of capsules once. A point on the axis is left unchanged.

    Each capsule is {start, end, radius}. One push can be undone by a later
    length projection; callers must record remaining penetration.
    """
    current = _vec(point, "point")
    degenerate = 0
    for capsule in capsules:
        start = _vec(capsule["start"], "capsule start")
        end = _vec(capsule["end"], "capsule end")
        radius = float(capsule["radius"])
        if not np.isfinite(radius) or radius <= 0:
            raise ValueError("capsule radius must be positive")
        axis = end - start
        length2 = float(np.dot(axis, axis))
        if length2 < 1e-12:
            closest = start
        else:
            t = float(np.dot(current - start, axis) / length2)
            t = min(1.0, max(0.0, t))
            closest = start + axis * t
        delta = current - closest
        dist = float(np.linalg.norm(delta))
        if dist >= radius:
            continue
        if dist < 1e-8:
            degenerate += 1
            continue
        current = closest + delta / dist * radius
    return current, degenerate


def step_tip(tip, velocity, target, origin, rest_length, dt, params, capsules=()):
    """Advance one bone tip. dt of 0 does not move. Large gaps are capped, not simulated.

    Returns tip, velocity, and a report with substeps, dt_clamped and degenerate.
    """
    tip = _vec(tip, "tip")
    velocity = _vec(velocity, "velocity")
    target = _vec(target, "target")
    origin = _vec(origin, "origin")
    if not isinstance(params, SpringParams):
        raise TypeError("params must be SpringParams")
    gravity = params.validated() * float(params.gravity_scale)
    if not np.isfinite(dt) or dt < 0 or not np.isfinite(rest_length) or rest_length <= 0:
        raise ValueError("invalid dt or rest length")
    if dt == 0:
        return tip.copy(), velocity.copy(), {"substeps": 0, "dt_clamped": False, "degenerate": 0}
    clamped = bool(dt > params.dt_cap)
    dt = min(float(dt), float(params.dt_cap))
    count = max(1, min(int(params.max_substeps), int(np.ceil(dt / params.substep))))
    step = dt / count
    degenerate = 0
    for _ in range(count):
        velocity = velocity * np.exp(-step / params.tau_drag)
        pull = 1.0 - np.exp(-step / params.tau_return)
        predicted = tip + velocity * step + (target - tip) * pull + gravity * (step * step)
        predicted, misses = push_capsules(predicted, capsules)
        degenerate += misses
        predicted = project_length(origin, predicted, rest_length)
        velocity = (predicted - tip) / step
        tip = predicted
        if not np.isfinite(tip).all() or not np.isfinite(velocity).all():
            raise ValueError("spring step became non-finite")
    return tip, velocity, {"substeps": count, "dt_clamped": clamped, "degenerate": degenerate}


def should_reset(previous_origin, origin, distance):
    """True when the bone head jumped farther than distance, such as a teleport."""
    if not np.isfinite(distance) or distance < 0:
        raise ValueError("reset distance must be finite and nonnegative")
    delta = _vec(origin, "origin") - _vec(previous_origin, "previous origin")
    return bool(np.linalg.norm(delta) > distance)


def blend_auxiliary(base, mask, auxiliary):
    """Scale existing weights by the remaining influence and add auxiliary weights.

    mask is 0 on protected vertices and increases toward free ends. Rows with mask 0
    keep the baseline weights exactly and receive no auxiliary influence.
    """
    base = np.asarray(base, dtype=float)
    auxiliary = np.asarray(auxiliary, dtype=float)
    mask = np.asarray(mask, dtype=float)
    if (
        base.ndim != 2
        or auxiliary.ndim != 2
        or mask.shape != (base.shape[0],)
        or auxiliary.shape[0] != base.shape[0]
        or not base.shape[1]
        or not auxiliary.shape[1]
        or not np.isfinite(base).all()
        or not np.isfinite(auxiliary).all()
        or not np.isfinite(mask).all()
        or np.any(base < 0)
        or np.any(auxiliary < 0)
        or np.any(mask < 0)
        or np.any(mask > 1)
        or not np.allclose(base.sum(1), 1, atol=2e-4, rtol=0)
        or not np.allclose(auxiliary.sum(1), 1, atol=2e-4, rtol=0)
    ):
        raise ValueError("expected normalized weights and a mask in 0..1")
    kept = base * (1.0 - mask[:, None])
    added = auxiliary * mask[:, None]
    combined = np.concatenate([kept, added], axis=1)
    if not np.allclose(combined.sum(1), 1, atol=2e-4, rtol=0):
        raise ValueError("blended weights are not normalized")
    return combined


def limit_influences(weights, max_influences):
    """Keep the strongest influences per row, then renormalize. Fewer influences stay."""
    weights = np.asarray(weights, dtype=float)
    if (
        weights.ndim != 2
        or not weights.shape[0]
        or not weights.shape[1]
        or not np.isfinite(weights).all()
        or np.any(weights < 0)
        or not isinstance(max_influences, int)
        or max_influences < 1
    ):
        raise ValueError("expected nonnegative weights and a positive influence limit")
    if weights.shape[1] <= max_influences:
        return weights.copy()
    limited = weights.copy()
    drop = np.argpartition(limited, -max_influences, axis=1)[:, :-max_influences]
    rows = np.arange(len(limited))[:, None]
    limited[rows, drop] = 0
    totals = limited.sum(1, keepdims=True)
    if np.any(totals <= 1e-12):
        raise ValueError("influence limit removed every weight")
    limited /= totals
    return limited


def limit_flexible_rows(weights, mask, max_influences):
    """Limit influences only where the flexible mask is positive."""
    weights = np.asarray(weights, dtype=float)
    mask = np.asarray(mask, dtype=float)
    if mask.shape != (weights.shape[0],):
        raise ValueError("mask length must match vertices")
    limited = weights.copy()
    chosen = mask > 0
    if np.any(chosen):
        limited[chosen] = limit_influences(weights[chosen], max_influences)
    if not np.array_equal(limited[~chosen], weights[~chosen]):
        raise ValueError("protected rows changed")
    return limited


def restore_rows(current, baseline, protected):
    """Copy baseline weights back onto protected vertices of the same topology."""
    current = np.asarray(current, dtype=float)
    baseline = np.asarray(baseline, dtype=float)
    protected = np.asarray(protected, dtype=bool)
    if current.shape != baseline.shape or protected.shape != (current.shape[0],):
        raise ValueError("restore requires matching topology and a vertex mask")
    if not np.isfinite(current).all() or not np.isfinite(baseline).all():
        raise ValueError("weights must be finite")
    restored = current.copy()
    restored[protected] = baseline[protected]
    return restored
