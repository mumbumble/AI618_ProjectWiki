"""Write the binary files of the sample project (paper/draft.pdf, figures/lve_plot.png) with PyMuPDF."""
from pathlib import Path

import pymupdf

ROOT = Path(__file__).parent / "sample_project"

PAPER = [
    ("EmoTalk-Lite: Emotion-Controllable Speech-Driven 3D Facial Animation with Diffusion",
     "Abstract. We present a diffusion model that generates FLAME expression coefficients from speech and a "
     "discrete emotion label. A lip-sync loss keeps mouth shapes accurate and an emotion consistency loss keeps "
     "the requested emotion recognizable. Compared with FaceFormer and EMOTE, our model reaches 3.78 mm lip "
     "vertex error with 68.9% emotion recognition accuracy."),
    ("1. Method",
     "Audio is encoded by a frozen wav2vec 2.0 model. A transformer denoiser, conditioned on audio features and "
     "an emotion embedding, predicts clean expression sequences (DDPM). Training combines the diffusion loss, an "
     "L2 lip-sync loss on mouth vertices, and an emotion consistency loss from a pretrained classifier."),
    ("2. Experiments",
     "Table 1 reports lip vertex error and emotion accuracy for three settings. Raising the lip-sync weight from "
     "0.5 to 1.0 lowers LVE from 4.12 to 3.71 mm. Adding the emotion loss raises emotion accuracy from 60.8% to "
     "68.9% at a small LVE cost. Figure 2 plots LVE for each setting."),
]


def make_pdf(path: Path) -> None:
    doc = pymupdf.open()
    for title, body in PAPER:
        page = doc.new_page()
        page.insert_textbox(pymupdf.Rect(60, 60, 540, 120), title, fontsize=15)
        page.insert_textbox(pymupdf.Rect(60, 130, 540, 760), body, fontsize=11)
    doc.set_metadata({"title": PAPER[0][0]})
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)


def make_plot(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=480, height=300)
    page.insert_text((150, 30), "Lip vertex error (mm) by setting", fontsize=13)
    page.draw_line((60, 260), (450, 260))
    page.draw_line((60, 260), (60, 50))
    for i, (name, lve) in enumerate([("baseline", 4.12), ("lip-sync 1.0", 3.71), ("+ emotion loss", 3.78)]):
        x = 100 + i * 120
        h = (lve - 3.0) * 150
        page.draw_rect(pymupdf.Rect(x, 260 - h, x + 60, 260), color=(0.2, 0.4, 0.7), fill=(0.3, 0.5, 0.8))
        page.insert_text((x, 280), name, fontsize=10)
        page.insert_text((x + 12, 255 - h), f"{lve:.2f}", fontsize=10)
    path.parent.mkdir(parents=True, exist_ok=True)
    page.get_pixmap(dpi=144).save(path)


if __name__ == "__main__":
    make_pdf(ROOT / "paper" / "draft.pdf")
    make_plot(ROOT / "figures" / "lve_plot.png")
    print("wrote", ROOT / "paper" / "draft.pdf", ROOT / "figures" / "lve_plot.png")
