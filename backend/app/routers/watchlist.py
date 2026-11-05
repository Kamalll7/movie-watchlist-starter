from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from app.models import Movie, User, Watchlist
from app.schemas import MovieResponse, WatchlistCreateRequest, WatchlistItemResponse

router = APIRouter(prefix="/api/watchlist", tags=["Watchlist"])

def serialize_watchlist_item(item: Watchlist) -> WatchlistItemResponse:
    return WatchlistItemResponse(
        id=item.id,
        user_id=item.user_id,
        movie_id=item.movie_id,
        movieId=item.movie_id,
        created_at=item.created_at,
        movie=MovieResponse.model_validate(item.movie),
    )

@router.get("", response_model=List[WatchlistItemResponse], status_code=status.HTTP_200_OK)
def get_user_watchlist(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = (
        db.query(Watchlist)
        .options(joinedload(Watchlist.movie))
        .filter(Watchlist.user_id == current_user.id)
        .order_by(Watchlist.created_at.desc())
        .all()
    )
    return [serialize_watchlist_item(item) for item in items]

@router.post("", response_model=WatchlistItemResponse, status_code=status.HTTP_201_CREATED)
def add_to_watchlist(
    payload: WatchlistCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    movie = db.query(Movie).filter(Movie.id == payload.movie_id).first()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Film dengan ID {payload.movie_id} tidak ditemukan di database",
        )

    existing = (
        db.query(Watchlist)
        .filter(
            Watchlist.user_id == current_user.id,
            Watchlist.movie_id == payload.movie_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Film ini sudah ada di dalam watchlist kamu",
        )

    new_item = Watchlist(user_id=current_user.id, movie_id=payload.movie_id)
    db.add(new_item)
    db.commit()
    db.refresh(new_item)

    new_item.movie = movie
    return serialize_watchlist_item(new_item)

@router.delete("/{movie_id}", status_code=status.HTTP_200_OK)
def remove_from_watchlist(
    movie_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = (
        db.query(Watchlist)
        .filter(
            Watchlist.user_id == current_user.id,
            Watchlist.movie_id == movie_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Film tidak ditemukan di dalam watchlist kamu",
        )

    db.delete(item)
    db.commit()
    return {"message": "Film berhasil dihapus dari watchlist", "movieId": movie_id}
