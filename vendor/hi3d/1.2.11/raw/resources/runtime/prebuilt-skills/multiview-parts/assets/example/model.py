"""Neutral module-contract example. Replace with geometry derived from the task references."""


def build(ctx):
    housing = ctx.part("housing", "外壳")
    ctx.box("housing-shell", (0, 0, 0.75), (1.6, 1.0, 1.5), "shell", housing, bevel=0.05)
    ctx.box("housing-trim", (0, -0.51, 0.9), (0.7, 0.06, 0.3), "trim", housing, bevel=0.015)
    cover = ctx.part("cover", "盖板")
    ctx.box("cover-panel", (0, 0, 0.12), (1.6, 1.0, 0.24), "shell", cover, bevel=0.025)
