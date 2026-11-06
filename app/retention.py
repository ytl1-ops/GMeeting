"""Rétention des données : suppression automatique des réunions anciennes (RETENTION_DAYS, 0 = désactivé).

Utile pour des contenus sensibles (comptes rendus, audio, pièces jointes) : on ne garde pas indéfiniment ce dont on n'a plus besoin.
Seules les réunions terminées (prêtes ou en erreur) sont supprimées ; jamais une réunion en cours d'enregistrement ou de traitement.
"""
from __future__ import annotations

import shutil
import threading
import time
from datetime import datetime, timedelta

from . import attachments, config, db


def purge(days: int | None = None) -> int:
    """Supprime les réunions créées il y a plus de `days` jours, avec audio, archive et pièces jointes. Retourne leur nombre."""
    days = config.RETENTION_DAYS if days is None else days
    if days <= 0:
        return 0
    limit = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
    removed = 0
    for m in db.list_all():
        if m["created_at"] < limit and m["status"] in ("done", "error"):
            mid = m["id"]
            attachments.delete_for_meeting(mid)
            shutil.rmtree(config.AUDIO_DIR / mid, ignore_errors=True)
            (config.ARCHIVE_DIR / f"{mid}.ogg").unlink(missing_ok=True)
            db.delete(mid)
            removed += 1
    attachments.purge_stale()
    return removed


def clean_tmp(max_age_hours: float = 24) -> int:
    """Supprime les fichiers temporaires abandonnés (envoi interrompu, arrêt brutal) vieux de plus de `max_age_hours`."""
    limit = time.time() - max_age_hours * 3600
    n = 0
    for p in config.TMP_DIR.iterdir():
        try:
            if p.is_file() and p.stat().st_mtime < limit:
                p.unlink(); n += 1
        except OSError:
            pass
    return n


def schedule(every_hours: float = 6) -> None:
    """Purge au démarrage puis toutes les `every_hours` heures (thread démon)."""
    clean_tmp()                                   # toujours, même sans rétention : un volume ne doit pas se remplir de résidus
    if config.RETENTION_DAYS <= 0:
        return

    def loop():
        while True:
            try:
                purge()
                clean_tmp()
            except Exception:  # noqa: BLE001  (ne jamais faire tomber le serveur pour une purge)
                import traceback
                traceback.print_exc()
            time.sleep(every_hours * 3600)

    threading.Thread(target=loop, name="retention", daemon=True).start()
