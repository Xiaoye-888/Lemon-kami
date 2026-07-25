import importlib.util
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
        "password": "dont-show",
        "cookie": "session=value",
        "nested": {"kami_code": "KAMI-ABCDEFG1234567", "device_fingerprint": "fingerprint-1234567890"},
    }
    redacted = qa.redact(payload)
    assert redacted["token"] == "<redacted>"
    assert redacted["password"] == "<redacted>"
    assert redacted["cookie"] == "<redacted>"
    assert redacted["nested"]["kami_code"].startswith("KAM")
    assert "***" in redacted["nested"]["kami_code"]
    assert redacted["nested"]["device_fingerprint"].endswith("890")


def test_run_prefix_is_unique_and_delete_safe():
    qa = load_qa_module()
    prefix = qa.build_run_prefix()
    assert prefix.startswith("E2E_UI_QA_")
    assert prefix.endswith("_")
    assert qa.is_owned_by_run(prefix + "merchant", prefix) is True
    assert qa.is_owned_by_run("real-user", prefix) is False


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


def test_browser_result_evaluation_flags_layout_and_runtime_failures():
    qa = load_qa_module()
    result = {
        "route": "/merchant/recharge",
        "viewport": "1440x900",
        "console_errors": [],
        "exceptions": [],
        "network_failures": [],
        "body_text_length": 1200,
        "layout": {"large_blank_ratio": 0.18, "horizontal_overflow": False, "overwide_cards": []},
    }
    assert qa.evaluate_browser_result(result) == []

    result["layout"]["large_blank_ratio"] = 0.72
    findings = qa.evaluate_browser_result(result)
    assert findings
    assert findings[0]["severity"] == "P2"
