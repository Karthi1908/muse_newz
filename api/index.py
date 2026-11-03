import os
import shutil
import sys
from pathlib import Path

# Ensure root workspace directory is in python search path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

# When deployed on Vercel, copy pre-seeded database & edition archives into temp data dir if not yet copied
if os.getenv("VERCEL") == "1":
    import tempfile
    tmp_data = Path(tempfile.gettempdir()) / "muse_data"
    tmp_data.mkdir(parents=True, exist_ok=True)
    src_data = root_dir / "data"
    if src_data.exists():
        src_db = src_data / "your_daily_muse.db"
        dst_db = tmp_data / "your_daily_muse.db"
        if src_db.exists() and not dst_db.exists():
            shutil.copy2(src_db, dst_db)

        src_editions = src_data / "editions"
        dst_editions = tmp_data / "editions"
        if src_editions.exists() and not dst_editions.exists():
            shutil.copytree(src_editions, dst_editions)

from app.main import app
