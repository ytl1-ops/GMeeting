"""Scripts de déploiement : la logique qui ne dépend pas de Docker (préparation de .env) est testée à chaque modification."""
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()
def site(tmp_path):
    """Copie isolée du dépôt (deploy/ + .env.example) : on n'écrit jamais un .env dans le vrai dépôt."""
    shutil.copytree(ROOT / "deploy", tmp_path / "deploy")
    shutil.copy(ROOT / ".env.example", tmp_path / ".env.example")
    return tmp_path


def install(site, *args, env=None):
    e = {k: v for k, v in os.environ.items() if k not in ("GMEETING_PASSWORD", "ANTHROPIC_API_KEY", "OPENAI_API_KEY")}
    e.update(env or {})
    return subprocess.run(["bash", "deploy/install.sh", *args, "--no-start"], cwd=site, env=e, capture_output=True, text=True, stdin=subprocess.DEVNULL)


def value(site, key):
    m = re.search(rf"^{key}=(.*)$", (site / ".env").read_text(), re.M)
    return m.group(1) if m else None


def test_first_install_creates_a_private_env_with_a_strong_generated_password(site):
    r = install(site, "reunions.exemple.fr")
    assert r.returncode == 0, r.stderr
    assert stat.S_IMODE((site / ".env").stat().st_mode) == 0o600                      # secrets : lisible par le propriétaire seul
    assert re.fullmatch(r"[A-Za-z0-9]{22}", value(site, "GMEETING_PASSWORD"))
    assert value(site, "DOMAIN") == "reunions.exemple.fr" and value(site, "TRANSCRIBE_PROVIDER") == "auto"


def test_generation_is_reliable_not_flaky(site):
    # régression : « tr … | head » sous « set -o pipefail » faisait avorter le script en silence (SIGPIPE) avant d'écrire le mot de passe
    for _ in range(8):
        (site / ".env").unlink(missing_ok=True)
        assert install(site).returncode == 0
        assert len(value(site, "GMEETING_PASSWORD")) == 22


def test_rerunning_never_changes_existing_secrets_or_domain(site):
    install(site, "reunions.exemple.fr")
    pw = value(site, "GMEETING_PASSWORD"); assert pw
    assert install(site).returncode == 0
    assert value(site, "GMEETING_PASSWORD") == pw and value(site, "DOMAIN") == "reunions.exemple.fr"


def test_special_characters_in_provided_values_are_preserved_exactly(site):
    pw, key = 'a\\b$c"d&e |f', "sk-ant-x\\123"
    assert install(site, env={"GMEETING_PASSWORD": pw, "ANTHROPIC_API_KEY": key}).returncode == 0
    assert value(site, "GMEETING_PASSWORD") == pw and value(site, "ANTHROPIC_API_KEY") == key
    assert len(re.findall(r"^GMEETING_PASSWORD=", (site / ".env").read_text(), re.M)) == 1       # jamais de ligne dupliquée


def test_unknown_option_is_rejected(site):
    r = subprocess.run(["bash", "deploy/install.sh", "--bizarre"], cwd=site, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    assert r.returncode != 0 and "option inconnue" in r.stderr


@pytest.mark.parametrize("script", sorted(p.name for p in (ROOT / "deploy").glob("*.sh")))
def test_every_deploy_script_has_valid_bash_syntax_and_is_executable(script):
    path = ROOT / "deploy" / script
    assert subprocess.run(["bash", "-n", str(path)]).returncode == 0
    if script != "lib.sh":
        assert os.access(path, os.X_OK), f"{script} doit être exécutable"


def test_restore_script_always_restarts_the_service_when_the_restore_fails():
    # régression constatée en essai : une restauration refusée (--force oublié) laissait la production arrêtée
    src = (ROOT / "deploy" / "restore.sh").read_text()
    assert "if ! docker compose run" in src and "docker compose up -d" in src.split("if ! docker compose run")[1].split("fi\n")[0]
    assert "< \"$FILE\"" in src                    # archive lue sur l'entrée standard : un fichier hôte (droits 600) serait illisible du conteneur


# ------------------------------------------------------------------ serveur de démonstration, préparation d'un serveur neuf, vérification à distance
def test_demo_mode_limits_retention_and_writes_reviewer_access(site):
    r = install(site, "demo.exemple.fr", "--demo")
    assert r.returncode == 0, r.stderr
    assert value(site, "RETENTION_DAYS") == "1" and value(site, "KEEP_AUDIO") == "false"          # données de relecteur : jamais gardées
    acc = site / "DEMO_ACCESS.txt"
    assert stat.S_IMODE(acc.stat().st_mode) == 0o600                                              # contient le mot de passe
    txt = acc.read_text()
    assert "https://demo.exemple.fr" in txt and value(site, "GMEETING_PASSWORD") in txt
    assert "Instructions pour le relecteur (FR)" in txt and "Instructions for the reviewer (EN)" in txt
    assert "DEMO_ACCESS.txt" in (ROOT / ".gitignore").read_text()                                 # ne jamais versionner ce fichier


def test_a_normal_install_never_writes_the_demo_file_nor_changes_retention(site):
    assert install(site, "reunions.exemple.fr").returncode == 0
    assert not (site / "DEMO_ACCESS.txt").exists() and value(site, "RETENTION_DAYS") in (None, "0")


def bootstrap(site, *args, env=None):
    e = dict(os.environ); e.update(env or {})
    return subprocess.run(["bash", "deploy/bootstrap-vps.sh", *args], cwd=site, env=e, capture_output=True, text=True, stdin=subprocess.DEVNULL)


def test_bootstrap_dry_run_shows_the_plan_and_changes_nothing(site):
    r = bootstrap(site, "demo.exemple.fr", "--demo", "--dry-run", env={"OS_ID_OVERRIDE": "ubuntu", "CODENAME_OVERRIDE": "noble", "DOCKER_PRESENT_OVERRIDE": "0"})
    out = r.stdout
    assert r.returncode == 0, r.stderr
    for step in ("apt-get install -y ca-certificates", "docker-ce", "ufw allow 80/tcp", "ufw allow 443/tcp", "ufw --force enable", "install.sh demo.exemple.fr --demo", "download.docker.com/linux/ubuntu"):
        assert step in out, step
    assert out.index("ufw allow 22/tcp") < out.index("ufw --force enable")                        # SSH autorisé AVANT d'activer le pare-feu
    assert not (site / ".env").exists() and not (site / "DEMO_ACCESS.txt").exists()
    # Docker déjà présent : rien à installer
    r2 = bootstrap(site, "demo.exemple.fr", "--dry-run", env={"OS_ID_OVERRIDE": "debian", "CODENAME_OVERRIDE": "bookworm", "DOCKER_PRESENT_OVERRIDE": "1"})
    assert "déjà installés" in r2.stdout and "docker-ce" not in r2.stdout


@pytest.mark.parametrize("args,env,msg", [
    ((), {}, "indiquez le nom de domaine"),
    (("pasundomaine",), {}, "nom de domaine invalide"),
    (("a..b.fr",), {}, "nom de domaine invalide"),
    (("--bizarre", "x.fr"), {}, "option inconnue"),
    (("demo.exemple.fr",), {"OS_ID_OVERRIDE": "alpine", "CODENAME_OVERRIDE": "x"}, "non pris en charge"),
])
def test_bootstrap_refuses_bad_input_before_touching_anything(site, args, env, msg):
    r = bootstrap(site, *args, "--dry-run", env=env)
    assert r.returncode != 0 and msg in r.stderr


def _serve(tmp_path, port, **env):
    e = {k: v for k, v in os.environ.items() if k not in ("GMEETING_PASSWORD", "ANTHROPIC_API_KEY")}
    e.update(DATA_DIR=str(tmp_path / f"d{port}"), **env)
    (tmp_path / f"d{port}").mkdir()
    p = subprocess.Popen([os.sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port), "--log-level", "warning"], cwd=ROOT, env=e, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import time, urllib.request
    for _ in range(80):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=1); return p
        except Exception:
            time.sleep(0.25)
    p.kill(); raise AssertionError("serveur de test non démarré")


def _check(*args):
    return subprocess.run(["bash", str(ROOT / "deploy" / "check-server.sh"), *args], capture_output=True, text=True)


def test_check_server_accepts_a_protected_server_and_refuses_an_open_one(tmp_path):
    p1 = _serve(tmp_path, 18721, GMEETING_PASSWORD="Secret123", ANTHROPIC_API_KEY="x")
    p2 = _serve(tmp_path, 18722)
    try:
        ok = _check("http://127.0.0.1:18721", "Secret123", "--allow-http")
        assert ok.returncode == 0 and "CONTRÔLE OK" in ok.stdout, ok.stdout
        assert "sans mot de passe : accès refusé (401)" in ok.stdout and "page Confidentialité : mot de passe actif" in ok.stdout
        bad_pw = _check("http://127.0.0.1:18721", "Mauvais", "--allow-http")
        assert bad_pw.returncode == 1 and "mot de passe refusé" in bad_pw.stdout
        open_ = _check("http://127.0.0.1:18722", "--allow-http")
        assert open_.returncode == 1 and "OUVERT" in open_.stdout                                 # serveur sans mot de passe : jamais publiable
        http_only = _check("http://127.0.0.1:18721", "Secret123")
        assert http_only.returncode == 1 and "utilisez HTTPS" in http_only.stdout               # la version publiée de l'application refuse le HTTP
        down = _check("https://127.0.0.1:9", "x")
        assert down.returncode == 1 and "injoignable" in down.stdout
    finally:
        p1.kill(); p2.kill()
