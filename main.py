"""ASGI entrypoint compatible with Render's default `uvicorn main:app`."""

from pathlib import Path
import sys


backend_path = Path(__file__).resolve().parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.main import app  # noqa: E402

__all__ = ["app"]
