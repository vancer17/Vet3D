"""Write a proportional humanoid T-pose seed. Fit it to the actual model before use."""

import argparse
import json
from pathlib import Path


def profile():
    bones = []

    def bone(name, head, tail, parent=None, deform=True):
        bones.append(
            dict(
                name=name,
                head=head,
                tail=tail,
                parent=parent,
                deform=deform,
                roll_axis=[0, -1, 0],
            )
        )

    bone("root", [0, 0, 0], [0, 0, 0.08], deform=False)
    bone("BODY_RIGID", [0, -0.011, 0.55], [0, -0.011, 0.835], "root")
    bone("head", [0, -0.017, 0.835], [0, -0.017, 0.94], "BODY_RIGID")
    regions = []
    rules = []
    mapping = {"BODY_RIGID": "Hips", "head": "Head"}
    for side, sign, word in [("L", 1, "Left"), ("R", -1, "Right")]:
        shoulder, elbow, wrist = (
            [sign * 0.111, -0.007, 0.790],
            [sign * 0.247, -0.007, 0.792],
            [sign * 0.392, -0.013, 0.792],
        )
        bone("upper_arm." + side, shoulder, elbow, "BODY_RIGID")
        bone("forearm." + side, elbow, wrist, "upper_arm." + side)
        bone("hand." + side, wrist, [sign * 0.469, -0.013, 0.791], "forearm." + side)
        hip, knee, ankle = (
            [sign * 0.0556, -0.010, 0.55],
            [sign * 0.048, -0.022, 0.333],
            [sign * 0.0544, -0.014, 0.072],
        )
        bone("thigh." + side, hip, knee, "BODY_RIGID")
        bone("shin." + side, knee, ankle, "thigh." + side)
        bone("foot." + side, ankle, [sign * 0.0556, -0.089, 0.022], "shin." + side)
        for a, b in [
            ("upper_arm", "Arm"),
            ("forearm", "ForeArm"),
            ("hand", "Hand"),
            ("thigh", "UpLeg"),
            ("shin", "Leg"),
            ("foot", "Foot"),
        ]:
            mapping[a + "." + side] = word + b
        xmin, xmax = (0.09, 0.6) if sign == 1 else (-0.6, -0.09)
        regions.append(
            dict(
                bounds=[[xmin, -0.3, 0.72], [xmax, 0.3, 0.85]],
                axis=0,
                sign=sign,
                bones=[
                    "BODY_RIGID",
                    "upper_arm." + side,
                    "forearm." + side,
                    "hand." + side,
                ],
                transitions=[[0.111, 0.017], [0.247, 0.015], [0.392, 0.011]],
            )
        )
        legmin, legmax = (0, 0.2) if sign == 1 else (-0.2, 0)
        regions.append(
            dict(
                bounds=[[legmin, -0.3, 0], [legmax, 0.3, 0.565]],
                axis=2,
                sign=-1,
                bones=["BODY_RIGID", "thigh." + side, "shin." + side, "foot." + side],
                transitions=[[-0.55, 0.022], [-0.333, 0.019], [-0.072, 0.017]],
            )
        )
        for label, low, high in [
            ("UpperArm", 0.111, 0.247),
            ("Forearm", 0.247, 0.392),
            ("Hand", 0.392, 0.60),
        ]:
            lo, hi = (low, high) if sign == 1 else (-high, -low)
            rules.append(
                dict(
                    name=label + "." + side, bounds=[[lo, -0.3, 0.72], [hi, 0.3, 0.85]]
                )
            )
        for label, low, high in [
            ("Thigh", 0.333, 0.55),
            ("Shin", 0.072, 0.333),
            ("Foot", 0, 0.072),
        ]:
            rules.append(
                dict(
                    name=label + "." + side,
                    bounds=[[legmin, -0.3, low], [legmax, 0.3, high]],
                )
            )
    regions.append(
        dict(
            bounds=[[-0.1, -0.2, 0.81], [0.1, 0.2, 1.1]],
            axis=2,
            bones=["BODY_RIGID", "head"],
            transitions=[[0.835, 0.014]],
        )
    )
    rules.append(dict(name="Head", bounds=[[-0.1, -0.2, 0.845], [0.1, 0.2, 1.1]]))
    return dict(
        calibrated=False,
        coordinates="fractions of normalized character height",
        fps=30,
        bones=bones,
        default_bone="BODY_RIGID",
        default_part="Body",
        weight_regions=regions,
        part_rules=rules,
        rigid_parts={},
        motion_map=mapping,
        animations=[],
        provenance=[],
        solver=dict(radius=0.0194, fidelity_length=0.0139, edge_floor=0.0000167),
    )


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args(argv)
    if a.output.exists():
        raise ValueError("Refusing to overwrite an existing calibration")
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(profile(), indent=2))
    print("Wrote uncalibrated humanoid seed; fit landmarks and regions before building")


if __name__ == "__main__":
    main()
