"""Génère l'icône 512×512 et l'image de présentation 1024×500 de la fiche Play Store (Pillow). Usage : python tests/e2e/store_assets.py"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[2] / "docs" / "store"; OUT.mkdir(parents=True, exist_ok=True)
BRAND, DARK, REC, WHITE = (31, 58, 95), (20, 40, 68), (217, 45, 32), (255, 255, 255)

def font(size, bold=True):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"):
        if Path(p).exists(): return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def mic(d, cx, cy, h, color=WHITE, bg=BRAND):
    w = h * 0.42
    d.rounded_rectangle([cx - w / 2, cy - h / 2, cx + w / 2, cy + h * 0.1], radius=w / 2, fill=color)           # capsule
    lw = max(2, int(h * 0.07))
    d.arc([cx - w * 0.85, cy - h * 0.32, cx + w * 0.85, cy + h * 0.32], 0, 180, fill=color, width=lw)           # arceau
    d.line([cx, cy + h * 0.32, cx, cy + h * 0.5], fill=color, width=lw)
    d.line([cx - w * 0.5, cy + h * 0.5, cx + w * 0.5, cy + h * 0.5], fill=color, width=lw)

def icon(size=512):
    im = Image.new("RGB", (size, size), BRAND); d = ImageDraw.Draw(im)
    mic(d, size / 2, size * 0.46, size * 0.52)
    d.ellipse([size * 0.70, size * 0.12, size * 0.86, size * 0.28], fill=REC)                                  # voyant d'enregistrement
    return im

icon().save(OUT / "icone-512.png")

fg = Image.new("RGB", (1024, 500), BRAND); d = ImageDraw.Draw(fg)
for y in range(500):                                                                                           # dégradé vertical sobre
    t = y / 500; d.line([(0, y), (1024, y)], fill=tuple(int(BRAND[i] * (1 - t) + DARK[i] * t) for i in range(3)))
ic = icon(300).convert("RGB"); mask = Image.new("L", (300, 300), 0); ImageDraw.Draw(mask).rounded_rectangle([0, 0, 299, 299], 60, fill=255)
fg.paste(ic, (90, 100), mask)
d.text((430, 130), "GMeeting", font=font(84), fill=WHITE)
d.text((432, 240), "Vos réunions, comptes rendus", font=font(36, False), fill=(220, 230, 245))
d.text((432, 290), "prêts à envoyer. Chez vous.", font=font(36, False), fill=(220, 230, 245))
d.text((432, 380), "PV · CR · Synthèse · Word · PDF · Excel · PowerPoint", font=font(20, False), fill=(170, 190, 220))
fg.save(OUT / "banniere-1024x500.png")
print("ok", sorted(p.name for p in OUT.iterdir()))
