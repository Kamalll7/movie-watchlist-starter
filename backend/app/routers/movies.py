from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Movie
from app.schemas import MovieResponse

router = APIRouter(prefix="/api/movies", tags=["Movies"])

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

    # Filter genre secara fleksibel di Python (karena disimpan dalam list/JSON)
    if genre and genre.strip().upper() != "ALL":
        target_genre = genre.strip().lower()
        filtered_movies = []
        for m in movies:
            genres_list = [g.strip().lower() for g in (m.genres if isinstance(m.genres, list) else str(m.genres).split(","))]
            if target_genre in genres_list:
                filtered_movies.append(m)
        movies = filtered_movies

    return movies

@router.get("/{movie_id}", response_model=MovieResponse, status_code=status.HTTP_200_OK)
def get_movie_detail(movie_id: int, db: Session = Depends(get_db)):
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Film dengan ID {movie_id} tidak ditemukan",
        )
    return movie
