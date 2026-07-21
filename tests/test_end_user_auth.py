from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

import routes_admin
import routes_user
from main import app as fastapi_app
from models import App, EndUser


def make_engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def override_session_factory(engine):
    def override_session():
        with Session(engine) as session:
            yield session

    return override_session


def override_admin_user():
    return {"sub": "admin", "is_admin": True}


def test_register_records_recent_login_for_admin_user_authorization_list():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_user.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        session.add(
            App(
                app_id="app_demo",
                name="Demo",
                app_secret="test-secret",
                rsa_public_key="public",
                rsa_private_key="private",
            )
        )
        session.commit()

    try:
        register_response = client.post(
            "/api/v1/user/register",
            json={
                "app_id": "app_demo",
                "username": "new-user",
                "password": "password123",
                "email": "new-user@example.com",
            },
        )
        assert register_response.status_code == 200
        assert register_response.json()["data"]["user"]["last_login"] is not None

        admin_response = client.get(
            "/api/v1/admin/end-users",
            params={"app_id": "app_demo"},
        )
        assert admin_response.status_code == 200
        item = admin_response.json()["data"]["items"][0]
        assert item["username"] == "new-user"
        assert item["last_login"] is not None

        with Session(engine) as session:
            user = session.exec(select(EndUser).where(EndUser.username == "new-user")).one()
            assert user.last_login is not None
    finally:
        fastapi_app.dependency_overrides.clear()
