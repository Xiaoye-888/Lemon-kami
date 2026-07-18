from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from config import settings
from main import get_cors_allowed_origins
from main import app as fastapi_app


def _cors_kwargs():
    cors_layers = [
        middleware
        for middleware in fastapi_app.user_middleware
        if middleware.cls is CORSMiddleware
    ]
    assert len(cors_layers) == 1
    return cors_layers[0].kwargs


def test_builtin_fastapi_docs_are_disabled_by_default():
    assert fastapi_app.docs_url is None
    assert fastapi_app.redoc_url is None
    assert fastapi_app.openapi_url is None


def test_production_cors_does_not_fall_back_to_wildcard():
    assert _cors_kwargs()["allow_origins"] == []


def test_production_cors_filters_explicit_wildcard(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", False)
    monkeypatch.setattr(settings, "CORS_ALLOWED_ORIGINS", "*, http://154.12.26.231")

    assert get_cors_allowed_origins() == ["http://154.12.26.231"]


def test_root_does_not_advertise_disabled_builtin_docs():
    response = TestClient(fastapi_app).get("/")
    assert response.status_code == 200
    body = response.json()

    assert "docs" not in body
    assert "redoc" not in body
    assert body["public_docs"] == "/docs/api#basic-info"
