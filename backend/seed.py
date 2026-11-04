import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import engine, SessionLocal, Base
from app.models import Movie

def seed_movies():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing_count = db.query(Movie).count()
        if existing_count > 0:
            print(f"[Seeder] Database already contains {existing_count} movies. Skipping seed.")
            return

        data_path = Path(__file__).resolve().parent.parent / "data" / "movies.json"
        if not data_path.exists():
            raise FileNotFoundError(f"Seed file not found at {data_path}")

        with open(data_path, "r", encoding="utf-8") as f:
            movies_data = json.load(f)

        for item in movies_data:
            movie = Movie(
                id=item["id"],
                title=item["title"],
                year=item["year"],
                director=item["director"],
                genres=item["genres"],
                rating=item["rating"],
                duration=item["duration"],
                synopsis=item["synopsis"],
                poster_url=item["poster_url"],
                cast=item["cast"],
            )
            db.add(movie)

        db.commit()
        print(f"[Seeder] Successfully seeded {len(movies_data)} movies into the database!")
    except Exception as e:
        db.rollback()
        print(f"[Seeder] Error seeding database: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_movies()
