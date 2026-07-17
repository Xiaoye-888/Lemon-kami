from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

import routes_docs
from main import app as fastapi_app


def make_engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def test_public_docs_interfaces_redirects_browser_to_readable_page():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    fastapi_app.dependency_overrides[routes_docs.get_session] = override_session
    client = TestClient(fastapi_app)

    try:
        response = client.get(
            "/api/v1/docs/interfaces",
            headers={"accept": "text/html,application/xhtml+xml"},
            follow_redirects=False,
        )

        assert response.status_code == 307
        assert response.headers["location"] == "/docs/api#basic-info"
    finally:
        fastapi_app.dependency_overrides.clear()


def test_public_docs_interfaces_keeps_json_for_api_clients():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    fastapi_app.dependency_overrides[routes_docs.get_session] = override_session
    client = TestClient(fastapi_app)

    try:
        response = client.get(
            "/api/v1/docs/interfaces",
            headers={"accept": "application/json"},
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        body = response.json()
        assert body["success"] is True
        assert body["data"]["total"] >= 1
    finally:
        fastapi_app.dependency_overrides.clear()
