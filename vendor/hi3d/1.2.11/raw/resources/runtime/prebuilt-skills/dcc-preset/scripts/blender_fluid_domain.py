"""Create a Blender fluid domain. Run only inside Blender. Does not bake."""

import bpy
import sys


def output_path(argv):
    if "--" in argv:
        args = argv[argv.index("--") + 1 :]
    else:
        args = argv[1:]
    if len(args) != 1:
        raise SystemExit("expected one output .blend path")
    return args[0]


def add_domain():
    bpy.ops.mesh.primitive_cube_add(size=4, location=(0, 0, 2))
    domain = bpy.context.active_object
    domain.name = "FluidDomain"
    modifier = domain.modifiers.new("Fluid", "FLUID")
    modifier.fluid_type = "DOMAIN"
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.4, location=(0, 0, 2))
    inflow = bpy.context.active_object
    inflow.name = "FluidInflow"
    flow = inflow.modifiers.new("Fluid", "FLUID")
    flow.fluid_type = "FLOW"
    flow.flow_settings.flow_type = "LIQUID"


def main(argv):
    destination = output_path(argv)
    add_domain()
    bpy.ops.wm.save_as_mainfile(filepath=destination)


if __name__ == "__main__":
    main(sys.argv)
