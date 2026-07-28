from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
import argparse
import json
import os
from pathlib import Path
import re
import requests
import subprocess
import sys
from typing import Any
import uuid
from PIL import Image, ImageChops, ImageStat


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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
PAYMENT_SENSITIVE_KEYS = {"qr_code_url", "account_name"}
MASKED_VALUE_KEYS = {"kami", "kami_code", "code", "device_fingerprint", "fingerprint"}
PRODUCTION_CONFIRMATION = "I_UNDERSTAND_THIS_CREATES_TEMP_PRODUCTION_DATA"
PAYMENT_CONFIG_CONFIRM_TEXT = "确认修改充值配置"
RECHARGE_APPROVAL_CONFIRM_TEXT = "确认审核入账"
GRANT_ISSUE_QUOTA_CONFIRM_TEXT = "确认调整额度"
GRANT_APP_AUTHORIZATION_CONFIRM_TEXT = "确认授权应用"
DELETE_APP_CONFIRM_TEXT = "确认删除应用"
DELETE_USER_CONFIRM_TEXT = "确认删除用户"
TEMP_RECHARGE_OPTION_AMOUNTS = tuple(range(991, 1000))
TEMP_BONUS_THRESHOLDS = tuple(range(993, 1000))
REPORT_FILENAME = "production-e2e-browser-report.md"
BROWSER_SWEEP_TIMEOUT_SECONDS = 300
VIEWPORTS = [
    {"name": "desktop", "width": 1440, "height": 900},
    {"name": "wide", "width": 1920, "height": 1080},
    {"name": "mobile", "width": 390, "height": 844},
]
VISUAL_BASELINE_DIR = PROJECT_ROOT / "tests" / "visual_baselines"
VISUAL_REGRESSION_TARGETS = [
    {
        "role": "merchant",
        "route": "/merchant/apps",
        "viewport": "desktop",
        "label": "merchant-apps-row-actions",
        "baseline": "merchant-apps-row-actions.desktop.png",
        "crop_padding": 12,
        "max_mean_diff": 5.0,
        "max_changed_ratio": 0.01,
    },
    {
        "role": "merchant",
        "route": "/merchant/batches",
        "viewport": "desktop",
        "label": "merchant-batches-spec-row-actions",
        "baseline": "merchant-batches-spec-row-actions.desktop.png",
        "screenshot_key": "screenshot",
        "crop_kind": "rect",
        "crop_key": "merchantBatchSpecRowActionsRect",
        "crop_padding": 12,
        "max_mean_diff": 8.0,
        "max_changed_ratio": 0.04,
    },
    {
        "role": "merchant",
        "route": "/merchant/batches",
        "viewport": "desktop",
        "label": "merchant-batches-detail-summary",
        "baseline": "merchant-batches-detail-summary.desktop.png",
        "screenshot_key": "detailScreenshot",
        "crop_kind": "rect",
        "crop_key": "detailSummaryRect",
        "crop_padding": 12,
        "max_mean_diff": 12.0,
        "max_changed_ratio": 0.08,
    },
    {
        "role": "merchant",
        "route": "/merchant/batches",
        "viewport": "desktop",
        "label": "merchant-batches-batch-row-actions",
        "baseline": "merchant-batches-batch-row-actions.desktop.png",
        "screenshot_key": "detailScreenshot",
        "crop_kind": "rect",
        "crop_key": "merchantBatchBatchRowActionsRect",
        "crop_padding": 12,
        "max_mean_diff": 8.0,
        "max_changed_ratio": 0.04,
    },
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
SENSITIVE_TEXT_KEY_NAMES = (
    "authorization",
    "refresh_token",
    "access_token",
    "private_key",
    "session_id",
    "app_secret",
    "auth_token",
    "sessionid",
    "password",
    "session",
    "ssh_key",
    "secret",
    "cookie",
    "token",
    "auth",
)
SENSITIVE_TEXT_KEY_RE = re.compile(
    r"(?<![A-Za-z0-9_])(" + "|".join(re.escape(key) for key in SENSITIVE_TEXT_KEY_NAMES) + r")(?![A-Za-z0-9_])",
    re.IGNORECASE,
)
QUOTED_SECRET_KV_RE = re.compile(
    r"([\"'])("
    + "|".join(re.escape(key) for key in SENSITIVE_TEXT_KEY_NAMES)
    + r")\1\s*:\s*([\"']).*?\3",
    re.IGNORECASE,
)
UNQUOTED_SECRET_KV_RE = re.compile(
    r"(?<![A-Za-z0-9_])("
    + "|".join(re.escape(key) for key in SENSITIVE_TEXT_KEY_NAMES)
    + r")(?![A-Za-z0-9_])\s*[:=]\s*[^,\s;}\]]+",
    re.IGNORECASE,
)


class QASafetyError(RuntimeError):
    pass


@dataclass
class QAConfig:
    base_url: str
    admin_username: str
    admin_password: str
    confirmation: str
    api_base_url: str | None = None
    browser_base_url: str | None = None

    def __post_init__(self):
        if not self.api_base_url:
            self.api_base_url = self.base_url
        if not self.browser_base_url:
            self.browser_base_url = self.base_url

    @classmethod
    def from_env(cls, require_confirmation=True):
        base_url = os.environ.get("LEMON_QA_BASE_URL", "")
        api_base_url = os.environ.get("LEMON_QA_API_BASE_URL", "") or base_url
        browser_base_url = os.environ.get("LEMON_QA_BROWSER_BASE_URL", "") or base_url
        admin_username = os.environ.get("LEMON_QA_ADMIN_USERNAME", "")
        admin_password = os.environ.get("LEMON_QA_ADMIN_PASSWORD", "")
        confirmation = os.environ.get("LEMON_QA_CONFIRM_PRODUCTION", "")

        errors = []
        if not (base_url.startswith("http://") or base_url.startswith("https://")):
            errors.append("LEMON_QA_BASE_URL must start with http:// or https://")
        if not (api_base_url.startswith("http://") or api_base_url.startswith("https://")):
            errors.append("LEMON_QA_API_BASE_URL must start with http:// or https://")
        if not (browser_base_url.startswith("http://") or browser_base_url.startswith("https://")):
            errors.append("LEMON_QA_BROWSER_BASE_URL must start with http:// or https://")
        if not admin_username.strip():
            errors.append("LEMON_QA_ADMIN_USERNAME must be non-empty")
        if not admin_password:
            errors.append("LEMON_QA_ADMIN_PASSWORD must be non-empty")
        if require_confirmation and confirmation != PRODUCTION_CONFIRMATION:
            errors.append("LEMON_QA_CONFIRM_PRODUCTION must match the required production confirmation")
        if errors:
            raise QASafetyError("; ".join(errors))

        return cls(
            base_url=base_url,
            admin_username=admin_username,
            admin_password=admin_password,
            confirmation=confirmation,
            api_base_url=api_base_url,
            browser_base_url=browser_base_url,
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


@dataclass
class PaymentSnapshot:
    channels: list[dict[str, Any]]
    fixed_options: list[dict[str, Any]]
    bonus_rules: list[dict[str, Any]]


@dataclass
class MerchantContext:
    prefix: str
    base_url: str
    username: str
    user_id: int | None
    auth: AuthSession
    client: Any

    def __repr__(self):
        return (
            "MerchantContext("
            f"prefix={self.prefix!r}, base_url={self.base_url!r}, "
            f"username={self.username!r}, user_id={self.user_id!r}, auth=<redacted>, client={type(self.client).__name__})"
        )


@dataclass
class AppResource:
    app_id: str
    name: str | None = None
    app_secret: str | None = None
    rsa_public_key: str | None = None

    def __repr__(self):
        return (
            "AppResource("
            f"app_id={self.app_id!r}, name={self.name!r}, "
            f"app_secret=<redacted>, rsa_public_key={'<present>' if self.rsa_public_key else None})"
        )


@dataclass
class SpecDescriptor:
    spec_id: int | None
    issue_payload: dict[str, Any]
    source: str = "in_memory"


@dataclass
class BatchResult:
    app_id: str
    batch_id: int | None
    batch_no: str
    count: int
    codes: list[str]
    preview: dict[str, Any]
    issue: dict[str, Any]


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


def _extract_sensitive_values(value):
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).lower()
            if (_is_sensitive_key(key) or normalized in PAYMENT_SENSITIVE_KEYS) and isinstance(item, str):
                found.append(item)
            found.extend(_extract_sensitive_values(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            found.extend(_extract_sensitive_values(item))
    return found


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
        try:
            return self.session.request(method, url, **kwargs)
        except requests.RequestException as error:
            sensitive_values = []
            if self.auth:
                sensitive_values.append(self.auth.token)
            sensitive_values.extend(_extract_sensitive_values(kwargs))
            safe_error = _sanitize_api_error_text(str(error), sensitive_values)
            raise QASafetyError(f"API {method} {path} request failed; error={safe_error!r}") from error

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
    if aes_key and str(aes_key).strip():
        try:
            from crypto import CryptoHelper

            encrypted = CryptoHelper.aes_encrypt({"username": username, "password": password}, aes_key)
            return {**encrypted, "encrypted": True}
        except Exception as error:
            safe_error = _sanitize_api_error_text(str(error), [username, password, aes_key])
            raise QASafetyError(f"Failed to build encrypted login payload; error={safe_error!r}") from error
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


def run_browser_sweep(
    base_url: str,
    artifact_dir: Path,
    admin_session: dict,
    merchant_session: dict,
    context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
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
        "context": context or {},
    }
    raw_payload = json.dumps(payload, ensure_ascii=True)
    try:
        completed = subprocess.run(
            ["node", str(helper)],
            input=raw_payload,
            text=True,
            encoding="utf-8",
            errors="replace",
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


def _payment_row_text_fields(row):
    for key in ("display_name", "remark", "label"):
        value = row.get(key) if isinstance(row, dict) else None
        if isinstance(value, str):
            yield value


def _payment_row_owned_by_run(row, prefix):
    return any(is_owned_by_run(value, prefix) for value in _payment_row_text_fields(row))


def _payment_row_mentions_qa_prefix(row):
    return any("E2E_UI_QA_" in value for value in _payment_row_text_fields(row))


def _payment_config_data(response):
    data = response.get("data") if isinstance(response, dict) else None
    return data if isinstance(data, dict) else {}


def _payment_config_options(data):
    return data.get("fixed_options") if data.get("fixed_options") is not None else data.get("options") or []


def load_payment_snapshot(admin: APIClient) -> PaymentSnapshot:
    response = admin.json("GET", "/api/v1/admin/commercial/recharge-config")
    data = _payment_config_data(response)
    return PaymentSnapshot(
        channels=[dict(row) for row in data.get("channels") or [] if isinstance(row, dict)],
        fixed_options=[
            dict(row)
            for row in _payment_config_options(data)
            if isinstance(row, dict)
        ],
        bonus_rules=[dict(row) for row in data.get("bonus_rules") or [] if isinstance(row, dict)],
    )


def _post_payment_channel(admin, payload):
    return admin.json("POST", "/api/v1/admin/commercial/payment-channels", json=payload)


def _post_recharge_option(admin, payload):
    return admin.json("POST", "/api/v1/admin/commercial/recharge-options", json=payload)


def _post_bonus_rule(admin, payload):
    return admin.json("POST", "/api/v1/admin/commercial/recharge-bonus-rules", json=payload)


def _delete_recharge_option(admin, option_id):
    return admin.json(
        "DELETE",
        f"/api/v1/admin/commercial/recharge-options/{option_id}",
        params={"confirm_text": PAYMENT_CONFIG_CONFIRM_TEXT},
    )


def _delete_bonus_rule(admin, rule_id):
    return admin.json(
        "DELETE",
        f"/api/v1/admin/commercial/recharge-bonus-rules/{rule_id}",
        params={"confirm_text": PAYMENT_CONFIG_CONFIRM_TEXT},
    )


def _disable_recharge_option(admin, row):
    payload = _option_payload_from_row(row, enabled=False)
    if not payload:
        raise QASafetyError("Cannot disable temporary recharge option because payload is incomplete")
    return _post_recharge_option(admin, payload)


def _decimal_amount(value):
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _row_amount_equals(row, key, amount):
    return _decimal_amount(row.get(key)) == Decimal(str(amount))


def _select_temp_option(config, prefix):
    options = [row for row in _payment_config_options(config) if isinstance(row, dict)]
    for amount in TEMP_RECHARGE_OPTION_AMOUNTS:
        matches = [row for row in options if _row_amount_equals(row, "amount", amount)]
        if not matches:
            return {"amount": amount, "existing": None}
        owned_matches = [row for row in matches if _payment_row_owned_by_run(row, prefix)]
        if owned_matches and len(owned_matches) == len(matches):
            return {"amount": amount, "existing": owned_matches[0]}
    raise QASafetyError("No safe temporary recharge option amount is available in reserved QA range")


def _select_temp_bonus_rule(config, prefix):
    rules = [row for row in config.get("bonus_rules") or [] if isinstance(row, dict)]
    owned_rules = [row for row in rules if _payment_row_owned_by_run(row, prefix)]
    if owned_rules:
        return {"threshold_amount": owned_rules[0].get("threshold_amount"), "existing": owned_rules[0]}
    for threshold_amount in TEMP_BONUS_THRESHOLDS:
        matches = [row for row in rules if _row_amount_equals(row, "threshold_amount", threshold_amount)]
        if not matches:
            return {"threshold_amount": threshold_amount, "existing": None}
    raise QASafetyError("No safe temporary bonus rule threshold is available in reserved QA range")


def ensure_temporary_payment_config(admin: APIClient, prefix: str) -> dict[str, Any] | None:
    validate_run_prefix(prefix)
    config_response = admin.json("GET", "/api/v1/admin/commercial/recharge-config")
    config = _payment_config_data(config_response)
    option_selection = _select_temp_option(config, prefix)
    bonus_selection = _select_temp_bonus_rule(config, prefix)
    other_channel = next(
        (
            row
            for row in config.get("channels") or []
            if isinstance(row, dict) and row.get("channel") == "other"
        ),
        None,
    )
    can_touch_other_channel = not (
        isinstance(other_channel, dict)
        and (other_channel.get("qr_code_url") or other_channel.get("account_name"))
    )
    channel_data = {}
    if can_touch_other_channel:
        channel_response = _post_payment_channel(
            admin,
            {
                "channel": "other",
                "display_name": f"{prefix}Temporary channel",
                "qr_code_url": None,
                "account_name": None,
                "enabled": True,
                "sort_order": 9000,
                "remark": f"{prefix}Temporary payment channel",
                "confirm_text": PAYMENT_CONFIG_CONFIRM_TEXT,
            },
        )
        channel_data = _payment_config_data(channel_response)
    option_data = option_selection["existing"] or {}
    if not option_data:
        option_response = _post_recharge_option(
            admin,
            {
                "amount": option_selection["amount"],
                "credit_quota": option_selection["amount"] * 10,
                "label": f"{prefix}Temporary option",
                "enabled": True,
                "sort_order": 9001,
                "remark": f"{prefix}Temporary recharge option",
                "confirm_text": PAYMENT_CONFIG_CONFIRM_TEXT,
            },
        )
        option_data = _payment_config_data(option_response)
    bonus_data = bonus_selection["existing"] or {}
    if not bonus_data:
        bonus_response = _post_bonus_rule(
            admin,
            {
                "threshold_amount": bonus_selection["threshold_amount"],
                "bonus_quota": 99,
                "enabled": True,
                "sort_order": 9002,
                "remark": f"{prefix}Temporary bonus rule",
                "confirm_text": PAYMENT_CONFIG_CONFIRM_TEXT,
            },
        )
        bonus_data = _payment_config_data(bonus_response)
    return {
        "channel": channel_data.get("channel"),
        "option_id": option_data.get("id"),
        "bonus_rule_id": bonus_data.get("id"),
    }


def _channel_payload_from_row(row, *, enabled=None):
    required = ("channel", "display_name")
    if any(row.get(key) in (None, "") for key in required):
        return None
    return {
        "channel": row["channel"],
        "display_name": row["display_name"],
        "qr_code_url": row.get("qr_code_url"),
        "account_name": row.get("account_name"),
        "enabled": row.get("enabled") if enabled is None else enabled,
        "sort_order": row.get("sort_order", 0),
        "remark": row.get("remark"),
        "confirm_text": PAYMENT_CONFIG_CONFIRM_TEXT,
    }


def _option_payload_from_row(row, *, enabled=None):
    required = ("amount", "credit_quota")
    if any(row.get(key) in (None, "") for key in required):
        return None
    return {
        "amount": row["amount"],
        "credit_quota": row["credit_quota"],
        "label": row.get("label"),
        "enabled": row.get("enabled") if enabled is None else enabled,
        "sort_order": row.get("sort_order", 0),
        "remark": row.get("remark"),
        "confirm_text": PAYMENT_CONFIG_CONFIRM_TEXT,
    }


def _bonus_payload_from_row(row, *, enabled=None):
    required = ("threshold_amount", "bonus_quota")
    if any(row.get(key) in (None, "") for key in required):
        return None
    return {
        "threshold_amount": row["threshold_amount"],
        "bonus_quota": row["bonus_quota"],
        "enabled": row.get("enabled") if enabled is None else enabled,
        "sort_order": row.get("sort_order", 0),
        "remark": row.get("remark"),
        "confirm_text": PAYMENT_CONFIG_CONFIRM_TEXT,
    }


def _snapshot_keys(snapshot):
    return {
        "channels": {row.get("channel") for row in snapshot.channels if isinstance(row, dict)},
        "fixed_options": {row.get("amount") for row in snapshot.fixed_options if isinstance(row, dict)},
        "bonus_rules": {row.get("id") for row in snapshot.bonus_rules if isinstance(row, dict)},
    }


def _sanitize_payment_snapshot(snapshot: PaymentSnapshot) -> PaymentSnapshot:
    return PaymentSnapshot(
        channels=[dict(row) for row in snapshot.channels if isinstance(row, dict) and not _payment_row_mentions_qa_prefix(row)],
        fixed_options=[dict(row) for row in snapshot.fixed_options if isinstance(row, dict) and not _payment_row_mentions_qa_prefix(row)],
        bonus_rules=[dict(row) for row in snapshot.bonus_rules if isinstance(row, dict) and not _payment_row_mentions_qa_prefix(row)],
    )


def restore_payment_snapshot(admin: APIClient, snapshot: PaymentSnapshot, prefix: str) -> None:
    validate_run_prefix(prefix)
    current = load_payment_snapshot(admin)
    clean_snapshot = _sanitize_payment_snapshot(snapshot)
    restore_summary = {
        "fallback_disabled_recharge_options": [],
        "disabled_temp_channels": [],
        "deleted_temp_recharge_options": [],
        "deleted_temp_bonus_rules": [],
    }

    for row in current.channels:
        if _payment_row_mentions_qa_prefix(row):
            payload = _channel_payload_from_row(row, enabled=False)
            if payload:
                _post_payment_channel(admin, payload)
                restore_summary["disabled_temp_channels"].append(row.get("channel"))

    for row in current.fixed_options:
        if _payment_row_mentions_qa_prefix(row):
            option_id = row.get("id")
            if option_id is not None:
                try:
                    _delete_recharge_option(admin, option_id)
                    restore_summary["deleted_temp_recharge_options"].append(option_id)
                except QASafetyError:
                    _disable_recharge_option(admin, row)
                    restore_summary["fallback_disabled_recharge_options"].append(option_id)

    for row in current.bonus_rules:
        if _payment_row_mentions_qa_prefix(row):
            rule_id = row.get("id")
            if rule_id is not None:
                _delete_bonus_rule(admin, rule_id)
                restore_summary["deleted_temp_bonus_rules"].append(rule_id)

    for row in clean_snapshot.channels:
        payload = _channel_payload_from_row(row)
        if payload:
            _post_payment_channel(admin, payload)
    for row in clean_snapshot.fixed_options:
        payload = _option_payload_from_row(row)
        if payload:
            _post_recharge_option(admin, payload)
    return {key: value for key, value in restore_summary.items() if value}


def cleanup_payment_config_by_prefix(admin: APIClient, prefix: str):
    validate_run_prefix(prefix)
    current = load_payment_snapshot(admin)
    cleanup_summary = {
        "disabled_channels": [],
        "deleted_recharge_options": [],
        "fallback_disabled_recharge_options": [],
        "deleted_bonus_rules": [],
    }

    for row in current.channels:
        if _payment_row_owned_by_run(row, prefix):
            payload = _channel_payload_from_row(row, enabled=False)
            if payload:
                _post_payment_channel(admin, payload)
                cleanup_summary["disabled_channels"].append(row.get("channel"))

    for row in current.fixed_options:
        if _payment_row_owned_by_run(row, prefix):
            option_id = row.get("id")
            if option_id is not None:
                try:
                    _delete_recharge_option(admin, option_id)
                    cleanup_summary["deleted_recharge_options"].append(option_id)
                except QASafetyError:
                    _disable_recharge_option(admin, row)
                    cleanup_summary["fallback_disabled_recharge_options"].append(option_id)

    for row in current.bonus_rules:
        if _payment_row_owned_by_run(row, prefix):
            rule_id = row.get("id")
            if rule_id is not None:
                _delete_bonus_rule(admin, rule_id)
                cleanup_summary["deleted_bonus_rules"].append(rule_id)

    return {key: value for key, value in cleanup_summary.items() if value}


TINY_PROOF_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff"
    b"\xff?\x00\x05\xfe\x02\xfeA\xe2$\xb5\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _response_json(response, method, path, sensitive_values=()):
    if response.status_code != 200:
        safe_text = _sanitize_api_error_text(response.text, sensitive_values)
        raise QASafetyError(f"API {method} {path} returned status {response.status_code}; response={safe_text!r}")
    try:
        return response.json()
    except ValueError as error:
        safe_text = _sanitize_api_error_text(response.text, sensitive_values)
        raise QASafetyError(f"API {method} {path} returned invalid JSON; response={safe_text!r}") from error


def _payload_data(response):
    if not isinstance(response, dict):
        return {}
    data = response.get("data")
    return data if isinstance(data, dict) else response


def _payload_items(response):
    if not isinstance(response, dict):
        return []
    data = response.get("data")
    if isinstance(data, dict):
        items = data.get("items")
        return items if isinstance(items, list) else []
    if isinstance(data, list):
        return data
    items = response.get("items")
    return items if isinstance(items, list) else []


def _extract_issue_balance(response):
    data = _payload_data(response)
    issue_card = data.get("issue_card") if isinstance(data, dict) else None
    if isinstance(issue_card, dict) and issue_card.get("balance") is not None:
        return int(issue_card["balance"])
    if isinstance(response, dict):
        issue_card = response.get("issue_card")
        if isinstance(issue_card, dict) and issue_card.get("balance") is not None:
            return int(issue_card["balance"])
    return int(data.get("kami_issue_balance", 0) or 0)


def get_issue_quota_balance(merchant: MerchantContext):
    return _extract_issue_balance(merchant.client.json("GET", "/api/v1/merchant/quotas"))


def assert_quota_delta(before, after, expected_delta, label):
    actual = int(after) - int(before)
    if actual != int(expected_delta):
        raise QASafetyError(f"{label} quota delta mismatch: expected {expected_delta}, got {actual}")


def redact_card_codes(codes):
    return [mask_middle(code) for code in codes]


def register_merchant(base_url: str, prefix: str, client: APIClient | None = None) -> MerchantContext:
    validate_run_prefix(prefix)
    public_client = client or APIClient(base_url)
    username = f"{prefix}merchant_{uuid.uuid4().hex[:6]}"
    password = f"QA-{uuid.uuid4().hex}-{uuid.uuid4().hex[:8]}"
    response = public_client.json(
        "POST",
        "/api/v1/auth/register",
        json={
            "username": username,
            "password": password,
            "email": f"{username}@example.invalid",
        },
        sensitive_values=[password],
    )
    token = response.get("token") if isinstance(response, dict) else None
    user_info = response.get("user_info") if isinstance(response, dict) else None
    role = response.get("role") if isinstance(response, dict) else None
    if not token or role != "merchant" or not isinstance(user_info, dict):
        safe_response = _sanitize_api_error_text(json.dumps(response, ensure_ascii=True), [password, token])
        raise QASafetyError(f"Merchant registration returned unexpected response; response={safe_response!r}")
    auth = AuthSession(token=token, role=role, user_info=user_info)
    return MerchantContext(
        prefix=prefix,
        base_url=base_url,
        username=user_info.get("username") or username,
        user_id=user_info.get("id"),
        auth=auth,
        client=APIClient(base_url, auth) if client is None else public_client,
    )


def submit_recharge_order(merchant: MerchantContext, channel):
    channel_data = channel if isinstance(channel, dict) else {"channel": channel}
    channel_name = channel_data.get("channel") or "other"
    option_id = channel_data.get("option_id")
    amount = channel_data.get("amount") or 991
    form = {
        "amount": str(amount),
        "mode": "fixed" if option_id is not None else "custom",
        "channel": str(channel_name),
        "remark": f"{merchant.prefix}temporary recharge proof",
    }
    if option_id is not None:
        form["option_id"] = str(option_id)
    path = "/api/v1/merchant/recharge/orders/upload"
    response = merchant.client.request(
        "POST",
        path,
        data=form,
        files={"proof_file": ("qa-proof.png", TINY_PROOF_PNG, "image/png")},
    )
    data = _payload_data(_response_json(response, "POST", path))
    if not data.get("order_no"):
        raise QASafetyError("Recharge upload response missing order_no")
    return data


def approve_recharge_order(admin: APIClient, order_no: str):
    response = admin.json(
        "POST",
        f"/api/v1/admin/commercial/recharge-orders/{order_no}/approve",
        json={"confirm_text": RECHARGE_APPROVAL_CONFIRM_TEXT},
    )
    return _payload_data(response)


def create_self_app(merchant: MerchantContext, prefix: str):
    validate_run_prefix(prefix)
    name = f"{prefix}Self app"
    response = merchant.client.json("POST", "/api/v1/merchant/apps", json={"name": name})
    data = _payload_data(response)
    if not data.get("app_id"):
        raise QASafetyError("Merchant app creation response missing app_id")
    return AppResource(
        app_id=data["app_id"],
        name=data.get("name") or name,
        app_secret=data.get("app_secret"),
        rsa_public_key=data.get("rsa_public_key"),
    )


def create_self_spec(_merchant: MerchantContext, _app_id: str):
    return SpecDescriptor(
        spec_id=None,
        issue_payload={
            "kami_type": "points",
            "points_amount": 10,
            "points_valid_days": 30,
        },
        source="self_owned_direct_fields",
    )


def create_merchant_ui_seed_spec(merchant: MerchantContext, app_id: str, prefix: str):
    validate_run_prefix(prefix)
    payload = {
        "spec_group": "custom",
        "kami_type": "points",
        "points_amount": 10,
        "points_valid_days": 30,
        "machine_bind_mode": "one_card_one_device",
        "authorization_owner": "device",
        "user_bind_mode": "none",
        "status": 1,
        "sort_order": 9000,
        "remark": f"{prefix}browser UI seed spec",
    }
    response = merchant.client.json("POST", f"/api/v1/merchant/apps/{app_id}/specs", json=payload)
    data = _payload_data(response)
    spec_id = data.get("id") or data.get("spec_id")
    if not spec_id:
        raise QASafetyError("Merchant browser UI seed spec creation response missing spec id")
    return SpecDescriptor(
        spec_id=int(spec_id),
        issue_payload={"spec_id": int(spec_id)},
        source="self_owned_ui_seed",
    )


def _issue_payload_from_spec(spec: SpecDescriptor, prefix: str, count=2):
    payload = {
        "spec_id": spec.spec_id,
        "count": count,
        "batch_no": f"{prefix}batch_{uuid.uuid4().hex[:8]}",
        "code_prefix": "QA",
        "code_length": 12,
        "charset": "upper_numeric",
    }
    if spec.spec_id is not None:
        return payload
    payload.update(spec.issue_payload)
    return payload


def issue_batch(merchant: MerchantContext, app_id: str, spec: SpecDescriptor, prefix: str, count=2) -> BatchResult:
    validate_run_prefix(prefix)
    payload = _issue_payload_from_spec(spec, prefix, count=count)
    preview = merchant.client.json(
        "POST",
        f"/api/v1/merchant/apps/{app_id}/kamis/preview",
        json=payload,
    )
    try:
        issue = merchant.client.json(
            "POST",
            f"/api/v1/merchant/apps/{app_id}/kamis/batch",
            json=payload,
        )
    except QASafetyError as error:
        context = {
            "app_id": app_id,
            "spec_id": spec.spec_id,
            "source": spec.source,
            "batch_no": payload.get("batch_no"),
            "count": payload.get("count"),
            "preview": _payload_data(preview),
        }
        safe_context = _format_report_line(redact(context))
        safe_error = sanitize_report_string(str(error))
        raise QASafetyError(f"Merchant issue batch failed; context={safe_context}; error={safe_error!r}") from error
    issue_data = _payload_data(issue)
    codes = list(issue_data.get("codes") or [])
    return BatchResult(
        app_id=app_id,
        batch_id=issue_data.get("batch_id") or issue_data.get("id"),
        batch_no=issue_data.get("batch_no") or payload["batch_no"],
        count=int(issue_data.get("count") or len(codes) or count),
        codes=codes,
        preview=_payload_data(preview),
        issue=redact(issue_data),
    )


def fetch_batch_cards(merchant: MerchantContext, batch: BatchResult):
    response = merchant.client.json(
        "GET",
        "/api/v1/merchant/kamis",
        params={"app_id": batch.app_id, "batch_no": batch.batch_no, "page": 1, "page_size": 20},
    )
    data = response.get("data") if isinstance(response, dict) else {}
    items = _payload_items(response)
    codes = [
        item.get("kami_code") or item.get("code")
        for item in items
        if isinstance(item, dict) and (item.get("kami_code") or item.get("code"))
    ]
    total = data.get("total") if isinstance(data, dict) else None
    return {"count": int(total if total is not None else len(items)), "sample_codes": redact_card_codes(codes[:3])}


def _decrypt_sdk_response(response, app_secret):
    if not isinstance(response, dict) or not response.get("encrypted"):
        return response
    try:
        import base64
        import json as json_module
        from crypto import AESCrypto, HMACSigner

        sign_data = f"{response['timestamp']}{response['nonce']}{response['encrypted_data']}"
        if not HMACSigner.verify_sign(sign_data, app_secret, response["sign"]):
            raise QASafetyError("SDK verify response signature mismatch")
        aes_key = base64.b64decode(response["encrypted_key"])
        raw = AESCrypto.decrypt(response["iv"], response["encrypted_data"], aes_key)
        return json_module.loads(raw.decode("utf-8"))
    except QASafetyError:
        raise
    except Exception as error:
        safe_error = _sanitize_api_error_text(str(error), [app_secret])
        raise QASafetyError(f"Failed to decrypt SDK verify response; error={safe_error!r}") from error


def _sdk_compatible_verify(**kwargs):
    base_url = kwargs["base_url"]
    app_id = kwargs["app_id"]
    card_code = kwargs["card_code"]
    app_secret = kwargs.get("app_secret")
    rsa_public_key = kwargs.get("rsa_public_key")
    if not app_secret:
        raise QASafetyError("app_secret is required for SDK-compatible verification")
    client = APIClient(base_url)
    if not rsa_public_key:
        key_response = client.json("GET", "/api/v1/sdk/public-key", params={"app_id": app_id})
        rsa_public_key = key_response.get("public_key") or _payload_data(key_response).get("public_key")
    if not rsa_public_key:
        raise QASafetyError("SDK public key response missing public_key")
    try:
        import time
        from crypto import CryptoHelper, HMACSigner

        encrypted = CryptoHelper.encrypt_payload(
            {
                "kami": card_code,
                "fingerprint": f"fingerprint-{uuid.uuid4().hex[:16]}",
                "_app_info": {"app_id": app_id},
            },
            rsa_public_key,
        )
        timestamp = int(time.time())
        nonce = uuid.uuid4().hex[:16]
        encrypted_data = encrypted["encrypted_data"]
        payload = {
            "app_id": app_id,
            "timestamp": timestamp,
            "nonce": nonce,
            "sign": HMACSigner.generate_sign(f"{timestamp}{nonce}{encrypted_data}", app_secret),
            **encrypted,
        }
        response = client.json(
            "POST",
            "/api/v1/sdk/verify",
            json=payload,
            sensitive_values=[card_code, app_secret],
        )
        return _decrypt_sdk_response(response, app_secret)
    except QASafetyError:
        raise
    except Exception as error:
        safe_error = _sanitize_api_error_text(str(error), [card_code, app_secret, rsa_public_key])
        raise QASafetyError(f"SDK-compatible verify failed; error={safe_error!r}") from error


def verify_one_card(base_url: str, app_id: str, card_code: str, app_secret=None, rsa_public_key=None, verifier=None):
    verify = verifier or _sdk_compatible_verify
    result = verify(
        base_url=base_url,
        app_id=app_id,
        card_code=card_code,
        app_secret=app_secret,
        rsa_public_key=rsa_public_key,
    )
    safe_result = redact(result)
    return {
        "app_id": app_id,
        "card_code": redact_card_codes([card_code])[0],
        "success": bool(result.get("success")) if isinstance(result, dict) else False,
        "result": safe_result,
    }


def create_admin_app_and_spec(admin: APIClient, prefix: str):
    validate_run_prefix(prefix)
    app_response = admin.json(
        "POST",
        "/api/v1/admin/apps",
        params={"name": f"{prefix}Admin app"},
    )
    app_data = _payload_data(app_response)
    if not app_data.get("app_id"):
        raise QASafetyError("Admin app creation response missing app_id")
    app = AppResource(
        app_id=app_data["app_id"],
        name=app_data.get("name") or f"{prefix}Admin app",
        app_secret=app_data.get("app_secret"),
        rsa_public_key=app_data.get("rsa_public_key"),
    )
    spec_payload = {
        "app_id": app.app_id,
        "kami_type": "points",
        "spec_group": "custom",
        "points_amount": 10,
        "points_valid_days": 30,
        "machine_bind_mode": "one_card_one_device",
        "authorization_owner": "device",
        "user_bind_mode": "none",
        "status": 1,
        "sort_order": 9000,
        "remark": f"{prefix}Temporary admin spec",
    }
    spec_response = admin.json("POST", "/api/v1/admin/kami-specs", json=spec_payload)
    spec_data = _payload_data(spec_response)
    if not spec_data.get("id"):
        raise QASafetyError("Admin spec creation response missing id")
    safe_spec_fields = {
        "spec_id": spec_data["id"],
    }
    for key in (
        "kami_type",
        "points_amount",
        "points_valid_days",
        "spec_group",
        "machine_bind_mode",
        "authorization_owner",
        "user_bind_mode",
        "status",
        "sort_order",
        "remark",
    ):
        value = spec_data.get(key)
        if value is None:
            value = spec_payload.get(key)
        if value is not None:
            safe_spec_fields[key] = value
    spec = SpecDescriptor(spec_id=spec_data["id"], issue_payload=safe_spec_fields, source="admin_authorized")
    return app, spec


def authorize_app_to_merchant(admin: APIClient, merchant_id: int, app_id: str):
    response = admin.json(
        "POST",
        f"/api/v1/admin/end-users/{merchant_id}/app-authorizations",
        json={
            "app_id": app_id,
            "remark": "temporary production E2E app authorization",
            "confirm_text": GRANT_APP_AUTHORIZATION_CONFIRM_TEXT,
        },
    )
    return _payload_data(response)


def grant_issue_quota(admin: APIClient, merchant_id: int, amount: int, prefix: str):
    validate_run_prefix(prefix)
    response = admin.json(
        "POST",
        f"/api/v1/admin/end-users/{merchant_id}/quotas/grant",
        json={
            "quota_type": "kami_issue",
            "amount": amount,
            "biz_id": f"{prefix}grant_{uuid.uuid4().hex[:8]}",
            "remark": f"{prefix}temporary issue quota",
            "confirm_text": GRANT_ISSUE_QUOTA_CONFIRM_TEXT,
        },
    )
    return _payload_data(response)


def verify_permission_boundaries(admin: APIClient, merchant: MerchantContext, prefix: str):
    validate_run_prefix(prefix)
    checks = [
        merchant.client.json(
            "GET",
            "/api/v1/admin/commercial/recharge-orders",
            expected=(401, 403),
        ),
        admin.json(
            "GET",
            "/api/v1/merchant/me",
            expected=(401, 403),
        ),
    ]
    return {"checked": len(checks), "results": [redact(item) for item in checks]}


def cleanup_run(admin: APIClient, prefix: str):
    validate_run_prefix(prefix)
    merchant_response = admin.json(
        "GET",
        "/api/v1/admin/commercial/merchants",
        params={"keyword": prefix, "page": 1, "page_size": 100},
    )
    merchant_ids = []
    for row in _payload_items(merchant_response):
        username = row.get("username") if isinstance(row, dict) else None
        if username and is_owned_by_run(username, prefix):
            merchant_ids.append(row.get("id"))
    merchant_ids = [int(user_id) for user_id in merchant_ids if user_id is not None]

    app_response = admin.json("GET", "/api/v1/admin/apps")
    app_ids = []
    for row in _payload_items(app_response):
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        app_id = row.get("app_id")
        if name and is_owned_by_run(name, prefix) and app_id:
            app_ids.append(app_id)

    for app_id in app_ids:
        admin.json(
            "DELETE",
            f"/api/v1/admin/apps/{app_id}",
            params={"confirm_text": DELETE_APP_CONFIRM_TEXT},
        )
    if merchant_ids:
        admin.json(
            "POST",
            "/api/v1/admin/end-users/delete",
            json={"user_ids": merchant_ids, "confirm_text": DELETE_USER_CONFIRM_TEXT},
        )
    payment_config_summary = cleanup_payment_config_by_prefix(admin, prefix)
    return {"merchant_user_ids": merchant_ids, "admin_app_ids": app_ids, "payment_config": payment_config_summary}


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
            if _is_sensitive_key(key) or normalized in PAYMENT_SENSITIVE_KEYS:
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


def _finding(severity, route, viewport, message, detail=None):
    finding = {
        "severity": severity,
        "route": route,
        "viewport": viewport,
        "message": message,
    }
    if detail is not None:
        finding["detail"] = detail
    return finding


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
    action_groups = layout.get("action_groups")
    if action_groups is None:
        action_groups = layout.get("actionGroups")
    duplicated_controls = layout.get("duplicated_controls")
    if duplicated_controls is None:
        duplicated_controls = layout.get("duplicatedControls")
    header_occlusions = layout.get("header_occlusions")
    if header_occlusions is None:
        header_occlusions = layout.get("headerOcclusions")
    table_column_mismatches = layout.get("table_column_mismatches")
    if table_column_mismatches is None:
        table_column_mismatches = layout.get("tableColumnMismatches")
    page_contract_mismatches = layout.get("page_contract_mismatches")
    if page_contract_mismatches is None:
        page_contract_mismatches = layout.get("pageContractMismatches")
    detail_panel_mismatches = layout.get("detail_panel_mismatches")
    if detail_panel_mismatches is None:
        detail_panel_mismatches = layout.get("detailPanelMismatches")
    detail_summary_mismatches = layout.get("detail_summary_mismatches")
    if detail_summary_mismatches is None:
        detail_summary_mismatches = layout.get("detailSummaryMismatches")
    split_workbench_detected = layout.get("split_workbench_detected")
    if split_workbench_detected is None:
        split_workbench_detected = layout.get("splitWorkbenchDetected")
    merchant_batch_detail_opened_as_drawer = layout.get("merchant_batch_detail_opened_as_drawer")
    if merchant_batch_detail_opened_as_drawer is None:
        merchant_batch_detail_opened_as_drawer = layout.get("merchantBatchDetailOpenedAsDrawer")
    merchant_batch_detail_url_has_batch_no = layout.get("merchant_batch_detail_url_has_batch_no")
    if merchant_batch_detail_url_has_batch_no is None:
        merchant_batch_detail_url_has_batch_no = layout.get("merchantBatchDetailUrlHasBatchNo")

    if horizontal_overflow:
        findings.append(_finding("P2", route, viewport, "Horizontal overflow detected"))
    if large_blank_ratio >= 0.55:
        findings.append(_finding("P2", route, viewport, "Large blank page area detected"))
    if overwide_cards:
        findings.append(_finding("P2", route, viewport, "Overwide cards detected"))
    if duplicated_controls:
        findings.append(_finding("P2", route, viewport, "Duplicated controls detected"))
    if header_occlusions:
        findings.append(_finding("P2", route, viewport, "Header/title occlusion detected"))
    if table_column_mismatches:
        findings.append(_finding("P1", route, viewport, "Admin/merchant table parity mismatch", table_column_mismatches))
    if page_contract_mismatches:
        contract_severities = [str(item.get("severity") or "P1").upper() for item in page_contract_mismatches if isinstance(item, dict)]
        severity = "P1" if any(item in {"P0", "P1"} for item in contract_severities) else "P2"
        findings.append(_finding(severity, route, viewport, "Page contract mismatch detected", {"contracts": page_contract_mismatches}))
    if detail_panel_mismatches and route.startswith("/merchant/") and route.endswith("/batches"):
        findings.append(_finding("P1", route, viewport, "Admin/merchant detail panel parity mismatch", detail_panel_mismatches))
    if detail_summary_mismatches and route.startswith("/merchant/") and route.endswith("/batches"):
        findings.append(_finding("P1", route, viewport, "Admin/merchant detail summary parity mismatch", detail_summary_mismatches))
    if split_workbench_detected and route.startswith("/merchant/") and route.endswith("/batches"):
        findings.append(_finding("P1", route, viewport, "Merchant batch page uses split workbench layout"))
    if merchant_batch_detail_opened_as_drawer is True and route.startswith("/merchant/") and route.endswith("/batches"):
        findings.append(_finding("P1", route, viewport, "Merchant batch detail opened as drawer instead of standalone detail page"))
    if merchant_batch_detail_url_has_batch_no is False and route.startswith("/merchant/") and route.endswith("/batches"):
        findings.append(_finding("P1", route, viewport, "Merchant batch detail route did not retain batch_no context"))
    for group in action_groups or []:
        if not isinstance(group, dict):
            continue
        if group.get("wrapped"):
            findings.append(
                _finding(
                    "P1",
                    route,
                    viewport,
                    "Action button group wraps across rows",
                )
            )
            break
        button_count = int(group.get("button_count") or 0)
        max_gap = int(group.get("max_gap") or 0)
        spread_ratio = float(group.get("spread_ratio") or 0)
        if button_count >= 2 and (max_gap >= 40 or (button_count <= 4 and spread_ratio >= 1.4)):
            findings.append(
                _finding(
                    "P1",
                    route,
                    viewport,
                    "Action button group is overly dispersed",
                )
            )
            break

    return findings


def _safe_int(value, default=0):
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _layout_action_groups(layout):
    groups = layout.get("action_groups")
    if groups is None:
        groups = layout.get("actionGroups")
    return [group for group in groups or [] if isinstance(group, dict)]


def _select_visual_action_group(layout):
    groups = _layout_action_groups(layout)
    candidates = [group for group in groups if _safe_int(group.get("button_count")) >= 2]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda group: (
            _safe_int(group.get("button_count")),
            -_safe_int(group.get("max_gap")),
            _safe_int(group.get("left")),
        ),
    )[0]


def _crop_visual_target(screenshot_path, group, padding):
    with Image.open(screenshot_path) as image:
        image = image.convert("RGBA")
        width, height = image.size
        left = max(0, _safe_int(group.get("left")) - padding)
        top = max(0, _safe_int(group.get("top")) - padding)
        right = min(width, _safe_int(group.get("left")) + _safe_int(group.get("width")) + padding)
        bottom = min(height, _safe_int(group.get("top")) + _safe_int(group.get("height")) + padding)
        if right <= left or bottom <= top:
            raise QASafetyError("Visual regression crop is invalid")
        return image.crop((left, top, right, bottom)), {
            "left": left,
            "top": top,
            "right": right,
            "bottom": bottom,
        }


def _compare_visual_images(expected, actual, pixel_threshold=16):
    if expected.size != actual.size:
        diff = Image.new("RGBA", actual.size, (255, 0, 0, 255))
        return {
            "mean_diff": float("inf"),
            "changed_ratio": 1.0,
            "diff_image": diff,
            "size_mismatch": True,
        }
    diff = ImageChops.difference(expected, actual).convert("RGBA")
    stat = ImageStat.Stat(diff)
    mean_diff = sum(stat.mean[:3]) / 3.0
    changed_pixels = 0
    total_pixels = diff.width * diff.height
    pixels = diff.get_flattened_data() if hasattr(diff, "get_flattened_data") else diff.getdata()
    for red, green, blue, _alpha in pixels:
        if red > pixel_threshold or green > pixel_threshold or blue > pixel_threshold:
            changed_pixels += 1
    return {
        "mean_diff": mean_diff,
        "changed_ratio": changed_pixels / total_pixels if total_pixels else 0.0,
        "diff_image": diff,
        "size_mismatch": False,
    }


def _visual_finding(target, message, detail=None):
    finding = _finding("P2", target["route"], target["viewport"], message)
    finding["role"] = target["role"]
    if detail:
        finding["detail"] = sanitize_report_string(detail)
    return finding


def _blocking_visual_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blocking_messages = {
        "Visual regression target layout region is missing",
        "Visual regression target action group is missing",
        "Visual regression screenshot is missing",
        "Visual regression baseline is missing",
        "Visual regression diff exceeded threshold",
        "Visual regression check failed",
    }
    return [
        finding for finding in findings
        if finding.get("message") in blocking_messages
    ]


def _blocking_browser_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        finding for finding in findings
        if str(finding.get("severity") or "").upper() in {"P0", "P1"}
    ]


def _should_skip_visual_target(target: dict[str, Any], layout: dict[str, Any]) -> bool:
    if target.get("label") != "merchant-batches-batch-row-actions":
        return False

    diagnostics = layout.get("merchantBatchDiagnostics") or {}
    return _safe_int(diagnostics.get("batchRowCount")) == 0


def run_visual_regression(browser_results, artifact_dir):
    results_by_key = {
        (result.get("role"), result.get("route"), result.get("viewport")): result
        for result in browser_results
    }
    output_dir = Path(artifact_dir) / "visual-regression"
    output_dir.mkdir(parents=True, exist_ok=True)
    comparisons = []
    findings = []

    for target in VISUAL_REGRESSION_TARGETS:
        key = (target["role"], target["route"], target["viewport"])
        result = results_by_key.get(key)
        if not result:
            continue
        layout = result.get("layout") or {}
        if _should_skip_visual_target(target, layout):
            continue
        crop_kind = target.get("crop_kind", "action_group")
        if crop_kind == "rect":
            group = layout.get(target.get("crop_key", ""))
            missing_crop_message = "Visual regression target layout region is missing"
        else:
            group = _select_visual_action_group(layout)
            missing_crop_message = "Visual regression target action group is missing"
        comparison = {
            "role": target["role"],
            "route": target["route"],
            "viewport": target["viewport"],
            "label": target["label"],
            "baseline": str(VISUAL_BASELINE_DIR / target["baseline"]),
            "crop_kind": crop_kind,
        }
        comparisons.append(comparison)
        if not group:
            diagnostics = layout.get("merchantBatchDiagnostics")
            detail = None
            if diagnostics:
                detail = f"crop_key={target.get('crop_key')}; diagnostics={json.dumps(redact(diagnostics), ensure_ascii=True, sort_keys=True)}"
            findings.append(_visual_finding(target, missing_crop_message, detail))
            continue

        screenshot_key = target.get("screenshot_key", "screenshot")
        comparison["screenshot_key"] = screenshot_key
        screenshot_path = result.get(screenshot_key)
        if not screenshot_path or not Path(screenshot_path).exists():
            findings.append(_visual_finding(target, "Visual regression screenshot is missing"))
            continue

        try:
            actual_crop, crop_box = _crop_visual_target(screenshot_path, group, target["crop_padding"])
        except Exception as error:
            findings.append(_visual_finding(target, "Visual regression check failed", str(error)))
            continue

        comparison["crop_box"] = crop_box
        actual_path = output_dir / f'{target["label"]}.{target["viewport"]}.actual.png'
        actual_crop.save(actual_path)
        comparison["actual"] = str(actual_path)

        baseline_path = VISUAL_BASELINE_DIR / target["baseline"]
        comparison["baseline_exists"] = baseline_path.exists()
        if not baseline_path.exists():
            findings.append(_visual_finding(target, "Visual regression baseline is missing"))
            continue

        try:
            with Image.open(baseline_path) as expected_image:
                expected = expected_image.convert("RGBA")
                metrics = _compare_visual_images(expected, actual_crop)
        except Exception as error:
            findings.append(_visual_finding(target, "Visual regression check failed", str(error)))
            continue

        comparison["mean_diff"] = round(metrics["mean_diff"], 3) if metrics["mean_diff"] != float("inf") else "inf"
        comparison["changed_ratio"] = round(metrics["changed_ratio"], 4)
        if metrics["size_mismatch"] or metrics["mean_diff"] > target["max_mean_diff"] or metrics["changed_ratio"] > target["max_changed_ratio"]:
            diff_path = output_dir / f'{target["label"]}.{target["viewport"]}.diff.png'
            metrics["diff_image"].save(diff_path)
            comparison["diff"] = str(diff_path)
            findings.append(_visual_finding(target, "Visual regression diff exceeded threshold"))

    return {"checks": len(comparisons), "comparisons": comparisons, "findings": findings}


def _finding_identity(finding):
    return (
        finding.get("role") or "<unknown>",
        finding.get("route") or "<unknown>",
        finding.get("viewport") or "<unknown>",
    )


def summarize_browser_sweep(browser_results: list[dict[str, Any]], browser_findings: list[dict[str, Any]]):
    summary = {}
    for result in browser_results:
        key = (
            result.get("role") or "<unknown>",
            result.get("route") or "<unknown>",
            result.get("viewport") or "<unknown>",
        )
        row = summary.setdefault(
            key,
            {
                "role": key[0],
                "route": key[1],
                "viewport": key[2],
                "checks": 0,
                "findings": 0,
                "severity_counts": {},
            },
        )
        row["checks"] += 1

    for finding in browser_findings:
        key = _finding_identity(finding)
        row = summary.setdefault(
            key,
            {
                "role": key[0],
                "route": key[1],
                "viewport": key[2],
                "checks": 0,
                "findings": 0,
                "severity_counts": {},
            },
        )
        row["findings"] += 1
        severity = str(finding.get("severity") or "P3").strip() or "P3"
        row["severity_counts"][severity] = row["severity_counts"].get(severity, 0) + 1

    return [summary[key] for key in sorted(summary)]


def format_finding(finding: dict[str, Any]) -> str:
    severity = str(finding.get("severity") or "P3").strip() or "P3"
    route = finding.get("route")
    viewport = finding.get("viewport")
    message = finding.get("message") or finding.get("detail") or "Finding requires review"
    suffix_parts = []
    if route:
        suffix_parts.append(str(route))
    if viewport:
        suffix_parts.append(str(viewport))
    suffix = f" [{' '.join(suffix_parts)}]" if suffix_parts else ""
    detail = finding.get("detail")
    line = f"{severity}{suffix} {message}"
    if detail and str(detail) != str(message):
        line = f"{line} - {detail}"
    return sanitize_report_string(line)


def add_analysis_sections(
    report: "QAReport",
    product_findings: list[dict[str, Any]],
    engineering_findings: list[dict[str, Any]],
    product_assessed: bool = True,
) -> None:
    if product_findings:
        product_lines = [format_finding(finding) for finding in product_findings]
    elif product_assessed:
        product_lines = ["产品体验未发现阻塞项。"]
    else:
        product_lines = ["浏览器用户体验未完成评估，数据不足以判断是否存在阻塞项。"]

    if engineering_findings:
        engineering_lines = [format_finding(finding) for finding in engineering_findings]
    else:
        engineering_lines = ["工程实现未发现阻塞项。"]

    report.add_section("产品经理视角", product_lines)
    report.add_section("资深开发工程师视角", engineering_lines)


def _analysis_finding(finding, default_severity="P3"):
    result = {
        "severity": finding.get("severity") or default_severity,
        "message": sanitize_report_string(finding.get("message") or "Finding requires review"),
    }
    for key in ("role", "route", "viewport"):
        if finding.get(key):
            result[key] = sanitize_report_string(finding[key])
    if finding.get("detail"):
        result["detail"] = sanitize_report_string(finding["detail"])
    return result


PRODUCT_BROWSER_MESSAGES = {
    "Console errors detected",
    "Runtime exceptions detected",
    "HTTP errors detected",
    "Route document returned bad status",
    "Page body text is unexpectedly sparse",
    "Horizontal overflow detected",
    "Large blank page area detected",
    "Overwide cards detected",
    "Action button group is overly dispersed",
    "Action button group wraps across rows",
    "Admin/merchant detail summary parity mismatch",
    "Visual regression baseline is missing",
    "Visual regression check failed",
    "Visual regression screenshot is missing",
    "Visual regression target action group is missing",
    "Visual regression target layout region is missing",
    "Visual regression diff exceeded threshold",
}

ENGINEERING_BROWSER_MESSAGES = {
    "Console errors detected",
    "Runtime exceptions detected",
    "Network failures detected",
    "HTTP errors detected",
    "Route document returned bad status",
    "Action button group is overly dispersed",
    "Action button group wraps across rows",
    "Admin/merchant detail summary parity mismatch",
    "Visual regression baseline is missing",
    "Visual regression check failed",
    "Visual regression screenshot is missing",
    "Visual regression target action group is missing",
    "Visual regression target layout region is missing",
    "Visual regression diff exceeded threshold",
}


def derive_product_findings(
    browser_findings: list[dict[str, Any]],
    flow_summaries: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    findings = []
    for finding in browser_findings:
        message = finding.get("message")
        if message in PRODUCT_BROWSER_MESSAGES:
            findings.append(_analysis_finding(finding))

    for finding in (flow_summaries or {}).get("product_findings", []) or []:
        if isinstance(finding, dict):
            findings.append(_analysis_finding(finding))
    return findings


def _append_if_unsuccessful_verify(findings, flow_name, flow_summary):
    verify = flow_summary.get("verify") if isinstance(flow_summary, dict) else None
    if not isinstance(verify, dict) or verify.get("success") is not False:
        return
    finding = {
        "severity": "P1",
        "route": "/api/v1/sdk/verify",
        "message": f"{flow_name} verify reported unsuccessful status",
    }
    error = verify.get("error")
    if error:
        finding["detail"] = error
    findings.append(_analysis_finding(finding))


def derive_engineering_findings(
    browser_findings: list[dict[str, Any]],
    flow_summaries: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    findings = []
    for finding in browser_findings:
        message = finding.get("message")
        if message in ENGINEERING_BROWSER_MESSAGES:
            findings.append(_analysis_finding(finding))

    flow_summaries = flow_summaries or {}
    _append_if_unsuccessful_verify(findings, "self_owned", flow_summaries.get("self_owned") or {})
    _append_if_unsuccessful_verify(findings, "authorized", flow_summaries.get("authorized") or {})

    payment_restore = (flow_summaries.get("cleanup") or {}).get("payment_restore") or {}
    if payment_restore.get("restored") is False or payment_restore.get("error"):
        findings.append(
            _analysis_finding(
                {
                    "severity": "P1",
                    "message": "Payment config restore failed",
                    "detail": payment_restore.get("error") or "restored flag was false",
                }
            )
        )

    cleanup_resources = (flow_summaries.get("cleanup") or {}).get("resources") or {}
    if cleanup_resources.get("error"):
        findings.append(
            _analysis_finding(
                {
                    "severity": "P1",
                    "message": "Temporary resource cleanup failed",
                    "detail": cleanup_resources.get("error"),
                }
            )
        )

    permission = flow_summaries.get("permission_boundaries") or {}
    if permission.get("error"):
        findings.append(
            _analysis_finding(
                {
                    "severity": "P1",
                    "message": "Permission boundary check failed",
                    "detail": permission.get("error"),
                }
            )
        )
    if permission.get("checked") is not None and permission.get("checked") != 2:
        findings.append(
            _analysis_finding(
                {
                    "severity": "P2",
                    "message": "Permission boundary check count mismatch",
                    "detail": f"checked={permission.get('checked')}",
                }
            )
        )

    recharge = flow_summaries.get("recharge") or {}
    recharge_values = (recharge.get("quota_before"), recharge.get("quota_after"), recharge.get("credit_quota"))
    if all(isinstance(value, int) for value in recharge_values):
        before, after, credit = recharge_values
        if after - before != credit:
            findings.append(
                _analysis_finding(
                    {
                        "severity": "P1",
                        "message": "Recharge quota delta mismatch",
                        "detail": f"expected {credit}, got {after - before}",
                    }
                )
            )

    if flow_summaries.get("flow_error"):
        findings.append(
            _analysis_finding(
                {
                    "severity": "P0",
                    "message": "Production flow raised exception",
                    "detail": flow_summaries.get("flow_error"),
                }
            )
        )

    for finding in flow_summaries.get("engineering_findings", []) or []:
        if isinstance(finding, dict):
            findings.append(_analysis_finding(finding))
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
    for pattern in STRING_SECRET_PATTERNS[:2]:
        text = pattern.sub("<redacted>", text)
    text = QUOTED_SECRET_KV_RE.sub(r'"<redacted_key>":"<redacted>"', text)
    text = UNQUOTED_SECRET_KV_RE.sub("<redacted>", text)
    for pattern in STRING_SECRET_PATTERNS[2:]:
        text = pattern.sub("<redacted>", text)
    text = SENSITIVE_TEXT_KEY_RE.sub("<redacted_key>", text)
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


def _artifact_dir_for_run(run_id):
    return Path("qa-artifacts") / run_id


def _check_node_cdp_capability():
    helper = Path(__file__).resolve().with_name("browser_cdp_sweep.mjs")
    if not helper.exists():
        raise QASafetyError(f"Browser CDP helper is missing: {helper}")
    candidates = [
        os.environ.get("CHROME_PATH"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
    ]
    if not any(candidate and Path(candidate).exists() for candidate in candidates):
        raise QASafetyError("Chrome executable was not found for CDP browser sweep")
    completed = subprocess.run(
        ["node", "-e", "if (typeof WebSocket !== 'function') process.exit(2); console.log('websocket-ok')"],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=15,
    )
    if completed.returncode != 0:
        stderr = sanitize_report_string(completed.stderr.strip())
        raise QASafetyError(f"Node global WebSocket capability check failed; stderr={stderr!r}")
    return {"node_websocket": True, "chrome": True}


def _require_openapi_paths(admin: APIClient):
    openapi = admin.json("GET", "/openapi.json")
    return _validate_openapi_paths(openapi, _required_openapi_routes())


def _validate_openapi_paths(openapi, required):
    paths = (openapi.get("paths") or {}) if isinstance(openapi, dict) else {}
    missing = [
        f"{method} {path}"
        for method, path in required
        if path not in paths or method.lower() not in {str(item).lower() for item in (paths.get(path) or {}).keys()}
    ]
    if missing:
        raise QASafetyError(f"Required API routes are missing: {missing}")
    return {"required_routes": len(required)}


def _require_status(response, method, path, allowed_statuses):
    if response.status_code not in allowed_statuses:
        allowed = "/".join(str(status) for status in allowed_statuses)
        raise QASafetyError(
            f"Preflight no-write probe {method} {path} returned status {response.status_code}; expected {allowed}"
        )


def _require_no_write_probe_routes(public: APIClient):
    public_routes = [
        ("GET", "/docs/api", (200,), {}),
        ("GET", "/api/v1/auth/login/public-key", (200,), {}),
    ]
    protected_routes = [
        ("GET", "/api/v1/admin/apps"),
        ("GET", "/api/v1/admin/commercial/recharge-orders"),
        ("GET", "/api/v1/merchant/me"),
        ("GET", "/api/v1/merchant/apps"),
        ("GET", "/api/v1/merchant/kamis"),
    ]
    invalid_write_probes = [
        ("POST", "/api/v1/sdk/verify", (400, 401, 422), {"json": {}}),
    ]

    for method, path, allowed_statuses, kwargs in public_routes:
        response = public.request(method, path, **kwargs)
        _require_status(response, method, path, allowed_statuses)
    for method, path in protected_routes:
        response = public.request(method, path)
        _require_status(response, method, path, (401, 403))
    for method, path, allowed_statuses, kwargs in invalid_write_probes:
        response = public.request(method, path, **kwargs)
        _require_status(response, method, path, allowed_statuses)

    return {
        "mode": "no_write_probe",
        "public_routes": len(public_routes),
        "protected_routes": len(protected_routes),
        "invalid_write_probes": len(invalid_write_probes),
    }


def _require_preflight_routes(public: APIClient):
    openapi_response = public.request("GET", "/openapi.json")
    if openapi_response.status_code == 200:
        try:
            openapi = openapi_response.json()
        except ValueError as error:
            raise QASafetyError("Preflight OpenAPI route returned invalid JSON") from error
        return {"mode": "openapi", **_validate_openapi_paths(openapi, _required_openapi_routes())}
    if openapi_response.status_code == 404:
        return _require_no_write_probe_routes(public)
    raise QASafetyError(f"Preflight OpenAPI route returned status {openapi_response.status_code}")


def _required_openapi_routes():
    return [
        ("POST", "/api/v1/auth/register"),
        ("GET", "/api/v1/merchant/me"),
        ("GET", "/api/v1/merchant/quotas"),
        ("POST", "/api/v1/merchant/apps"),
        ("GET", "/api/v1/merchant/apps/{app_id}/specs"),
        ("POST", "/api/v1/merchant/apps/{app_id}/kamis/preview"),
        ("POST", "/api/v1/merchant/apps/{app_id}/kamis/batch"),
        ("GET", "/api/v1/merchant/kamis"),
        ("POST", "/api/v1/merchant/recharge/orders/upload"),
        ("POST", "/api/v1/admin/apps"),
        ("POST", "/api/v1/admin/kami-specs"),
        ("POST", "/api/v1/admin/commercial/recharge-orders/{order_no}/approve"),
        ("POST", "/api/v1/admin/end-users/{user_id}/quotas/grant"),
        ("POST", "/api/v1/admin/end-users/{user_id}/app-authorizations"),
        ("GET", "/api/v1/sdk/public-key"),
        ("POST", "/api/v1/sdk/verify"),
    ]


def run_preflight(config: QAConfig):
    public = APIClient(config.api_base_url)
    health = public.json("GET", "/health")
    cdp = _check_node_cdp_capability()
    routes = _require_preflight_routes(public)
    return {
        "health": redact(health),
        "admin_login": {
            "skipped": True,
            "reason": "skipped to preserve no-write preflight behavior",
        },
        "cdp": cdp,
        "routes": routes,
    }


def _report_batch_summary(batch: BatchResult, cards_summary):
    return {
        "app_id": batch.app_id,
        "batch_id": batch.batch_id,
        "batch_no": batch.batch_no,
        "count": batch.count,
        "sample_codes": cards_summary.get("sample_codes", []),
    }


def _report_spec_summary(spec: SpecDescriptor):
    return {
        "source": spec.source,
        "spec_id": spec.spec_id,
        "issue_fields": redact(dict(spec.issue_payload or {})),
    }


def _report_flow_summary(batch: BatchResult, spec: SpecDescriptor, cards_summary, verify_summary):
    return {
        "app_id": batch.app_id,
        "spec": _report_spec_summary(spec),
        "batch": _report_batch_summary(batch, cards_summary),
        "cards": cards_summary,
        "verify": verify_summary,
    }


def run_production_flow(config: QAConfig):
    prefix = build_run_prefix()
    run_id = prefix.rstrip("_")
    artifact_dir = _artifact_dir_for_run(run_id)
    report = QAReport(run_id=run_id, artifact_dir=artifact_dir)
    admin_auth = login(config.api_base_url, config.admin_username, config.admin_password)
    admin = APIClient(config.api_base_url, admin_auth)
    payment_snapshot = load_payment_snapshot(admin)
    merchant = None
    payment_restore_status = {"restored": False}
    cleanup_status = {}
    flow_error = None
    browser_results = []
    browser_findings = []
    flow_summaries = {
        "deployment_health": {
            "base_url": config.base_url,
            "api_base_url": config.api_base_url,
            "browser_base_url": config.browser_base_url,
            "health": "checked",
        },
    }
    try:
        temp_payment = ensure_temporary_payment_config(admin, prefix) or {}
        merchant = register_merchant(config.api_base_url, prefix)
        before_recharge = get_issue_quota_balance(merchant)
        order = submit_recharge_order(
            merchant,
            {
                "channel": temp_payment.get("channel") or "other",
                "option_id": temp_payment.get("option_id"),
                "amount": 991,
            },
        )
        approved = approve_recharge_order(admin, order["order_no"])
        after_recharge = get_issue_quota_balance(merchant)
        expected_credit = int(approved.get("credit_quota") or 9910)
        assert_quota_delta(before_recharge, after_recharge, expected_credit, "recharge credit")
        recharge_summary = {
            "order_no": order.get("order_no"),
            "quota_before": before_recharge,
            "quota_after": after_recharge,
            "credit_quota": expected_credit,
        }
        flow_summaries["recharge"] = recharge_summary

        self_app = create_self_app(merchant, prefix)
        self_spec = create_self_spec(merchant, self_app.app_id)
        before_self_issue = get_issue_quota_balance(merchant)
        self_batch = issue_batch(merchant, self_app.app_id, self_spec, prefix)
        after_self_issue = get_issue_quota_balance(merchant)
        self_issue_cost = int(self_batch.preview.get("total_cost") or self_batch.count)
        assert_quota_delta(before_self_issue, after_self_issue, -self_issue_cost, "self-owned issue debit")
        self_cards = fetch_batch_cards(merchant, self_batch)
        self_verify = verify_one_card(
            config.api_base_url,
            self_app.app_id,
            self_batch.codes[0],
            app_secret=self_app.app_secret,
            rsa_public_key=self_app.rsa_public_key,
        ) if self_batch.codes else {"success": False, "card_code": None}
        self_flow_summary = _report_flow_summary(self_batch, self_spec, self_cards, self_verify)
        flow_summaries["self_owned"] = self_flow_summary

        ui_seed_spec = create_merchant_ui_seed_spec(merchant, self_app.app_id, prefix)
        before_ui_seed_issue = get_issue_quota_balance(merchant)
        ui_seed_batch = issue_batch(merchant, self_app.app_id, ui_seed_spec, prefix)
        after_ui_seed_issue = get_issue_quota_balance(merchant)
        ui_seed_issue_cost = int(ui_seed_batch.preview.get("total_cost") or ui_seed_batch.count)
        assert_quota_delta(before_ui_seed_issue, after_ui_seed_issue, -ui_seed_issue_cost, "browser UI seed issue debit")
        ui_seed_cards = fetch_batch_cards(merchant, ui_seed_batch)
        flow_summaries["browser_ui_seed"] = _report_flow_summary(
            ui_seed_batch,
            ui_seed_spec,
            ui_seed_cards,
            {"success": True, "purpose": "browser-visible batch page seed"},
        )

        admin_app, admin_spec = create_admin_app_and_spec(admin, prefix)
        authorize_app_to_merchant(admin, merchant.user_id, admin_app.app_id)
        before_authorized_issue = get_issue_quota_balance(merchant)
        authorized_batch = issue_batch(merchant, admin_app.app_id, admin_spec, prefix)
        after_authorized_issue = get_issue_quota_balance(merchant)
        authorized_issue_cost = int(authorized_batch.preview.get("total_cost") or authorized_batch.count)
        assert_quota_delta(
            before_authorized_issue,
            after_authorized_issue,
            -authorized_issue_cost,
            "authorized issue debit",
        )
        authorized_cards = fetch_batch_cards(merchant, authorized_batch)
        authorized_verify = verify_one_card(
            config.api_base_url,
            admin_app.app_id,
            authorized_batch.codes[0],
            app_secret=admin_app.app_secret,
            rsa_public_key=admin_app.rsa_public_key,
        ) if authorized_batch.codes else {"success": False, "card_code": None}
        authorized_flow_summary = _report_flow_summary(authorized_batch, admin_spec, authorized_cards, authorized_verify)
        flow_summaries["authorized"] = authorized_flow_summary

        boundaries = verify_permission_boundaries(admin, merchant, prefix)
        flow_summaries["permission_boundaries"] = boundaries
        browser_results = run_browser_sweep(
            config.browser_base_url,
            artifact_dir,
            admin_auth.as_browser_storage(),
            merchant.auth.as_browser_storage(),
            context={"adminBatchAppId": admin_app.app_id, "merchantBatchAppId": self_app.app_id},
        )
        for result in browser_results:
            for finding in evaluate_browser_result(result):
                if result.get("role"):
                    finding["role"] = result.get("role")
                browser_findings.append(finding)
        visual_regression = run_visual_regression(browser_results, artifact_dir)
        browser_findings.extend(visual_regression["findings"])
        flow_summaries["browser_sweep"] = {
            "results": len(browser_results),
            "summary": summarize_browser_sweep(browser_results, browser_findings),
            "findings": browser_findings,
        }
        flow_summaries["visual_regression"] = visual_regression
        blocking_visual = _blocking_visual_findings(visual_regression["findings"])
        if blocking_visual:
            raise QASafetyError(f"Blocking visual regression findings detected: {len(blocking_visual)}")
        blocking_browser = _blocking_browser_findings(browser_findings)
        if blocking_browser:
            raise QASafetyError(f"Blocking browser findings detected: {len(blocking_browser)}")
    except Exception as error:
        flow_error = error
        flow_summaries["flow_error"] = sanitize_report_string(str(error))
    finally:
        try:
            restore_summary = restore_payment_snapshot(admin, payment_snapshot, prefix) or {}
            payment_restore_status = {"restored": True, **restore_summary}
        except Exception as error:
            payment_restore_status = {"restored": False, "error": sanitize_report_string(str(error))}
        try:
            cleanup_status = cleanup_run(admin, prefix)
        except Exception as error:
            cleanup_status = {"error": sanitize_report_string(str(error))}
        flow_summaries["cleanup"] = {
            "payment_restore": payment_restore_status,
            "resources": cleanup_status,
        }
        if flow_summaries.get("deployment_health"):
            report.add_section("Deployment And Health", [flow_summaries["deployment_health"]])
        if flow_summaries.get("browser_sweep"):
            report.add_section("Browser Sweep", [flow_summaries["browser_sweep"]])
        if flow_summaries.get("visual_regression"):
            report.add_section("Visual Regression", [flow_summaries["visual_regression"]])
        if flow_summaries.get("recharge"):
            report.add_section("Recharge Flow", [flow_summaries["recharge"]])
        if flow_summaries.get("self_owned"):
            report.add_section("Self Owned Flow", [flow_summaries["self_owned"]])
        if flow_summaries.get("browser_ui_seed"):
            report.add_section("Browser UI Seed Flow", [flow_summaries["browser_ui_seed"]])
        if flow_summaries.get("authorized"):
            report.add_section("Authorized Flow", [flow_summaries["authorized"]])
        if flow_summaries.get("permission_boundaries"):
            report.add_section("Permission Boundaries", [flow_summaries["permission_boundaries"]])
        if flow_summaries.get("flow_error"):
            report.add_section("Flow Error", [flow_summaries["flow_error"]])
        report.add_section("Cleanup And Restore", [payment_restore_status, cleanup_status])
        add_analysis_sections(
            report,
            derive_product_findings(browser_findings, flow_summaries),
            derive_engineering_findings(browser_findings, flow_summaries),
            product_assessed=bool(browser_results),
        )
        report_path = report.write()
    if flow_error is not None:
        raise QASafetyError(f"Production E2E flow failed; sanitized report written to {report_path}") from flow_error
    if payment_restore_status.get("error") or cleanup_status.get("error"):
        raise QASafetyError(f"Production E2E cleanup/restore had errors; sanitized report written to {report_path}")
    return report_path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Production E2E browser QA harness")
    parser.add_argument("--preflight", action="store_true", help="Run read-only environment and route checks")
    parser.add_argument("--run-production", action="store_true", help="Run production E2E business flow")
    parser.add_argument("--cleanup-prefix", help="Safely clean resources owned by an exact QA run prefix")
    args = parser.parse_args(argv)

    selected = sum(bool(value) for value in (args.preflight, args.run_production, args.cleanup_prefix))
    if selected > 1:
        raise QASafetyError("Choose only one mode")
    if args.preflight:
        result = run_preflight(QAConfig.from_env(require_confirmation=False))
        print(_format_report_line({"preflight": "ok", **result}))
        return 0
    if args.run_production:
        report_path = run_production_flow(QAConfig.from_env(require_confirmation=True))
        print(f"Production E2E report: {report_path}")
        return 0
    if args.cleanup_prefix:
        prefix = validate_run_prefix(args.cleanup_prefix)
        config = QAConfig.from_env(require_confirmation=True)
        admin_auth = login(config.api_base_url, config.admin_username, config.admin_password)
        admin = APIClient(config.api_base_url, admin_auth)
        result = cleanup_run(admin, prefix)
        print(_format_report_line({"cleanup": result}))
        return 0
    print("Production E2E browser QA harness ready. Choose --preflight, --run-production, or --cleanup-prefix.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
