import argparse
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


def build_smoke_targets(base_url: str) -> list[dict[str, str]]:
    normalized = base_url.rstrip("/")
    return [
        {"name": "frontend", "url": f"{normalized}/", "expect": "html"},
        {"name": "health", "url": f"{normalized}/health", "expect": "json"},
        {"name": "login_key", "url": f"{normalized}/api/v1/admin/login/public-key", "expect": "json"},
    ]


def check_target(target: dict[str, str], timeout: int = 10) -> dict[str, object]:
    request = Request(target["url"], headers={"User-Agent": "lemon-kami-smoke/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(1024 * 1024)
            status = response.status
            content_type = response.headers.get("content-type", "")
    except HTTPError as error:
        return {"name": target["name"], "ok": False, "status": error.code, "error": str(error)}
    except URLError as error:
        return {"name": target["name"], "ok": False, "status": None, "error": str(error.reason)}

    ok = 200 <= status < 300
    if target["expect"] == "json":
        try:
            json.loads(body.decode("utf-8"))
        except Exception as error:
            ok = False
            return {
                "name": target["name"],
                "ok": False,
                "status": status,
                "content_type": content_type,
                "error": f"invalid json: {error}",
            }
    elif target["expect"] == "html":
        ok = ok and b"<html" in body.lower()

    return {
        "name": target["name"],
        "ok": ok,
        "status": status,
        "content_type": content_type,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Lemon Kami deployment smoke checks.")
    parser.add_argument("--base-url", default="http://localhost", help="Public site base URL.")
    parser.add_argument("--timeout", type=int, default=10, help="Request timeout in seconds.")
    args = parser.parse_args()

    results = [check_target(target, timeout=args.timeout) for target in build_smoke_targets(args.base_url)]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if all(result["ok"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
