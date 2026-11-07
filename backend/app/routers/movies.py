import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import GEMINI_API_KEY
from app.database import get_db
from app.models import Movie
from app.schemas import MovieResponse, RecommendRequest, RecommendResponse

router = APIRouter(prefix="/api/movies", tags=["Movies"])

class GeminiOutputSchema(BaseModel):
    movie_id: int = Field(..., description="ID film yang dipilih, WAJIB berasal dari daftar katalog database lokal.")
    reasoning: str = Field(..., description="Penjelasan dalam Bahasa Indonesia mengapa film ini paling cocok dengan permintaan user.")

@router.get("", response_model=List[MovieResponse], status_code=status.HTTP_200_OK)
def get_movies(
    genre: Optional[str] = Query(None, description="Filter berdasarkan genre film (misal: Sci-Fi)"),
    search: Optional[str] = Query(None, description="Cari berdasarkan judul film atau sutradara"),
    db: Session = Depends(get_db),
):
    query = db.query(Movie)

    if search:
        search_pattern = f"%{search.strip().lower()}%"
        query = query.filter(
            (Movie.title.ilike(search_pattern)) | (Movie.director.ilike(search_pattern))
        )

    movies = query.all()

    if genre and genre.strip().upper() != "ALL":
        target_genre = genre.strip().lower()
        filtered_movies = []
        for m in movies:
            genres_list = [g.strip().lower() for g in (m.genres if isinstance(m.genres, list) else str(m.genres).split(","))]
            if target_genre in genres_list:
                filtered_movies.append(m)
        movies = filtered_movies

    return movies

@router.post("/recommend", response_model=RecommendResponse, status_code=status.HTTP_200_OK)
def recommend_movie(payload: RecommendRequest, db: Session = Depends(get_db)):
    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_google_ai_studio_api_key_here":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GEMINI_API_KEY belum dikonfigurasi di file backend/.env",
        )

    movies = db.query(Movie).all()
    if not movies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Database film kosong, jalankan seeder terlebih dahulu",
        )

    catalog_context = [
        {
            "id": m.id,
            "title": m.title,
            "year": m.year,
            "director": m.director,
            "genres": m.genres,
            "rating": m.rating,
            "synopsis": m.synopsis,
        }
        for m in movies
    ]
    valid_ids = {m.id: m for m in movies}

    system_instruction = (
        "Kamu adalah kurator film ahli untuk platform FilmLog. "
        "ATURAN KETAT (GROUNDING): Kamu HANYA BOLEH merekomendasikan SATU film yang terdapat di dalam "
        "DAFTAR KATALOG DATABASE LOKAL berikut ini. Dilarang keras mengarang atau memilih film di luar daftar ini.\n\n"
        f"DAFTAR KATALOG DATABASE LOKAL:\n{json.dumps(catalog_context, ensure_ascii=False, indent=2)}\n\n"
        "Pilih tepat satu film (movie_id) dari daftar di atas yang paling sesuai dengan suasana/deskripsi yang diminta user, "
        "dan berikan alasan (reasoning) yang menarik dalam Bahasa Indonesia."
    )

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"Permintaan User: {payload.prompt}",
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=GeminiOutputSchema,
                temperature=0.2,
            ),
        )

        result_json = json.loads(response.text)
        chosen_id = int(result_json.get("movie_id"))
        reasoning = result_json.get("reasoning", "").strip()

        if chosen_id not in valid_ids:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AI mengembalikan movie_id ({chosen_id}) di luar katalog database lokal",
            )

        matched_movie = valid_ids[chosen_id]
        return RecommendResponse(
            movie_id=matched_movie.id,
            movieId=matched_movie.id,
            reasoning=reasoning,
            movie=MovieResponse.model_validate(matched_movie),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gagal menghubungi layanan Gemini AI: {str(e)}",
        )

@router.get("/{movie_id}", response_model=MovieResponse, status_code=status.HTTP_200_OK)
def get_movie_detail(movie_id: int, db: Session = Depends(get_db)):
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Film dengan ID {movie_id} tidak ditemukan",
        )
    return movie
