import json
import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

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


class GeminiOutputSchema(BaseModel):
    movie_id: int
    reasoning: str


@router.post("/recommend", response_model=RecommendResponse)
def recommend_movie(payload: RecommendRequest, db: Session = Depends(get_db)):
    api_key = os.getenv("GEMINI_API_KEY") or config.GEMINI_API_KEY
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

    system_instruction = (
        "Anda adalah kurator film FilmLog. "
        "ATURAN GROUNDING: Pilih TEPAT SATU film HANYA dari daftar JSON di bawah ini. "
        "DILARANG memilih film di luar daftar. "
        "Kembalikan JSON sesuai skema berisi 'movie_id' (int) dan 'reasoning' (2 kalimat alasan menarik).\n"
        f"KATALOG:\n{json.dumps(catalog_for_prompt, ensure_ascii=False, separators=(',', ':'))}"
    )

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key.strip())

        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=f"Permintaan user: {payload.prompt}",
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=GeminiOutputSchema,
                temperature=0.2,
            ),
        )

        if not response or not response.text:
            raise RuntimeError("Respons kosong dari Gemini AI.")

        parsed_data = json.loads(response.text)
        chosen_id = int(parsed_data.get("movie_id"))
        reasoning = parsed_data.get("reasoning", "").strip()

        chosen_movie = valid_ids.get(chosen_id, movies[0])
        movie_schema = MovieResponse.model_validate(chosen_movie)

        return RecommendResponse(
            movie=movie_schema,
            recommendation=reasoning,
            reason=reasoning,
            explanation=reasoning,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gagal memanggil layanan Gemini AI: {str(e)}",
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
