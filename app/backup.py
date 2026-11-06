"""Sauvegarde et restauration des données (base, pièces jointes, gabarit, archives audio).

    python -m app.backup create [--no-audio] [--keep 14]     → DATA_DIR/backups/gmeeting-AAAAMMJJ-HHMMSS.tar.gz
    python -m app.backup restore FICHIER [--force]           → remet les données en place (serveur arrêté de préférence)

La base SQLite est copiée avec l'API de sauvegarde en ligne : l'instantané est cohérent même si le serveur écrit pendant ce temps.
Ne sont PAS sauvegardés : les fichiers de travail du traitement en cours et les enregistrements non finalisés (dossier `audio/`),
qui sont transitoires ; l'audio conservé (`KEEP_AUDIO`) l'est, sauf avec --no-audio (il est volumineux).
Une archive est un fichier sensible (comptes rendus, pièces jointes) : protégez-la et chiffrez les copies hors du serveur.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path

from . import config

PREFIX = "gmeeting-"
INCLUDED_DIRS = ("attachments", "branding", "archive")
ALLOWED_TOP = {"gmeeting.db", *INCLUDED_DIRS}


def backups_dir() -> Path:
    d = config.DATA_DIR / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def create(dest_dir: Path | None = None, include_audio: bool = True, keep: int = 0) -> Path:
    """Crée l'archive et retourne son chemin. `keep` > 0 : ne garde que les `keep` archives les plus récentes."""
    dest_dir = dest_dir or backups_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / f"{PREFIX}{datetime.now().strftime('%Y%m%d-%H%M%S')}.tar.gz"
    with tempfile.TemporaryDirectory() as tmp:
        snap = Path(tmp) / "gmeeting.db"
        src = sqlite3.connect(config.DB_PATH)
        dst = sqlite3.connect(snap)
        with dst:
            src.backup(dst)                                   # instantané cohérent, même si le serveur écrit
        src.close(); dst.close()
        tmp_out = out.with_suffix(".tmp")
        with tarfile.open(tmp_out, "w:gz") as tar:
            tar.add(snap, arcname="gmeeting.db")
            for name in INCLUDED_DIRS:
                if name == "archive" and not include_audio:
                    continue
                p = config.DATA_DIR / name
                if p.is_dir():
                    tar.add(p, arcname=name)
        os.chmod(tmp_out, 0o600)                              # contenu sensible : lisible par le seul propriétaire
        tmp_out.replace(out)
    if keep > 0:
        for old in sorted(dest_dir.glob(f"{PREFIX}*.tar.gz"))[:-keep]:
            old.unlink()
    return out


def _safe_members(tar: tarfile.TarFile):
    """Refuse une archive piégée : chemins absolus ou « .. », liens, périphériques, ou éléments hors du périmètre attendu."""
    for m in tar.getmembers():
        parts = Path(m.name).parts
        if m.name.startswith("/") or ".." in parts or not parts or parts[0] not in ALLOWED_TOP:
            raise ValueError(f"Archive refusée : élément inattendu « {m.name} »")
        if not (m.isfile() or m.isdir()):
            raise ValueError(f"Archive refusée : « {m.name} » n'est ni un fichier ni un dossier")
        yield m


def _has_data() -> bool:
    """Y a-t-il de vraies données à protéger ? (un serveur neuf démarre avec une base vide : ce n'est pas un obstacle)"""
    if not config.DB_PATH.exists():
        return False
    try:
        with sqlite3.connect(config.DB_PATH) as c:
            return any(c.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("meetings", "attachments"))
    except sqlite3.DatabaseError:
        return True            # base illisible : par prudence on ne l'écrase pas sans --force


def restore(archive: Path, force: bool = False) -> None:
    """Restaure l'archive dans DATA_DIR. Refuse d'écraser des données existantes sans `force`."""
    if not archive.is_file():
        raise FileNotFoundError(archive)
    if _has_data() and not force:
        raise RuntimeError("Des données existent déjà : la restauration les remplacerait. Relancez avec --force (après avoir sauvegardé).")
    with tempfile.TemporaryDirectory(dir=config.DATA_DIR) as tmp:
        with tarfile.open(archive, "r:gz") as tar:
            members = list(_safe_members(tar))
            tar.extractall(tmp, members=members, filter="data")
        stage = Path(tmp)
        if not (stage / "gmeeting.db").is_file():
            raise ValueError("Archive invalide : base de données absente.")
        try:
            sqlite3.connect(stage / "gmeeting.db").execute("SELECT count(*) FROM meetings").fetchone()
        except sqlite3.DatabaseError as e:
            raise ValueError(f"Archive invalide : base illisible ({e}).") from e
        for name in INCLUDED_DIRS:                             # remplacement complet des dossiers présents dans l'archive
            if (stage / name).is_dir():
                shutil.rmtree(config.DATA_DIR / name, ignore_errors=True)
                shutil.move(str(stage / name), str(config.DATA_DIR / name))
        for ext in ("-wal", "-shm"):
            Path(str(config.DB_PATH) + ext).unlink(missing_ok=True)
        shutil.move(str(stage / "gmeeting.db"), str(config.DB_PATH))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m app.backup", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create", help="crée une archive")
    c.add_argument("--no-audio", action="store_true", help="n'inclut pas l'audio conservé (volumineux)")
    c.add_argument("--keep", type=int, default=0, help="ne garder que les N archives les plus récentes")
    c.add_argument("--out", type=Path, help="dossier de destination (défaut : DATA_DIR/backups)")
    r = sub.add_parser("restore", help="restaure une archive")
    r.add_argument("file", type=Path, help="archive à restaurer, ou « - » pour la lire sur l'entrée standard (évite tout problème de droits "
                                          "sur un fichier de l'hôte monté dans un conteneur non-root)")
    r.add_argument("--force", action="store_true", help="remplace les données existantes")
    a = p.parse_args(argv)
    try:
        if a.cmd == "create":
            out = create(a.out, include_audio=not a.no_audio, keep=a.keep)
            print(f"Sauvegarde créée : {out} ({out.stat().st_size / 1048576:.1f} Mo)")
        elif str(a.file) == "-":
            with tempfile.NamedTemporaryFile(dir=config.TMP_DIR, suffix=".tar.gz") as tmp:   # sur le volume de données, pas en mémoire
                shutil.copyfileobj(sys.stdin.buffer, tmp); tmp.flush()
                restore(Path(tmp.name), force=a.force)
            print("Restauration terminée. Redémarrez le service : docker compose up -d")
        else:
            restore(a.file, force=a.force)
            print("Restauration terminée. Redémarrez le service : docker compose up -d")
    except (ValueError, RuntimeError, FileNotFoundError) as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
