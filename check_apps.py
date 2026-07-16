import os

import requests


BASE_URL = os.getenv("LEMON_API_BASE_URL", "http://localhost:8000/api/v1")
TOKEN = os.getenv("LEMON_ADMIN_TOKEN")


def main():
    if not TOKEN:
        raise SystemExit("Please set LEMON_ADMIN_TOKEN before running this script.")

    response = requests.get(
        f"{BASE_URL}/admin/apps",
        params={"token": TOKEN},
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    apps = payload.get("data", [])

    print(f"Total apps: {len(apps)}")
    for index, app in enumerate(apps, start=1):
        has_key = bool(app.get("rsa_public_key"))
        print(f"{index}. {app.get('name')} (ID: {app.get('app_id')})")
        print(f"   RSA public key: {'yes' if has_key else 'no'}")
        if has_key:
            print(f"   Public key length: {len(app['rsa_public_key'])} chars")


if __name__ == "__main__":
    main()
