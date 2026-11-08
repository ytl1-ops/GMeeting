"""Serveur Oracle Cloud : pare-feu de l'hôte (règles iptables insérées AVANT le rejet final), aide au déploiement depuis le poste de l'utilisateur.
iptables et netfilter-persistent sont simulés (fichier de règles) ; ssh/scp ne sont jamais lancés (--dry-run)."""
import os
import shutil
import stat
import subprocess
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ORACLE_RULES = [
    "-m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT",
    "-p icmp -j ACCEPT",
    "-i lo -j ACCEPT",
    "-p tcp --dport 22 -m conntrack --ctstate NEW -j ACCEPT",
    "-j REJECT --reject-with icmp-host-prohibited",
]
IPTABLES = r"""#!/usr/bin/env bash
R="$RULES_FILE"
case "$1" in
  -C) want="${*:2}"; want="${want#INPUT }"; grep -qxF -- "$want" "$R" ;;
  -L) echo "Chain INPUT (policy ACCEPT)"; echo "num  target     prot opt source               destination"
      n=1; while IFS= read -r l; do tgt="${l##*-j }"; echo "$n    $tgt     all  --  0.0.0.0/0            0.0.0.0/0   $l"; n=$((n+1)); done < "$R" ;;
  -I) pos="$3"; shift 3; awk -v p="$pos" -v r="$*" 'NR==p{print r} {print} END{if (NR<p) print r}' "$R" > "$R.tmp" && mv "$R.tmp" "$R" ;;
  *) echo "iptables factice : $1" >&2; exit 2 ;;
esac
"""


@pytest.fixture()
def fw(tmp_path):
    bin_ = tmp_path / "bin"; bin_.mkdir()
    (bin_ / "iptables").write_text(IPTABLES); (bin_ / "iptables").chmod(0o755)
    rules = tmp_path / "rules"; rules.write_text("\n".join(ORACLE_RULES) + "\n")
    marker = tmp_path / "saved"
    (bin_ / "netfilter-persistent").write_text(f'#!/usr/bin/env bash\necho "$@" >> "{marker}"\n'); (bin_ / "netfilter-persistent").chmod(0o755)
    env = dict(os.environ, PATH=f"{bin_}:{os.environ['PATH']}", RULES_FILE=str(rules))
    return type("F", (), {"rules": rules, "env": env, "marker": marker, "bin": bin_})()


def fwrun(fw, *args, env=None):
    return subprocess.run(["bash", str(ROOT / "deploy" / "oracle-firewall.sh"), *args], env=env or fw.env, capture_output=True, text=True)


def lines(fw):
    return fw.rules.read_text().splitlines()


def test_ports_are_inserted_before_the_final_reject_rule_and_saved(fw):
    r = fwrun(fw)
    assert r.returncode == 0, r.stderr
    rules = lines(fw)
    reject = next(i for i, l in enumerate(rules) if "REJECT" in l)
    for port in (80, 443):
        idx = rules.index(f"-p tcp --dport {port} -m conntrack --ctstate NEW -j ACCEPT")
        assert idx < reject, f"port {port} : règle APRÈS le rejet final (elle serait ignorée)"
    assert rules[-1] == ORACLE_RULES[-1]                                                      # le rejet final reste la dernière règle
    assert rules[:4] == ORACLE_RULES[:4]                                                      # SSH et règles existantes intacts
    assert fw.marker.read_text().strip() == "save"                                            # enregistré pour survivre au redémarrage


def test_running_twice_does_not_duplicate_rules(fw):
    fwrun(fw); once = lines(fw)
    r = fwrun(fw)
    assert r.returncode == 0 and lines(fw) == once and "déjà ouvert" in r.stdout


def test_dry_run_changes_nothing(fw):
    before = fw.rules.read_text()
    r = fwrun(fw, "--dry-run")
    assert r.returncode == 0 and fw.rules.read_text() == before and not fw.marker.exists()
    assert "iptables -I INPUT 5" in r.stdout and "--dport 443" in r.stdout


def test_missing_persistence_tool_is_reported_not_silent(fw):
    (fw.bin / "netfilter-persistent").unlink()
    env = dict(fw.env, PATH=f"{fw.bin}:/usr/bin:/bin")                                       # sans /usr/sbin : netfilter-persistent introuvable
    if subprocess.run(["bash", "-c", "command -v netfilter-persistent"], env=env, capture_output=True).returncode == 0:
        pytest.skip("netfilter-persistent présent dans le système de test")
    r = fwrun(fw, env=env)
    assert r.returncode == 0 and "netfilter-persistent est absent" in r.stdout and "iptables-persistent" in r.stdout


def test_bootstrap_uses_the_oracle_firewall_instead_of_ufw_on_oracle_only():
    base = dict(os.environ, OS_ID_OVERRIDE="ubuntu", CODENAME_OVERRIDE="noble", DOCKER_PRESENT_OVERRIDE="1")
    run = lambda **e: subprocess.run(["bash", str(ROOT / "deploy" / "bootstrap-vps.sh"), "demo.exemple.fr", "--dry-run"], env={**base, **e}, capture_output=True, text=True)
    o = run(ORACLE_OVERRIDE="1")
    assert o.returncode == 0, o.stderr
    assert "iptables-persistent" in o.stdout and "ufw" not in o.stdout.replace("pas ufw", "") and "règle de rejet finale" in o.stdout and "docs/ORACLE.md" in o.stdout
    n = run(ORACLE_OVERRIDE="0")
    assert "ufw allow 80/tcp" in n.stdout and "oracle-firewall" not in n.stdout and "iptables-persistent" not in n.stdout


# ------------------------------------------------------------------ aide depuis le poste de l'utilisateur
def helper(*args, env=None):
    return subprocess.run(["bash", str(ROOT / "deploy" / "oracle-helper.sh"), *args], env={**os.environ, **(env or {})}, capture_output=True, text=True)


@pytest.mark.skipif(not shutil.which("ssh-keygen"), reason="ssh-keygen absent")
def test_keygen_creates_a_private_key_shows_the_public_one_and_never_overwrites(tmp_path):
    key = tmp_path / "ssh" / "gm_key"
    r = helper("keygen", env={"GMEETING_SSH_KEY": str(key)})
    assert r.returncode == 0, r.stderr
    assert stat.S_IMODE(key.stat().st_mode) == 0o600 and (tmp_path / "ssh" / "gm_key.pub").exists()
    pub = (tmp_path / "ssh" / "gm_key.pub").read_text().strip()
    assert pub.startswith("ssh-ed25519 ") and pub in r.stdout and "JAMAIS" in r.stdout        # seule la partie publique est affichée
    assert "PRIVATE KEY" not in r.stdout
    before = key.read_bytes()
    again = helper("keygen", env={"GMEETING_SSH_KEY": str(key)})
    assert again.returncode != 0 and "ne l'écrase pas" in again.stderr and key.read_bytes() == before


def test_keygen_without_openssh_explains_what_to_install(tmp_path):
    bin_ = tmp_path / "bin"; bin_.mkdir()
    (bin_ / "dirname").symlink_to(shutil.which("dirname"))                                     # PATH minimal : tout sauf ssh-keygen
    r = subprocess.run(["/bin/bash", str(ROOT / "deploy" / "oracle-helper.sh"), "keygen"], env={"PATH": str(bin_), "GMEETING_SSH_KEY": str(tmp_path / "k"), "HOME": str(tmp_path)}, capture_output=True, text=True)
    assert r.returncode != 0 and "ssh-keygen est introuvable" in r.stderr and not (tmp_path / "k").exists()


def test_pack_contains_the_committed_project_and_no_secrets(tmp_path):
    r = helper("pack", env={"GMEETING_PACK_DIR": str(tmp_path)})
    assert r.returncode == 0, r.stderr
    names = tarfile.open(tmp_path / "gmeeting.tar.gz").getnames()
    assert "app/main.py" in names and "deploy/bootstrap-vps.sh" in names and "docker-compose.yml" in names
    assert not any(n in (".env", "DEMO_ACCESS.txt", ".backup-cloud.env") or n.endswith((".jks", "keystore.properties")) for n in names)


@pytest.mark.parametrize("args,msg", [
    (("send", "999.1.1.1", "demo.exemple.fr"), "adresse IP invalide"),
    (("send", "pas-une-ip", "demo.exemple.fr"), "adresse IP invalide"),
    (("send", "1.2.3.4", "pasundomaine"), "nom de domaine invalide"),
    (("send", "1.2.3.4", "demo.exemple.fr", "--bizarre"), "option inconnue"),
    (("send", "1.2.3.4", "demo.exemple.fr", "--data-dir", "relatif"), "chemin absolu"),
    (("send", "1.2.3.4"), "nom de domaine invalide"),
    (("inconnue",), "commande inconnue"),
])
def test_send_refuses_bad_input(args, msg, tmp_path):
    r = helper(*args, "--dry-run" if args[0] == "send" else "", env={"GMEETING_SSH_KEY": str(tmp_path / "k")})
    assert r.returncode != 0 and msg in r.stderr


def test_send_dry_run_prints_the_exact_commands_and_runs_nothing(tmp_path):
    r = helper("send", "10.20.30.40", "demo.exemple.fr", "--demo", "--data-dir", "/mnt/volume/gmeeting", "--dry-run", env={"GMEETING_SSH_KEY": str(tmp_path / "k")})
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert "[dry-run] scp -i" in out and "ubuntu@10.20.30.40:~/gmeeting.tar.gz" in out and "StrictHostKeyChecking=accept-new" in out
    assert "bootstrap-vps.sh demo.exemple.fr --demo --data-dir /mnt/volume/gmeeting" in out
    assert "check-server.sh https://demo.exemple.fr" in out and "read -r -s" in out           # les clés d'IA sont saisies sans écho, jamais écrites dans la commande


def test_send_without_a_key_or_archive_asks_to_prepare_them_first(tmp_path):
    r = helper("send", "10.20.30.40", "demo.exemple.fr", env={"GMEETING_SSH_KEY": str(tmp_path / "nokey"), "GMEETING_PACK_DIR": str(tmp_path)})
    assert r.returncode != 0 and "keygen" in r.stderr
    (tmp_path / "k").write_text("x")
    r = helper("send", "10.20.30.40", "demo.exemple.fr", env={"GMEETING_SSH_KEY": str(tmp_path / "k"), "GMEETING_PACK_DIR": str(tmp_path)})
    assert r.returncode != 0 and "pack" in r.stderr
