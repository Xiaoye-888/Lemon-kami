import importlib.util
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "production_e2e_browser_qa.py"


def load_qa_module():
    spec = importlib.util.spec_from_file_location("production_e2e_browser_qa", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_secret_redaction_masks_sensitive_values():
    qa = load_qa_module()
    payload = {
        "token": "abc123secret",
        "api_token": "api-token-value",
        "csrf_token": "csrf-token-value",
        "authToken": "auth-token-value",
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
    malformed_prefixes = ["", "prod", "admin", "E2E_UI_QA_", "E2E_UI_QA_20260726_030000_bad!_"]
    for prefix in malformed_prefixes:
        try:
            qa.validate_run_prefix(prefix)
        except qa.QASafetyError as error:
            assert "Invalid QA run prefix" in str(error)
        else:
            raise AssertionError(f"cleanup prefix validation allowed {prefix!r}")

        assert qa.is_owned_by_run(prefix + "resource", prefix) is False


def test_cleanup_guard_rejects_non_prefixed_resources():
    qa = load_qa_module()
    prefix = "E2E_UI_QA_20260726_030000_"
    qa.assert_owned_by_run(prefix + "app", prefix)
    try:
        qa.assert_owned_by_run("production-app", prefix)
    except qa.QASafetyError as error:
        assert "Refusing cleanup" in str(error)
    else:
        raise AssertionError("cleanup guard allowed non-prefixed resource")


def test_report_writer_rejects_forbidden_secret_words(tmp_path):
    qa = load_qa_module()
    report = qa.QAReport(run_id="E2E_UI_QA_20260726_030000", artifact_dir=tmp_path)
    report.add_section("Safe", ["health 200", "orders cleaned"])
    report.write()
    assert (tmp_path / "production-e2e-browser-report.md").exists()

    report.add_section("Unsafe", ["token=abc123"])
    try:
        report.write()
    except qa.QASafetyError as error:
        assert "forbidden sensitive marker" in str(error)
    else:
        raise AssertionError("report writer allowed token output")


def test_report_writer_redacts_structured_section_lines(tmp_path):
    qa = load_qa_module()
    report = qa.QAReport(run_id="E2E_UI_QA_20260726_030000", artifact_dir=tmp_path)
    report.add_section(
        "Structured",
        [
            {
                "api_token": "api-token-value",
                "server_password": "server-password-value",
                "kami_code": "KAMI-ABCDEFG1234567",
                "device_fingerprint": "fingerprint-1234567890",
                "nested": [{"private_key": "private-key-value"}],
            }
        ],
    )

    content = report.render()
    assert "api-token-value" not in content
    assert "server-password-value" not in content
    assert "private-key-value" not in content
    assert "KAM***567" in content
    assert "fin***890" in content
    assert "<redacted>" in content
    report.write()
    assert (tmp_path / "production-e2e-browser-report.md").exists()


def test_report_writer_rejects_adversarial_secret_markers(tmp_path):
    qa = load_qa_module()
    unsafe_lines = [
        "ToKeN: fake-token-value",
        "server password: fake-password-value",
        "-----BEGIN PRIVATE KEY-----",
        "ssh_key: fake-key-value",
        "Bearer fake-bearer-value",
        "app_secret=fake-app-secret-value",
    ]

    for index, unsafe_line in enumerate(unsafe_lines):
        report = qa.QAReport(run_id="E2E_UI_QA_20260726_030000", artifact_dir=tmp_path / str(index))
        report.add_section("Unsafe", [unsafe_line])
        try:
            report.write()
        except qa.QASafetyError as error:
            assert "forbidden sensitive marker" in str(error)
        else:
            raise AssertionError(f"report writer allowed unsafe marker: {unsafe_line}")


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
