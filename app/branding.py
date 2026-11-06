"""Gabarit d'identité visuelle : logo, en-tête, pied de page et couleur des documents exportés."""
from __future__ import annotations

import io
import json
import re
from typing import Any

from . import config

DIR = config.DATA_DIR / "branding"
SETTINGS = DIR / "settings.json"
LOGO = DIR / "logo.png"

DEFAULTS: dict[str, str] = {
    "org_name": "",         # affiché à côté du logo (ou seul)
    "header_right": "",     # ex. « Direction de la Sûreté – Diffusion restreinte »
    "footer": "",           # remplace le pied de page par défaut
    "confidential": "",     # mention en rouge au pied (ex. « CONFIDENTIEL »)
    "color": "#1F3A5F",     # couleur des titres et des tableaux
}
LIMITS = {"org_name": 80, "header_right": 120, "footer": 160, "confidential": 40}
MAX_LOGO_BYTES = 5 * 1024 * 1024
MAX_LOGO_PX = (800, 300)  # largeur, hauteur max après redimensionnement


def get() -> dict[str, str]:
    data = dict(DEFAULTS)
    try:
        data.update({k: v for k, v in json.loads(SETTINGS.read_text("utf-8")).items() if k in DEFAULTS})
    except (FileNotFoundError, ValueError):
        pass
    return data


def save(values: dict[str, Any]) -> dict[str, str]:
    cur = get()
    for k in DEFAULTS:
        if k not in values or values[k] is None:
            continue
        v = str(values[k]).strip()
        if k == "color":
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", v):
                raise ValueError("Couleur invalide (format attendu : #RRGGBB).")
            v = v.upper()
        else:
            v = v[: LIMITS[k]]
        cur[k] = v
    DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(json.dumps(cur, ensure_ascii=False, indent=2), "utf-8")
    return cur


def save_logo(raw: bytes) -> None:
    """Valide l'image et la ré-encode en PNG (supprime métadonnées et contenu actif éventuel)."""
    if len(raw) > MAX_LOGO_BYTES:
        raise ValueError("Logo trop volumineux (max 5 Mo).")
    from PIL import Image, UnidentifiedImageError
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValueError("Fichier image invalide. Formats acceptés : PNG, JPEG, GIF, WebP.")
    img = img.convert("RGBA")
    img.thumbnail(MAX_LOGO_PX)
    DIR.mkdir(parents=True, exist_ok=True)
    img.save(LOGO, "PNG", optimize=True)


def delete_logo() -> None:
    LOGO.unlink(missing_ok=True)


def logo_bytes() -> bytes | None:
    try:
        return LOGO.read_bytes()
    except FileNotFoundError:
        return None


def for_export() -> dict[str, Any]:
    """Gabarit prêt à l'emploi pour les exporteurs (couleur sans '#', logo en octets)."""
    s = get()
    logo = logo_bytes()
    size = None
    if logo:
        from PIL import Image
        size = Image.open(io.BytesIO(logo)).size
    return {**s, "color": s["color"].lstrip("#").upper(), "logo": logo, "logo_size": size}


DEFAULT_EXPORT: dict[str, Any] = {**DEFAULTS, "color": "1F3A5F", "logo": None, "logo_size": None}
