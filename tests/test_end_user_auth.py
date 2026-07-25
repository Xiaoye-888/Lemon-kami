from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

import routes_admin
import routes_user
from auth_utils import hash_password
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


def test_application_user_register_requires_app_id():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_user.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    try:
        response = client.post(
            "/api/v1/user/register",
            json={"username": "floating-user", "password": "password123"},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "APP_ID_REQUIRED"

        with Session(engine) as session:
            user = session.exec(select(EndUser).where(EndUser.username == "floating-user")).first()
            assert user is None
    finally:
        fastapi_app.dependency_overrides.clear()


def test_merchant_accounts_cannot_use_application_user_api():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_user.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        merchant = EndUser(
            username="merchant-login-boundary",
            password_hash=hash_password("password123"),
            app_id=None,
            status=1,
        )
        session.add(merchant)
        session.commit()
        session.refresh(merchant)
        merchant_token = routes_user.create_user_access_token(merchant)

    try:
        login_response = client.post(
            "/api/v1/user/login",
            json={"username": "merchant-login-boundary", "password": "password123"},
        )
        assert login_response.status_code == 403
        assert login_response.json()["detail"]["code"] == "MERCHANT_ACCOUNT_NOT_ALLOWED"

        me_response = client.get(
            "/api/v1/user/me",
            headers={"Authorization": f"Bearer {merchant_token}"},
        )
        assert me_response.status_code == 403
        assert me_response.json()["detail"]["code"] == "MERCHANT_ACCOUNT_NOT_ALLOWED"

        balance_response = client.get(
            "/api/v1/user/points/balance",
            headers={"Authorization": f"Bearer {merchant_token}"},
        )
        assert balance_response.status_code == 403
        assert balance_response.json()["detail"]["code"] == "MERCHANT_ACCOUNT_NOT_ALLOWED"
    finally:
        fastapi_app.dependency_overrides.clear()
