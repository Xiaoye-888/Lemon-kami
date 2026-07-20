from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_app_config_preview_embeds_update_url_in_download_button():
    source = (PROJECT_ROOT / "admin/src/views/AppInterfaces.vue").read_text(encoding="utf-8")

    assert 'class="client-preview__url"' not in source
    assert "{{ appConfigPreview.updateUrl }}" not in source
    assert ':href="appConfigPreview.updateUrl"' in source
    assert 'target="_blank"' in source
    assert 'rel="noopener noreferrer"' in source


def test_devices_page_defaults_to_all_apps_with_keyword_search():
    source = (PROJECT_ROOT / "admin/src/views/Devices.vue").read_text(encoding="utf-8")

    assert 'label="全部应用"' in source
    assert 'v-model="queryParams.keyword"' in source
    assert "搜索卡密/设备" in source
    assert "请先选择应用" not in source
    assert "apps.value[0].app_id" not in source
    assert "if (!queryParams.app_id)" not in source
