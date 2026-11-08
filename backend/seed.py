import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from app.database import engine, SessionLocal, Base
from app.models import Movie

def find_movies_json() -> Path:
    candidates = [
        BASE_DIR / "movies.json",
        BASE_DIR / "data" / "movies.json",
        BASE_DIR.parent / "data" / "movies.json",
        Path.cwd() / "data" / "movies.json",
        Path.cwd() / "backend" / "movies.json",
        Path("/var/task/movies.json"),
        Path("/var/task/backend/movies.json"),
        Path("/var/task/data/movies.json"),
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(f"Seed file movies.json not found in any expected path: {[str(p) for p in candidates]}")

def seed_movies():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing_count = db.query(Movie).count()
        if existing_count > 0:
            print(f"[Seeder] Database already contains {existing_count} movies. Skipping seed.")
            return

        data_path = find_movies_json()
        with open(data_path, "r", encoding="utf-8") as f:
            movies_data = json.load(f)

        movies_to_insert = []
        for item in movies_data:
            movie = Movie(
                id=item.get("id"),
                title=item["title"],
                year=int(item["year"]),
                director=item["director"],
                genres=item.get("genres", []),
                rating=float(item["rating"]),
                duration=item.get("duration", "N/A"),
                synopsis=item.get("synopsis", ""),
                poster_url=item.get("posterUrl") or item.get("poster_url", ""),
                cast=item.get("cast", []),
            )
            movies_to_insert.append(movie)

        db.add_all(movies_to_insert)
        db.commit()
        print(f"[Seeder] Successfully seeded {len(movies_to_insert)} movies into the database.")
    except Exception as e:
        db.rollback()
        print(f"[Seeder] Error seeding database: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_movies()
