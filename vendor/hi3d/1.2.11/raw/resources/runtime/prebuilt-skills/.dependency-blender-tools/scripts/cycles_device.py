"""Process-local Cycles device selection; no render profile or saved preferences."""
from contextlib import contextmanager

GPU_BACKENDS = ('OPTIX', 'CUDA', 'METAL', 'HIP', 'ONEAPI')


def _preferences():
    import bpy
    return bpy.context.preferences.addons['cycles'].preferences


def select_cycles_device(scene, device='CPU', *, fallback_cpu=False):
    """Return backend/devices/fallback; CPU fallback always requires explicit opt-in."""
    if device not in ('CPU', 'AUTO', *GPU_BACKENDS):
        raise ValueError('Unsupported Cycles device request')
    if device == 'CPU':
        scene.cycles.device = 'CPU'
        return {'backend': 'CPU', 'devices': [], 'fallback': False}
    prefs = _preferences()
    for backend in (GPU_BACKENDS if device == 'AUTO' else (device,)):
        try:
            prefs.compute_device_type = backend
            prefs.get_devices()
        except (RuntimeError, TypeError):
            continue
        available = [d for d in prefs.devices if d.type == backend]
        if not available:
            continue
        for d in prefs.devices:
            d.use = d.type == backend
        scene.cycles.device = 'GPU'
        return {'backend': backend, 'devices': [d.name for d in available], 'fallback': False}
    if not fallback_cpu:
        raise RuntimeError('Requested Cycles GPU backend is unavailable: ' + device)
    scene.cycles.device = 'CPU'
    reason = 'No supported GPU device detected' if device == 'AUTO' else 'Requested GPU backend unavailable: ' + device
    return {'backend': 'CPU', 'devices': [], 'fallback': True, 'reason': reason}


@contextmanager
def cycles_device_context(scene, device='CPU', *, fallback_cpu=False):
    """Restore scene device, compute backend and device-use flags on success/failure."""
    prefs = _preferences()
    old_device, old_compute = scene.cycles.device, prefs.compute_device_type
    old_use = {(d.id, d.type): d.use for d in prefs.devices}
    try:
        yield select_cycles_device(scene, device, fallback_cpu=fallback_cpu)
    finally:
        scene.cycles.device = old_device
        prefs.compute_device_type = old_compute
        # Enumeration can replace device objects or discover new ones.
        for d in prefs.devices:
            d.use = old_use.get((d.id, d.type), False)
