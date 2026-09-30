"""根目录启动入口：python run_backend.py

无需手工设置 PYTHONPATH，直接可运行。
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
os.environ.setdefault("PYTHONPATH", str(SRC))


def main() -> None:
    # MySQL 不可达时自动降级 SQLite，避免本地启动即崩
    if os.getenv("DATABASE_URL", "").startswith("mysql"):
        try:
            import socket
            from urllib.parse import urlparse

            url = os.environ["DATABASE_URL"]
            host = urlparse(url).hostname or "localhost"
            port = urlparse(url).port or 3306
            with socket.create_connection((host, port), timeout=1.5):
                pass
        except Exception:
            os.environ["DATABASE_URL"] = "sqlite:///./data/vibeutopia.db"
            os.environ["MYSQL_HOST"] = ""
            print("[run_backend] MySQL 不可达，已降级为 SQLite: data/vibeutopia.db")

    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("RELOAD", "1") == "1",
    )


if __name__ == "__main__":
    main()
