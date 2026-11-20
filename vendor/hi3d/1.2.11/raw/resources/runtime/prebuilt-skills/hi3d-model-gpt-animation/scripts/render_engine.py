"""Resolve renderer identifiers against the running Blender, without version guesses."""


def engine_identifier(requested, available):
    """EEVEE aliases resolve to the installed identifier; unsupported engines fail."""
    available = set(available)
    if requested in {'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'}:
        for candidate in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
            if candidate in available:
                return candidate
    elif requested in available:
        return requested
    raise ValueError('Renderer is unavailable: ' + requested)


def set_engine(scene, requested='BLENDER_EEVEE'):
    """Set one scene's engine using its runtime enum and return the actual identifier."""
    # Add-on renderers such as Cycles may not appear in the static RNA list.
    # Blender's setter validates their dynamically registered identifiers.
    if requested not in {'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'}:
        scene.render.engine = requested
        return scene.render.engine
    items = scene.render.bl_rna.properties['engine'].enum_items
    actual = engine_identifier(requested, [item.identifier for item in items])
    scene.render.engine = actual
    return actual


def set_samples(scene, count):
    """Set samples only when the selected renderer exposes a sample control."""
    if type(count) is not int or count <= 0:
        raise ValueError('Samples must be a positive integer')
    if scene.render.engine == 'CYCLES':
        scene.cycles.samples = count
    elif hasattr(scene, 'eevee') and hasattr(scene.eevee, 'taa_render_samples'):
        scene.eevee.taa_render_samples = count
    else:
        return None
    return count
