import os
import shutil
import sys
from pathlib import Path
from starlette.responses import JSONResponse

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

from app.main import app as fastapi_app

async def app(scope, receive, send):
    if scope.get("type") == "http":
        raw_path = scope.get("path", "")
        # Diagnostic endpoint
        if raw_path in ("/debug_info", "/api/debug_info", "/api/index.py/debug_info"):
            headers_dict = {}
            for k, v in scope.get("headers", []):
                k_str = k.decode("latin-1") if isinstance(k, bytes) else str(k)
                v_str = v.decode("latin-1") if isinstance(v, bytes) else str(v)
                headers_dict[k_str] = v_str
            resp = JSONResponse({
                "scope_path": scope.get("path"),
                "scope_raw_path": scope.get("raw_path", b"").decode("latin-1", errors="ignore") if isinstance(scope.get("raw_path"), bytes) else str(scope.get("raw_path")),
                "root_path": scope.get("root_path", ""),
                "headers": headers_dict,
            })
            await resp(scope, receive, send)
            return

        headers = {}
        for k, v in scope.get("headers", []):
            k_str = k.decode("latin-1").lower() if isinstance(k, bytes) else str(k).lower()
            v_str = v.decode("latin-1") if isinstance(v, bytes) else str(v)
            headers[k_str] = v_str

        matched = headers.get("x-matched-path", "")
        if matched:
            if "?" in matched:
                matched = matched.split("?", 1)[0]
            if not matched.startswith("/api/index"):
                scope["path"] = matched

        path = scope.get("path", "")
        for prefix in ("/api/index.py", "/api/index"):
            if path == prefix:
                scope["path"] = "/"
                break
            elif path.startswith(prefix + "/"):
                scope["path"] = path[len(prefix):]
                break

        if not scope.get("path", "").startswith("/"):
            scope["path"] = "/" + scope.get("path", "")

    await fastapi_app(scope, receive, send)
