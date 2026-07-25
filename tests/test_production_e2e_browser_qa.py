import importlib.util
import base64
import hashlib
import subprocess
import requests
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "production_e2e_browser_qa.py"


def load_qa_module():
    spec = importlib.util.spec_from_file_location("production_e2e_browser_qa", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text if text is not None else ""

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, "kwargs": kwargs})
        if not self.responses:
            raise AssertionError("unexpected API request")
        return self.responses.pop(0)


class FakeAPIClient:
    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.calls = []

    def json(self, method, path, expected=(200,), **kwargs):
        self.calls.append({"method": method, "path": path, "expected": expected, "kwargs": kwargs})
        if not self.responses:
            return {"success": True, "data": {}}
        response = self.responses.pop(0)
        return response() if callable(response) else response


def install_fake_api_session(monkeypatch, qa, session):
    original_init = qa.APIClient.__init__

    def fake_init(self, base_url, auth=None):
        original_init(self, base_url, auth)
        self.session = session

    monkeypatch.setattr(qa.APIClient, "__init__", fake_init)


def secret_digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def assert_text_excludes_secrets(text, secrets):
    for secret in secrets:
        if secret in text:
            raise AssertionError("sensitive value leaked")


def test_secret_redaction_masks_sensitive_values():
    qa = load_qa_module()
    payload = {
        "token": "abc123secret",
        "api_token": "api-token-value",
        "csrf_token": "csrf-token-value",
        "authToken": "auth-token-value",
        "auth": "auth-value",
        "auth_header": "auth-header-value",
        "proxy_auth": "proxy-auth-value",
        "session": "session-value",
        "session_id": "session-id-value",
        "sessionid": "sessionid-value",
        "browser_session": "browser-session-value",
        "password": "dont-show",
        "server_password": "server-password-value",
        "db_password": "db-password-value",
        "cookie": "session=value",
        "ssh_key": "ssh-private-key-value",
        "private_key": "private-key-value",
        "nested": {
            "app_secret": "app-secret-value",
            "kami_code": "KAMI-ABCDEFG1234567",
            "device_fingerprint": "fingerprint-1234567890",
        },
    }
    redacted = qa.redact(payload)
    assert redacted["token"] == "<redacted>"
    assert redacted["api_token"] == "<redacted>"
    assert redacted["csrf_token"] == "<redacted>"
    assert redacted["authToken"] == "<redacted>"
    assert redacted["auth"] == "<redacted>"
    assert redacted["auth_header"] == "<redacted>"
    assert redacted["proxy_auth"] == "<redacted>"
    assert redacted["session"] == "<redacted>"
    assert redacted["session_id"] == "<redacted>"
    assert redacted["sessionid"] == "<redacted>"
    assert redacted["browser_session"] == "<redacted>"
    assert redacted["password"] == "<redacted>"
    assert redacted["server_password"] == "<redacted>"
    assert redacted["db_password"] == "<redacted>"
    assert redacted["cookie"] == "<redacted>"
    assert redacted["ssh_key"] == "<redacted>"
    assert redacted["private_key"] == "<redacted>"
    assert redacted["nested"]["app_secret"] == "<redacted>"
    assert redacted["nested"]["kami_code"].startswith("KAM")
    assert "***" in redacted["nested"]["kami_code"]
    assert redacted["nested"]["device_fingerprint"].endswith("890")


def test_config_from_env_requires_exact_production_confirmation(monkeypatch):
    qa = load_qa_module()
    monkeypatch.setenv("LEMON_QA_BASE_URL", "https://qa.example.invalid")
    monkeypatch.setenv("LEMON_QA_ADMIN_USERNAME", "fake-admin")
    monkeypatch.setenv("LEMON_QA_ADMIN_PASSWORD", "fake-password")
    monkeypatch.setenv("LEMON_QA_CONFIRM_PRODUCTION", "yes")

    try:
        qa.QAConfig.from_env()
    except qa.QASafetyError as error:
        message = str(error)
        assert "LEMON_QA_CONFIRM_PRODUCTION" in message
        assert "yes" not in message
    else:
        raise AssertionError("config accepted missing production confirmation")


def test_config_from_env_rejects_missing_or_invalid_values_without_leaking(monkeypatch):
    qa = load_qa_module()
    fake_values = {
        "LEMON_QA_BASE_URL": "ftp://fake-secret-host.invalid",
        "LEMON_QA_ADMIN_USERNAME": " ",
        "LEMON_QA_ADMIN_PASSWORD": "fake-password-should-not-leak",
        "LEMON_QA_CONFIRM_PRODUCTION": "wrong-confirmation-should-not-leak",
    }
    for key, value in fake_values.items():
        monkeypatch.setenv(key, value)

    try:
        qa.QAConfig.from_env()
    except qa.QASafetyError as error:
        message = str(error)
        assert "LEMON_QA_BASE_URL" in message
        assert "LEMON_QA_ADMIN_USERNAME" in message
        assert "LEMON_QA_CONFIRM_PRODUCTION" in message
        assert "ftp://fake-secret-host.invalid" not in message
        assert "fake-password-should-not-leak" not in message
        assert "wrong-confirmation-should-not-leak" not in message
    else:
        raise AssertionError("config accepted invalid env values")


def test_config_from_env_rejects_missing_credentials_and_confirmation(monkeypatch):
    qa = load_qa_module()
    for key in (
        "LEMON_QA_BASE_URL",
        "LEMON_QA_ADMIN_USERNAME",
        "LEMON_QA_ADMIN_PASSWORD",
        "LEMON_QA_CONFIRM_PRODUCTION",
    ):
        monkeypatch.delenv(key, raising=False)

    try:
        qa.QAConfig.from_env()
    except qa.QASafetyError as error:
        message = str(error)
        assert "LEMON_QA_BASE_URL" in message
        assert "LEMON_QA_ADMIN_USERNAME" in message
        assert "LEMON_QA_ADMIN_PASSWORD" in message
        assert "LEMON_QA_CONFIRM_PRODUCTION" in message
    else:
        raise AssertionError("config accepted missing env values")


def test_config_from_env_builds_config_without_printing_values(monkeypatch, capsys):
    qa = load_qa_module()
    env = {
        "LEMON_QA_BASE_URL": "https://qa.example.invalid/",
        "LEMON_QA_ADMIN_USERNAME": "fake-admin",
        "LEMON_QA_ADMIN_PASSWORD": "fake-password-not-printed",
        "LEMON_QA_CONFIRM_PRODUCTION": qa.PRODUCTION_CONFIRMATION,
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    config = qa.QAConfig.from_env()

    assert config.base_url == env["LEMON_QA_BASE_URL"]
    assert config.admin_username == env["LEMON_QA_ADMIN_USERNAME"]
    assert config.admin_password == env["LEMON_QA_ADMIN_PASSWORD"]
    assert config.confirmation == qa.PRODUCTION_CONFIRMATION
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_auth_session_browser_storage_uses_frontend_keys():
    qa = load_qa_module()
    session = qa.AuthSession(
        token="fake-token",
        role="admin",
        user_info={"id": 1, "username": "fake-admin"},
    )

    assert session.as_browser_storage() == {
        "token": "fake-token",
        "role": "admin",
        "userInfo": {"id": 1, "username": "fake-admin"},
    }


def test_api_client_attaches_bearer_authorization_and_default_timeout():
    qa = load_qa_module()
    auth = qa.AuthSession(token="fake-token", role="admin", user_info={})
    session = FakeSession([FakeResponse(payload={"success": True})])
    client = qa.APIClient("https://qa.example.invalid/", auth=auth)
    client.session = session

    response = client.request("GET", "/api/v1/protected")

    assert response.status_code == 200
    call = session.calls[0]
    assert call["url"] == "https://qa.example.invalid/api/v1/protected"
    assert call["kwargs"]["headers"]["Authorization"] == "Bearer fake-token"
    assert call["kwargs"]["timeout"] == 30


def test_api_client_wraps_request_exception_without_leaking_auth_or_password():
    qa = load_qa_module()
    token = "fake-client-session-value"
    password = "fake-request-passphrase"

    class FailingSession:
        def request(self, method, url, **kwargs):
            raise requests.RequestException(
                f"Authorization: Bearer {token}; password={password}; token={token}"
            )

    client = qa.APIClient(
        "https://qa.example.invalid",
        auth=qa.AuthSession(token=token, role="admin", user_info={}),
    )
    client.session = FailingSession()

    try:
        client.request("POST", "/api/v1/protected", json={"password": password})
    except qa.QASafetyError as error:
        message = str(error)
        assert "API POST /api/v1/protected request failed" in message
        assert_text_excludes_secrets(message, [token, password])
    else:
        raise AssertionError("request exception was not wrapped")


def test_login_uses_aes_key_for_encrypted_payload_and_returns_auth_session(monkeypatch):
    qa = load_qa_module()
    from crypto import CryptoHelper

    aes_key = base64.b64encode(b"0123456789abcdef").decode("ascii")
    response_token = "fake-session-value"
    password = "fake-passphrase"
    session = FakeSession(
        [
            FakeResponse(payload={"success": True, "aes_key": aes_key}),
            FakeResponse(
                payload={
                    "success": True,
                    "token": response_token,
                    "role": "admin",
                    "user_info": {"id": 1, "username": "fake-admin"},
                }
            ),
        ]
    )
    install_fake_api_session(monkeypatch, qa, session)
    auth = qa.login("https://qa.example.invalid", "fake-admin", password)

    assert secret_digest(auth.token) == secret_digest(response_token)
    assert auth.role == "admin"
    assert auth.user_info == {"id": 1, "username": "fake-admin"}
    assert session.calls[0]["method"] == "GET"
    assert session.calls[0]["url"].endswith("/api/v1/auth/login/public-key")
    assert session.calls[1]["method"] == "POST"
    payload = session.calls[1]["kwargs"]["json"]
    assert payload["encrypted"] is True
    assert "encrypted_data" in payload
    assert "iv" in payload
    assert "username" not in payload
    assert "password" not in payload
    decrypted = CryptoHelper.aes_decrypt(
        encrypted_data=payload["encrypted_data"],
        key_b64=aes_key,
        iv=payload["iv"],
    )
    assert decrypted["username"] == "fake-admin"
    assert secret_digest(decrypted["password"]) == secret_digest(password)


def test_login_rejects_advertised_aes_key_when_encryption_fails_without_posting(monkeypatch):
    qa = load_qa_module()
    username = "fake-admin"
    password = "fake-passphrase"
    session = FakeSession([FakeResponse(payload={"success": True, "aes_key": "not-valid-aes-key"})])
    install_fake_api_session(monkeypatch, qa, session)

    try:
        qa.login("https://qa.example.invalid", username, password)
    except qa.QASafetyError as error:
        message = str(error)
        assert "encrypted login payload" in message
        assert_text_excludes_secrets(message, [username, password])
    else:
        raise AssertionError("login fell back after advertised AES encryption failed")

    assert len(session.calls) == 1


def test_login_falls_back_to_plaintext_payload_for_legacy_public_key_only_response(monkeypatch):
    qa = load_qa_module()
    password = "fake-passphrase"
    session = FakeSession(
        [
            FakeResponse(payload={"success": True, "public_key": "unused-public-key"}),
            FakeResponse(
                payload={
                    "success": True,
                    "token": "fake-session-value",
                    "role": "admin",
                    "user_info": {"id": 1, "username": "fake-admin"},
                }
            ),
        ]
    )
    install_fake_api_session(monkeypatch, qa, session)
    auth = qa.login("https://qa.example.invalid", "fake-admin", password)

    assert auth.role == "admin"
    assert auth.user_info["username"] == "fake-admin"
    payload = session.calls[1]["kwargs"]["json"]
    assert payload["encrypted"] is False
    assert payload["username"] == "fake-admin"
    assert secret_digest(payload["password"]) == secret_digest(password)


def test_login_requires_token_and_sanitizes_password_and_token_in_error(monkeypatch):
    qa = load_qa_module()
    session = FakeSession(
        [
            FakeResponse(payload={"success": True}),
            FakeResponse(
                payload={
                    "success": True,
                    "role": "admin",
                    "user_info": {"token": "fake-nested-session-value-should-not-leak"},
                },
                text='{"token":"fake-session-value-should-not-leak","detail":"fake-passphrase-should-not-leak"}',
            ),
        ]
    )
    install_fake_api_session(monkeypatch, qa, session)
    try:
        qa.login("https://qa.example.invalid", "fake-admin", "fake-passphrase-should-not-leak")
    except qa.QASafetyError as error:
        message = str(error)
        assert "token" in message.lower()
        assert_text_excludes_secrets(
            message,
            [
                "fake-passphrase-should-not-leak",
                "fake-session-value-should-not-leak",
                "fake-nested-session-value-should-not-leak",
            ],
        )
    else:
        raise AssertionError("login accepted a response without token")


def test_run_prefix_is_unique_and_delete_safe():
    qa = load_qa_module()
    first_prefix = qa.build_run_prefix(datetime(2026, 7, 26, 3, 0, 0), suffix="abc123")
    second_prefix = qa.build_run_prefix(datetime(2026, 7, 26, 3, 0, 0), suffix="def456")
    assert first_prefix == "E2E_UI_QA_20260726_030000_abc123_"
    assert second_prefix == "E2E_UI_QA_20260726_030000_def456_"
    assert first_prefix != second_prefix
    generated_prefix = qa.build_run_prefix(datetime(2026, 7, 26, 3, 0, 0))
    assert generated_prefix.startswith("E2E_UI_QA_20260726_030000_")
    assert generated_prefix.endswith("_")
    assert generated_prefix != "E2E_UI_QA_20260726_030000_"

    prefix = qa.build_run_prefix(datetime(2026, 7, 26, 3, 0, 2), suffix="ghi789")
    assert prefix.startswith("E2E_UI_QA_")
    assert prefix.endswith("_")
    assert qa.is_owned_by_run(prefix + "merchant", prefix) is True
    assert qa.is_owned_by_run("real-user", prefix) is False


def test_cleanup_prefix_validation_rejects_malformed_prefixes():
    qa = load_qa_module()
    malformed_prefixes = [
        "",
        "prod",
        "admin",
        "E2E_UI_QA_",
        "E2E_UI_QA_20260726_030000_",
        "E2E_UI_QA_20260726_030000_bad!_",
    ]
    for prefix in malformed_prefixes:
        try:
            qa.validate_run_prefix(prefix)
        except qa.QASafetyError as error:
            assert "Invalid QA run prefix" in str(error)
        else:
            raise AssertionError(f"cleanup prefix validation allowed {prefix!r}")

        assert qa.is_owned_by_run(prefix + "resource", prefix) is False

    assert (
        qa.is_owned_by_run(
            "E2E_UI_QA_20260726_030000_abc123_app",
            "E2E_UI_QA_20260726_030000_",
        )
        is False
    )


def test_cleanup_guard_rejects_non_prefixed_resources():
    qa = load_qa_module()
    prefix = "E2E_UI_QA_20260726_030000_abc123_"
    qa.assert_owned_by_run(prefix + "app", prefix)
    try:
        qa.assert_owned_by_run("production-app", prefix)
    except qa.QASafetyError as error:
        assert "Refusing cleanup" in str(error)
    else:
        raise AssertionError("cleanup guard allowed non-prefixed resource")


def test_report_writer_sanitizes_forbidden_secret_words(tmp_path):
    qa = load_qa_module()
    report = qa.QAReport(run_id="E2E_UI_QA_20260726_030000_abc123", artifact_dir=tmp_path)
    report.add_section("Safe", ["health 200", "orders cleaned"])
    report.write()
    assert (tmp_path / "production-e2e-browser-report.md").exists()

    report.add_section("Unsafe", ["token=abc123"])
    content = report.render()
    assert "token=abc123" not in content
    assert "<redacted>" in content
    report.write()


def test_report_writer_redacts_structured_section_lines(tmp_path):
    qa = load_qa_module()
    report = qa.QAReport(run_id="E2E_UI_QA_20260726_030000_abc123", artifact_dir=tmp_path)
    report.add_section(
        "Structured",
        [
            {
                "api_token": "api-token-value",
                "auth": "auth-value",
                "auth_cookie": "auth-cookie-value",
                "proxy_auth": "proxy-auth-value",
                "session_id": "session-id-value",
                "sessionid": "sessionid-value",
                "browser_session": "browser-session-value",
                "server_password": "server-password-value",
                "kami_code": "KAMI-ABCDEFG1234567",
                "device_fingerprint": "fingerprint-1234567890",
                "nested": [{"private_key": "private-key-value"}],
            }
        ],
    )

    content = report.render()
    assert "api-token-value" not in content
    assert "auth-value" not in content
    assert "auth-cookie-value" not in content
    assert "proxy-auth-value" not in content
    assert "session-id-value" not in content
    assert "sessionid-value" not in content
    assert "browser-session-value" not in content
    assert "server-password-value" not in content
    assert "private-key-value" not in content
    assert "KAM***567" in content
    assert "fin***890" in content
    assert "<redacted>" in content
    report.write()
    assert (tmp_path / "production-e2e-browser-report.md").exists()


def test_report_writer_sanitizes_free_form_sensitive_lines(tmp_path):
    qa = load_qa_module()
    sensitive_samples = [
        "created card KAMI-ABCDEFG1234567 for smoke test",
        "device fingerprint fingerprint-1234567890 observed",
        "response cookie session=temporary-session-value",
        "Authorization: Bearer bearer-like-value",
        "auth=dummy-auth-value",
        "url /x?auth=query-auth-value&auth_token=query-auth-token-value",
        "session_id=dummy-session-value",
        "url /callback?session_id=query-session-id-value&sessionid=query-sessionid-value",
        "received token temporary-token-value",
        "url /callback?token=query-token-value&password=query-password-value",
    ]
    report = qa.QAReport(run_id="E2E_UI_QA_20260726_030000_abc123", artifact_dir=tmp_path)
    report.add_section("Sanitized", sensitive_samples)

    content = report.render()
    assert "KAM***567" in content
    assert "KAMI-ABCDEFG1234567" not in content
    assert "fin***890" in content
    assert "fingerprint-1234567890" not in content
    assert "session=temporary-session-value" not in content
    assert "bearer-like-value" not in content
    assert "dummy-auth-value" not in content
    assert "query-auth-value" not in content
    assert "query-auth-token-value" not in content
    assert "dummy-session-value" not in content
    assert "query-session-id-value" not in content
    assert "query-sessionid-value" not in content
    assert "temporary-token-value" not in content
    assert "query-token-value" not in content
    assert "query-password-value" not in content
    assert "token=" not in content.lower()
    assert "password=" not in content.lower()
    assert "authorization:" not in content.lower()
    assert "auth=" not in content.lower()
    assert "session_id=" not in content.lower()
    assert "sessionid=" not in content.lower()
    assert "bearer " not in content.lower()
    report.write()
    assert (tmp_path / "production-e2e-browser-report.md").exists()


def test_report_writer_rejects_unsanitized_private_key_markers(tmp_path):
    qa = load_qa_module()
    report = qa.QAReport(run_id="E2E_UI_QA_20260726_030000_abc123", artifact_dir=tmp_path)
    report.add_section("Unsafe", ["-----BEGIN PRIVATE KEY-----"])
    try:
        report.write()
    except qa.QASafetyError as error:
        assert "forbidden sensitive marker" in str(error)
    else:
        raise AssertionError("report writer allowed private key marker")


def test_browser_routes_for_roles_are_declared():
    qa = load_qa_module()
    routes = qa.browser_routes()
    assert "/login" in routes["public"]
    assert "/admin/dashboard" in routes["admin"]
    assert "/admin/commercial/recharge-settings" in routes["admin"]
    assert "/merchant/dashboard" in routes["merchant"]
    assert "/merchant/batches" in routes["merchant"]


def test_browser_result_evaluation_flags_layout_and_runtime_failures():
    qa = load_qa_module()
    clean_result = {
        "route": "/merchant/recharge",
        "viewport": "1440x900",
        "console_errors": [],
        "exceptions": [],
        "network_failures": [],
        "body_text_length": 1200,
        "bodyTextLength": 1200,
        "layout": {"large_blank_ratio": 0.18, "horizontal_overflow": False, "overwide_cards": []},
    }
    assert qa.evaluate_browser_result(clean_result) == []

    cases = [
        ({"console_errors": ["ReferenceError: app is not defined"]}, "P0", "Console errors detected"),
        ({"exceptions": ["Unhandled promise rejection"]}, "P0", "Runtime exceptions detected"),
        ({"network_failures": ["GET /api/orders 500"]}, "P1", "Network failures detected"),
        ({"http_errors": [{"status": 500, "url": "/api/orders"}]}, "P1", "HTTP errors detected"),
        ({"status": 404}, "P1", "Route document returned bad status"),
        ({"body_text_length": 12}, "P1", "Page body text is unexpectedly sparse"),
        ({"body_text_length": None, "bodyTextLength": 12}, "P1", "Page body text is unexpectedly sparse"),
        ({"layout": {"horizontal_overflow": True}}, "P2", "Horizontal overflow detected"),
        ({"layout": {"large_blank_ratio": 0.72}}, "P2", "Large blank page area detected"),
        ({"layout": {"overwide_cards": [".card"]}}, "P2", "Overwide cards detected"),
    ]

    for patch, severity, message in cases:
        result = {
            **clean_result,
            **patch,
            "layout": {**clean_result["layout"], **patch.get("layout", {})},
        }
        findings = qa.evaluate_browser_result(result)

        assert findings
        assert findings[0]["severity"] == severity
        assert findings[0]["message"] == message


def test_browser_result_evaluation_flags_non_2xx_document_status_without_sparse_noise():
    qa = load_qa_module()
    result = {
        "route": "/admin/dashboard",
        "viewport": "desktop",
        "console_errors": [],
        "exceptions": [],
        "network_failures": [],
        "http_errors": [],
        "status": 500,
        "bodyTextLength": 1200,
        "layout": {"largeBlankRatio": 0.18, "horizontalOverflow": False, "overwideCards": []},
    }

    assert qa.evaluate_browser_result(result) == [
        {
            "severity": "P1",
            "route": "/admin/dashboard",
            "viewport": "desktop",
            "message": "Route document returned bad status",
        }
    ]


def test_run_browser_sweep_timeout_raises_sanitized_error(monkeypatch, tmp_path):
    qa = load_qa_module()

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            cmd=kwargs.get("args", args[0] if args else "node"),
            timeout=kwargs.get("timeout"),
            output="token=should-not-leak",
            stderr="Authorization: Bearer should-not-leak",
        )

    monkeypatch.setattr(qa.subprocess, "run", fake_run)

    try:
        qa.run_browser_sweep(
            "https://example.invalid",
            tmp_path,
            {"token": "admin-secret"},
            {"token": "merchant-secret"},
        )
    except qa.QASafetyError as error:
        message = str(error)
        assert "timed out" in message
        assert "should-not-leak" not in message
        assert "admin-secret" not in message
        assert "merchant-secret" not in message
        assert "<redacted>" in message
    else:
        raise AssertionError("browser sweep timeout did not raise QASafetyError")


def test_browser_result_evaluation_accepts_cdp_layout_keys():
    qa = load_qa_module()
    result = {
        "route": "/admin/dashboard",
        "viewport": "mobile",
        "console_errors": [],
        "exceptions": [],
        "network_failures": [],
        "bodyTextLength": 1200,
        "layout": {
            "horizontalOverflow": True,
            "largeBlankRatio": 0.72,
            "overwideCards": [{"className": "el-card", "width": 380}],
        },
    }

    findings = qa.evaluate_browser_result(result)

    assert [finding["message"] for finding in findings] == [
        "Horizontal overflow detected",
        "Large blank page area detected",
        "Overwide cards detected",
    ]


def test_load_payment_snapshot_reads_and_redacts_recharge_config_options_alias():
    qa = load_qa_module()
    admin = FakeAPIClient(
        [
            {
                "success": True,
                "data": {
                    "channels": [
                        {
                            "id": 1,
                            "channel": "wechat",
                            "display_name": "Wechat",
                            "qr_code_url": "https://pay.example.invalid/real-qr",
                            "account_name": "real-payment-account",
                            "enabled": True,
                            "sort_order": 1,
                            "remark": "production row",
                        }
                    ],
                    "options": [
                        {
                            "id": 2,
                            "amount": 100,
                            "credit_quota": 1000,
                            "label": "100 plan",
                            "enabled": True,
                            "sort_order": 2,
                            "remark": "production option",
                        }
                    ],
                    "bonus_rules": [
                        {
                            "id": 3,
                            "threshold_amount": 200,
                            "bonus_quota": 50,
                            "enabled": False,
                            "sort_order": 3,
                            "remark": "production bonus",
                        }
                    ],
                },
            }
        ]
    )

    snapshot = qa.load_payment_snapshot(admin)

    assert isinstance(snapshot, qa.PaymentSnapshot)
    assert admin.calls[0]["method"] == "GET"
    assert admin.calls[0]["path"] == "/api/v1/admin/commercial/recharge-config"
    assert snapshot.fixed_options == [
        {
            "id": 2,
            "amount": 100,
            "credit_quota": 1000,
            "label": "100 plan",
            "enabled": True,
            "sort_order": 2,
            "remark": "production option",
        }
    ]
    assert snapshot.channels[0]["qr_code_url"] == "<redacted>"
    assert snapshot.channels[0]["account_name"] == "<redacted>"
    assert "real-qr" not in qa._format_report_line(snapshot.__dict__)
    assert "real-payment-account" not in qa._format_report_line(snapshot.__dict__)


def test_load_payment_snapshot_prefers_fixed_options_when_present():
    qa = load_qa_module()
    admin = FakeAPIClient(
        [
            {
                "success": True,
                "data": {
                    "channels": [],
                    "fixed_options": [{"amount": 10, "credit_quota": 10, "enabled": True}],
                    "options": [{"amount": 20, "credit_quota": 20, "enabled": True}],
                    "bonus_rules": [],
                },
            }
        ]
    )

    snapshot = qa.load_payment_snapshot(admin)

    assert snapshot.fixed_options == [{"amount": 10, "credit_quota": 10, "enabled": True}]


def test_ensure_temporary_payment_config_uses_valid_channel_enum_and_prefixed_safe_payloads():
    qa = load_qa_module()
    prefix = "E2E_UI_QA_20260726_030000_abc123_"
    admin = FakeAPIClient(
        [
            {"success": True, "data": {"channels": [], "options": [], "bonus_rules": []}},
            {"success": True, "data": {"channel": "other", "id": 10}},
            {"success": True, "data": {"id": 20}},
            {"success": True, "data": {"id": 30}},
        ]
    )

    summary = qa.ensure_temporary_payment_config(admin, prefix)

    assert summary == {"channel": "other", "option_id": 20, "bonus_rule_id": 30}
    assert [call["path"] for call in admin.calls] == [
        "/api/v1/admin/commercial/recharge-config",
        "/api/v1/admin/commercial/payment-channels",
        "/api/v1/admin/commercial/recharge-options",
        "/api/v1/admin/commercial/recharge-bonus-rules",
    ]
    channel_payload = admin.calls[1]["kwargs"]["json"]
    option_payload = admin.calls[2]["kwargs"]["json"]
    bonus_payload = admin.calls[3]["kwargs"]["json"]
    assert channel_payload["channel"] == "other"
    assert channel_payload["display_name"].startswith(prefix)
    assert channel_payload["remark"].startswith(prefix)
    assert channel_payload["confirm_text"] == "确认修改充值配置"
    assert channel_payload["qr_code_url"] is None
    assert channel_payload["account_name"] is None
    assert option_payload["label"].startswith(prefix)
    assert option_payload["remark"].startswith(prefix)
    assert option_payload["confirm_text"] == "确认修改充值配置"
    assert bonus_payload["remark"].startswith(prefix)
    assert bonus_payload["confirm_text"] == "确认修改充值配置"


def test_ensure_temporary_payment_config_skips_channel_when_other_has_sensitive_payment_fields():
    qa = load_qa_module()
    prefix = "E2E_UI_QA_20260726_030000_abc123_"
    admin = FakeAPIClient(
        [
            {
                "success": True,
                "data": {
                    "channels": [
                        {
                            "channel": "other",
                            "display_name": "Production Other",
                            "qr_code_url": "https://pay.example.invalid/real-qr",
                            "account_name": "real-payment-account",
                            "enabled": True,
                        }
                    ],
                    "options": [],
                    "bonus_rules": [],
                },
            },
            {"success": True, "data": {"id": 20}},
            {"success": True, "data": {"id": 30}},
        ]
    )

    summary = qa.ensure_temporary_payment_config(admin, prefix)

    assert summary == {"channel": None, "option_id": 20, "bonus_rule_id": 30}
    assert [call["path"] for call in admin.calls] == [
        "/api/v1/admin/commercial/recharge-config",
        "/api/v1/admin/commercial/recharge-options",
        "/api/v1/admin/commercial/recharge-bonus-rules",
    ]
    assert "real-qr" not in qa._format_report_line(summary)
    assert "real-payment-account" not in qa._format_report_line(summary)


def test_restore_payment_snapshot_restores_other_channel_deletes_temp_options_and_bonus_without_duplication():
    qa = load_qa_module()
    prefix = "E2E_UI_QA_20260726_030000_abc123_"
    snapshot = qa.PaymentSnapshot(
        channels=[
            {
                "id": 1,
                "channel": "other",
                "display_name": "Other production channel",
                "qr_code_url": "<redacted>",
                "account_name": "<redacted>",
                "enabled": True,
                "sort_order": 1,
                "remark": "production channel",
            }
        ],
        fixed_options=[
            {
                "id": 2,
                "amount": 100,
                "credit_quota": 1000,
                "label": "100 plan",
                "enabled": False,
                "sort_order": 2,
                "remark": "production option",
            }
        ],
        bonus_rules=[
            {
                "id": 3,
                "threshold_amount": 200,
                "bonus_quota": 50,
                "enabled": True,
                "sort_order": 3,
                "remark": "production bonus",
            }
        ],
    )
    admin = FakeAPIClient(
        [
            {
                "success": True,
                "data": {
                    "channels": [
                        {
                            "id": 9,
                            "channel": "other",
                            "display_name": prefix + "Temporary channel",
                            "qr_code_url": None,
                            "account_name": None,
                            "enabled": True,
                            "sort_order": 9000,
                            "remark": prefix + "Temporary channel",
                        },
                        {
                            "id": 10,
                            "channel": "alipay",
                            "display_name": "Production Alipay",
                            "enabled": True,
                            "sort_order": 4,
                            "remark": "not ours",
                        },
                    ],
                    "fixed_options": [
                        *snapshot.fixed_options,
                        {
                            "id": 11,
                            "amount": 991,
                            "credit_quota": 9910,
                            "label": prefix + "Temporary option",
                            "enabled": True,
                            "sort_order": 9001,
                            "remark": prefix + "Temporary option",
                        },
                        {
                            "id": 12,
                            "amount": 992,
                            "credit_quota": 9920,
                            "label": "Production option",
                            "enabled": True,
                            "sort_order": 5,
                            "remark": "not ours",
                        },
                    ],
                    "bonus_rules": [
                        *snapshot.bonus_rules,
                        {
                            "id": 13,
                            "threshold_amount": 993,
                            "bonus_quota": 99,
                            "enabled": True,
                            "sort_order": 9002,
                            "remark": prefix + "Temporary bonus",
                        },
                        {
                            "id": 14,
                            "threshold_amount": 994,
                            "bonus_quota": 44,
                            "enabled": True,
                            "sort_order": 6,
                            "remark": "not ours",
                        },
                    ],
                },
            }
        ]
    )

    qa.restore_payment_snapshot(admin, snapshot, prefix)

    post_calls = [call for call in admin.calls if call["method"] == "POST"]
    delete_calls = [call for call in admin.calls if call["method"] == "DELETE"]
    assert [call["path"] for call in post_calls] == [
        "/api/v1/admin/commercial/payment-channels",
        "/api/v1/admin/commercial/recharge-options",
    ]
    assert [call["path"] for call in delete_calls] == [
        "/api/v1/admin/commercial/recharge-options/11",
        "/api/v1/admin/commercial/recharge-bonus-rules/13",
    ]
    assert all(
        call["kwargs"]["params"] == {"confirm_text": "确认修改充值配置"} for call in delete_calls
    )
    payloads = [call["kwargs"]["json"] for call in post_calls]
    assert payloads[0] == {
        "channel": "other",
        "display_name": "Other production channel",
        "qr_code_url": None,
        "account_name": None,
        "enabled": True,
        "sort_order": 1,
        "remark": "production channel",
        "confirm_text": "确认修改充值配置",
    }
    assert payloads[1]["amount"] == 100
    assert payloads[1]["enabled"] is False
    assert not any(payload.get("threshold_amount") == 200 for payload in payloads)
    assert not any(payload.get("channel") == "alipay" for payload in payloads)
    assert not any(payload.get("amount") == 992 for payload in payloads)
    assert not any(payload.get("threshold_amount") == 994 for payload in payloads)


def test_restore_payment_snapshot_replays_colliding_temp_option_amount_from_snapshot():
    qa = load_qa_module()
    prefix = "E2E_UI_QA_20260726_030000_abc123_"
    snapshot = qa.PaymentSnapshot(
        channels=[],
        fixed_options=[
            {
                "id": 2,
                "amount": 991,
                "credit_quota": 1234,
                "label": "Production 991 option",
                "enabled": True,
                "sort_order": 7,
                "remark": "production option",
            }
        ],
        bonus_rules=[],
    )
    admin = FakeAPIClient(
        [
            {
                "success": True,
                "data": {
                    "channels": [],
                    "options": [
                        {
                            "id": 2,
                            "amount": 991,
                            "credit_quota": 9910,
                            "label": prefix + "Temporary option",
                            "enabled": True,
                            "sort_order": 9001,
                            "remark": prefix + "Temporary option",
                        }
                    ],
                    "bonus_rules": [],
                },
            }
        ]
    )

    qa.restore_payment_snapshot(admin, snapshot, prefix)

    post_calls = [call for call in admin.calls if call["method"] == "POST"]
    delete_calls = [call for call in admin.calls if call["method"] == "DELETE"]
    assert len(post_calls) == 1
    assert post_calls[0]["path"] == "/api/v1/admin/commercial/recharge-options"
    assert post_calls[0]["kwargs"]["json"]["credit_quota"] == 1234
    assert post_calls[0]["kwargs"]["json"]["label"] == "Production 991 option"
    assert delete_calls == []


def test_restore_payment_snapshot_rejects_non_prefixed_temporary_cleanup():
    qa = load_qa_module()
    prefix = "E2E_UI_QA_20260726_030000_abc123_"
    snapshot = qa.PaymentSnapshot(channels=[], fixed_options=[], bonus_rules=[])
    admin = FakeAPIClient(
        [
            {
                "success": True,
                "data": {
                    "channels": [
                        {
                            "channel": "other",
                            "display_name": "E2E_UI_QA_not_valid_Temporary channel",
                            "enabled": True,
                        }
                    ],
                    "fixed_options": [],
                    "bonus_rules": [],
                },
            }
        ]
    )

    try:
        qa.restore_payment_snapshot(admin, snapshot, prefix)
    except qa.QASafetyError as error:
        assert "non-prefixed temporary payment config" in str(error)
        assert "E2E_UI_QA_not_valid_Temporary channel" not in str(error)
    else:
        raise AssertionError("restore allowed non-prefixed temporary cleanup")
