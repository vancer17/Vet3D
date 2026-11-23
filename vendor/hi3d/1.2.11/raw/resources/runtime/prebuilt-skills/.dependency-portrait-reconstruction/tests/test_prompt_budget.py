"""Budget the actual sending recipes using their materialized unique sources."""
from pathlib import Path
import re
import unittest


class PromptBudgetTests(unittest.TestCase):
    def test_every_budgeted_composition_and_revision_fits_image_limit(self):
        for names, prompt in long_compositions(compact=True):
            with self.subTest(composition=names):
                self.assertLessEqual(len(prompt), 4000)
                # A representative local repair must also fit, including non-BMP text.
                revision = "\n局部修订：保持已通过的身份、姿态、材质和妆容，只调整本次失败区域；保留其他结构。🔎"
                self.assertLessEqual(len(prompt + revision), 4000)


def quoted(section):
    return "\n".join(line[2:] for line in section.splitlines() if line.startswith("> "))


def section(document, heading):
    return document.split(heading + "\n", 1)[1].split("\n## ", 1)[0]


def linked(document_path, label):
    document = document_path.read_text(encoding="utf-8")
    target = re.search(r"\[" + re.escape(label) + r"\]\(([^)]+)\)", document).group(1)
    return (document_path.parent / target).resolve()


def long_compositions(compact=False):
    recipe_path = Path(__file__).resolve().parents[1] / "references/prompts.md"
    recipe = recipe_path.read_text(encoding="utf-8")
    head = linked(recipe_path, "head-reference").read_text(encoding="utf-8")
    gray_guide = linked(recipe_path.parent / "gray-resin.md", "完整契约")
    gray = linked(gray_guide, "灰树脂提示词").read_text(encoding="utf-8")
    hair = quoted(section(recipe, "## Hi3D H 预算内等义表达" if compact else "## H. 所有模式共用、不可省略的头发质感"))
    ears = quoted(section(recipe, "## Hi3D E 预算内等义表达" if compact else "## E. 四视图耳朵位置与头发遮挡一致，不要求露耳"))
    subject = quoted(section(head, "## A. 共用主体与身份块"))
    subject = subject.replace("the agreed neck crop", "a natural short neck, with no shoulders")
    # Apply the documented A/H local-deletion exception, not contradictory full retention.
    subject = subject.replace("including the full hairstyle", "including the hairstyle except locally removed isolated fine strands")
    subject = subject.replace("all visible hair tips", "all retained visible hair tips")
    pose_section = section(head, "## B. 姿态增量：二选一")
    current, aligned = pose_section.split("### B(aligned)", 1)
    poses = {"current": quoted(current) + "\n" + re.search(r"`(Preserve the source yaw[^`]+)`", current).group(1),
             "aligned": quoted(aligned)}
    gray_paragraphs = quoted(section(gray, "## 通用正文")).split("\n")
    gray_material = "\n".join(p for p in gray_paragraphs if p.startswith(("SKIN:", "MATERIAL AND EYES:", "Soft broad")))
    gray_material = gray_material.replace(" No fragile individual eyelashes.", "")
    materials = {"colored": quoted(section(recipe, "## 彩色树脂外观增量")),
                 "natural": quoted(section(head, "## C. 外观：与姿态模式独立")),
                 "gray": gray_material}
    # Continuations retain their approved material rather than resending a transformation.
    keep_material = {"colored": quoted(section(recipe, "## 彩色树脂基准续做四视图")),
                     "natural": "Preserve the approved natural appearance, makeup and colors in every view.",
                     "gray": "Preserve the approved neutral-gray resin material, smooth skin with principal age folds, and smooth convex all-gray eyes without iris, pupil marks or highlights in every view."}
    for pose in ("aligned", "current"):
        heading = "## D(aligned). 转正四视图" if pose == "aligned" else "## D(current). 当前视角四视图"
        sheet = quoted(section(head, heading))
        if pose == "current":
            sheet += "\nArrange a 2x2 sheet: view_0 upper left, view_90 upper right, view_180 lower left, view_270 lower right. Use equal-size cells, no text, and comfortable margins."
        for material, appearance in materials.items():
            for target, blocks in (("single", (subject, hair, poses[pose], appearance)),
                                   ("anchor", (subject, hair, ears, poses[pose], appearance)),
                                   ("sheet", (sheet, hair, ears, keep_material[material]))):
                yield (target, pose, material), "\n".join(blocks)


if __name__ == "__main__":
    unittest.main()
