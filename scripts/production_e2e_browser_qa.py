from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


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
FORBIDDEN_REPORT_MARKERS = ("token=", "password=", "cookie=", "Authorization:", "Bearer ")
REPORT_FILENAME = "production-e2e-browser-report.md"


class QASafetyError(RuntimeError):
    pass


def build_run_prefix(now=None):
    moment = now or datetime.now()
    return f"E2E_UI_QA_{moment:%Y%m%d_%H%M%S}_"


def is_owned_by_run(value, prefix):
    return isinstance(value, str) and bool(prefix) and value.startswith(prefix)


def assert_owned_by_run(value, prefix):
    if not is_owned_by_run(value, prefix):
        raise QASafetyError(f"Refusing cleanup for non-QA resource: {value!r}")


def mask_middle(value, keep=3):
    text = str(value)
    if len(text) <= keep * 2:
        return "***"
    return f"{text[:keep]}***{text[-keep:]}"


def redact(value):
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            normalized = str(key).lower()
            if normalized in SECRET_KEYS:
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
    if result.get("body_text_length", 0) < 40:
        findings.append(_finding("P1", route, viewport, "Page body text is unexpectedly sparse"))
    if layout.get("horizontal_overflow"):
        findings.append(_finding("P2", route, viewport, "Horizontal overflow detected"))
    if layout.get("large_blank_ratio", 0) >= 0.55:
        findings.append(_finding("P2", route, viewport, "Large blank page area detected"))
    if layout.get("overwide_cards"):
        findings.append(_finding("P2", route, viewport, "Overwide cards detected"))

    return findings


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
                lines.extend(f"- {line}" for line in section_lines)
            else:
                lines.append("- No findings")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def write(self):
        content = self.render()
        for marker in FORBIDDEN_REPORT_MARKERS:
            if marker in content:
                raise QASafetyError(f"Report contains forbidden sensitive marker: {marker}")
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.artifact_dir / REPORT_FILENAME
        output_path.write_text(content, encoding="utf-8")
        return output_path


def main():
    print("Production E2E browser QA harness skeleton ready; no browser run executed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
