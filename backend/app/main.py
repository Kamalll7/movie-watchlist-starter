from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.database import Base, engine
from seed import seed_movies

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Buat tabel otomatis & jalankan seeder jika DB masih kosong saat server nyala
    Base.metadata.create_all(bind=engine)
    seed_movies()
    yield

app = FastAPI(
    title="FilmLog API — GDGoC UGM Backend Assignment",
    description="RESTful API untuk platform Movie Watchlist, Review, dan Rekomendasi Film berbasis Google Gemini LLM.",
    version="1.0.0",
    lifespan=lifespan,
)

# Izinkan CORS agar Companion Frontend (termasuk dari file:// atau localhost) bisa mengakses API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Seragamkan format error agar langsung terbaca oleh frontend/app.js (responseData.message / error)
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    detail_msg = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": detail_msg, "error": detail_msg, "detail": detail_msg},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    first_msg = errors[0].get("msg", "Invalid input") if errors else "Validation error"
    loc = " -> ".join(str(x) for x in errors[0].get("loc", []) if x != "body") if errors else ""
    clean_msg = f"{loc}: {first_msg}" if loc else first_msg
    return JSONResponse(
        status_code=400,
        content={"message": clean_msg, "error": clean_msg, "detail": errors},
    )

@app.get("/api/health", tags=["Health"])
def health_check():
    return {"status": "ok", "service": "FilmLog Backend API"}

from app.routers import auth as auth_router
app.include_router(auth_router.router)

from app.routers import movies as movies_router
app.include_router(movies_router.router)

from app.routers import watchlist as watchlist_router
app.include_router(watchlist_router.router)

from app.routers import watched as watched_router
app.include_router(watched_router.router)
