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


def test_public_docs_sdk_user_identity_fields_are_documented_together():
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
            params={"page_size": 100},
            headers={"accept": "application/json"},
        )

        assert response.status_code == 200
        items = response.json()["data"]["items"]
        by_key = {item["interface_key"]: item for item in items}

        for interface_key in ("sdk.verify", "sdk.consume"):
            params = {item["name"]: item for item in by_key[interface_key]["request_params"]}
            assert "payload.user_id" in params
            assert "payload.username" in params
            assert params["payload.user_id"]["required"] is False
            assert params["payload.username"]["required"] is False
            assert "user_id" in by_key[interface_key]["remark"]
            assert "username" in by_key[interface_key]["remark"]

        verify_params = {item["name"]: item for item in by_key["sdk.verify"]["request_params"]}
        assert "稳定绑定标识" in verify_params["payload.user_id"]["description"]
        assert "后台展示注册用户名" in verify_params["payload.username"]["description"]
    finally:
        fastapi_app.dependency_overrides.clear()
