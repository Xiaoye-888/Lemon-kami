from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_app_config_preview_embeds_update_url_in_download_button():
    source = (PROJECT_ROOT / "admin/src/views/AppInterfaces.vue").read_text(encoding="utf-8")

    assert 'class="client-preview__url"' not in source
    assert "{{ appConfigPreview.updateUrl }}" not in source
    assert ':href="appConfigPreview.updateUrl"' in source
    assert 'target="_blank"' in source
    assert 'rel="noopener noreferrer"' in source
