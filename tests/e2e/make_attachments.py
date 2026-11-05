"""Crée des pièces jointes de test (e-mail Outlook .msg, .eml, Word, Excel, image, exécutable refusé) dans un dossier.
Usage : python tests/e2e/make_attachments.py <dossier>"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tests import attbuild as B  # noqa: E402

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
B.msg_file(out / "Ordre du jour.msg")
(out / "cr_precedent.docx").write_bytes(B.docx_bytes())
(out / "budget.xlsx").write_bytes(B.xlsx_bytes(rows=40))
(out / "plan.png").write_bytes(B.png_bytes((1200, 700)))
(out / "virus.exe").write_bytes(b"MZ not really")
print("ok", sorted(p.name for p in out.iterdir()))
