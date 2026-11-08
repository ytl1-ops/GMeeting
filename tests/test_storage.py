"""Emplacement des données : disque désigné (PC), cloud désigné (sauvegardes chiffrées avant envoi). Les scripts sont testés avec un « rclone » factice
(dossier local) et le VRAI GnuPG : le chiffrement et le déchiffrement sont réels."""
import os
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
NAME = re.compile(r"^gmeeting-\d{8}-\d{6}\.tar\.gz\.gpg$")

STUB = """#!/usr/bin/env bash
# rclone factice : « nom:dossier/fichier » → $CLOUD_DIR/dossier/fichier
map() { printf '%s' "$CLOUD_DIR/${1#*:}"; }
case "$1" in
  copyto) if [[ "$2" == *:* && ! -e "$2" ]]; then cp "$(map "$2")" "$3"; else mkdir -p "$(dirname "$(map "$3")")"; cp "$2" "$(map "$3")"; fi ;;
  lsf) ls -1 "$(map "$2")" 2>/dev/null ;;
  deletefile) rm -f "$(map "$2")" ;;
  *) echo "rclone factice : commande inconnue $1" >&2; exit 2 ;;
esac
"""


@pytest.fixture()
def box(tmp_path):
    site = tmp_path / "site"; (site / "backups").mkdir(parents=True)
    shutil.copytree(ROOT / "deploy", site / "deploy")
    cloud = tmp_path / "cloud"; (cloud / "sauv").mkdir(parents=True)
    bin_ = tmp_path / "bin"; bin_.mkdir()
    (bin_ / "rclone").write_text(STUB); (bin_ / "rclone").chmod(0o755)
    # GnuPG lance un agent dont le socket est limité à ~108 caractères : trousseau de test dans un dossier COURT (le chemin temporaire de pytest est trop long)
    gnupg = Path(tempfile.mkdtemp(prefix="gp", dir="/tmp")); gnupg.chmod(0o700)
    env = {k: v for k, v in os.environ.items() if not k.startswith("BACKUP_")}
    env.update(PATH=f"{bin_}:{env['PATH']}", CLOUD_DIR=str(cloud), GNUPGHOME=str(gnupg))
    yield type("Box", (), {"site": site, "cloud": cloud, "env": env, "bin": bin_})()
    subprocess.run(["gpgconf", "--kill", "gpg-agent"], env=env, capture_output=True)
    shutil.rmtree(gnupg, ignore_errors=True)


def run(box, script, *args, env=None, cwd=None):
    e = dict(box.env); e.update(env or {})
    return subprocess.run(["bash", str(box.site / "deploy" / script), *args], cwd=cwd or box.site, env=e, capture_output=True, text=True, stdin=subprocess.DEVNULL)


def archive(box, stamp="20261108-031500", marker="DONNEES-CONFIDENTIELLES-ne-doivent-jamais-sortir-en-clair"):
    p = box.site / "backups" / f"gmeeting-{stamp}.tar.gz"
    p.write_bytes(b"\x1f\x8b-faux-tar-" + marker.encode() * 50)
    return p


PASS = "phrase-secrete-de-test-123"


def test_init_writes_private_settings_and_refuses_to_overwrite(box):
    r = run(box, "backup-cloud.sh", "--init", env={"BACKUP_REMOTE": "macloud:sauv"})
    assert r.returncode == 0, r.stderr
    conf = box.site / ".backup-cloud.env"
    assert stat.S_IMODE(conf.stat().st_mode) == 0o600
    txt = conf.read_text()
    assert "BACKUP_REMOTE=macloud:sauv" in txt and len(re.search(r"BACKUP_PASSPHRASE=(.*)", txt).group(1)) >= 12
    assert "NOTEZ LA PHRASE SECRÈTE" in r.stdout
    again = run(box, "backup-cloud.sh", "--init", env={"BACKUP_REMOTE": "macloud:sauv"})
    assert again.returncode != 0 and "ne l'écrasez pas" in again.stderr                       # une phrase écrasée rendrait les copies illisibles
    assert txt == conf.read_text()


@pytest.mark.parametrize("remote", ["", "pas-un-cloud", "a b:c", "x:$(rm -rf /)", "x:;ls"])
def test_init_refuses_invalid_cloud_names(box, remote):
    r = run(box, "backup-cloud.sh", "--init", env={"BACKUP_REMOTE": remote})
    assert r.returncode != 0 and not (box.site / ".backup-cloud.env").exists()


def test_the_cloud_only_ever_receives_encrypted_data_that_decrypts_with_the_passphrase(box):
    a = archive(box)
    r = run(box, "backup-cloud.sh", "--file", str(a), env={"BACKUP_REMOTE": "macloud:sauv", "BACKUP_PASSPHRASE": PASS})
    assert r.returncode == 0, r.stderr + r.stdout
    sent = sorted(p.name for p in (box.cloud / "sauv").iterdir())
    assert sent == ["gmeeting-20261108-031500.tar.gz.gpg"] and NAME.match(sent[0])
    blob = (box.cloud / "sauv" / sent[0]).read_bytes()
    assert b"DONNEES-CONFIDENTIELLES" not in blob and blob != a.read_bytes()                  # jamais en clair dans le cloud
    out = box.site / "dec.tar.gz"
    d = subprocess.run(["gpg", "--batch", "--yes", "--quiet", "--pinentry-mode", "loopback", "--passphrase-fd", "0", "--decrypt", "-o", str(out), str(box.cloud / "sauv" / sent[0])],
                       input=PASS, text=True, capture_output=True, env=box.env)
    assert d.returncode == 0, d.stderr
    assert out.read_bytes() == a.read_bytes()                                                  # déchiffré = identique à l'original
    bad = subprocess.run(["gpg", "--batch", "--yes", "--quiet", "--pinentry-mode", "loopback", "--passphrase-fd", "0", "--decrypt", "-o", str(box.site / "x"), str(box.cloud / "sauv" / sent[0])],
                         input="mauvaise-phrase-xxxxx", text=True, capture_output=True, env=box.env)
    assert bad.returncode != 0                                                                 # sans la bonne phrase : illisible


def test_old_copies_are_pruned_in_the_cloud_but_the_newest_are_kept(box):
    for i in range(1, 6):
        run(box, "backup-cloud.sh", "--file", str(archive(box, f"2026110{i}-030000")), env={"BACKUP_REMOTE": "macloud:sauv", "BACKUP_PASSPHRASE": PASS, "BACKUP_KEEP_REMOTE": "2"})
    left = sorted(p.name for p in (box.cloud / "sauv").iterdir())
    assert left == ["gmeeting-20261104-030000.tar.gz.gpg", "gmeeting-20261105-030000.tar.gz.gpg"]


def test_restore_from_cloud_decrypts_the_latest_and_hands_it_to_the_restore_script(box):
    a1 = archive(box, "20261101-030000", marker="ancienne"); a2 = archive(box, "20261102-030000", marker="recente")
    env = {"BACKUP_REMOTE": "macloud:sauv", "BACKUP_PASSPHRASE": PASS}
    for a in (a1, a2):
        assert run(box, "backup-cloud.sh", "--file", str(a), env=env).returncode == 0
    hook = box.bin / "restore-hook"; got = box.site / "got.bin"
    hook.write_text(f'#!/usr/bin/env bash\ncp "$1" "{got}"\necho "args: $*" > "{got}.args"\n'); hook.chmod(0o755)
    r = run(box, "restore-cloud.sh", "--force", env={**env, "GMEETING_RESTORE_CMD": str(hook)})
    assert r.returncode == 0, r.stderr + r.stdout
    assert got.read_bytes() == a2.read_bytes()                                                # la plus récente, déchiffrée
    assert "--force" in (box.site / "got.bin.args").read_text()
    r2 = run(box, "restore-cloud.sh", "gmeeting-20261101-030000.tar.gz.gpg", env={**env, "GMEETING_RESTORE_CMD": str(hook)})
    assert r2.returncode == 0 and got.read_bytes() == a1.read_bytes()                         # une copie précise


def test_restore_fails_cleanly_with_a_wrong_passphrase_or_a_tampered_copy(box):
    env = {"BACKUP_REMOTE": "macloud:sauv", "BACKUP_PASSPHRASE": PASS}
    assert run(box, "backup-cloud.sh", "--file", str(archive(box)), env=env).returncode == 0
    hook = box.bin / "restore-hook"; hook.write_text('#!/usr/bin/env bash\ntouch "$0.called"\n'); hook.chmod(0o755)
    wrong = run(box, "restore-cloud.sh", env={**env, "BACKUP_PASSPHRASE": "autre-phrase-secrete", "GMEETING_RESTORE_CMD": str(hook)})
    assert wrong.returncode != 0 and "déchiffrement impossible" in wrong.stderr
    f = box.cloud / "sauv" / "gmeeting-20261108-031500.tar.gz.gpg"; raw = bytearray(f.read_bytes()); raw[len(raw) // 2] ^= 0xFF; f.write_bytes(bytes(raw))
    tampered = run(box, "restore-cloud.sh", env={**env, "GMEETING_RESTORE_CMD": str(hook)})
    assert tampered.returncode != 0 and "déchiffrement impossible" in tampered.stderr
    assert not (box.bin / "restore-hook.called").exists()                                     # jamais de restauration à partir d'une copie douteuse


def test_missing_prerequisites_and_bad_settings_fail_with_a_clear_message(box):
    no_rclone = {**box.env, "PATH": "/usr/bin:/bin"}
    r = subprocess.run(["bash", str(box.site / "deploy" / "backup-cloud.sh"), "--file", str(archive(box))], cwd=box.site, env={**no_rclone, "BACKUP_REMOTE": "a:b", "BACKUP_PASSPHRASE": PASS}, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if not shutil.which("rclone", path="/usr/bin:/bin"):
        assert r.returncode != 0 and "rclone est requis" in r.stderr
    assert "cloud non configuré" in run(box, "backup-cloud.sh", "--file", str(archive(box))).stderr
    assert "trop courte" in run(box, "backup-cloud.sh", "--file", str(archive(box)), env={"BACKUP_REMOTE": "a:b", "BACKUP_PASSPHRASE": "court"}).stderr
    assert "archive introuvable" in run(box, "backup-cloud.sh", "--file", "/nexiste/pas", env={"BACKUP_REMOTE": "a:b", "BACKUP_PASSPHRASE": PASS}).stderr
    assert "option inconnue" in run(box, "backup-cloud.sh", "--bizarre").stderr


def test_cloud_settings_never_reach_the_container_or_the_repository():
    compose = (ROOT / "docker-compose.yml").read_text()
    assert "env_file: .env" in compose and ".backup-cloud.env" not in compose                 # la phrase secrète n'entre jamais dans le conteneur
    assert ".backup-cloud.env" in (ROOT / ".gitignore").read_text()


# ------------------------------------------------------------------ disque désigné
@pytest.fixture()
def site(tmp_path):
    shutil.copytree(ROOT / "deploy", tmp_path / "deploy")
    for f in (".env.example", "docker-compose.yml", "Caddyfile"):
        shutil.copy(ROOT / f, tmp_path / f)
    return tmp_path


def install(site, *args):
    e = {k: v for k, v in os.environ.items() if k not in ("GMEETING_PASSWORD", "GMEETING_DATA")}
    return subprocess.run(["bash", "deploy/install.sh", *args, "--no-start"], cwd=site, env=e, capture_output=True, text=True, stdin=subprocess.DEVNULL)


def test_designated_disk_is_created_owned_by_the_container_user_and_recorded(site, tmp_path):
    disk = tmp_path / "disque-pc"
    r = install(site, "d.exemple.fr", "--data-dir", str(disk))
    assert r.returncode == 0, r.stderr
    assert disk.is_dir() and stat.S_IMODE(disk.stat().st_mode) == 0o700                       # lecture réservée au propriétaire, avec ou sans droits administrateur
    if os.getuid() == 0:
        assert disk.stat().st_uid == 10001                                                    # le conteneur n'est jamais root
    assert f"GMEETING_DATA={disk}" in (site / ".env").read_text()


@pytest.mark.parametrize("bad", ["relatif/dossier", "/", "/tmp/a b", "/tmp/a'b", '/tmp/a"b', "/tmp/a$b"])
def test_designated_disk_refuses_dangerous_paths(site, bad):
    r = install(site, "d.exemple.fr", "--data-dir", bad)
    assert r.returncode != 0 and "--data-dir" in r.stderr
    env_file = site / ".env"
    assert not env_file.exists() or "GMEETING_DATA" not in env_file.read_text()               # rien n'est enregistré


def test_designated_disk_refuses_a_folder_that_holds_other_files(site, tmp_path):
    d = tmp_path / "pas-vide"; d.mkdir(); (d / "photo.jpg").write_text("x")
    r = install(site, "d.exemple.fr", "--data-dir", str(d))
    assert r.returncode != 0 and "pas vide" in r.stderr
    (d / "photo.jpg").unlink(); (d / "gmeeting.db").write_text("x")
    assert install(site, "d.exemple.fr", "--data-dir", str(d)).returncode == 0                # un dossier de données existant est accepté (reprise)


def test_data_dir_requires_a_value(site):
    assert install(site, "d.exemple.fr", "--data-dir").returncode != 0


@pytest.mark.skipif(not shutil.which("docker"), reason="docker absent")
def test_compose_mounts_the_designated_disk_or_defaults_to_a_docker_volume(site, tmp_path):
    def cfg(**env):
        e = {k: v for k, v in os.environ.items() if k != "GMEETING_DATA"}; e.update(env)
        return subprocess.run(["docker", "compose", "config", "--format", "json"], cwd=site, env=e, capture_output=True, text=True)
    import json
    (site / ".env").write_text("")                                                           # env_file: .env doit exister pour « docker compose config »
    disk = tmp_path / "mon-disque"; disk.mkdir()
    r = cfg(GMEETING_DATA=str(disk), DOMAIN="x.fr")
    if r.returncode != 0:
        pytest.skip("docker compose indisponible : " + r.stderr[:100])
    vols = json.loads(r.stdout)["services"]["app"]["volumes"]
    assert any(v["target"] == "/data" and v["type"] == "bind" and v["source"] == str(disk) for v in vols)
    vols = json.loads(cfg(DOMAIN="x.fr").stdout)["services"]["app"]["volumes"]
    assert any(v["target"] == "/data" and v["type"] == "volume" for v in vols)               # par défaut : volume Docker
