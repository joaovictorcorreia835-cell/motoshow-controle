import os
from pathlib import Path

basedir = Path(__file__).resolve().parent


def _get_env(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _database_url():
    url = _get_env("DATABASE_URL", f"sqlite:///{basedir / 'motoshow.db'}")
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


class Config:
    SECRET_KEY = _get_env("SECRET_KEY", "change-this-secret-key")
    APP_ENV = _get_env("APP_ENV", "development")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {"check_same_thread": False}
    } if SQLALCHEMY_DATABASE_URI.startswith("sqlite:") else {}
    FLASK_ENV = _get_env("FLASK_ENV", "development")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = APP_ENV == "production"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = APP_ENV == "production"
    PREFERRED_URL_SCHEME = "https" if APP_ENV == "production" else "http"
