from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from app.models import Movie, Review, User, Watchlist
from app.schemas import MovieResponse, WatchedCreateRequest, WatchedItemResponse

router = APIRouter(prefix="/api/watched", tags=["Watched & Reviews"])

def serialize_watched_item(item: Review) -> WatchedItemResponse:
    return WatchedItemResponse(
        id=item.id,
        user_id=item.user_id,
        movie_id=item.movie_id,
        movieId=item.movie_id,
        rating=item.rating,
        review=item.review,
        created_at=item.created_at,
        movie=MovieResponse.model_validate(item.movie),
    )

@router.get("", response_model=List[WatchedItemResponse], status_code=status.HTTP_200_OK)
def get_watched_movies(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = (
        db.query(Review)
        .options(joinedload(Review.movie))
        .filter(Review.user_id == current_user.id)
        .order_by(Review.created_at.desc())
        .all()
    )
    return [serialize_watched_item(item) for item in items]

@router.post("", response_model=WatchedItemResponse, status_code=status.HTTP_201_CREATED)
def log_watched_movie(
    payload: WatchedCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    movie = db.query(Movie).filter(Movie.id == payload.movie_id).first()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Film dengan ID {payload.movie_id} tidak ditemukan di database",
        )

    new_review = Review(
        user_id=current_user.id,
        movie_id=payload.movie_id,
        rating=payload.rating,
        review=payload.review,
    )
    db.add(new_review)

    # Jika film ada di watchlist user, otomatis hapus dari watchlist karena sudah ditonton
    watchlist_item = (
        db.query(Watchlist)
        .filter(
            Watchlist.user_id == current_user.id,
            Watchlist.movie_id == payload.movie_id,
        )
        .first()
    )
    if watchlist_item:
        db.delete(watchlist_item)

    db.commit()
    db.refresh(new_review)

    new_review.movie = movie
    return serialize_watched_item(new_review)
