from dataclasses import dataclass, field
from datetime import datetime
import json
import os
from pathlib import Path
import re
import requests
import subprocess
from typing import Any
import uuid


SECRET_KEYS = {
    "authorization",
    "cookie",
    "password",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "app_secret",
}
MASKED_VALUE_KEYS = {"kami", "kami_code", "code", "device_fingerprint", "fingerprint"}
PRODUCTION_CONFIRMATION = "I_UNDERSTAND_THIS_CREATES_TEMP_PRODUCTION_DATA"
REPORT_FILENAME = "production-e2e-browser-report.md"
BROWSER_SWEEP_TIMEOUT_SECONDS = 300
VIEWPORTS = [
    {"name": "desktop", "width": 1440, "height": 900},
    {"name": "wide", "width": 1920, "height": 1080},
    {"name": "mobile", "width": 390, "height": 844},
]
RUN_PREFIX_RE = re.compile(r"^E2E_UI_QA_\d{8}_\d{6}_[A-Za-z0-9]{6,16}_$")
FORBIDDEN_REPORT_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\btoken\s*[:=]",
        r"\bpassword\s*[:=]",
        r"\bcookie\s*[:=]",
        r"\bauthorization\s*:",
        r"\bauth\s*[:=]",
        r"\bauth_token\s*[:=]",
        r"\bbearer\s+",
        r"\bsession(?:_id|id)?\s*[:=]",
        r"\bapp_secret\b",
        r"\bserver\s+password\b",
        r"\b(?:private|ssh)[_-]?key\b",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        r"\bKAMI-[A-Za-z0-9]{8,}\b",
        r"\bfingerprint-[A-Za-z0-9]{8,}\b",
    )
)
CARD_CODE_RE = re.compile(r"\bKAMI-[A-Za-z0-9]{8,}\b")
FINGERPRINT_RE = re.compile(r"\bfingerprint-[A-Za-z0-9]{8,}\b", re.IGNORECASE)
STRING_SECRET_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bauthorization\s*:\s*bearer\s+[^\s&]+",
        r"\bbearer\s+[^\s&]+",
        r"([?&](?:auth|auth_token|token|password|access_token|refresh_token|session|session_id|sessionid|cookie)=)[^&#\s]+",
        r"\b(?:auth|auth_token|token|password|cookie|session|session_id|sessionid|access_token|refresh_token)\s*[:=]\s*[^\s&]+",
        r"\b(?:auth|auth_token|token|password|cookie|session|session_id|sessionid|access_token|refresh_token)\s+[^\s&]+",
    )
)


class QASafetyError(RuntimeError):
    pass


@dataclass
class QAConfig:
    base_url: str
    admin_username: str
    admin_password: str
    confirmation: str

    @classmethod
    def from_env(cls):
        base_url = os.environ.get("LEMON_QA_BASE_URL", "")
        admin_username = os.environ.get("LEMON_QA_ADMIN_USERNAME", "")
        admin_password = os.environ.get("LEMON_QA_ADMIN_PASSWORD", "")
        confirmation = os.environ.get("LEMON_QA_CONFIRM_PRODUCTION", "")

        errors = []
        if not (base_url.startswith("http://") or base_url.startswith("https://")):
            errors.append("LEMON_QA_BASE_URL must start with http:// or https://")
        if not admin_username.strip():
            errors.append("LEMON_QA_ADMIN_USERNAME must be non-empty")
        if not admin_password:
            errors.append("LEMON_QA_ADMIN_PASSWORD must be non-empty")
        if confirmation != PRODUCTION_CONFIRMATION:
            errors.append("LEMON_QA_CONFIRM_PRODUCTION must match the required production confirmation")
        if errors:
            raise QASafetyError("; ".join(errors))

        return cls(
            base_url=base_url,
            admin_username=admin_username,
            admin_password=admin_password,
            confirmation=confirmation,
        )


@dataclass
class AuthSession:
    token: str
    role: str
    user_info: dict[str, Any]

    def as_browser_storage(self):
        return {
            "token": self.token,
            "role": self.role,
            "userInfo": self.user_info,
        }


def _sanitize_api_error_text(value, sensitive_values=()):
    text = str(value)
    try:
        parsed = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        sanitized = sanitize_report_string(text)
    else:
        sanitized = _format_report_line(parsed)

    for sensitive in sensitive_values or ():
        if sensitive:
            sanitized = sanitized.replace(str(sensitive), "<redacted>")
    return sanitized


class APIClient:
    def __init__(self, base_url: str, auth: AuthSession | None = None):
        self.base_url = base_url
        self.auth = auth
        self.session = requests.Session()

    def request(self, method, path, **kwargs):
        url = self.base_url.rstrip("/") + path
        headers = dict(kwargs.pop("headers", {}) or {})
        if self.auth:
            headers["Authorization"] = f"Bearer {self.auth.token}"
        kwargs["headers"] = headers
        kwargs.setdefault("timeout", 30)
        return self.session.request(method, url, **kwargs)

    def json(self, method, path, expected=(200,), **kwargs):
        sensitive_values = list(kwargs.pop("sensitive_values", []) or [])
        if self.auth:
            sensitive_values.append(self.auth.token)
        if isinstance(expected, int):
            expected = (expected,)

        response = self.request(method, path, **kwargs)
        if response.status_code not in expected:
            safe_text = _sanitize_api_error_text(response.text, sensitive_values)
            raise QASafetyError(
                f"API {method} {path} returned status {response.status_code}; response={safe_text!r}"
            )
        try:
            return response.json()
        except ValueError as error:
            safe_text = _sanitize_api_error_text(response.text, sensitive_values)
            raise QASafetyError(f"API {method} {path} returned invalid JSON; response={safe_text!r}") from error


def _build_login_payload(username, password, key_data):
    aes_key = key_data.get("aes_key") if isinstance(key_data, dict) else None
    if aes_key:
        try:
            from crypto import CryptoHelper

            encrypted = CryptoHelper.aes_encrypt({"username": username, "password": password}, aes_key)
            return {**encrypted, "encrypted": True}
        except Exception:
            pass
    return {"username": username, "password": password, "encrypted": False}


def login(base_url: str, username: str, password: str) -> AuthSession:
    client = APIClient(base_url)
    key_data = {}
    key_response = client.request("GET", "/api/v1/auth/login/public-key")
    if key_response.status_code == 200:
        try:
            key_data = key_response.json()
        except ValueError:
            key_data = {}

    payload = _build_login_payload(username, password, key_data)
    data = client.json(
        "POST",
        "/api/v1/auth/login",
        json=payload,
        sensitive_values=[password],
    )
    token = data.get("token") if isinstance(data, dict) else None
    if not token:
        safe_data = _sanitize_api_error_text(json.dumps(data, ensure_ascii=True), [password])
        raise QASafetyError(f"Login response missing required token field; response={safe_data!r}")
    return AuthSession(
        token=token,
        role=data.get("role"),
        user_info=data.get("user_info") or {},
    )


def browser_routes():
    return {
        "public": ["/", "/login", "/docs/api"],
        "admin": [
            "/admin/dashboard",
            "/admin/commercial/merchants",
            "/admin/commercial/recharge-orders",
            "/admin/commercial/recharge-settings",
            "/admin/commercial/issue-pricing",
            "/admin/commercial/finance",
            "/admin/commercial/audit-logs",
            "/admin/ops",
            "/admin/commercial/quota-transactions",
            "/admin/apps/info",
            "/admin/apps/notices",
            "/admin/apps/versions",
            "/admin/kamis/batches",
            "/admin/kamis/list",
            "/admin/devices",
            "/admin/end-users",
            "/admin/users",
            "/admin/logs",
            "/admin/interfaces/new",
            "/admin/interfaces/list",
            "/docs/api",
        ],
        "merchant": [
            "/merchant/dashboard",
            "/merchant/recharge",
            "/merchant/orders",
            "/merchant/transactions",
            "/merchant/apps",
            "/merchant/batches",
            "/merchant/cards",
            "/merchant/devices",
            "/merchant/account",
        ],
    }


def run_browser_sweep(base_url: str, artifact_dir: Path, admin_session: dict, merchant_session: dict) -> list[dict[str, Any]]:
    helper = Path(__file__).resolve().with_name("browser_cdp_sweep.mjs")
    if not helper.exists():
        raise QASafetyError(f"Browser CDP helper is missing: {helper}")

    payload = {
        "baseUrl": base_url,
        "artifactDir": str(artifact_dir),
        "viewports": VIEWPORTS,
        "routes": browser_routes(),
        "sessions": {
            "admin": admin_session,
            "merchant": merchant_session,
        },
    }
    raw_payload = json.dumps(payload, ensure_ascii=True)
    try:
        completed = subprocess.run(
            ["node", str(helper)],
            input=raw_payload,
            text=True,
            capture_output=True,
            check=False,
            timeout=BROWSER_SWEEP_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        stderr = sanitize_report_string((error.stderr or "").strip())
        stdout = sanitize_report_string((error.output or "").strip())
        raise QASafetyError(
            f"Browser CDP sweep timed out after {error.timeout} seconds; stderr={stderr!r}; stdout={stdout!r}"
        ) from error
    if completed.returncode != 0:
        stderr = sanitize_report_string(completed.stderr.strip())
        stdout = sanitize_report_string(completed.stdout.strip())
        raise QASafetyError(
            f"Browser CDP sweep failed with exit {completed.returncode}; stderr={stderr!r}; stdout={stdout!r}"
        )

    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        stdout = sanitize_report_string(completed.stdout.strip())
        raise QASafetyError(f"Browser CDP sweep returned invalid JSON: {error}; stdout={stdout!r}") from error


def build_run_prefix(now=None, suffix=None):
    moment = now or datetime.now()
    safe_suffix = suffix or uuid.uuid4().hex[:8]
    if not re.fullmatch(r"[A-Za-z0-9]{6,16}", safe_suffix):
        raise QASafetyError(f"Invalid QA run prefix suffix: {safe_suffix!r}")
    return f"E2E_UI_QA_{moment:%Y%m%d_%H%M%S}_{safe_suffix}_"


def validate_run_prefix(prefix):
    if not isinstance(prefix, str) or not RUN_PREFIX_RE.fullmatch(prefix):
        raise QASafetyError(f"Invalid QA run prefix: {prefix!r}")
    return prefix


def is_owned_by_run(value, prefix):
    try:
        validate_run_prefix(prefix)
    except QASafetyError:
        return False
    return isinstance(value, str) and value.startswith(prefix)


def assert_owned_by_run(value, prefix):
    if not is_owned_by_run(value, prefix):
        raise QASafetyError(f"Refusing cleanup for non-QA resource: {value!r}")


def mask_middle(value, keep=3):
    text = str(value)
    if len(text) <= keep * 2:
        return "***"
    return f"{text[:keep]}***{text[-keep:]}"


def _is_sensitive_key(key):
    normalized = str(key).lower()
    return (
        normalized in SECRET_KEYS
        or normalized == "auth"
        or normalized.startswith("auth_")
        or normalized.endswith("_auth")
        or normalized == "session"
        or normalized == "session_id"
        or normalized == "sessionid"
        or normalized.endswith("_session")
        or normalized.endswith("_token")
        or "token" in normalized
        or "password" in normalized
        or "private_key" in normalized
        or "ssh_key" in normalized
    )


def redact(value):
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            normalized = str(key).lower()
            if _is_sensitive_key(key):
                redacted[key] = "<redacted>"
            elif normalized in MASKED_VALUE_KEYS and isinstance(item, str):
                redacted[key] = mask_middle(item)
            else:
                redacted[key] = redact(item)
        return redacted
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    return value


def _finding(severity, route, viewport, message):
    return {
        "severity": severity,
        "route": route,
        "viewport": viewport,
        "message": message,
    }


def evaluate_browser_result(result):
    findings = []
    route = result.get("route", "<unknown>")
    viewport = result.get("viewport", "<unknown>")
    layout = result.get("layout") or {}

    if result.get("console_errors"):
        findings.append(_finding("P0", route, viewport, "Console errors detected"))
    if result.get("exceptions"):
        findings.append(_finding("P0", route, viewport, "Runtime exceptions detected"))
    if result.get("network_failures"):
        findings.append(_finding("P1", route, viewport, "Network failures detected"))
    if result.get("http_errors"):
        findings.append(_finding("P1", route, viewport, "HTTP errors detected"))
    status = result.get("status")
    if status is not None and (status < 200 or status >= 400):
        findings.append(_finding("P1", route, viewport, "Route document returned bad status"))
    body_text_length = result.get("body_text_length")
    if body_text_length is None:
        body_text_length = result.get("bodyTextLength", 0)
    if body_text_length < 40:
        findings.append(_finding("P1", route, viewport, "Page body text is unexpectedly sparse"))
    horizontal_overflow = layout.get("horizontal_overflow")
    if horizontal_overflow is None:
        horizontal_overflow = layout.get("horizontalOverflow")
    large_blank_ratio = layout.get("large_blank_ratio")
    if large_blank_ratio is None:
        large_blank_ratio = layout.get("largeBlankRatio", 0)
    overwide_cards = layout.get("overwide_cards")
    if overwide_cards is None:
        overwide_cards = layout.get("overwideCards")

    if horizontal_overflow:
        findings.append(_finding("P2", route, viewport, "Horizontal overflow detected"))
    if large_blank_ratio >= 0.55:
        findings.append(_finding("P2", route, viewport, "Large blank page area detected"))
    if overwide_cards:
        findings.append(_finding("P2", route, viewport, "Overwide cards detected"))

    return findings


def _report_safe_value(value):
    if isinstance(value, dict):
        safe_value = {}
        for key, item in redact(value).items():
            safe_key = "<redacted_key>" if _is_sensitive_key(key) else key
            safe_value[safe_key] = _report_safe_value(item)
        return safe_value
    if isinstance(value, list):
        return [_report_safe_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_report_safe_value(item) for item in value)
    if isinstance(value, str):
        return sanitize_report_string(value)
    return value


def _format_report_line(line):
    if isinstance(line, (dict, list, tuple)):
        return json.dumps(_report_safe_value(line), ensure_ascii=True, sort_keys=True)
    return sanitize_report_string(line)


def sanitize_report_string(value):
    text = str(value)
    text = CARD_CODE_RE.sub(lambda match: mask_middle(match.group(0)), text)
    text = FINGERPRINT_RE.sub(lambda match: mask_middle(match.group(0)), text)
    for pattern in STRING_SECRET_PATTERNS:
        text = pattern.sub("<redacted>", text)
    return text


def _assert_report_content_safe(content):
    for pattern in FORBIDDEN_REPORT_PATTERNS:
        if pattern.search(content):
            raise QASafetyError(f"Report contains forbidden sensitive marker: {pattern.pattern}")


@dataclass
class QAReport:
    run_id: str
    artifact_dir: Path
    sections: list = field(default_factory=list)

    def add_section(self, title, lines):
        self.sections.append((title, list(lines)))

    def render(self):
        lines = [f"# Production E2E Browser QA Report", "", f"Run ID: {self.run_id}", ""]
        for title, section_lines in self.sections:
            lines.extend([f"## {title}", ""])
            if section_lines:
                lines.extend(f"- {_format_report_line(line)}" for line in section_lines)
            else:
                lines.append("- No findings")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def write(self):
        content = self.render()
        _assert_report_content_safe(content)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.artifact_dir / REPORT_FILENAME
        output_path.write_text(content, encoding="utf-8")
        return output_path


def main():
    print("Production E2E browser QA harness skeleton ready; no browser run executed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
