from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field, model_validator

# 1. AUTH SCHEMAS

class UserRegisterRequest(BaseModel):
    username: Optional[str] = Field(default=None, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6, description="Password minimal 6 karakter")

    @model_validator(mode="after")
    def ensure_username(self):
        if not self.username or not self.username.strip():
            self.username = self.email.split("@")[0]
        return self

class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)

class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

class AuthResponse(BaseModel):
    token: str
    user: UserResponse


# 2. MOVIE SCHEMAS

class MovieResponse(BaseModel):
    id: int
    title: str
    year: int
    director: str
    genres: List[str]
    rating: float
    duration: str
    synopsis: str
    poster_url: str
    cast: List[str]

    model_config = {"from_attributes": True}


# 3. WATCHLIST SCHEMAS

class WatchlistCreateRequest(BaseModel):
    movieId: Optional[int] = None
    movie_id: Optional[int] = None

    @model_validator(mode="after")
    def check_movie_id(self):
        target_id = self.movieId if self.movieId is not None else self.movie_id
        if target_id is None:
            raise ValueError("movieId wajib diisi")
        self.movieId = target_id
        self.movie_id = target_id
        return self

class WatchlistItemResponse(BaseModel):
    id: int
    user_id: int
    movie_id: int
    movieId: int
    created_at: datetime
    movie: MovieResponse

    model_config = {"from_attributes": True}


# 4. WATCHED & REVIEW SCHEMAS

class WatchedCreateRequest(BaseModel):
    movieId: Optional[int] = None
    movie_id: Optional[int] = None
    rating: float = Field(..., ge=1.0, le=5.0, description="Rating wajib antara 1 sampai 5 bintang")
    review: Optional[str] = None
    opinion: Optional[str] = None

    @model_validator(mode="after")
    def validate_fields(self):
        target_id = self.movieId if self.movieId is not None else self.movie_id
        if target_id is None:
            raise ValueError("movieId wajib diisi")
        self.movieId = target_id
        self.movie_id = target_id

        review_text = (self.review or self.opinion or "").strip()
        if not review_text:
            raise ValueError("Isi review/opini tidak boleh kosong")
        self.review = review_text
        return self

class WatchedItemResponse(BaseModel):
    id: int
    user_id: int
    movie_id: int
    movieId: int
    rating: float
    review: str
    created_at: datetime
    movie: MovieResponse

    model_config = {"from_attributes": True}


# 5. GEMINI AI RECOMMENDATION SCHEMAS

class RecommendRequest(BaseModel):
    prompt: Optional[str] = None
    query: Optional[str] = None
    description: Optional[str] = None

    @model_validator(mode="after")
    def validate_prompt(self):
        text = (self.prompt or self.query or self.description or "").strip()
        if not text:
            raise ValueError("Prompt deskripsi film tidak boleh kosong")
        self.prompt = text
        return self

class RecommendResponse(BaseModel):
    movie_id: int
    movieId: int
    reasoning: str
    movie: Optional[MovieResponse] = None
