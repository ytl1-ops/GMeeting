import io
import zipfile

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from PIL import Image

from app import branding, exporters, main
from tests.sample import ANALYSIS


def _png(color=(200, 30, 30), size=(300, 100)) -> bytes:
    buf = io.BytesIO(); Image.new("RGB", size, color).save(buf, "PNG"); return buf.getvalue()


@pytest.fixture()
def brand():
    branding.save({"org_name": "ACME Sûreté", "header_right": "Direction Sûreté – Diffusion restreinte",
                   "footer": "ACME – Document interne", "confidential": "CONFIDENTIEL", "color": "#8B1E3F"})
    branding.save_logo(_png())
    yield branding.for_export()
    branding.delete_logo(); branding.SETTINGS.unlink(missing_ok=True)


def test_color_validation():
    with pytest.raises(ValueError):
        branding.save({"color": "red"})
    with pytest.raises(ValueError):
        branding.save({"color": "#12345"})


def test_logo_rejects_non_image_and_normalizes_jpeg():
    with pytest.raises(ValueError):
        branding.save_logo(b"<svg onload=alert(1)></svg>")
    buf = io.BytesIO(); Image.new("RGB", (4000, 2000), "blue").save(buf, "JPEG")
    branding.save_logo(buf.getvalue())
    img = Image.open(io.BytesIO(branding.logo_bytes()))
    assert img.format == "PNG" and img.size[0] <= 800 and img.size[1] <= 300
    branding.delete_logo()


@pytest.mark.parametrize("doc_type", ["pv", "cr", "note"])
def test_exports_contain_logo_and_header(doc_type, brand):
    plain = {f: exporters.export(ANALYSIS, doc_type, f)[0] for f in ("pdf", "docx", "xlsx")}
    for fmt in ("pdf", "docx", "xlsx"):
        data, *_ = exporters.export(ANALYSIS, doc_type, fmt, "[00:00:01] x", brand)
        assert len(data) > len(plain[fmt]) if fmt == "pdf" else True
    # Word : image dans l'en-tête + texte de l'en-tête
    z = zipfile.ZipFile(io.BytesIO(exporters.export(ANALYSIS, doc_type, "docx", None, brand)[0]))
    assert any(n.startswith("word/media/") for n in z.namelist())
    header = "".join(z.read(n).decode() for n in z.namelist() if n.startswith("word/header"))
    assert "ACME Sûreté" in header and "Diffusion restreinte" in header
    assert "8B1E3F" in header
    footer = "".join(z.read(n).decode() for n in z.namelist() if n.startswith("word/footer"))
    assert "CONFIDENTIEL" in footer and "ACME – Document interne" in footer
    # Excel : logo + nom d'organisation
    wb = load_workbook(io.BytesIO(exporters.export(ANALYSIS, doc_type, "xlsx", None, brand)[0]))
    ws = wb["Document"]
    assert len(ws._images) == 1 and ws["B1"].value == "ACME Sûreté"
    assert wb["Actions"]["A1"].fill.fgColor.rgb.endswith("8B1E3F")


def test_pdf_branding_is_embedded(brand):
    pdf, *_ = exporters.export(ANALYSIS, "pv", "pdf", None, brand)
    assert b"/Subtype /Image" in pdf or b"/Image" in pdf


def test_no_branding_still_works_without_logo():
    only_text = {**exporters.DEFAULT_BRAND, "org_name": "Texte seul"}
    for f in ("pdf", "docx", "xlsx"):
        assert exporters.export(ANALYSIS, "cr", f, None, only_text)[0]


def test_branding_api(brand):
    c = TestClient(main.app)
    assert c.get("/api/branding").json()["org_name"] == "ACME Sûreté"
    r = c.put("/api/branding", json={"org_name": "Nouveau", "color": "#112233"})
    assert r.json()["org_name"] == "Nouveau" and r.json()["has_logo"]
    assert c.put("/api/branding", json={"color": "zzz"}).status_code == 422
    assert c.get("/api/branding/logo").headers["content-type"] == "image/png"
    assert c.post("/api/branding/logo", files={"file": ("x.png", b"not an image")}).status_code == 422
    assert c.post("/api/branding/logo", files={"file": ("l.png", _png((0, 0, 255)))}).status_code == 200
    assert c.delete("/api/branding/logo").json() == {"has_logo": False}
    assert c.get("/api/branding/logo").status_code == 404
