"""Rendu PowerPoint (.pptx) : présentation standard ou illustrée.

Tout est généré sans ressource externe (confidentialité, hors-ligne) :
  * pictogrammes : formes vectorielles PowerPoint groupées → modifiables et recolorables dans PowerPoint ;
  * images : visuels d'ouverture générés (Pillow) aux couleurs du gabarit ;
  * graphiques : objets graphiques natifs (données modifiables dans PowerPoint).
Le gabarit (logo, couleur, en-tête, pied de page, confidentialité) est appliqué comme pour les autres exports.
"""
from __future__ import annotations

import io
import math
from typing import Any

from pptx import Presentation
from . import labels
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt
from lxml import etree


W, H = 13.333, 7.5
LM, RM = 0.6, 12.733          # marges gauche / droite (pouces)
FONT = "Calibri"


# ------------------------------------------------------------------ couleurs
def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _mix(h1: str, h2: str, t: float) -> str:
    a, b = _hex_to_rgb(h1), _hex_to_rgb(h2)
    return "".join(f"{round(a[i] + (b[i] - a[i]) * t):02X}" for i in range(3))


def _lum(h: str) -> float:
    r, g, b = (v / 255 for v in _hex_to_rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def palette(primary: str) -> dict[str, str]:
    p = primary.upper()
    # texte posé sur la couleur principale : blanc, sauf couleur de marque très claire
    onp = "FFFFFF" if _lum(p) < 0.55 else "1C2430"
    return {"p": p, "dark": _mix(p, "000000", 0.38), "light": _mix(p, "FFFFFF", 0.90), "mid": _mix(p, "FFFFFF", 0.62),
            "onp": onp, "ink": "1C2430", "mute": "5F6B7A", "line": "D9DFE8", "bg": "F4F6FA", "white": "FFFFFF",
            "green": "2E9E5B", "green_l": "E3F4EA", "amber": "D98A00", "amber_l": "FCF1DB",
            "red": "D64545", "red_l": "FBE5E5", "purple": "7B5EA7", "purple_l": "EDE7F6"}


def _rgb(h: str) -> RGBColor:
    return RGBColor.from_string(h)


# ------------------------------------------------------------------ texte
def _lines(par: str, w_in: float, pt: float) -> int:
    cpl = max(1, int(w_in * 72 / (pt * 0.50)))
    return max(1, math.ceil(len(par) / cpl))


def fit_pt(paras: list[str], w_in: float, h_in: float, max_pt: float, min_pt: float, gap_pt: float = 0, lh: float = 1.2) -> float:
    pt = max_pt
    while pt >= min_pt:
        total = sum(_lines(p, w_in, pt) * pt * lh + gap_pt for p in paras)
        if total / 72 <= h_in:
            return pt
        pt -= 1
    return min_pt


def _bullet(p, color: str, marl: float = 0.28, char: str = "•") -> None:
    pPr = p._p.get_or_add_pPr()
    pPr.set("marL", str(int(Inches(marl)))); pPr.set("indent", str(-int(Inches(marl))))
    for tag in ("a:buClr", "a:buFont", "a:buChar"):
        for el in pPr.findall(qn(tag)):
            pPr.remove(el)
    buClr = etree.SubElement(pPr, qn("a:buClr")); etree.SubElement(buClr, qn("a:srgbClr")).set("val", color)
    etree.SubElement(pPr, qn("a:buFont")).set("typeface", "Arial")
    etree.SubElement(pPr, qn("a:buChar")).set("char", char)


def text(shapes, x, y, w, h, paras, size=18, color="1C2430", bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
         bullet: str | None = None, gap_pt: float = 0, italic: bool = False):
    """paras : str | list[str | (str, dict)] — le dict peut surcharger size/color/bold."""
    tb = shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    items = [paras] if isinstance(paras, (str, tuple)) else paras
    for i, it in enumerate(items):
        t, o = (it if isinstance(it, tuple) else (it, {}))
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = o.get("align", align)
        if gap_pt and i:
            p.space_before = Pt(gap_pt)
        r = p.add_run(); r.text = t
        f = r.font; f.name = FONT; f.size = Pt(o.get("size", size)); f.bold = o.get("bold", bold); f.italic = italic
        f.color.rgb = _rgb(o.get("color", color))
        if bullet or o.get("bullet"):
            _bullet(p, o.get("bullet_color", color if not o.get("bullet") else o["bullet"]), char="•")
    return tb


def _alpha(shape, pct: float) -> None:
    clr = shape.fill._xPr.find(qn("a:solidFill"))[0]
    for el in clr.findall(qn("a:alpha")):
        clr.remove(el)
    etree.SubElement(clr, qn("a:alpha")).set("val", str(int(pct * 1000)))


def _flat(sh) -> None:
    """Retire le style de thème hérité (ombre/relief) : rendu plat identique dans PowerPoint, LibreOffice, Keynote…"""
    sh.shadow.inherit = False
    st = sh._element.find(qn("p:style"))
    if st is not None:
        sh._element.remove(st)


def rect(shapes, x, y, w, h, fill: str | None, line: str | None = None, radius: float = 0, lw: float = 0.75, oval=False):
    kind = MSO_SHAPE.OVAL if oval else (MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE)
    sh = shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    if fill:
        sh.fill.solid(); sh.fill.fore_color.rgb = _rgb(fill)
    else:
        sh.fill.background()
    if line:
        sh.line.color.rgb = _rgb(line); sh.line.width = Pt(lw)
    else:
        sh.line.fill.background()
    _flat(sh)
    if radius and not oval:
        sh.adjustments[0] = min(0.5, radius / min(w, h))
    return sh


# ------------------------------------------------------------------ pictogrammes (formes vectorielles groupées)
def _glyph_table():
    """Chaque pictogramme dessine sur une grille 0..1000 : P(polygone), C(cercle), B(rectangle), T(texte), bg=couleur du badge."""
    def check(P, C, B, T, bg, fg):
        C(500, 500, 500, fg); P([(260, 540), (340, 460), (440, 560), (670, 300), (750, 380), (440, 730)], bg)

    def target(P, C, B, T, bg, fg):
        C(500, 500, 500, fg); C(500, 500, 380, bg); C(500, 500, 270, fg); C(500, 500, 150, bg); C(500, 500, 60, fg)

    def people(P, C, B, T, bg, fg):
        C(330, 280, 150, fg); C(690, 330, 125, fg)
        B(110, 500, 440, 380, fg, shape=MSO_SHAPE.ROUND_2_SAME_RECTANGLE); B(530, 540, 360, 340, fg, shape=MSO_SHAPE.ROUND_2_SAME_RECTANGLE)

    def calendar(P, C, B, T, bg, fg):
        B(90, 170, 820, 740, fg, rad=70); B(160, 400, 680, 440, bg, rad=30)
        B(270, 70, 80, 200, fg, rad=40); B(650, 70, 80, 200, fg, rad=40)
        for r in range(2):
            for c in range(3):
                B(220 + c * 200, 450 + r * 180, 130, 110, fg, rad=20)

    def action(P, C, B, T, bg, fg):
        C(500, 500, 500, fg); P([(240, 420), (520, 420), (520, 260), (790, 500), (520, 740), (520, 580), (240, 580)], bg)

    def warning(P, C, B, T, bg, fg):
        P([(500, 80), (960, 880), (40, 880)], fg); B(455, 360, 90, 290, bg, rad=40); C(500, 740, 52, bg)

    def bulb(P, C, B, T, bg, fg):
        C(500, 390, 300, fg); P([(340, 560), (660, 560), (610, 740), (390, 740)], fg)
        B(380, 770, 240, 70, fg, rad=35); B(455, 330, 90, 300, bg, rad=40)

    def budget(P, C, B, T, bg, fg):
        C(500, 500, 500, fg); T("€", bg)

    def shield(P, C, B, T, bg, fg):
        pts = [(500, 40), (900, 190), (900, 480)]
        for k in range(1, 12):
            a = math.pi / 2 * k / 11
            pts.append((int(500 + 400 * math.cos(a)), int(480 + 480 * math.sin(a))))
        pts += [(int(500 - (x - 500)), y) for x, y in reversed(pts[3:])] + [(100, 480), (100, 190)]
        P(pts, fg); P([(300, 480), (380, 400), (460, 480), (640, 290), (720, 370), (460, 640)], bg)

    def gear(P, C, B, T, bg, fg):
        pts = []
        for k in range(8):
            for da, r in ((-12, 0.36), (-8, 0.5), (8, 0.5), (12, 0.36)):
                a = math.radians(k * 45 + da)
                pts.append((int(500 + 1000 * r * math.cos(a)), int(500 + 1000 * r * math.sin(a))))
        P(pts, fg); C(500, 500, 320, fg); C(500, 500, 150, bg)

    def chat(P, C, B, T, bg, fg):
        B(70, 130, 860, 590, fg, rad=120); P([(220, 700), (220, 920), (470, 700)], fg)
        for i in range(3):
            C(300 + i * 200, 425, 55, bg)

    def doc(P, C, B, T, bg, fg):
        P([(190, 60), (620, 60), (830, 270), (830, 940), (190, 940)], fg)
        for i in range(4):
            B(300, 400 + i * 120, 430 if i < 3 else 260, 55, bg, rad=25)
        P([(620, 60), (620, 270), (830, 270)], bg)

    def chart(P, C, B, T, bg, fg):
        B(110, 560, 210, 340, fg); B(395, 360, 210, 540, fg); B(680, 130, 210, 770, fg)

    def question(P, C, B, T, bg, fg):
        C(500, 500, 500, fg); T("?", bg)

    def flag(P, C, B, T, bg, fg):
        B(190, 80, 80, 850, fg, rad=30); P([(270, 110), (860, 110), (700, 310), (860, 510), (270, 510)], fg)

    def clock(P, C, B, T, bg, fg):
        C(500, 500, 500, fg); C(500, 500, 390, bg); B(470, 230, 60, 300, fg, rad=30); B(470, 470, 240, 60, fg, rad=30)

    return {"decision": check, "objectif": target, "equipe": people, "planning": calendar, "action": action,
            "risque": warning, "idee": bulb, "budget": budget, "securite": shield, "technique": gear,
            "communication": chat, "juridique": doc, "qualite": chart, "question": question, "jalon": flag, "horloge": clock}


_GLYPHS = _glyph_table()


def icon(shapes, name: str, x: float, y: float, d: float, badge: str, glyph: str, badge_ring: str | None = None) -> None:
    """Pictogramme = pastille ronde (couleur `badge`) + glyphe (couleur `glyph`), regroupés en un seul objet."""
    g = shapes.add_group_shape()
    sh = g.shapes
    rect(sh, x, y, d, d, badge, line=badge_ring, oval=True, lw=1.5)
    inner = d * 0.56
    ox, oy = x + (d - inner) / 2, y + (d - inner) / 2
    scale = Inches(inner) / 1000

    def P(pts, color=glyph):
        fb = sh.build_freeform(int(pts[0][0]), int(pts[0][1]), scale=scale)
        fb.add_line_segments([(int(a), int(b)) for a, b in pts[1:]], close=True)
        s = fb.convert_to_shape(Inches(ox), Inches(oy))
        s.fill.solid(); s.fill.fore_color.rgb = _rgb(color); s.line.fill.background(); _flat(s)

    def C(cx, cy, r, color=glyph):
        rect(sh, ox + inner * (cx - r) / 1000, oy + inner * (cy - r) / 1000, inner * 2 * r / 1000, inner * 2 * r / 1000, color, oval=True)

    def B(bx, by, bw, bh, color=glyph, rad=0, shape=None):
        if shape is not None:
            s = sh.add_shape(shape, Inches(ox + inner * bx / 1000), Inches(oy + inner * by / 1000), Inches(inner * bw / 1000), Inches(inner * bh / 1000))
            s.fill.solid(); s.fill.fore_color.rgb = _rgb(color); s.line.fill.background(); _flat(s)
            try:
                s.adjustments[0] = 0.5
            except Exception:
                pass
            return
        rect(sh, ox + inner * bx / 1000, oy + inner * by / 1000, inner * bw / 1000, inner * bh / 1000, color,
             radius=(inner * rad / 1000) if rad else 0)

    def T(txt, color):
        text(sh, x, y + d * 0.08, d, d * 0.84, txt, size=max(8, d * 72 * 0.52), color=color, bold=True,
             align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)

    _GLYPHS.get(name, _GLYPHS["objectif"])(P, C, B, T, badge, glyph)
    g.name = f"Pictogramme {name}"


# ------------------------------------------------------------------ images générées
def _gradient(w: int, h: int, c1: str, c2: str, diagonal: bool = True):
    from PIL import Image, ImageOps
    base = Image.linear_gradient("L")                       # 256x256, noir → blanc de haut en bas
    v = base.resize((w, h))
    if diagonal:
        hz = base.rotate(90).resize((w, h))                 # horizontal
        v = Image.blend(v, hz, 0.5)
    return ImageOps.colorize(v, "#" + c1, "#" + c2).convert("RGBA")


def art_cover(w: int, h: int, p: dict[str, str]) -> bytes:
    """Visuel d'ouverture : dégradé de marque, grands anneaux et trame de points (généré, sans ressource externe)."""
    from PIL import Image, ImageDraw
    img = _gradient(w, h, p["dark"], p["p"])
    k = 2
    layer = Image.new("RGBA", (w * k, h * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = int(w * k * 0.80), int(h * k * 0.48)
    for i, r in enumerate((250, 380, 520, 680, 860)):
        r *= k * h // 900
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(255, 255, 255, 70 - i * 10), width=3 * k)
    r0 = 150 * k * h // 900
    d.ellipse((cx - r0, cy - r0, cx + r0, cy + r0), fill=(255, 255, 255, 40))
    step = 46 * k
    for gx in range(int(w * k * 0.56), w * k, step):
        for gy in range(int(h * k * 0.64), h * k, step):
            d.ellipse((gx - 4 * k, gy - 4 * k, gx + 4 * k, gy + 4 * k), fill=(255, 255, 255, 60))
    img = Image.alpha_composite(img, layer.resize((w, h), Image.LANCZOS)).convert("RGB")
    buf = io.BytesIO(); img.save(buf, "JPEG", quality=88, optimize=True)
    return buf.getvalue()


def art_panel(w: int, h: int, p: dict[str, str], seed: int = 0) -> bytes:
    """Bandeau vertical des diapositives de sujet : variations de position des anneaux selon le sujet."""
    from PIL import Image, ImageDraw
    img = _gradient(w, h, p["dark"], p["p"], diagonal=True)
    k = 2
    layer = Image.new("RGBA", (w * k, h * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx = int(w * k * (0.15 + 0.7 * ((seed * 37) % 100) / 100))
    cy = int(h * k * (0.55 + 0.35 * ((seed * 53) % 100) / 100))
    for i, r in enumerate((180, 300, 440, 600)):
        r *= k * w // 640
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(255, 255, 255, 60 - i * 10), width=3 * k)
    img = Image.alpha_composite(img, layer.resize((w, h), Image.LANCZOS)).convert("RGB")
    buf = io.BytesIO(); img.save(buf, "JPEG", quality=88, optimize=True)
    return buf.getvalue()


# ------------------------------------------------------------------ rendu
TONES = {"primary": ("p", "light"), "green": ("green", "green_l"), "red": ("red", "red_l"),
         "amber": ("amber", "amber_l"), "purple": ("purple", "purple_l")}


class Deck:
    def __init__(self, brand: dict[str, Any], visual: bool, title: str, total: int):
        self.b, self.visual, self.total = brand, visual, total
        self.c = palette(brand["color"])
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = Inches(W), Inches(H)
        self.prs.core_properties.title = title
        self.prs.core_properties.author = brand["org_name"] or "GMeeting"
        self.n = 0
        self.has_head = bool(brand["logo"] or brand["header_right"])
        self.footer_text = brand["footer"] or title

    # --- ossature commune
    def new(self, bg: str | None = None):
        s = self.prs.slides.add_slide(self.prs.slide_layouts[6])
        s.background.fill.solid(); s.background.fill.fore_color.rgb = _rgb(bg or self.c["white"])
        self.n += 1
        return s

    def logo(self, sh, x: float, y: float, height: float, max_w: float, on_dark: bool = False):
        """Logo ; sur fond sombre il est posé sur une pastille blanche pour rester lisible."""
        lw, lh = self.b["logo_size"]
        h = height; w = h * lw / lh
        if w > max_w:
            w, h = max_w, max_w * lh / lw
        if on_dark:
            rect(sh, x - 0.14, y - 0.12, w + 0.28, h + 0.24, "FFFFFF", radius=0.12)
        pic = sh.add_picture(io.BytesIO(self.b["logo"]), Inches(x), Inches(y), Inches(w), Inches(h))
        pic._element.nvPicPr.cNvPr.set("descr", f"Logo {self.b['org_name']}".strip())
        return w

    def chrome(self, s, left: float = LM, dark: bool = False, header: bool = True):
        sh, c = s.shapes, self.c
        muted = "FFFFFF" if dark else c["mute"]
        conf = 2.7 if self.b["confidential"] else 0
        text(sh, left, 7.02, (RM - 1.3) - left - conf - 0.2, 0.3, self.footer_text[:110], size=10, color=muted)
        text(sh, RM - 1.2, 7.02, 1.2, 0.3, f"{self.n} / {self.total}", size=10, color=muted, align=PP_ALIGN.RIGHT)
        if self.b["confidential"]:   # à gauche du numéro de page : ne chevauche jamais le pied de page
            text(sh, RM - 1.3 - conf, 7.02, conf, 0.3, self.b["confidential"], size=10, color=c["red"] if not dark else "FFFFFF", bold=True, align=PP_ALIGN.RIGHT)
        if header and self.has_head:
            y = 0.34
            if self.b["logo"]:
                self.logo(sh, RM - 1.9, y, 0.5, 1.9)
                y += 0.58
            if self.b["header_right"]:
                text(sh, RM - 3.6, y, 3.6, 0.25, self.b["header_right"], size=10, color=c["mute"], align=PP_ALIGN.RIGHT)

    def title_w(self) -> float:
        return (RM - LM) - (2.4 if self.has_head else 0)

    def title(self, s, t: str, ic: str | None = None):
        sh, c = s.shapes, self.c
        w = self.title_w()
        if self.visual:
            icon(sh, ic or "objectif", LM, 0.42, 0.78, c["p"], c["onp"])
            pt = fit_pt([t], w - 1.0, 0.8, 32, 20)
            text(sh, LM + 1.0, 0.42, w - 1.0, 0.78, t, size=pt, bold=True, color=c["ink"], anchor=MSO_ANCHOR.MIDDLE)
        else:
            pt = fit_pt([t], w, 0.75, 32, 20)
            text(sh, LM, 0.38, w, 0.75, t, size=pt, bold=True, color=c["p"], anchor=MSO_ANCHOR.MIDDLE)
            rect(sh, LM, 1.2, 1.1, 0.055, c["p"])

    # --- layouts
    def cover(self, d: dict):
        s = self.new(self.c["white"]); sh, c = s.shapes, self.c
        if self.visual:
            pic = sh.add_picture(io.BytesIO(art_cover(1600, 900, c)), 0, 0, self.prs.slide_width, self.prs.slide_height)
            pic._element.nvPicPr.cNvPr.set("descr", labels.tr("Visuel décoratif aux couleurs de l'organisation", self.b.get("_lang", "fr")))
            if self.b["logo"]:
                self.logo(sh, 0.9, 0.7, 0.7, 2.6, on_dark=True)
            elif self.b["org_name"]:
                text(sh, 0.9, 0.75, 6, 0.5, self.b["org_name"], size=18, bold=True, color="FFFFFF")
            text(sh, 0.9, 2.2, 8.2, 0.4, d["subtitle"].upper(), size=15, bold=True, color=self.c["mid"] if _lum(c["p"]) < 0.55 else "FFFFFF")
            pt = fit_pt([d["title"]], 8.2, 2.4, 46, 28, lh=1.15)
            text(sh, 0.9, 2.7, 8.2, 2.4, d["title"], size=pt, bold=True, color="FFFFFF", anchor=MSO_ANCHOR.TOP)
            y = 5.35
            for k, v in d["meta"]:
                ic = "planning" if k == "Date" else "objectif"
                icon(sh, ic, 0.9, y, 0.5, "FFFFFF", c["p"])
                text(sh, 1.55, y, 6.5, 0.5, v, size=17, color="FFFFFF", anchor=MSO_ANCHOR.MIDDLE)
                y += 0.62
            if self.b["confidential"]:
                rect(sh, 0.9, 6.95 - 0.04, 2.3, 0.36, c["red"], radius=0.18)
                text(sh, 0.9, 6.95 - 0.04, 2.3, 0.36, self.b["confidential"], size=11, bold=True, color="FFFFFF", align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        else:
            rect(sh, 0, 0, 8.6, H, c["p"])
            rect(sh, 8.6, 0, W - 8.6, H, c["light"])
            text(sh, 0.8, 2.0, 7.0, 0.4, d["subtitle"].upper(), size=14, bold=True, color=c["onp"])
            pt = fit_pt([d["title"]], 7.2, 2.6, 42, 26, lh=1.15)
            text(sh, 0.8, 2.5, 7.2, 2.6, d["title"], size=pt, bold=True, color=c["onp"])
            x = 9.1
            if self.b["logo"]:
                self.logo(sh, x, 0.8, 0.9, 3.2)
            elif self.b["org_name"]:
                text(sh, x, 0.85, 3.6, 0.6, self.b["org_name"], size=18, bold=True, color=c["p"])
            y = 3.0
            for k, v in d["meta"]:
                text(sh, x, y, 3.6, 0.28, k.upper(), size=10, bold=True, color=c["mute"])
                hgt = 0.35 if k != "Objet" else 1.5
                text(sh, x, y + 0.28, 3.6, hgt, v, size=fit_pt([v], 3.6, hgt, 15, 10), color=c["ink"])
                y += 0.28 + hgt + 0.2
            if self.b["org_name"] and self.b["logo"]:
                text(sh, x, 6.7, 3.6, 0.3, self.b["org_name"], size=11, color=c["mute"])
            if self.b["confidential"]:
                text(sh, x, 7.02, 3.6, 0.3, self.b["confidential"], size=10, bold=True, color=c["red"])

    def bullets(self, d: dict):
        s = self.new(); sh, c = s.shapes, self.c
        self.title(s, d["title"], d.get("icon"))
        y, hh = 1.55, 5.25
        paras = []
        if d.get("paragraph"):
            ph = hh * (0.55 if d["items"] else 1.0)
            paras = [p for p in d["paragraph"].split("\n\n") if p.strip()] or [d["paragraph"]]    # paragraphes distincts (courriels, extraits)
            pt = fit_pt(paras, RM - LM, ph, 30 if len(paras) == 1 else 22, 12, gap_pt=10)
            text(sh, LM, y, RM - LM, ph, paras, size=pt, color=c["ink"], gap_pt=10)
            if d["items"]:
                y += hh * 0.55 + 0.1; hh = hh * 0.45 - 0.1
            else:
                y = None
        if y is not None and d["items"]:
            pt = fit_pt(d["items"], RM - LM - 0.3, hh, 28, 13, gap_pt=12)
            text(sh, LM, y, RM - LM, hh, d["items"], size=pt, color=c["ink"], bullet="•", gap_pt=12)
        self.chrome(s)

    def topic(self, d: dict):
        c = self.c
        s = self.new(); sh = s.shapes
        if d.get("notes"):
            s.notes_slide.notes_text_frame.text = d["notes"]
        if not self.visual:
            self.title(s, d["title"])
            y, bottom = 1.55, 6.85
            sec = ([("pos", 1.45)] if d["bullets"] else []) + ([("dec", 1.35)] if d["decisions"] else [])
            # le résumé prend la hauteur dont il a besoin (borné) ; les sections suivent juste en dessous
            cap = 3.4 if not sec else 2.7
            pt = fit_pt([d["summary"]], RM - LM, cap, 28, 13)
            need = min(cap, _lines(d["summary"], RM - LM, pt) * pt * 1.2 / 72 + 0.15)
            text(sh, LM, y, RM - LM, need, d["summary"], size=pt, color=c["ink"])
            y += need + 0.3
            tot = sum(w for _, w in sec) or 1
            for name, wt in sec:
                hh = min(wt * (bottom - y) / tot, 2.4) - 0.12
                label, items, col = (d["bullets_label"] or labels.tr("Points", self.b.get("_lang", "fr")), d["bullets"], c["p"]) if name == "pos" else (labels.tr("Décisions", self.b.get("_lang", "fr")), d["decisions"], c["green"])
                rect(sh, LM, y + 0.04, 0.07, hh - 0.04, col)
                text(sh, LM + 0.25, y, 4, 0.3, label.upper(), size=12, bold=True, color=col)
                pt2 = fit_pt(items, RM - LM - 0.6, hh - 0.35, 22, 12, gap_pt=5)
                text(sh, LM + 0.25, y + 0.33, RM - LM - 0.3, hh - 0.35, items, size=pt2, color=c["ink"], bullet="•", gap_pt=5)
                y += hh + 0.12
            self.chrome(s)
            return
        # illustrée : bandeau gauche (image + pictogramme) / contenu à droite
        pw = 4.3
        pic = sh.add_picture(io.BytesIO(art_panel(640, 1120, c, d["number"])), 0, 0, Inches(pw), self.prs.slide_height)
        pic._element.nvPicPr.cNvPr.set("descr", labels.tr("Visuel décoratif", self.b.get("_lang", "fr")))
        icon(sh, d["icon"], pw / 2 - 0.95, 1.2, 1.9, "FFFFFF", c["p"])
        text(sh, 0.5, 3.45, pw - 1.0, 0.3, f"POINT {d['number']}", size=13, bold=True, color="FFFFFF", align=PP_ALIGN.CENTER)
        pt = fit_pt([d["title"]], pw - 1.0, 2.4, 28, 16, lh=1.15)
        text(sh, 0.5, 3.85, pw - 1.0, 2.6, d["title"], size=pt, bold=True, color="FFFFFF", align=PP_ALIGN.CENTER)
        x0, w = pw + 0.6, RM - pw - 0.6
        pt = fit_pt([d["summary"]], w, 1.9, 30, 15)
        text(sh, x0, 0.9, w, 2.0, d["summary"], size=pt, bold=True, color=c["ink"], anchor=MSO_ANCHOR.TOP)
        y = 3.15
        if d["bullets"]:
            hh = 2.35 if d["decisions"] else 3.3
            pt = fit_pt(d["bullets"], w - 0.3, hh, 24, 13, gap_pt=10)
            text(sh, x0, y, w, hh, d["bullets"], size=pt, color=c["ink"], bullet="•", gap_pt=10)
            y += hh + 0.1
        for dec in d["decisions"][:2]:
            rect(sh, x0, y, w, 0.62, c["green_l"], radius=0.1)
            icon(sh, "decision", x0 + 0.12, y + 0.09, 0.44, c["green"], "FFFFFF")
            text(sh, x0 + 0.72, y, w - 0.85, 0.62, dec, size=fit_pt([dec], w - 0.85, 0.6, 17, 10), bold=True, color=c["ink"], anchor=MSO_ANCHOR.MIDDLE)
            y += 0.72
        self.chrome(s, left=x0, header=False)
        # logo discret en haut à droite du contenu
        if self.has_head and self.b["logo"]:
            self.logo(sh, RM - 1.6, 0.3, 0.4, 1.6)

    def cards(self, d: dict):
        s = self.new(self.c["bg"]); sh, c = s.shapes, self.c
        self.title(s, d["title"], d.get("icon"))
        items = d["items"]; n = len(items)
        cols = 1 if n == 1 else 2 if n in (2, 4) else 3
        rows = math.ceil(n / cols)
        gx, gy = 0.3, 0.3
        x0, aw, ah = LM, RM - LM, 5.2
        cw = (aw - gx * (cols - 1)) / cols
        ch = (ah - gy * (rows - 1)) / rows
        if rows == 1:                      # peu d'éléments : cartes compactes, pas des pans de blanc
            ch = min(ch, 3.3 if cols <= 2 else 3.9)
        y0 = 1.65 if rows > 1 else 1.65 + (ah - ch) * 0.18
        col, light = TONES.get(d.get("tone", "primary"), TONES["primary"])
        horizontal = cols <= 2
        t_cap, d_cap = ({1: (30, 22), 2: (26, 19)}[cols]) if horizontal else (21, 16)
        for i, it in enumerate(items):
            x, y = x0 + (i % cols) * (cw + gx), y0 + (i // cols) * (ch + gy)
            rect(sh, x, y, cw, ch, "FFFFFF", line=c["line"])
            rect(sh, x, y, cw, 0.09, c[col])
            has_chip = bool(it.get("chip"))
            chip_area = (0.34 + 0.25) if has_chip else 0.25
            if horizontal:
                icon(sh, it["icon"], x + 0.3, y + 0.38, 0.85, c[col], "FFFFFF")
                tx, tw = x + 1.4, cw - 1.7
                avail = ch - 0.38 - chip_area
                th, dh = (avail * 0.5, avail * 0.5 - 0.1) if it.get("detail") else (avail, 0)
                text(sh, tx, y + 0.38, tw, th, it["title"], size=fit_pt([it["title"]], tw, th, t_cap, 12), bold=True, color=c["ink"])
                if it.get("detail"):
                    text(sh, tx, y + 0.38 + th + 0.1, tw, dh, it["detail"], size=fit_pt([it["detail"]], tw, dh, d_cap, 11), color=c["mute"])
            else:
                # 3 colonnes : pictogramme à gauche du titre (plus compact), résumé dessous, étiquette en bas : rien ne se chevauche
                icon(sh, it["icon"], x + 0.25, y + 0.32, 0.66, c[col], "FFFFFF")
                tx, tw = x + 1.1, cw - 1.1 - 0.25
                if it.get("detail"):
                    th = 0.85
                    text(sh, tx, y + 0.28, tw, th, it["title"], size=fit_pt([it["title"]], tw, th, 18, 11), bold=True, color=c["ink"])
                    dh = ch - 1.25 - chip_area
                    text(sh, x + 0.25, y + 1.25, cw - 0.5, dh, it["detail"], size=fit_pt([it["detail"]], cw - 0.5, dh, 15, 10), color=c["mute"])
                else:
                    th = ch - 0.28 - chip_area
                    text(sh, tx, y + 0.28, tw, th, it["title"], size=fit_pt([it["title"]], tw, th, t_cap, 11), bold=True, color=c["ink"])
            if has_chip:
                cwid = min(cw - 0.6, 0.3 + len(it["chip"]) * 0.115)
                cy = y + ch - 0.34 - 0.22
                rect(sh, x + 0.3, cy, cwid, 0.34, c[light], radius=0.17)
                text(sh, x + 0.3, cy, cwid, 0.34, it["chip"], size=12, bold=True, color=c[col], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        self.chrome(s)

    def kpis(self, d: dict):
        s = self.new(self.c["bg"]); sh, c = s.shapes, self.c
        self.title(s, d["title"], d["icon"])
        tiles, extra = d["tiles"], d["extra"]
        y = 1.65
        if tiles:
            n = len(tiles); gap = 0.3; w = (RM - LM - gap * (n - 1)) / n; h = 2.35
            for i, t in enumerate(tiles):
                x = LM + i * (w + gap)
                rect(sh, x, y, w, h, "FFFFFF", line=c["line"]); rect(sh, x, y, 0.09, h, c["p"])
                icon(sh, t["icon"], x + 0.3, y + 0.3, 0.7, c["p"], c["onp"])
                text(sh, x + 0.3, y + 1.0, w - 0.5, 0.85, t["value"], size=54, bold=True, color=c["p"], anchor=MSO_ANCHOR.MIDDLE)
                text(sh, x + 0.3, y + 1.85, w - 0.5, 0.4, t["label"], size=17, color=c["mute"])
            y += h + 0.3
        if extra:
            n = len(extra); gap = 0.3; w = (RM - LM - gap * (n - 1)) / n; h = 1.15
            for i, t in enumerate(extra):
                x = LM + i * (w + gap)
                rect(sh, x, y, w, h, c["light"], radius=0.1)
                vw = w * 0.5
                text(sh, x + 0.2, y, vw, h, t["value"], size=fit_pt([t["value"]], vw, 0.9, 30, 16), bold=True, color=c["p"], anchor=MSO_ANCHOR.MIDDLE)
                text(sh, x + 0.2 + vw + 0.1, y, w - vw - 0.5, h, t["label"], size=fit_pt([t["label"]], w - vw - 0.5, h - 0.2, 14, 10), color=c["ink"], anchor=MSO_ANCHOR.MIDDLE)
            y += h + 0.3
        if d.get("highlight"):
            hh = min(max(0.8, 6.85 - y), 2.0)
            rect(sh, LM, y, 0.08, hh, c["p"])
            text(sh, LM + 0.3, y, RM - LM - 0.3, hh, d["highlight"], size=fit_pt([d["highlight"]], RM - LM - 0.3, hh, 24, 12), color=c["ink"], anchor=MSO_ANCHOR.MIDDLE, italic=True)
        self.chrome(s)

    def people(self, d: dict):
        s = self.new(self.c["bg"]); sh, c = s.shapes, self.c
        self.title(s, d["title"], d["icon"])
        cols, cw, ch = 4, (RM - LM) / 4, 2.55
        colors = [c["p"], c["dark"], c["purple"], c["green"], c["amber"], c["mid"]]
        pills = {"présent": ("green", "green_l"), "excusé": ("amber", "amber_l"), "absent": ("red", "red_l"),
                 "present": ("green", "green_l"), "excused": ("amber", "amber_l")}
        n = len(d["people"]); rows = math.ceil(n / cols)
        y_start = 1.7 + (2 - min(rows, 2)) * ch * 0.2
        for i, p in enumerate(d["people"]):
            r, k = divmod(i, cols)
            in_row = min(cols, n - r * cols)
            x = LM + (cols - in_row) * cw / 2 + k * cw        # dernière ligne centrée
            y = y_start + r * ch
            cx = x + cw / 2
            col = colors[i % len(colors)]
            rect(sh, cx - 0.52, y, 1.04, 1.04, col, oval=True)
            ini = "".join(w[0] for w in p["nom"].replace("-", " ").split()[:2]).upper() or "?"
            text(sh, cx - 0.52, y, 1.04, 1.04, ini, size=28, bold=True, color="FFFFFF" if _lum(col) < 0.62 else c["ink"], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
            # nom (jusqu'à 2 lignes) puis fonction (jusqu'à 2 lignes) puis statut : aucune zone ne se chevauche
            text(sh, x + 0.1, y + 1.12, cw - 0.2, 0.5, p["nom"], size=fit_pt([p["nom"]], cw - 0.2, 0.5, 18, 11), bold=True, color=c["ink"], align=PP_ALIGN.CENTER)
            if p.get("fonction"):
                text(sh, x + 0.1, y + 1.64, cw - 0.2, 0.45, p["fonction"], size=fit_pt([p["fonction"]], cw - 0.2, 0.45, 14, 9), color=c["mute"], align=PP_ALIGN.CENTER)
            fg, bgc = pills.get(p.get("statut", "présent"), pills["présent"])
            pw = 1.05
            rect(sh, cx - pw / 2, y + 2.15, pw, 0.28, c[bgc], radius=0.14)
            text(sh, cx - pw / 2, y + 2.15, pw, 0.28, p.get("statut", "présent"), size=11, bold=True, color=c[fg], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        self.chrome(s)

    def table(self, d: dict):
        s = self.new(self.c["bg"] if self.visual else None); sh, c = s.shapes, self.c
        self.title(s, d["title"], d.get("icon"))
        charts = d.get("charts")
        tw = 7.9 if charts else RM - LM
        rows, headers = d["rows"], d["headers"]
        gf = sh.add_table(len(rows) + 1, len(headers), Inches(LM), Inches(1.6), Inches(tw), Inches(0.4 * (len(rows) + 1)))
        tbl = gf.table
        tbl.first_row = True; tbl.horz_banding = False
        for i, w in enumerate(d["widths"]):
            tbl.columns[i].width = Inches(tw * w)
        pt = 14
        # couleurs sémantiques des colonnes de constat / statut / priorité
        prio_col = {"Haute": c["red"], "Moyenne": c["amber"], "Basse": c["green"], "Écart": c["red"], "Confirmé": c["green"],
                    "Complément": c["p"], "Soldée": c["green"], "En cours": c["amber"], "Reportée": c["amber"], "Non évoquée": c["red"],
                    "High": c["red"], "Medium": c["amber"], "Low": c["green"], "Gap": c["red"], "Confirmed": c["green"], "Addition": c["p"],
                    "Closed": c["green"], "In progress": c["amber"], "Postponed": c["amber"], "Not discussed": c["red"]}
        coded = {"Priorité", "Constat", "Statut", "Priority", "Finding", "Status"}
        def cell(r, ci, txt, header=False, color=None, bold=False):
            ce = tbl.cell(r, ci)
            ce.margin_left = ce.margin_right = Inches(0.1); ce.margin_top = ce.margin_bottom = Inches(0.05)
            ce.vertical_anchor = MSO_ANCHOR.MIDDLE
            ce.fill.solid()
            ce.fill.fore_color.rgb = _rgb(c["p"] if header else ("FFFFFF" if r % 2 else c["light"]))
            tf = ce.text_frame; tf.word_wrap = True
            p = tf.paragraphs[0]; p.text = ""
            run = p.add_run(); run.text = txt
            run.font.name = FONT; run.font.size = Pt(15 if header else pt); run.font.bold = header or bold
            run.font.color.rgb = _rgb(c["onp"] if header else (color or c["ink"]))
        for r_ in tbl.rows:
            r_.height = Inches(0.5)
        for ci, h in enumerate(headers):
            cell(0, ci, h, header=True)
        for ri, row in enumerate(rows, 1):
            for ci, v in enumerate(row):
                cell(ri, ci, str(v), color=prio_col.get(v) if headers[ci] in coded else None, bold=headers[ci] in coded and v in prio_col)
        if charts:
            self._charts(s, charts)
        self.chrome(s)

    def _charts(self, s, charts: dict):
        c = self.c
        sh = s.shapes
        x, w = 8.85, RM - 8.85
        rect(sh, x, 1.6, w, 2.55 if charts["owners"] else 5.0, "FFFFFF", line=c["line"])
        text(sh, x + 0.2, 1.68, w - 0.4, 0.3, labels.tr("RÉPARTITION PAR PRIORITÉ", self.b.get("_lang", "fr")), size=10, bold=True, color=c["mute"])
        cd = CategoryChartData(); cd.categories = ["Haute", "Moyenne", "Basse"]
        pr = charts["priorities"]; cd.add_series("Actions", [pr["haute"], pr["moyenne"], pr["basse"]])
        gf = sh.add_chart(XL_CHART_TYPE.DOUGHNUT, Inches(x + 0.1), Inches(1.95), Inches(w - 0.2), Inches(2.15 if charts["owners"] else 4.55), cd)
        ch = gf.chart
        ch.has_legend = True; ch.legend.position = XL_LEGEND_POSITION.RIGHT; ch.legend.include_in_layout = False
        ch.legend.font.size = Pt(11); ch.legend.font.name = FONT
        ch.has_title = False
        plot = ch.plots[0]; plot.has_data_labels = True
        plot.data_labels.font.size = Pt(12); plot.data_labels.font.bold = True; plot.data_labels.font.color.rgb = _rgb("FFFFFF")
        plot.data_labels.show_value = True; plot.data_labels.show_percentage = False
        for i, col in enumerate((c["red"], c["amber"], c["green"])):
            pt_ = plot.series[0].points[i]; pt_.format.fill.solid(); pt_.format.fill.fore_color.rgb = _rgb(col)
        if charts["owners"]:
            rect(sh, x, 4.3, w, 2.3, "FFFFFF", line=c["line"])
            text(sh, x + 0.2, 4.38, w - 0.4, 0.3, "ACTIONS PAR RESPONSABLE", size=10, bold=True, color=c["mute"])
            cd2 = CategoryChartData(); cd2.categories = [o for o, _ in charts["owners"]][::-1]
            cd2.add_series("Actions", [n for _, n in charts["owners"]][::-1])
            gf2 = sh.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(x + 0.1), Inches(4.65), Inches(w - 0.2), Inches(1.9), cd2)
            c2 = gf2.chart; c2.has_legend = False; c2.has_title = False
            p2 = c2.plots[0]; p2.gap_width = 60; p2.has_data_labels = True; p2.data_labels.font.size = Pt(11); p2.data_labels.show_value = True
            p2.series[0].format.fill.solid(); p2.series[0].format.fill.fore_color.rgb = _rgb(c["p"])
            c2.value_axis.visible = False; c2.value_axis.has_major_gridlines = False
            c2.category_axis.tick_labels.font.size = Pt(11); c2.category_axis.format.line.fill.background()

    def timeline(self, d: dict):
        s = self.new(self.c["bg"]); sh, c = s.shapes, self.c
        self.title(s, d["title"], d["icon"])
        steps = d["steps"]; n = len(steps)
        ly = 3.45
        full = (RM - LM) - 1.8
        span = min(full / max(1, n - 1), 3.1) if n > 1 else 0
        total = span * (n - 1)
        x0 = (LM + RM) / 2 - total / 2
        colw = min(2.75, span - 0.15) if n > 1 else 3.6
        rect(sh, x0 - 0.7, ly - 0.03, total + 1.4, 0.06, c["mid"])
        for i, st in enumerate(steps):
            cx = x0 + i * span
            col = c[{"red": "red", "amber": "amber", "green": "green"}[st["tone"]]]
            text(sh, cx - colw / 2, ly - 1.3, colw, 0.8, st["when"], size=fit_pt([st["when"]], colw, 0.8, 24, 12), bold=True, color=c["ink"], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.BOTTOM)
            rect(sh, cx - 0.3, ly - 0.3, 0.6, 0.6, col, oval=True, line="FFFFFF", lw=3)
            text(sh, cx - 0.3, ly - 0.3, 0.6, 0.6, str(i + 1), size=18, bold=True, color="FFFFFF", align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
            rect(sh, cx - colw / 2, ly + 0.6, colw, 2.7, "FFFFFF", line=c["line"]); rect(sh, cx - colw / 2, ly + 0.6, colw, 0.08, col)
            text(sh, cx - colw / 2 + 0.18, ly + 0.82, colw - 0.36, 1.6, st["label"], size=fit_pt([st["label"]], colw - 0.36, 1.6, 20, 11), color=c["ink"], bold=True)
            text(sh, cx - colw / 2 + 0.18, ly + 2.6, colw - 0.36, 0.55, st["who"], size=fit_pt([st["who"]], colw - 0.36, 0.55, 15, 10), color=c["mute"], anchor=MSO_ANCHOR.BOTTOM)
        self.chrome(s)

    def image(self, d: dict):
        """Pièce jointe image : insérée à l'échelle, centrée dans la zone de contenu, légende dessous."""
        s = self.new(self.c["bg"] if self.visual else None); sh = s.shapes
        self.title(s, d["title"], d.get("icon"))
        data = self.assets.get(d["id"])
        if data:
            iw, ih = d.get("size") or (800, 600)
            bw, bh = RM - LM, 4.85
            k = min(bw / iw, bh / ih)
            w, h = iw * k, ih * k
            pic = sh.add_picture(io.BytesIO(data), Inches(LM + (bw - w) / 2), Inches(1.6 + (bh - h) / 2), Inches(w), Inches(h))
            pic._element.nvPicPr.cNvPr.set("descr", d.get("caption", "Pièce jointe"))
        text(sh, LM, 6.55, RM - LM, 0.3, d.get("caption", ""), size=12, color=self.c["mute"], align=PP_ALIGN.CENTER)
        self.chrome(s)

    def save(self) -> bytes:
        buf = io.BytesIO(); self.prs.save(buf)
        return buf.getvalue()


def render(slide_list: list[dict], brand: dict[str, Any], visual: bool, title: str, assets: dict[str, bytes] | None = None) -> bytes:
    deck = Deck(brand, visual, title, len(slide_list))
    deck.assets = assets or {}
    for sl in slide_list:
        getattr(deck, sl["layout"])(sl)
    return deck.save()
