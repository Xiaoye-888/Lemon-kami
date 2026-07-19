from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_apps_detail_masks_app_secret_but_allows_copying_it():
    source = (ROOT / "admin/src/views/Apps.vue").read_text(encoding="utf-8")

    assert "{{ currentApp.app_secret }}" not in source
    assert "copyTextToClipboard" in source
    assert "copyAppSecret" in source
    assert "currentApp.value.app_secret" in source
