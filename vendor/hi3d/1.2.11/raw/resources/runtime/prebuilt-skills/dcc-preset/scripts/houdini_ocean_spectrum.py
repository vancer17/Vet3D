"""Create a HIP containing the built-in Ocean Spectrum SOP. Does not cache."""

import sys


def output_path(argv):
    args = [item for item in argv[1:] if item != "--"]
    if len(args) != 1:
        raise SystemExit("expected one output .hip path")
    return args[0]


def main(argv):
    import hou

    destination = output_path(argv)
    category = hou.sopNodeTypeCategory()
    if category.nodeType("oceanspectrum") is None:
        raise SystemExit("this Houdini has no oceanspectrum SOP")
    container = hou.node("/obj").createNode("geo", "ocean_preset")
    spectrum = container.createNode("oceanspectrum", "ocean_spectrum")
    spectrum.setDisplayFlag(True)
    spectrum.setRenderFlag(True)
    container.layoutChildren()
    hou.hipFile.save(destination)


if __name__ == "__main__":
    main(sys.argv)
