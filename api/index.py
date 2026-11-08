import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend"))

from app.main import app
from seed import seed_movies

# Pastikan /tmp/filmlog.db langsung terisi 20 film saat instance Vercel menyala
try:
    seed_movies()
except Exception as e:
    print(f"Seed info: {e}")
