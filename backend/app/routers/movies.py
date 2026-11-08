import json
import os
import re
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Movie
from app.schemas import MovieResponse, RecommendRequest, RecommendResponse
from app import config

router = APIRouter(prefix="/api/movies", tags=["Movies"])


@router.get("", response_model=List[MovieResponse])
def get_movies(
    genre: Optional[str] = Query(default=None, description="Filter berdasarkan nama genre"),
    search: Optional[str] = Query(default=None, description="Cari berdasarkan judul atau sutradara"),
    db: Session = Depends(get_db),
):
    movies = db.query(Movie).order_by(Movie.id.asc()).all()

    if genre and genre.strip().lower() not in ("", "all"):
        target_genre = genre.strip().lower()
        movies = [
            m for m in movies
            if any(target_genre == g.lower() for g in (m.genres or []))
        ]

    if search and search.strip():
        q = search.strip().lower()
        movies = [
            m for m in movies
            if q in m.title.lower()
            or q in m.director.lower()
            or q in (m.synopsis or "").lower()
        ]

    return movies


def _local_smart_fallback(prompt: str, movies: list) -> tuple:
    """Fallback cerdas berbasis pencocokan kata kunci lokal jika kuota/koneksi API sedang gangguan."""
    q_words = [w.lower() for w in re.findall(r"\w+", prompt) if len(w) > 2]
    best_movie = movies[0]
    best_score = -1

    for m in movies:
        haystack = f"{m.title} {m.director} {' '.join(m.genres or [])} {m.synopsis}".lower()
        score = sum(3 if w in [g.lower() for g in (m.genres or [])] else (1 if w in haystack else 0) for w in q_words)
        score += (m.rating or 0) * 0.1
        if score > best_score:
            best_score = score
            best_movie = m

    genres_str = ", ".join(best_movie.genres or [])
    reasoning = (
        f"Berdasarkan preferensi Anda, '{best_movie.title}' ({best_movie.year}) karya sutradara {best_movie.director} "
        f"adalah pilihan paling tepat di katalog kami. Film bergenre {genres_str} dengan rating {best_movie.rating} ini "
        f"menawarkan cerita yang sangat relevan: {best_movie.synopsis}"
    )
    return best_movie, reasoning


@router.post("/recommend", response_model=RecommendResponse)
def recommend_movie(payload: RecommendRequest, db: Session = Depends(get_db)):
    api_key = (os.getenv("GEMINI_API_KEY") or config.GEMINI_API_KEY or "").strip()
    if not api_key or api_key == "your-gemini-api-key-here":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GEMINI_API_KEY belum dikonfigurasi pada file backend/.env",
        )

    movies = db.query(Movie).order_by(Movie.id.asc()).all()
    if not movies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Database film masih kosong.",
        )

    catalog_for_prompt = [
        {
            "id": m.id,
            "title": m.title,
            "year": m.year,
            "genres": m.genres,
            "rating": m.rating,
            "synopsis": (m.synopsis or "")[:140],
        }
        for m in movies
    ]
    valid_ids = {m.id: m for m in movies}

    full_prompt = (
        "Anda adalah kurator film cerdas untuk aplikasi FilmLog.\n"
        "ATURAN MUTLAK (GROUNDING): Pilih TEPAT SATU film HANYA dari daftar JSON KATALOG di bawah ini. "
        "DILARANG memilih film di luar daftar.\n"
        "Balas HANYA dengan format JSON murni (tanpa markdown) dengan key:\n"
        '{"movie_id": <int id film>, "reasoning": "<2-3 kalimat alasan menarik dalam bahasa yang sesuai dengan prompt user>"}\n\n'
        f"KATALOG DATABASE LOKAL:\n{json.dumps(catalog_for_prompt, ensure_ascii=False)}\n\n"
        f"Permintaan user: {payload.prompt}"
    )

    try:
        from google import genai

        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=full_prompt,
        )

        raw_text = (response.text or "").strip()
        print(f"[AI Recommend] Raw response dari Gemini: {raw_text[:200]}")

        # Ekstrak blok JSON {...} meskipun dibungkus ```json ... ```
        json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if not json_match:
            raise ValueError(f"Output Gemini bukan JSON: {raw_text}")

        parsed_data = json.loads(json_match.group(0))
        chosen_id = int(parsed_data.get("movie_id"))
        reasoning = str(parsed_data.get("reasoning", "")).strip()

        chosen_movie = valid_ids.get(chosen_id, movies[0])

    except Exception as e:
        print(f"[AI Recommend Warning] Gemini SDK gagal ({type(e).__name__}: {e}). Menggunakan Smart Grounded Fallback.")
        chosen_movie, reasoning = _local_smart_fallback(payload.prompt, movies)

    movie_schema = MovieResponse.model_validate(chosen_movie)

    return RecommendResponse(
        movie=movie_schema,
        recommendation=reasoning,
        reason=reasoning,
        explanation=reasoning,
    )


@router.get("/{movie_id}", response_model=MovieResponse)
def get_movie_detail(movie_id: int, db: Session = Depends(get_db)):
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Film dengan ID {movie_id} tidak ditemukan.",
        )
    return movie
