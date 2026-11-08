from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse

from app.database import Base, engine
from seed import seed_movies
from app.routers import auth as auth_router
from app.routers import movies as movies_router
from app.routers import watchlist as watchlist_router
from app.routers import watched as watched_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    try:
        seed_movies()
    except Exception as e:
        print(f"[Startup Warning] Auto-seed skipped or failed: {e}")
    yield

app = FastAPI(
    title="FilmLog API — GDGoC UGM Backend Assignment",
    description="RESTful API untuk Movie Watchlist, Reviews, dan Rekomendasi Film berbasis Gemini AI",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    first_msg = errors[0].get("msg", "Input tidak valid") if errors else "Input tidak valid"
    field_loc = " -> ".join(str(loc) for loc in errors[0].get("loc", []) if loc != "body") if errors else ""
    detail_msg = f"Validasi gagal pada '{field_loc}': {first_msg}" if field_loc else f"Validasi gagal: {first_msg}"
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": detail_msg, "message": detail_msg, "errors": errors},
    )

@app.get("/", include_in_schema=False)
def serve_frontend():
    candidates = [
        Path(__file__).resolve().parent.parent / "index.html",
        Path(__file__).resolve().parent.parent.parent / "frontend" / "index.html",
        Path(__file__).resolve().parent.parent.parent / "index.html",
    ]
    for html_path in candidates:
        if html_path.exists():
            return HTMLResponse(content=html_path.read_text(encoding="utf-8"), status_code=200)
    return {"status": "ok", "message": "FilmLog Backend API is running. Visit /docs for Swagger UI or /api/movies."}

@app.get("/api/health", tags=["Health"])
def health_check():
    return {"status": "ok", "service": "FilmLog Backend API"}

app.include_router(auth_router.router)
app.include_router(movies_router.router)
app.include_router(watchlist_router.router)
app.include_router(watched_router.router)
