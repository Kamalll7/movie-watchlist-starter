import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Pastikan modul di dalam backend/ bisa di-import
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.database import Base, get_db
from app.main import app
from app.models import Movie

# Gunakan SQLite file khusus testing agar tidak mengotori filmlog.db utama
TEST_DB_PATH = BACKEND_DIR / "test_filmlog.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    db.add(
        Movie(
            id=1,
            title="Inception",
            year=2010,
            director="Christopher Nolan",
            genres=["Sci-Fi", "Action", "Thriller"],
            rating=8.8,
            duration="148 min",
            synopsis="Sci-fi dream heist movie.",
            poster_url="https://example.com/inception.jpg",
            cast=["Leonardo DiCaprio"],
        )
    )
    db.commit()
    db.close()
    yield
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

client = TestClient(app)

def test_discover_movies_public():
    res = client.get("/api/movies")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1
    assert data[0]["title"] == "Inception"

def test_movie_detail_not_found():
    res = client.get("/api/movies/9999")
    assert res.status_code == 404

def test_register_and_login_flow():
    reg_res = client.post(
        "/api/auth/register",
        json={"username": "kamal", "email": "kamal@ugm.ac.id", "password": "securepassword123"},
    )
    assert reg_res.status_code == 201
    assert "token" in reg_res.json()

    # Duplikat email harus ditolak dengan 409 Conflict
    dup_res = client.post(
        "/api/auth/register",
        json={"username": "kamal2", "email": "kamal@ugm.ac.id", "password": "securepassword123"},
    )
    assert dup_res.status_code == 409

    # Login dengan kredensial benar
    login_res = client.post(
        "/api/auth/login",
        json={"email": "kamal@ugm.ac.id", "password": "securepassword123"},
    )
    assert login_res.status_code == 200
    assert "token" in login_res.json()

def test_protected_routes_require_jwt():
    res_watchlist = client.get("/api/watchlist")
    assert res_watchlist.status_code == 401

    res_watched = client.get("/api/watched")
    assert res_watched.status_code == 401

def test_watchlist_crud_and_duplicate_conflict():
    login_res = client.post(
        "/api/auth/login",
        json={"email": "kamal@ugm.ac.id", "password": "securepassword123"},
    )
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Tambah ke watchlist (201 Created)
    add_res = client.post("/api/watchlist", json={"movieId": 1}, headers=headers)
    assert add_res.status_code == 201

    # 2. Tambah film yang sama lagi harus 409 Conflict
    dup_res = client.post("/api/watchlist", json={"movieId": 1}, headers=headers)
    assert dup_res.status_code == 409

    # 3. Tambah film yang tidak ada di DB harus 404 Not Found
    nf_res = client.post("/api/watchlist", json={"movieId": 9999}, headers=headers)
    assert nf_res.status_code == 404

    # 4. Hapus dari watchlist (200 OK)
    del_res = client.delete("/api/watchlist/1", headers=headers)
    assert del_res.status_code == 200

def test_watched_review_flow():
    login_res = client.post(
        "/api/auth/login",
        json={"email": "kamal@ugm.ac.id", "password": "securepassword123"},
    )
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Rating di luar 1-5 harus ditolak (400 Bad Request)
    bad_res = client.post(
        "/api/watched",
        json={"movieId": 1, "rating": 9.0, "review": "Invalid rating"},
        headers=headers,
    )
    assert bad_res.status_code == 400

    # Rating & review valid (201 Created)
    ok_res = client.post(
        "/api/watched",
        json={"movieId": 1, "rating": 5.0, "review": "Masterpiece sci-fi!"},
        headers=headers,
    )
    assert ok_res.status_code == 201
    assert ok_res.json()["rating"] == 5.0
