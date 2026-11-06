import io
import sqlite3
import tarfile
import threading
import time

import pytest

from app import backup, config, db


@pytest.fixture()
def data(tmp_path, monkeypatch):
    """Dossier de données isolé : base vide initialisée + dossiers habituels."""
    def make(name):
        d = tmp_path / name
        for sub in ("audio", "archive", "attachments", "branding"):
            (d / sub).mkdir(parents=True)
        return d

    def use(d):
        monkeypatch.setattr(config, "DATA_DIR", d)
        monkeypatch.setattr(config, "DB_PATH", d / "gmeeting.db")
        monkeypatch.setattr(config, "ATTACH_DIR", d / "attachments")
        monkeypatch.setattr(config, "ARCHIVE_DIR", d / "archive")
        monkeypatch.setattr(config, "AUDIO_DIR", d / "audio")
        db.init()
        return d
    return make, use


def _fill(d):
    m = db.create(title="Réunion sauvegardée", source_type="text", status="done", transcript="[00:00:01] x")["id"]
    db.update(m, analysis={"titre": "T", "actions": [{"action": "a"}]})
    (d / "attachments" / "abc").mkdir(); (d / "attachments" / "abc" / "original.txt").write_text("pièce jointe")
    (d / "archive" / f"{m}.ogg").write_bytes(b"OggS-audio")
    (d / "branding" / "settings.json").write_text('{"org_name": "ACME"}')
    (d / "audio" / "temporaire.bin").write_bytes("ne doit pas être sauvegardé".encode())
    return m


def _names(path):
    with tarfile.open(path) as t:
        return {m.name for m in t.getmembers()}


def test_roundtrip_restores_database_and_files_on_a_fresh_server(data):
    make, use = data
    a = use(make("a")); m = _fill(a)
    out = backup.create()
    assert out.parent == a / "backups" and oct(out.stat().st_mode & 0o777) == "0o600"        # contenu sensible : propriétaire seul
    names = _names(out)
    assert "gmeeting.db" in names and "attachments/abc/original.txt" in names and f"archive/{m}.ogg" in names
    assert not any(n.startswith("audio") or n.startswith("backups") for n in names)           # fichiers transitoires exclus
    b = use(make("b"))                                                                         # « nouveau serveur »
    backup.restore(out)
    assert db.get(m)["title"] == "Réunion sauvegardée" and db.get(m)["analysis"]["actions"][0]["action"] == "a"
    assert (b / "attachments" / "abc" / "original.txt").read_text() == "pièce jointe"
    assert (b / "archive" / f"{m}.ogg").read_bytes() == b"OggS-audio"
    assert '"ACME"' in (b / "branding" / "settings.json").read_text()


def test_restore_never_overwrites_existing_data_without_force(data):
    make, use = data
    a = use(make("a")); _fill(a); out = backup.create()
    use(make("b")); keep = db.create(title="à ne pas perdre", source_type="text", status="done")["id"]
    with pytest.raises(RuntimeError, match="--force"):
        backup.restore(out)
    assert db.get(keep) is not None                                                            # rien n'a été touché
    backup.restore(out, force=True)
    assert db.get(keep) is None and len(db.list_all()) == 1                                    # remplacé volontairement


def test_snapshot_is_consistent_while_the_server_keeps_writing(data):
    make, use = data
    a = use(make("a")); _fill(a)
    stop = threading.Event()

    def writer():
        while not stop.is_set():
            db.create(title="en cours", source_type="text", status="done")
    t = threading.Thread(target=writer); t.start(); time.sleep(0.05)
    try:
        out = backup.create()
    finally:
        stop.set(); t.join()
    use(make("b")); backup.restore(out)
    assert sqlite3.connect(config.DB_PATH).execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert len(db.list_all()) >= 1


def test_no_audio_option_and_pruning(data):
    make, use = data
    a = use(make("a")); _fill(a)
    assert not any(n.startswith("archive") for n in _names(backup.create(include_audio=False)))
    d = backup.backups_dir()
    for i in range(3):                                                                         # trois anciennes archives
        (d / f"gmeeting-2000010{i}-000000.tar.gz").write_bytes(b"x")
    backup.create(keep=2)
    left = sorted(p.name for p in d.glob("gmeeting-*.tar.gz"))
    assert len(left) == 2 and left[0] == "gmeeting-20000102-000000.tar.gz"                     # les plus anciennes sont supprimées


def _evil(path, name, kind="file"):
    with tarfile.open(path, "w:gz") as t:
        ti = tarfile.TarInfo(name)
        if kind == "link":
            ti.type = tarfile.SYMTYPE; ti.linkname = "/etc/passwd"; t.addfile(ti)
        else:
            data = b"x"; ti.size = len(data); t.addfile(ti, io.BytesIO(data))


@pytest.mark.parametrize("name,kind", [("../evil.txt", "file"), ("/etc/cron.d/x", "file"), ("attachments/../../evil", "file"),
                                       ("etc/passwd", "file"), ("attachments/lien", "link")])
def test_booby_trapped_archives_are_rejected_before_extracting_anything(data, tmp_path, name, kind):
    make, use = data
    use(make("a")); bad = tmp_path / "bad.tar.gz"; _evil(bad, name, kind)
    with pytest.raises(ValueError, match="refusée"):
        backup.restore(bad, force=True)
    assert not (tmp_path / "evil.txt").exists() and not (config.DATA_DIR / "evil").exists()


def test_invalid_archives_are_rejected(data, tmp_path):
    make, use = data
    use(make("a"))
    nodb = tmp_path / "nodb.tar.gz"
    with tarfile.open(nodb, "w:gz") as t:
        ti = tarfile.TarInfo("branding/x.json"); ti.size = 2; t.addfile(ti, io.BytesIO(b"{}"))
    with pytest.raises(ValueError, match="base de données absente"):
        backup.restore(nodb, force=True)
    corrupt = tmp_path / "corrupt.tar.gz"
    with tarfile.open(corrupt, "w:gz") as t:
        ti = tarfile.TarInfo("gmeeting.db"); ti.size = 20; t.addfile(ti, io.BytesIO(b"ceci n'est pas sqlite"[:20]))
    with pytest.raises(ValueError, match="illisible"):
        backup.restore(corrupt, force=True)
    with pytest.raises(FileNotFoundError):
        backup.restore(tmp_path / "absent.tar.gz")


def test_command_line_interface(data, tmp_path, capsys):
    make, use = data
    a = use(make("a")); _fill(a)
    assert backup.main(["create", "--out", str(tmp_path / "out"), "--keep", "5"]) == 0
    arch = next((tmp_path / "out").glob("gmeeting-*.tar.gz"))
    assert "Sauvegarde créée" in capsys.readouterr().out
    assert backup.main(["restore", str(arch)]) == 1 and "--force" in capsys.readouterr().err   # données présentes : refus explicite
    assert backup.main(["restore", str(tmp_path / "nope.tar.gz"), "--force"]) == 1


def test_restore_reads_the_archive_from_standard_input(data, tmp_path, monkeypatch):
    """`restore -` : la méthode des scripts de déploiement (un fichier de l'hôte monté dans un conteneur non-root serait illisible)."""
    import io, sys, types
    make, use = data
    a = use(make("a")); m = _fill(a); out = backup.create()
    use(make("b"))
    monkeypatch.setattr(sys, "stdin", types.SimpleNamespace(buffer=io.BytesIO(out.read_bytes())))
    assert backup.main(["restore", "-"]) == 0
    assert db.get(m)["title"] == "Réunion sauvegardée" and not list(config.TMP_DIR.glob("*.tar.gz"))     # aucun résidu
