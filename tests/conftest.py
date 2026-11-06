import os, sys, tempfile
from pathlib import Path

os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="gmeeting_test_")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db  # noqa: E402

db.init()   # certains fichiers de tests n'importent pas app.main (qui initialise la base)
