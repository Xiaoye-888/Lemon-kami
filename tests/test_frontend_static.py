from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_version_update_preview_embeds_download_url_in_download_button():
    source = (PROJECT_ROOT / "admin/src/views/AppVersions.vue").read_text(encoding="utf-8")

    assert "{{ form.download_url }}" not in source
    assert ':href="form.download_url"' in source
    assert 'target="_blank"' in source
    assert 'rel="noopener noreferrer"' in source


def test_app_versions_page_is_windows_only_release_console():
    source = (PROJECT_ROOT / "admin/src/views/AppVersions.vue").read_text(encoding="utf-8")

    assert "WINDOWS_PLATFORM = 'windows'" in source
    assert 'class="control locked"' in source
    assert ">Windows<" in source
    assert 'v-model="platformFilter"' not in source
    assert 'label="全部平台"' not in source
    assert 'label="通用"' not in source
    assert 'label="macOS"' not in source
    assert 'label="Android"' not in source
    assert "platformText" not in source


def test_app_versions_new_version_defaults_are_generated_from_app_and_date():
    source = (PROJECT_ROOT / "admin/src/views/AppVersions.vue").read_text(encoding="utf-8")

    assert "function formatLocalDate" in source
    assert "function defaultUpdateTitle" in source
    assert "selectedAppName" in source
    assert "formatLocalDate()" in source
    assert "${selectedAppName.value} ${formatLocalDate()} ${DEFAULT_TITLE_SUFFIX}" in source
    assert "更新内容" in source
    assert "const nextVersionCode = computed" in source
    next_version_code_source = source.split("const nextVersionCode = computed", 1)[1][:800]
    assert "+ 1" in next_version_code_source
    assert "form.title = defaultUpdateTitle()" in source
    assert "form.version_code = nextVersionCode.value" in source


def test_app_versions_uses_windows_payload_and_windows_query():
    source = (PROJECT_ROOT / "admin/src/views/AppVersions.vue").read_text(encoding="utf-8")

    assert "function versionPayloadFromForm" in source
    assert "function versionPayloadFromVersion" in source
    payload_source = source.split("function versionPayloadFromForm", 1)[1][:1200]
    assert "platform: WINDOWS_PLATFORM" in payload_source
    assert "getAppVersions(selectedAppId.value, { platform: WINDOWS_PLATFORM })" in source
    assert "platform: form.platform" not in source


def test_app_versions_row_actions_write_immediately_and_guard_duplicates():
    source = (PROJECT_ROOT / "admin/src/views/AppVersions.vue").read_text(encoding="utf-8")

    assert "const rowActionLoading = ref('')" in source
    assert ':loading="rowActionLoading === `publish:${row.id}`"' in source
    assert ':loading="rowActionLoading === `archive:${row.id}`"' in source

    publish_source = source.split("async function publishDraft", 1)[1].split("async function archiveVersion", 1)[0]
    assert "versionPayloadFromVersion(row, 'published')" in publish_source
    assert "updateAppVersion(selectedAppId.value, row.id, payload)" in publish_source
    assert "confirmLowVersionPublish(payload, row.id)" in publish_source
    assert "rowActionLoading.value = `publish:${row.id}`" in publish_source
    assert "openEdit(row)" not in publish_source

    archive_source = source.split("async function archiveVersion", 1)[1].split("const copyUpdateCheckUrl", 1)[0]
    assert "versionPayloadFromVersion(row, 'archived')" in archive_source
    assert "updateAppVersion(selectedAppId.value, row.id, payload)" in archive_source
    assert "rowActionLoading.value = `archive:${row.id}`" in archive_source
    assert "openEdit(row)" not in archive_source


def test_app_versions_copy_update_check_url_includes_windows_and_current_code():
    source = (PROJECT_ROOT / "admin/src/views/AppVersions.vue").read_text(encoding="utf-8")

    copy_source = source.split("const copyUpdateCheckUrl", 1)[1]
    assert "new URLSearchParams" in copy_source
    assert "platform: WINDOWS_PLATFORM" in copy_source
    assert "current_version_code: String(currentVersion.value?.version_code || 0)" in copy_source


def test_app_versions_has_release_workspace_and_copy_actions():
    source = (PROJECT_ROOT / "admin/src/views/AppVersions.vue").read_text(encoding="utf-8")

    assert "currentVersion" in source
    assert "effectiveState" in source
    assert "复制检查接口" in source
    assert '@click="copyUpdateCheckUrl"' in source
    assert "copyTextToClipboard" in source
    assert "copyAsNewVersion" in source
    assert "复制新版本" in source
    assert '@click.stop="copyAsNewVersion(row, row.status === \'archived\')"' in source
    assert "复制为回退包" in source
    assert "客户端判断" in source
    assert "新增版本" in source
    assert '@click.stop="publishDraft(row)"' in source
    assert '@click.stop="archiveVersion(row)"' in source
    assert "弹窗预览" in source


def test_devices_page_defaults_to_all_apps_with_keyword_search():
    source = (PROJECT_ROOT / "admin/src/views/Devices.vue").read_text(encoding="utf-8")

    assert 'label="全部应用"' in source
    assert 'v-model="queryParams.keyword"' in source
    assert "搜索卡密/设备" in source
    assert "请先选择应用" not in source
    assert "apps.value[0].app_id" not in source
    assert "if (!queryParams.app_id)" not in source


def test_application_menu_groups_info_notice_and_versions():
    layout = (PROJECT_ROOT / "admin/src/layouts/MainLayout.vue").read_text(encoding="utf-8")
    router = (PROJECT_ROOT / "admin/src/router/index.js").read_text(encoding="utf-8")

    assert '<el-sub-menu index="/apps">' in layout
    assert '<span>应用管理</span>' in layout
    assert 'index="/apps/info"' in layout
    assert '<span>应用信息</span>' in layout
    assert 'index="/apps/notices"' in layout
    assert '<span>公告管理</span>' in layout
    assert 'index="/apps/versions"' in layout
    assert '<span>版本更新</span>' in layout
    assert "path: 'apps/info'" in router
    assert "path: 'apps/notices'" in router
    assert "path: 'apps/versions'" in router


def test_notice_and_version_pages_are_not_configured_in_app_interfaces():
    interfaces_source = (PROJECT_ROOT / "admin/src/views/AppInterfaces.vue").read_text(encoding="utf-8")

    assert "最新版本" not in interfaces_source
    assert "更新说明" not in interfaces_source
    assert "强制更新" not in interfaces_source
    assert "更新/下载外链" not in interfaces_source
    assert "兼容下载地址" not in interfaces_source
    assert "公告标题" not in interfaces_source
    assert "应用公告" not in interfaces_source
