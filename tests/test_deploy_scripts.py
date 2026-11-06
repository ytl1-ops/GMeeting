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
