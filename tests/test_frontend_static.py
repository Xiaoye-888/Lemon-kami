import re
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


def test_app_versions_uses_windows_payload_and_windows_compatible_source_rows():
    source = (PROJECT_ROOT / "admin/src/views/AppVersions.vue").read_text(encoding="utf-8")

    assert "function versionPayloadFromForm" in source
    assert "function versionPayloadFromVersion" in source
    payload_source = source.split("function versionPayloadFromForm", 1)[1][:1200]
    assert "platform: WINDOWS_PLATFORM" in payload_source
    assert "WINDOWS_COMPATIBLE_PLATFORMS" in source
    assert "function isWindowsCompatibleVersion" in source
    assert "getAppVersions(selectedAppId.value)" in source
    assert "versions.value = (res.data?.items || []).filter(isWindowsCompatibleVersion)" in source
    assert "getAppVersions(selectedAppId.value, { platform: WINDOWS_PLATFORM })" not in source
    assert "platform: form.platform" not in source


def test_app_versions_workspace_publish_requires_explicit_windows_confirmation():
    source = (PROJECT_ROOT / "admin/src/views/AppVersions.vue").read_text(encoding="utf-8")

    assert "保存草稿" in source
    assert "检查并发布" in source
    assert "@click=\"saveVersion('draft')\"" in source
    assert "@click=\"saveVersion('published')\"" in source
    assert "const pendingSaveStatus = ref('')" in source
    assert "async function confirmDialogPublish(payload)" in source
    assert "发布确认明细" in source
    assert "应用：" in source
    assert "平台：Windows" in source
    assert "发布状态：" in source
    assert "更新说明：" in source
    assert "地址类型：" in source
    assert "按钮文案：" in source
    assert "客户端弹窗：" in source

    save_source = source.split("async function saveVersion", 1)[1].split("async function publishDraft", 1)[0]
    assert "if (!(await confirmDialogPublish(payload))) return" in save_source
    assert "createAppVersion(selectedAppId.value, payload)" in save_source
    assert "updateAppVersion(selectedAppId.value, editingVersion.value.id, payload)" in save_source

    publish_source = source.split("async function publishDraft", 1)[1].split("async function archiveVersion", 1)[0]
    assert "if (!(await confirmDialogPublish(payload))) return" in publish_source


def test_app_versions_current_effective_order_matches_sdk_release_selection():
    source = (PROJECT_ROOT / "admin/src/views/AppVersions.vue").read_text(encoding="utf-8")

    assert "function compareSdkEffectiveVersions(left, right)" in source
    comparator_source = source.split("function compareSdkEffectiveVersions", 1)[1].split("const publishedVersions", 1)[0]
    assert "Number(right.version_code || 0) - Number(left.version_code || 0)" in comparator_source
    assert "String(right.published_at || '').localeCompare(String(left.published_at || ''))" in comparator_source
    assert "Number(right.id || 0) - Number(left.id || 0)" in comparator_source
    assert "String(right.id || '').localeCompare(String(left.id || ''))" not in comparator_source
    assert "updated_at" not in comparator_source

    assert "const effectivePublishedVersions = computed(() => [...publishedVersions.value].sort(compareSdkEffectiveVersions))" in source
    assert "const currentVersion = computed(() => effectivePublishedVersions.value[0] || null)" in source
    assert "const currentVersion = computed(() => publishedVersions.value[0] || null)" not in source


def test_app_versions_row_actions_write_immediately_and_guard_duplicates():
    source = (PROJECT_ROOT / "admin/src/views/AppVersions.vue").read_text(encoding="utf-8")

    assert "const rowActionLoading = ref('')" in source
    assert ':disabled="!selectedAppId || Boolean(rowActionLoading)"' in source
    assert '@click.stop="openEdit(row)"' in source
    assert '@click.stop="deleteVersion(row)"' in source
    assert "deleteAppVersion(appId, row.id)" in source
    assert "rowActionLoading.value = `delete:${row.id}`" in source
    assert "确认删除版本" in source
    assert "删除" in source
    assert "copyAsNewVersion" not in source
    assert "复制新版本" not in source
    assert "复制为回退包" not in source
    assert ':disabled="Boolean(rowActionLoading)"' in source
    assert ':disabled="!selectedAppId || saving || Boolean(rowActionLoading)"' in source
    assert ':loading="rowActionLoading === `publish:${row.id}`"' in source
    assert ':loading="rowActionLoading === `archive:${row.id}`"' in source
    assert ':loading="rowActionLoading === `delete:${row.id}`"' in source

    publish_source = source.split("async function publishDraft", 1)[1].split("async function archiveVersion", 1)[0]
    assert "const appId = selectedAppId.value" in publish_source
    assert "versionPayloadFromVersion(row, 'published')" in publish_source
    assert "updateAppVersion(appId, row.id, payload)" in publish_source
    assert "confirmLowVersionPublish(payload, row.id)" in publish_source
    assert "confirmDialogPublish(payload)" in publish_source
    assert "rowActionLoading.value = `publish:${row.id}`" in publish_source
    assert "openEdit(row)" not in publish_source

    archive_source = source.split("async function archiveVersion", 1)[1].split("onMounted", 1)[0]
    assert "const appId = selectedAppId.value" in archive_source
    assert "versionPayloadFromVersion(row, 'archived')" in archive_source
    assert "updateAppVersion(appId, row.id, payload)" in archive_source
    assert "rowActionLoading.value = `archive:${row.id}`" in archive_source
    assert "openEdit(row)" not in archive_source


def test_app_notices_can_be_deleted_with_explicit_confirmation():
    source = (PROJECT_ROOT / "admin/src/views/AppNotices.vue").read_text(encoding="utf-8")
    api_source = (PROJECT_ROOT / "admin/src/api/appContent.js").read_text(encoding="utf-8")

    assert "deleteAppNotice" in api_source
    assert "method: 'delete'" in api_source
    assert "deleteAppNotice" in source
    assert "const rowActionLoading = ref('')" in source
    assert '@click.stop="deleteNotice(row)"' in source
    assert ':loading="rowActionLoading === `delete:${row.id}`"' in source
    assert "rowActionLoading.value = `delete:${row.id}`" in source
    assert "确认删除公告" in source
    assert "deleteAppNotice(appId, row.id)" in source
    assert "公告已删除" in source


def test_app_versions_header_removes_default_title_and_copy_check_entry():
    source = (PROJECT_ROOT / "admin/src/views/AppVersions.vue").read_text(encoding="utf-8")

    header_source = source.split('class="page-header"', 1)[1].split('class="current-release"', 1)[0]
    summary_source = source.split('class="current-release"', 1)[1].split('class="workspace-grid"', 1)[0]

    assert "复制检查接口" not in header_source
    assert '@click="copyUpdateCheckUrl"' not in header_source
    assert "DocumentCopy" not in source
    assert "copyTextToClipboard" not in source
    assert "copyUpdateCheckUrl" not in source

    assert "默认标题" not in summary_source
    assert "defaultUpdateTitle()" not in summary_source
    assert "当前生效" in summary_source
    assert "建议版本编码" in summary_source
    assert "客户端判断" in summary_source


def test_admin_view_router_navigation_uses_admin_scoped_paths():
    admin_roots = "apps|kamis|end-users|logs|interfaces|devices|users"
    path_pattern = re.compile(
        rf"(?:router\.(?:push|replace)\(\s*['\"]|path:\s*[`'\"])/({admin_roots})(?:/|[`'\"]|\?)"
    )
    offenders = []
    for source_path in (PROJECT_ROOT / "admin/src/views").glob("*.vue"):
        source = source_path.read_text(encoding="utf-8")
        for match in path_pattern.finditer(source):
            offenders.append(f"{source_path.name}:{match.group(0)}")

    assert offenders == []


def test_app_versions_has_quick_publish_and_history_actions():
    source = (PROJECT_ROOT / "admin/src/views/AppVersions.vue").read_text(encoding="utf-8")

    assert "currentVersion" in source
    assert "effectiveState" in source
    assert "客户端判断" in source
    assert "新增完整版本" in source
    assert "完整版本信息" in source
    assert "createDialogVisible" in source
    assert '@click.stop="publishDraft(row)"' in source
    assert '@click.stop="archiveVersion(row)"' in source
    assert '@click.stop="deleteVersion(row)"' in source
    assert "快捷发布" in source
    assert "检查并发布" in source
    assert "弹窗预览" in source
    assert "复制新版本" not in source
    assert "复制为回退包" not in source

    assert "发布工作区" not in source
    assert ">发布版本<" not in source


def test_app_versions_release_console_is_chinese_and_directly_editable():
    source = (PROJECT_ROOT / "admin/src/views/AppVersions.vue").read_text(encoding="utf-8")

    for label in (
        'label="版本信息"',
        'label="发布状态"',
        'label="生效状态"',
        'label="标题与说明"',
        'label="发布时间"',
        'label="操作"',
    ):
        assert label in source

    for english in (
        'label="Version"',
        'label="Status"',
        'label="Effective state"',
        'label="Title / Summary"',
        'label="Actions"',
        "current_version_code &lt; latest_version_code",
    ):
        assert english not in source

    assert "客户端版本编码低于当前已发布最高编码时，将提示更新" in source
    assert "发布检查" in source
    assert "客户端弹窗预览" in source
    assert "最近发布活动" not in source
    assert "客户端判断规则" not in source
    assert "当前选择版本详情" not in source
    assert "还没有发布过 Windows 版本" in source

    history_secondary_source = source.split('class="history-secondary"', 1)[1].split('class="release-sidebar"', 1)[0]
    sidebar_source = source.split('class="release-sidebar"', 1)[1]
    assert "客户端弹窗预览" in history_secondary_source
    assert "update-preview" in history_secondary_source
    assert "客户端弹窗预览" not in sidebar_source

    workspace_source = source.split('class="release-form"', 1)[1].split('class="workspace-actions"', 1)[0]
    for binding in (
        'v-model="form.version"',
        'v-model="form.version_code"',
        'v-model="form.status"',
        'v-model="form.title"',
        'v-model="form.notes"',
        'v-model="form.button_text"',
        'v-model="form.download_url"',
        'v-model="form.url_type"',
        'v-model="form.force_update"',
    ):
        assert binding in workspace_source

    dialog_source = source.split('<el-dialog', 1)[1].split('</el-dialog>', 1)[0]
    assert "完整版本信息" in dialog_source
    assert "@click=\"saveVersion('draft')\"" in dialog_source
    assert "@click=\"saveVersion('published')\"" in dialog_source

    assert "保存草稿" in source
    assert "检查并发布" in source
    assert "@click=\"saveVersion('draft')\"" in source
    assert "@click=\"saveVersion('published')\"" in source


def test_app_versions_bottom_cards_are_bounded_to_prevent_overflow():
    source = (PROJECT_ROOT / "admin/src/views/AppVersions.vue").read_text(encoding="utf-8")

    assert 'class="history-secondary"' in source
    assert 'class="assistant-card preview-panel preview-panel--inline"' in source
    assert "recent-activity" not in source
    assert 'const recentActivities = computed' not in source
    assert "sortedVersions.value.slice(0, 3)" not in source
    assert "max-height" in source
    assert "overflow: hidden" in source
    assert "check-list" in source


def test_app_versions_desktop_columns_share_equal_height():
    source = (PROJECT_ROOT / "admin/src/views/AppVersions.vue").read_text(encoding="utf-8")

    workspace_blocks = [block.split("}", 1)[0] for block in source.split(".workspace-grid {")[1:]]
    workspace_css = next(block for block in workspace_blocks if "grid-template-columns" in block)
    assert "align-items: stretch" in workspace_css
    assert "align-items: start" not in workspace_css

    history_css = source.split(".history-panel {", 1)[1].split("}", 1)[0]
    sidebar_css = source.split(".release-sidebar {", 1)[1].split("}", 1)[0]
    draft_css = source.split(".draft-panel {", 1)[1].split("}", 1)[0]
    assert "height: 100%" in history_css
    assert "height: 100%" in sidebar_css
    assert "height: 100%" in draft_css

    desktop_media_source = source.split("@media (max-width: 1200px)", 1)[1]
    assert ".draft-panel" in desktop_media_source
    assert "height: auto" in desktop_media_source


def test_devices_page_defaults_to_all_apps_with_keyword_search():
    source = (PROJECT_ROOT / "admin/src/views/Devices.vue").read_text(encoding="utf-8")

    assert 'label="全部应用"' in source
    assert 'v-model="queryParams.keyword"' in source
    assert "搜索卡密/设备" in source
    assert "请先选择应用" not in source
    assert "apps.value[0].app_id" not in source
    assert "if (!queryParams.app_id)" not in source


def test_devices_page_uses_merchant_scoped_api_in_merchant_console():
    source = (PROJECT_ROOT / "admin/src/views/Devices.vue").read_text(encoding="utf-8")
    device_api = (PROJECT_ROOT / "admin/src/api/device.js").read_text(encoding="utf-8")

    assert "getMerchantDevices" in device_api
    assert "url: '/merchant/devices'" in device_api
    assert "useRoute" in source
    assert "isMerchantConsole" in source
    assert "getMerchantDevices(queryParams)" in source
    assert "getMerchantApps()" in source
    assert "updateMerchantDeviceRisk" in device_api
    assert "url: `/merchant/devices/${deviceId}/risk`" in device_api
    assert 'v-if="showRiskActionColumn"' in source
    assert "row?.can_manage_risk === true" in source
    assert "isMerchantConsole.value ? await updateMerchantDeviceRisk(row.id, level) : await updateDeviceRisk(row.id, level)" in source
    assert "deviceInfoText(row.device_name)" in source
    assert "deviceInfoText(row.device_model)" in source
    assert "deviceInfoText(row.device_id)" in source
    assert "等待新版SDK上报" in source


def test_devices_page_keeps_main_row_actions_and_opens_details_from_policy_text():
    source = (PROJECT_ROOT / "admin/src/views/Devices.vue").read_text(encoding="utf-8")

    assert "deviceDetailVisible" in source
    assert "selectedDeviceGroup" in source
    assert "openDeviceDetail(row)" in source
    assert "device_items" in source
    assert "设备明细" in source
    assert "每台机器" not in source
    assert "查看设备" not in source
    assert 'label="操作"' in source
    assert '@click="updateRisk(row, 0)"' in source
    assert '@click="updateRisk(row, 1)"' in source
    assert '@click="updateRisk(row, 2)"' in source
    assert "明细设备" in source
    assert "总设备" not in source
    assert "同时拉黑该设备 ID 和当前 IP" in source
    assert "设备名称" in source
    assert "设备型号" in source
    assert "设备 ID" in source
    assert "IP地址" in source
    assert "device.device_name" in source
    assert "device.device_model" in source
    assert "device.device_id" in source
    assert "device.last_ip" in source

    device_name_column = source.split('prop="device_name"', 1)[1].split('<el-table-column prop="device_model"', 1)[0]
    device_model_column = source.split('prop="device_model"', 1)[1].split('<el-table-column prop="device_id"', 1)[0]
    device_id_column = source.split('prop="device_id"', 1)[1].split('<el-table-column label="关联卡密"', 1)[0]
    policy_column = source.split('prop="machine_bind_mode_text"', 1)[1].split('<el-table-column prop="device_count"', 1)[0]
    assert '@click="openDeviceDetail(row)"' not in device_name_column
    assert '@click="openDeviceDetail(row)"' not in device_model_column
    assert '@click="openDeviceDetail(row)"' not in device_id_column
    assert '@click="openDeviceDetail(row)"' in policy_column


def test_application_menu_groups_info_notice_and_versions():
    layout = (PROJECT_ROOT / "admin/src/layouts/MainLayout.vue").read_text(encoding="utf-8")
    router = (PROJECT_ROOT / "admin/src/router/index.js").read_text(encoding="utf-8")

    assert "index: '/admin/apps'" in layout
    assert "label: '应用管理'" in layout
    assert "index: '/admin/apps/info'" in layout
    assert "label: '应用信息'" in layout
    assert "index: '/admin/apps/notices'" in layout
    assert "label: '公告管理'" in layout
    assert "index: '/admin/apps/versions'" in layout
    assert "label: '版本更新'" in layout
    assert "path: 'apps/info'" in router
    assert "path: 'apps/notices'" in router
    assert "path: 'apps/versions'" in router


def test_main_layout_uses_explicit_router_push_for_menu_selection():
    layout = (PROJECT_ROOT / "admin/src/layouts/MainLayout.vue").read_text(encoding="utf-8")

    assert ':router="true"' not in layout
    assert '@select="handleMenuSelect"' in layout
    assert "import { useRoute, useRouter } from 'vue-router'" in layout
    assert "const router = useRouter()" in layout
    assert "function handleMenuSelect(index)" in layout
    assert "router.push(index)" in layout


def test_merchant_menu_exposes_notice_and_version_management_without_admin_core_config():
    layout = (PROJECT_ROOT / "admin/src/layouts/MainLayout.vue").read_text(encoding="utf-8")
    router = (PROJECT_ROOT / "admin/src/router/index.js").read_text(encoding="utf-8")
    app_content_api = (PROJECT_ROOT / "admin/src/api/appContent.js").read_text(encoding="utf-8")

    merchant_menu = layout.split("const merchantMenuItems = [", 1)[1].split("const menuItems", 1)[0]
    merchant_routes = router.split("const merchantChildren = [", 1)[1].split("]\n\nconst legacyAdminRedirects", 1)[0]

    assert "label: '应用设置'" in merchant_menu
    assert "label: '卡密管理'" in merchant_menu
    app_settings_group = merchant_menu.split("label: '应用设置'", 1)[1].split("label: '卡密管理'", 1)[0]
    assert "children: [" in app_settings_group
    assert "index: '/merchant/apps'" in app_settings_group
    assert "label: '我的应用'" in app_settings_group
    assert "index: '/merchant/apps/notices'" in app_settings_group
    assert "label: '公告管理'" in app_settings_group
    assert "index: '/merchant/apps/versions'" in app_settings_group
    assert "label: '版本更新'" in app_settings_group
    kami_group = merchant_menu.split("label: '卡密管理'", 1)[1].split("index: '/merchant/devices'", 1)[0]
    assert "children: [" in kami_group
    assert "index: '/merchant/batches'" in kami_group
    assert "label: '批次管理'" in kami_group
    assert "index: '/merchant/cards'" in kami_group
    assert "label: '我的卡密'" in kami_group
    assert "path: 'apps/notices'" in merchant_routes
    assert "path: 'apps/versions'" in merchant_routes
    assert "AppNotices" in merchant_routes
    assert "AppVersions" in merchant_routes

    for core_admin_only in (
        "/merchant/commercial/recharge-settings",
        "/merchant/commercial/issue-pricing",
        "充值配置",
        "发卡额度配置",
        "充值订单审核",
    ):
        assert core_admin_only not in merchant_menu

    assert "isMerchantContentRoute" in app_content_api
    assert "contentBasePath" in app_content_api
    assert "`/merchant/apps/${appId}/notices`" in app_content_api
    assert "`/merchant/apps/${appId}/updates`" in app_content_api


def test_notice_and_version_pages_are_not_configured_in_app_interfaces():
    interfaces_source = (PROJECT_ROOT / "admin/src/views/AppInterfaces.vue").read_text(encoding="utf-8")

    assert "最新版本" not in interfaces_source
    assert "更新说明" not in interfaces_source
    assert "强制更新" not in interfaces_source
    assert "更新/下载外链" not in interfaces_source
    assert "兼容下载地址" not in interfaces_source
    assert "公告标题" not in interfaces_source
    assert "应用公告" not in interfaces_source


def test_commercial_shared_login_and_role_routes_are_present():
    store = (PROJECT_ROOT / "admin/src/stores/user.js").read_text(encoding="utf-8")
    router = (PROJECT_ROOT / "admin/src/router/index.js").read_text(encoding="utf-8")
    login = (PROJECT_ROOT / "admin/src/views/Login.vue").read_text(encoding="utf-8")

    assert "sharedLogin" in store
    assert "role = ref" in store
    assert "localStorage.setItem('role'" in store
    assert "res.redirect" in store
    assert "管理员 / 发卡用户共用登录" in login
    assert "使用管理员或发卡用户账号登录" in login
    assert "path: '/admin'" in router
    assert "path: '/merchant'" in router
    assert "MerchantDashboard" in router
    assert "AdminRechargeOrders" in router


def test_login_view_reports_friendly_password_error_and_bypasses_global_401_handling():
    request_source = (PROJECT_ROOT / "admin/src/utils/request.js").read_text(encoding="utf-8")
    login_source = (PROJECT_ROOT / "admin/src/views/Login.vue").read_text(encoding="utf-8")

    assert "authEndpoints" in request_source
    assert "isAuthRequest" in request_source
    assert "/auth/login" in request_source
    assert "/auth/register" in request_source
    assert "账号或密码错误，请重新输入" in login_source
    assert "getLoginErrorMessage" in login_source
    assert "extractErrorDetail" in login_source
    assert "Request failed with status code 401" not in login_source


def test_commercial_admin_and_merchant_navigation_entries_are_visible():
    layout = (PROJECT_ROOT / "admin/src/layouts/MainLayout.vue").read_text(encoding="utf-8")

    assert "商业版后台" in layout
    assert "发卡用户后台" in layout
    assert "发卡工作台" in layout
    assert "充值订单" in layout
    assert "充值配置" in layout
    assert "发卡额度流水" in layout
    assert "我的订单" in layout
    assert "批次管理" in layout
    assert "我的卡密" in layout


def test_merchant_console_uses_card_issuer_language_in_visible_shell():
    layout = (PROJECT_ROOT / "admin/src/layouts/MainLayout.vue").read_text(encoding="utf-8")
    router = (PROJECT_ROOT / "admin/src/router/index.js").read_text(encoding="utf-8")
    login = (PROJECT_ROOT / "admin/src/views/Login.vue").read_text(encoding="utf-8")
    dashboard = (PROJECT_ROOT / "admin/src/views/MerchantDashboard.vue").read_text(encoding="utf-8")

    combined = "\n".join([layout, router, login, dashboard])

    assert "\u53d1\u5361\u7528\u6237\u540e\u53f0" in layout
    assert "\u53d1\u5361\u7528\u6237" in layout
    assert "\u53d1\u5361\u5de5\u4f5c\u53f0" in router
    assert "\u53d1\u5361\u5de5\u4f5c\u53f0" in dashboard
    assert "\u5546\u6237\u63a7\u5236\u53f0" not in combined
    assert "\u5546\u6237\u8d26\u53f7" not in combined


def test_merchant_apps_interface_management_is_read_only_for_authorized_apps():
    source = (PROJECT_ROOT / "admin/src/views/MerchantApps.vue").read_text(encoding="utf-8")

    assert "canEditCurrentAppInterfaces" in source
    assert ":title=\"currentApp?.is_owned ? '接口配置' : '接口查看'\"" in source
    assert ":disabled=\"!canEditCurrentAppInterfaces\"" in source
    assert "v-if=\"canEditCurrentAppInterfaces\"" in source
    assert "授权应用只读" in source
    assert "授权应用不公开密钥" in source


def test_merchant_transactions_show_business_semantics_instead_of_raw_ids():
    merchant_transactions = (PROJECT_ROOT / "admin/src/views/MerchantTransactions.vue").read_text(encoding="utf-8")
    admin_transactions = (PROJECT_ROOT / "admin/src/views/AdminQuotaTransactions.vue").read_text(encoding="utf-8")

    for source in (merchant_transactions, admin_transactions):
        assert 'label="业务场景"' in source
        assert 'label="额度方向"' in source
        assert 'label="额度变动"' in source
        assert 'label="关联对象"' in source
        assert "display_scene" in source
        assert "display_direction" in source
        assert "display_subject" in source
        assert "openTransactionDetail" in source

    merchant_table = merchant_transactions.split("<el-table", 1)[1].split("</el-table>", 1)[0]
    for raw_column in ('label="流水号"', 'label="类型"', 'label="额度类型"', 'label="业务单号"'):
        assert raw_column not in merchant_table


def test_merchant_batches_exposes_grouped_specs_and_beijing_time_rendering():
    source = (PROJECT_ROOT / "admin/src/views/MerchantBatches.vue").read_text(encoding="utf-8")

    for token in (
        "specGroupTab",
        "commonSpecs.length",
        "customSpecs.length",
        "SPEC_GROUP_OPTIONS",
        "TYPE_OPTIONS",
        "AUTHORIZATION_OWNER_OPTIONS",
        "USER_BIND_MODE_OPTIONS",
        "TIME_UNIT_OPTIONS",
        "getSpecGroupText",
        "getTypeText",
        "getMachineBindModeText",
        "getAuthorizationOwnerText",
        "getUserBindModeText",
        "getValidityText",
        "formatBeijingTime(row.created_at)",
    ):
        assert token in source

    assert "常用规格" in source
    assert "自定义规格" in source
    assert "规格分组" in source
    assert "授权归属" in source
    assert "编辑模式仅允许调整规格分组、状态、排序和备注" in source


def test_merchant_batches_loads_apps_from_paginated_response_and_keeps_quota_optional():
    source = (PROJECT_ROOT / "admin/src/views/MerchantBatches.vue").read_text(encoding="utf-8")
    load_apps = source.split("async function loadApps()", 1)[1].split("async function hydrateRouteDetail()", 1)[0]
    load_all = source.split("async function loadAll()", 1)[1].split("async function handleAppChange()", 1)[0]

    assert "apps.value = responseItems(res)" in load_apps
    assert "apps.value = res.data || []" not in load_apps
    assert "if (routeAppId) {" in load_apps
    assert "apps.value.some((app) => app.app_id === routeAppId)" not in load_apps
    assert "async function loadQuotaSafely()" in source
    assert "await Promise.all([loadQuotaSafely(), loadApps()])" in load_all
    assert "await loadQuota()" not in load_all
    assert "const routeAppId = route.query.app_id ? String(route.query.app_id) : ''" in load_all
    assert load_all.count("queryParams.app_id = routeAppId") >= 2
    assert load_all.index("queryParams.app_id = routeAppId") < load_all.index("await Promise.all([loadQuotaSafely(), loadApps()])")
    assert load_all.rindex("queryParams.app_id = routeAppId") < load_all.index("await loadSpecs()")


def test_main_layout_imports_every_menu_icon_it_uses():
    source = (PROJECT_ROOT / "admin/src/layouts/MainLayout.vue").read_text(encoding="utf-8")
    import_match = re.search(
        r"import\s+\{(?P<body>.*?)\}\s+from\s+'@element-plus/icons-vue'",
        source,
        re.S,
    )
    assert import_match is not None
    imported_icons = set(re.findall(r"\b[A-Z][A-Za-z0-9_]*\b", import_match.group("body")))
    menu_source = source.split("const adminMenuItems", 1)[1].split("const menuItems", 1)[0]
    used_icons = set(re.findall(r"icon:\s*([A-Z][A-Za-z0-9_]*)", menu_source))

    assert used_icons <= imported_icons


def test_commercial_recharge_pages_expose_order_review_and_upload_flow():
    admin_orders = (PROJECT_ROOT / "admin/src/views/AdminRechargeOrders.vue").read_text(encoding="utf-8")
    admin_settings = (PROJECT_ROOT / "admin/src/views/AdminRechargeSettings.vue").read_text(encoding="utf-8")
    merchant_recharge = (PROJECT_ROOT / "admin/src/views/MerchantRecharge.vue").read_text(encoding="utf-8")
    commercial_api = (PROJECT_ROOT / "admin/src/api/commercial.js").read_text(encoding="utf-8")
    merchant_api = (PROJECT_ROOT / "admin/src/api/merchant.js").read_text(encoding="utf-8")

    assert "approveRechargeOrder" in admin_orders
    assert "rejectRechargeOrder" in admin_orders
    assert "pending_review" in admin_orders
    assert "支付凭证" in admin_orders
    assert "savePaymentChannelWithUpload" in commercial_api
    assert "deletePaymentChannelQrCode" in commercial_api
    assert "savePaymentChannelWithUpload" in admin_settings
    assert "deletePaymentChannelQrCode" in admin_settings
    assert "handleDeleteQrCode" in admin_settings
    assert "ElMessageBox" in admin_settings
    assert "删除二维码" in admin_settings
    assert "二维码地址" not in admin_settings
    assert 'v-model="channelForm.qr_code_url"' not in admin_settings
    assert "payload.append('qr_code_url'" not in admin_settings
    assert "qr_code_file" in admin_settings
    assert "saveRechargeOption" in admin_settings
    assert "saveBonusRule" in admin_settings
    assert "createMerchantRechargeOrderUpload" in merchant_api
    assert "createMerchantRechargeOrderUpload" in merchant_recharge
    assert "paymentChannels" in merchant_recharge
    assert "FormData" in merchant_recharge
    assert "proof_file" in merchant_recharge
    assert "FileReader" not in merchant_recharge
    assert "proof_image_data_url" not in merchant_recharge
    assert 'type="file"' in merchant_recharge
    assert "customPreview" in merchant_recharge


def test_account_routes_use_shared_profile_and_password_pages():
    router = (PROJECT_ROOT / "admin/src/router/index.js").read_text(encoding="utf-8")
    profile_view_path = PROJECT_ROOT / "admin/src/views/AccountProfile.vue"
    password_view_path = PROJECT_ROOT / "admin/src/views/AccountPassword.vue"

    assert profile_view_path.exists()
    assert password_view_path.exists()

    admin_routes = router.split("const adminChildren = [", 1)[1].split("]\n\nconst merchantChildren", 1)[0]
    merchant_routes = router.split("const merchantChildren = [", 1)[1].split("]\n\nconst legacyAdminRedirects", 1)[0]

    for routes_block in (admin_routes, merchant_routes):
        account_route = re.search(r"\{\s*path:\s*'account'.*?\}\n\s*\]", routes_block, re.S)
        assert account_route is not None
        account_block = account_route.group(0)
        assert "AccountProfile.vue" in account_block
        assert "AccountPassword.vue" in account_block
        assert "MerchantAccount.vue" not in account_block
        assert "path: 'profile'" in account_block
        assert "path: 'password'" in account_block

    profile_view = profile_view_path.read_text(encoding="utf-8")
    password_view = password_view_path.read_text(encoding="utf-8")
    assert "getCurrentAccountProfile" in profile_view
    assert "updateCurrentAccountProfile" in profile_view
    assert "uploadCurrentAccountAvatar" in profile_view
    assert "openEditDialog" in profile_view
    assert "handleAvatarUpload" in profile_view
    assert "资料编辑" in profile_view
    assert "基本信息" in profile_view
    assert "安全设置" not in profile_view
    assert "原密码" not in profile_view
    assert "新密码" not in profile_view
    assert "updateCurrentAccountPassword" in password_view
    assert "原密码" in password_view
    assert "新密码" in password_view
    assert "确认新密码" in password_view
    assert "上传头像" not in password_view
    assert "基本信息" not in password_view
    assert "安全设置" not in password_view


def test_merchant_recharge_channel_radios_use_value_prop():
    merchant_recharge = (PROJECT_ROOT / "admin/src/views/MerchantRecharge.vue").read_text(encoding="utf-8")

    assert ':value="item.channel"' in merchant_recharge
    assert ':label="item.channel"' not in merchant_recharge


def test_merchant_recharge_layout_places_amount_left_and_payment_right():
    merchant_recharge = (PROJECT_ROOT / "admin/src/views/MerchantRecharge.vue").read_text(encoding="utf-8")

    assert 'class="panel amount-panel"' in merchant_recharge
    assert 'class="panel payment-panel"' in merchant_recharge
    assert merchant_recharge.index('class="panel amount-panel"') < merchant_recharge.index('class="panel payment-panel"')
    assert "grid-template-columns: minmax(520px, 680px) minmax(340px, 420px)" in merchant_recharge
    assert "grid-template-columns: repeat(auto-fill, minmax(132px, 160px))" in merchant_recharge
    assert "justify-content: start" in merchant_recharge
    assert "minmax(0, 1fr)" not in merchant_recharge.split(".recharge-grid", 1)[1].split("}", 1)[0]

def test_account_profile_view_formats_visible_time_columns():
    merchant_account = (PROJECT_ROOT / "admin/src/views/AccountProfile.vue").read_text(encoding="utf-8")
    merchant_dashboard = (PROJECT_ROOT / "admin/src/views/MerchantDashboard.vue").read_text(encoding="utf-8")
    merchant_orders = (PROJECT_ROOT / "admin/src/views/MerchantOrders.vue").read_text(encoding="utf-8")
    merchant_transactions = (PROJECT_ROOT / "admin/src/views/MerchantTransactions.vue").read_text(encoding="utf-8")
    merchant_cards = (PROJECT_ROOT / "admin/src/views/MerchantCards.vue").read_text(encoding="utf-8")

    assert "formatBeijingTime" in merchant_account
    assert "formatOptionalTime" in merchant_account
    assert "{{ formatBeijingTime(profile.created_at) }}" in merchant_account
    assert "{{ formatOptionalTime(profile.last_login) }}" in merchant_account

    for source in (merchant_dashboard, merchant_orders, merchant_transactions, merchant_cards):
        assert "formatBeijingTime" in source

    assert "formatOptionalTime" in merchant_orders
    assert "formatOptionalTime" in merchant_cards
    assert "profile.created_at || '-'" not in merchant_account
    assert "profile.last_login || '-'" not in merchant_account
    assert "安全设置" not in merchant_account
    assert "uploadCurrentAccountAvatar" in merchant_account


def test_merchant_cards_render_chinese_type_and_status_tags():
    merchant_cards = (PROJECT_ROOT / "admin/src/views/MerchantCards.vue").read_text(encoding="utf-8")

    assert 'label="类型" width="120"' in merchant_cards
    assert 'label="状态" width="100"' in merchant_cards
    assert '{{ getTypeText(row.kami_type) }}' in merchant_cards
    assert 'getKamiStatusText(row)' in merchant_cards
    assert 'getKamiStatusType(row)' in merchant_cards
    assert 'prop="kami_type" label="类型" width="100" />' not in merchant_cards
    assert 'prop="status" label="状态" width="100" />' not in merchant_cards


def test_merchant_time_formatter_calls_have_script_bindings():
    offenders = []
    for source_path in sorted((PROJECT_ROOT / "admin/src/views").glob("Merchant*.vue")):
        source = source_path.read_text(encoding="utf-8")
        if "formatBeijingTime(" in source and "from '../utils/datetime'" not in source:
            offenders.append(f"{source_path.name}: missing formatBeijingTime import")
        if "formatOptionalTime(" in source and not re.search(r"\b(?:const|function)\s+formatOptionalTime\b", source):
            offenders.append(f"{source_path.name}: missing formatOptionalTime binding")

    assert offenders == []


def test_merchant_apps_create_flow_uses_dialog_instead_of_inline_input():
    merchant_apps = (PROJECT_ROOT / "admin/src/views/MerchantApps.vue").read_text(encoding="utf-8")

    assert "<el-dialog" in merchant_apps
    assert "createDialogVisible" in merchant_apps
    assert "createResultVisible" in merchant_apps
    assert "createForm" in merchant_apps
    assert "@click=\"openCreateDialog\"" in merchant_apps
    assert "handleCreateApp" in merchant_apps
    toolbar_source = merchant_apps.split('class="page-toolbar"', 1)[1].split("</div>", 2)[0]
    assert 'placeholder="\u5e94\u7528\u540d\u79f0"' not in toolbar_source
    assert "newAppName" not in merchant_apps

def test_merchant_apps_expose_self_owned_actions_and_interface_management():
    merchant_apps = (PROJECT_ROOT / "admin/src/views/MerchantApps.vue").read_text(encoding="utf-8")
    merchant_api = (PROJECT_ROOT / "admin/src/api/merchant.js").read_text(encoding="utf-8")

    for token in (
        "getMerchantAppDetail",
        "updateMerchantApp",
        "deleteMerchantApp",
        "getMerchantAppInterfaces",
        "updateMerchantAppInterface",
    ):
        assert token in merchant_api

    for token in (
        "detailDialogVisible",
        "editDialogVisible",
        "deleteDialogVisible",
        "interfacesDialogVisible",
        "interfaceConfigDialogVisible",
        "showEditDialog",
        "handleUpdateApp",
        "handleDeleteApp",
        "openInterfacesDialog",
        "saveInterfaceConfig",
    ):
        assert token in merchant_apps

    assert 'v-if="row.is_owned"' in merchant_apps
    assert 'label="操作" width="260" fixed="right" align="left"' in merchant_apps
    assert "接口列表" in merchant_apps
    assert "改名" in merchant_apps
    assert "删除" in merchant_apps
    assert "规格批次" not in merchant_apps
    assert "goBatches(row)" not in merchant_apps
    assert "display: inline-flex" in merchant_apps
    assert "justify-content: flex-start" in merchant_apps
    assert "white-space: nowrap" in merchant_apps


def test_merchant_app_detail_masks_secret_and_public_key_with_copy_controls():
    merchant_apps = (PROJECT_ROOT / "admin/src/views/MerchantApps.vue").read_text(encoding="utf-8")
    detail_dialog = merchant_apps.split('v-model="detailDialogVisible"', 1)[1].split("</el-dialog>", 1)[0]

    assert "maskedAppSecret" in merchant_apps
    assert "maskedRsaPublicKey" in merchant_apps
    assert "copyAppSecret" in merchant_apps
    assert "copyRsaPublicKey" in merchant_apps
    assert "copyTextToClipboard" in merchant_apps
    assert 'aria-label="复制 App Secret"' in detail_dialog
    assert 'aria-label="复制 RSA 公钥"' in detail_dialog
    assert "{{ maskedAppSecret }}" in detail_dialog
    assert "{{ maskedRsaPublicKey }}" in detail_dialog
    assert "{{ detailApp.is_owned ? detailApp.app_secret" not in detail_dialog
    assert "{{ detailApp.is_owned ? detailApp.rsa_public_key" not in detail_dialog


def test_merchant_app_interface_config_uses_per_interface_schema_not_generic_quota_expiry():
    merchant_apps = (PROJECT_ROOT / "admin/src/views/MerchantApps.vue").read_text(encoding="utf-8")

    for token in (
        "interfaceConfigSchemas",
        "currentInterfaceSchema",
        "schemaDefaults",
        "allow_redeem",
        "bind_user_on_redeem",
        "signature_required",
        "ip_lock_enabled",
        "heartbeat_timeout_seconds",
        "max_unbind_count",
        "sdk.notice",
        "sdk.update_check",
        "max_notice_length",
        "min_supported_version_code",
    ):
        assert token in merchant_apps

    assert "允许卡密充值" in merchant_apps
    assert "签名校验" in merchant_apps
    assert "心跳超时秒数" in merchant_apps
    assert "最大解绑次数" in merchant_apps
    assert "公告最大长度" in merchant_apps
    assert "最低支持版本编码" in merchant_apps

    dialog_source = merchant_apps.split('v-model="interfaceConfigDialogVisible"', 1)[1].split("</el-dialog>", 1)[0]
    assert "额度限制" not in dialog_source
    assert "过期时间" not in dialog_source
    assert "配置 JSON" not in dialog_source


def test_merchant_batches_exposes_spec_first_workbench_and_scoped_apis():
    merchant_api = (PROJECT_ROOT / "admin/src/api/merchant.js").read_text(encoding="utf-8")
    merchant_batches = (PROJECT_ROOT / "admin/src/views/MerchantBatches.vue").read_text(encoding="utf-8")

    for api_name in (
        "getMerchantDashboard",
        "createMerchantAppSpec",
        "updateMerchantAppSpec",
        "deleteMerchantAppSpec",
        "getMerchantSpecBatches",
        "getMerchantSpecKamis",
        "getMerchantBatchKamis",
        "updateMerchantBatch",
        "deleteMerchantBatch",
        "appendMerchantBatchKamis",
    ):
        assert api_name in merchant_api

    for view_token in (
        "admin-isomorphic-batch-workbench",
        "viewMode === 'list'",
        "yz-clean-table",
        "section-title-row",
        "visibleCustomSpecs",
        "specRows",
        "specDialogVisible",
        "generateDialogVisible",
        "openBatchDetail",
        "loadSpecBatches",
        "loadSpecKamis",
        "showGenerateForGroup",
        "openSpecGroup",
        "openSpecDialog",
        "resetListFilters",
    ):
        assert view_token in merchant_batches

    assert "spec-workbench" not in merchant_batches
    assert "detail-panel" not in merchant_batches
    assert "spec-tabs" not in merchant_batches
    assert merchant_batches.count('v-model="queryParams.app_id"') == 1
    assert "\u81ea\u5efa\u5e94\u7528" in merchant_batches
    assert "\u6388\u6743\u5e94\u7528" in merchant_batches
    assert "\u5e38\u7528\u89c4\u683c" in merchant_batches


def test_merchant_batches_align_with_admin_type_and_group_vocab():
    merchant_batches = (PROJECT_ROOT / "admin/src/views/MerchantBatches.vue").read_text(encoding="utf-8")

    for token in (
        "TYPE_OPTIONS",
        "commonSpecs",
        "customSpecs",
        "getSpecGroupText",
        "getTypeText",
        "getMachineBindModeText",
        "getAuthorizationOwnerText",
        "getUserBindModeText",
        "getValidityText",
        "formatBeijingTime",
    ):
        assert token in merchant_batches

    assert "day" in merchant_batches
    assert "week" in merchant_batches
    assert "month" in merchant_batches
    assert "quarter" in merchant_batches
    assert "year" in merchant_batches
    assert "lifetime" in merchant_batches
    assert "common" in merchant_batches
    assert "custom" in merchant_batches


def test_merchant_batches_share_admin_workbench_contract_with_permission_clipping():
    admin_batches = (PROJECT_ROOT / "admin/src/views/KamiBatches.vue").read_text(encoding="utf-8")
    merchant_batches = (PROJECT_ROOT / "admin/src/views/MerchantBatches.vue").read_text(encoding="utf-8")

    for token in (
        "kami-batches-page",
        "admin-isomorphic-batch-workbench",
        "yz-admin-panel",
        "yz-filter-strip",
        "overview-strip",
        "spec-section",
        "variant-panel",
        "summary-metric-card",
        "batches-panel",
        "cards-panel",
        "yz-clean-table",
        "section-title-row",
        "batch-title-link",
        "type-badge",
        "row-actions",
        "icon-actions",
        "count-pills",
        "tooltip-action-wrap",
        "batchDialogVisible",
        "appendDialogVisible",
        "showAppendDialog",
        "showGenerateForGroup",
        "openSpecGroup",
        "handleSaveBatch",
        "handleAppendKamis",
        "merchantBatchPermissions",
        "canManageSelectedApp",
        "resetListFilters",
    ):
        assert token in merchant_batches

    for token in (
        "yz-filter-strip",
        "overview-strip",
        "section-title-row",
        "row-actions",
        "tooltip-action-wrap",
    ):
        assert token in admin_batches

    assert "spec-workbench" not in merchant_batches
    assert "detail-panel" not in merchant_batches
    assert "spec-tabs" not in merchant_batches
    assert merchant_batches.count('v-model="queryParams.app_id"') == 1
    assert "批次管理" in merchant_batches
    assert "自定义规格" in merchant_batches
    assert "自建应用可管理" in merchant_batches
    assert "授权应用只读" in merchant_batches


def test_merchant_batch_spec_detail_matches_admin_card_panel_contract():
    merchant_batches = (PROJECT_ROOT / "admin/src/views/MerchantBatches.vue").read_text(encoding="utf-8")

    for token in (
        "ArrowLeft",
        "DocumentCopy",
        "Download",
        "copyTextToClipboard",
        "detailLoading",
        "detailKamis",
        "selectedDetailKamis",
        "detailTotal",
        "detailQuery",
        "detailQuery.batch_no",
        "detailQuery.status",
        "detailQuery.keyword",
        "handleDetailExport",
        "handleDeleteSelectedDetail",
        "resetDetailFilters",
        "loadDetailKamis",
        "getKamiStatusType",
        "getKamiStatusText",
        "getKamiUserText",
        "getPointsRedeemed",
        "getPointsRemaining",
        "getTimesConsumed",
        "getBoundDeviceText",
        "getTimeCardValidity",
        "formatOptionalTime",
        "exportMerchantKamis(params)",
        "getMerchantSpecKamis(selectedSpec.value.id, params)",
        "getMerchantBatchKamis(selectedBatch.value.id, params)",
    ):
        assert token in merchant_batches

    assert 'el-table-column type="selection"' in merchant_batches
    assert 'v-model="detailQuery.batch_no"' in merchant_batches
    assert 'placeholder="全部批次"' in merchant_batches
    assert 'placeholder="全部状态"' in merchant_batches
    assert 'placeholder="搜索卡密/用户"' in merchant_batches
    assert "规格卡密列表" in merchant_batches
    assert "批次卡密列表" in merchant_batches
    assert "删除选中" in merchant_batches
    assert "发卡用户无批量删除卡密权限" in merchant_batches
    assert "追加卡密" in merchant_batches


def test_merchant_batch_spec_detail_top_summary_matches_admin_three_card_layout():
    merchant_batches = (PROJECT_ROOT / "admin/src/views/MerchantBatches.vue").read_text(encoding="utf-8")

    detail_shell = merchant_batches.split('<div class="batch-detail-shell">', 1)[1].split(
        '<section class="yz-admin-panel batches-panel">',
        1,
    )[0]
    summary_block = detail_shell.split('<section class="summary-metric-card">', 1)[1].split("</section>", 1)[0]

    assert summary_block.count('<div class="metric-item">') == 3
    for token in (
        "currentDetailTarget?.total_count || 0",
        "currentDetailTarget?.unused_count || 0",
        "usedCount(currentDetailTarget)",
        "currentDetailTitle",
        "currentBatch",
        "currentDetailTarget",
        "viewMode === 'batch' && currentSpec",
    ):
        assert token in merchant_batches

    for token in (
        "grid-template-columns: minmax(0, 1fr) 420px;",
        "grid-template-columns: repeat(3, 1fr);",
        "text-align: center;",
    ):
        assert token in merchant_batches

    for forbidden in (
        "selectedSpec?.created_at",
        "selectedSpec?.updated_at",
        "selectedSpec?.total_count || 0",
        "selectedSpec?.unused_count || 0",
        "usedCount(selectedSpec)",
        "创建时间",
        "更新时间",
        "is-time",
    ):
        assert forbidden not in summary_block

    for forbidden in (
        "grid-template-columns: repeat(auto-fit",
    ):
        assert forbidden not in merchant_batches


def test_merchant_batch_row_actions_stay_single_line_and_match_admin_spacing():
    merchant_batches = (PROJECT_ROOT / "admin/src/views/MerchantBatches.vue").read_text(encoding="utf-8")
    admin_batches = (PROJECT_ROOT / "admin/src/views/KamiBatches.vue").read_text(encoding="utf-8")

    icon_block = merchant_batches.split(".icon-actions {", 1)[1].split("}", 1)[0]

    assert ".row-actions {\n  display: flex;" in merchant_batches
    assert "flex-wrap: nowrap;" in merchant_batches
    assert ".row-actions,\n.icon-actions" not in merchant_batches
    assert "display: flex;" in icon_block
    assert "flex-wrap: nowrap;" in icon_block
    assert "flex-wrap: wrap;" not in icon_block
    assert ".row-actions :deep(.el-button)" in merchant_batches
    assert "margin-left: 0;" in merchant_batches
    assert "border-radius: 8px;" in merchant_batches
    assert "font-weight: 600;" in merchant_batches
    for token in (
        ".icon-action {",
        "width: 36px;",
        "height: 36px;",
        "padding: 0;",
        ".icon-action.info",
        ".icon-action.subtle",
        ".icon-action.danger",
    ):
        assert token in merchant_batches

    assert "flex-wrap: nowrap;" in admin_batches
    assert "Action button group wraps across rows" not in merchant_batches


def test_admin_and_merchant_batch_detail_hero_actions_do_not_wrap_on_desktop():
    for source_path in (
        PROJECT_ROOT / "admin/src/views/KamiBatches.vue",
        PROJECT_ROOT / "admin/src/views/MerchantBatches.vue",
    ):
        source = source_path.read_text(encoding="utf-8")
        assert ".hero-actions {" in source, f"{source_path.name} must define a dedicated hero-actions block"
        hero_block = source.split(".hero-actions {", 1)[1].split("}", 1)[0]

        assert "flex-wrap: nowrap;" in hero_block
        assert "justify-content: flex-end;" in hero_block
        assert "white-space: nowrap;" in source


def test_merchant_batch_list_opens_admin_isomorphic_batch_detail_not_drawer():
    merchant_batches = (PROJECT_ROOT / "admin/src/views/MerchantBatches.vue").read_text(encoding="utf-8")

    assert "openBatchDrawer" not in merchant_batches
    assert "batchDrawerVisible" not in merchant_batches
    assert "<el-drawer" not in merchant_batches
    assert 'class="batch-title-link" @click="openBatchDetail(row)"' in merchant_batches
    assert 'class="icon-action info" :icon="View" @click="openBatchDetail(row)"' in merchant_batches
    assert "viewMode.value = 'batch'" in merchant_batches
    assert "batch_no: row.batch_no" in merchant_batches
    assert "route.query.batch_no" in merchant_batches
    assert "getMerchantBatchKamis(selectedBatch.value.id, params)" in merchant_batches


def test_merchant_batch_detail_cards_panel_exposes_append_action_like_admin():
    merchant_batches = (PROJECT_ROOT / "admin/src/views/MerchantBatches.vue").read_text(encoding="utf-8")

    cards_header = merchant_batches.split('<section class="yz-admin-panel cards-panel">', 1)[1].split(
        '<div class="yz-filter-strip">',
        1,
    )[0]

    assert 'v-if="viewMode === \'batch\'"' in cards_header
    assert ':disabled="!currentBatch?.can_append"' in cards_header
    assert '@click="showAppendDialog(currentBatch)"' in cards_header
    assert "追加卡密" in cards_header


def test_merchant_batch_generation_dialog_exposes_admin_grade_code_controls_and_quota_semantics():
    merchant_batches = (PROJECT_ROOT / "admin/src/views/MerchantBatches.vue").read_text(encoding="utf-8")

    for token in (
        "按规格生成卡密",
        "随机长度",
        "字符集",
        "卡密有效期",
        "格式预览",
        "generateForm.code_validity_mode",
        "generateForm.code_valid_days",
        "generateCodePreview",
        "单张消耗发卡额度",
        "积分面额",
    ):
        assert token in merchant_batches

    assert "当前额度" not in merchant_batches
    assert "当前发卡额度" not in merchant_batches
    assert "lowBalanceWarning" not in merchant_batches


def test_merchant_batch_generation_defaults_match_admin_batch_number_logic():
    merchant_batches = (PROJECT_ROOT / "admin/src/views/MerchantBatches.vue").read_text(encoding="utf-8")
    admin_batches = (PROJECT_ROOT / "admin/src/views/KamiBatches.vue").read_text(encoding="utf-8")

    admin_generate_block = admin_batches.split("const showGenerateDialog = (row) => {", 1)[1].split(
        "const showGenerateForGroup",
        1,
    )[0]
    merchant_generate_block = merchant_batches.split("async function openGenerateDialog(row) {", 1)[1].split(
        "function showGenerateDialog(row)",
        1,
    )[0]

    assert "const date = new Date().toISOString().slice(0, 10).replaceAll('-', '')" in admin_generate_block
    assert "generateForm.batch_no = `${row.spec_name || getSpecBenefitText(row)}-${date}`.slice(0, 64)" in admin_generate_block
    assert "generateForm.code_valid_days = 7" in admin_generate_block

    assert "const date = new Date().toISOString().slice(0, 10).replaceAll('-', '')" in merchant_generate_block
    assert "generateForm.batch_no = `${variant.spec_name || getSpecBenefitText(variant)}-${date}`.slice(0, 64)" in merchant_generate_block
    assert "generateForm.batch_no = ''" not in merchant_generate_block
    assert "generateForm.code_valid_days = 7" in merchant_generate_block
    assert 'placeholder="例如：150积分-20260714"' in merchant_batches
    assert 'placeholder="可留空自动生成"' not in merchant_batches


def test_merchant_spec_edit_mode_keeps_group_editable_like_admin():
    merchant_batches = (PROJECT_ROOT / "admin/src/views/MerchantBatches.vue").read_text(encoding="utf-8")

    assert 'v-model="specForm.spec_group" style="width: 100%"' in merchant_batches
    assert 'v-model="specForm.spec_group" :disabled="Boolean(editingSpec)"' not in merchant_batches
    assert 'v-model="specForm.kami_type" :disabled="Boolean(editingSpec)"' in merchant_batches
    assert "deleteDetailKamis: viewMode.value !== 'list'" in merchant_batches
    assert "deleteMerchantKamis" in merchant_batches


def test_commercial_ops_stability_controls_are_exposed():
    admin_orders = (PROJECT_ROOT / "admin/src/views/AdminRechargeOrders.vue").read_text(encoding="utf-8")
    admin_settings = (PROJECT_ROOT / "admin/src/views/AdminRechargeSettings.vue").read_text(encoding="utf-8")
    merchant_orders = (PROJECT_ROOT / "admin/src/views/MerchantOrders.vue").read_text(encoding="utf-8")
    merchant_batches = (PROJECT_ROOT / "admin/src/views/MerchantBatches.vue").read_text(encoding="utf-8")
    commercial_api = (PROJECT_ROOT / "admin/src/api/commercial.js").read_text(encoding="utf-8")
    merchant_api = (PROJECT_ROOT / "admin/src/api/merchant.js").read_text(encoding="utf-8")

    assert "deleteRechargeOption" in commercial_api
    assert "deleteBonusRule" in commercial_api
    assert "handleDeleteRechargeOption" in admin_settings
    assert "handleDeleteBonusRule" in admin_settings

    assert "expireRechargeOrder" in commercial_api
    assert "cleanupRechargeProofs" in commercial_api
    assert "expireRechargeOrder" in admin_orders
    assert "cleanupRechargeProofs" in admin_orders
    assert "detailVisible" in admin_orders
    assert "selectedOrder" in admin_orders
    assert "payment_snapshot" not in admin_orders
    assert "preview_snapshot" not in admin_orders
    assert "formatSnapshot" not in admin_orders
    assert "reviewer" in admin_orders
    assert "canceled" in admin_orders
    assert "expired" in admin_orders

    assert "cancelMerchantRechargeOrder" in merchant_api
    assert "cancelMerchantRechargeOrder" in merchant_orders
    assert "canceled" in merchant_orders
    assert "expired" in merchant_orders

    assert "previewMerchantKamis" in merchant_api
    assert "previewMerchantKamis" in merchant_batches
    assert "issuePreview" in merchant_batches
    assert "can_issue" in merchant_batches


def test_admin_recharge_orders_use_status_scoped_actions_and_center_dialog():
    admin_orders = (PROJECT_ROOT / "admin/src/views/AdminRechargeOrders.vue").read_text(encoding="utf-8")

    assert "<el-drawer" not in admin_orders
    assert '<el-dialog v-model="detailVisible"' in admin_orders
    assert "visibleOrderActions(row)" in admin_orders
    assert "visibleOrderActions(selectedOrder)" in admin_orders
    assert "const orderActions" in admin_orders
    assert "const terminalOrderActionByStatus" in admin_orders
    assert "runOrderAction(row, action)" in admin_orders
    assert "row.status !== 'pending_review'" not in admin_orders


def test_admin_merchants_formats_visible_time_columns():
    admin_merchants = (PROJECT_ROOT / "admin/src/views/AdminMerchants.vue").read_text(encoding="utf-8")

    assert "formatBeijingTime" in admin_merchants
    assert "formatOptionalTime" in admin_merchants
    assert "{{ formatBeijingTime(row.created_at) }}" in admin_merchants
    assert "{{ formatOptionalTime(row.last_login) }}" in admin_merchants
    assert "{{ formatBeijingTime(row.created_at) }}" in admin_merchants.split('label="授权时间"', 1)[1]
    assert 'prop="created_at" label="注册时间" width="180" />' not in admin_merchants
    assert 'prop="last_login" label="最近登录" width="180" />' not in admin_merchants


def test_phase2_sensitive_actions_use_fixed_confirmation_texts():
    admin_api = (PROJECT_ROOT / "admin/src/api/admin.js").read_text(encoding="utf-8")
    commercial_api = (PROJECT_ROOT / "admin/src/api/commercial.js").read_text(encoding="utf-8")
    kami_api = (PROJECT_ROOT / "admin/src/api/kami.js").read_text(encoding="utf-8")
    points_api = (PROJECT_ROOT / "admin/src/api/points.js").read_text(encoding="utf-8")
    apps = (PROJECT_ROOT / "admin/src/views/Apps.vue").read_text(encoding="utf-8")
    admin_orders = (PROJECT_ROOT / "admin/src/views/AdminRechargeOrders.vue").read_text(encoding="utf-8")
    admin_settings = (PROJECT_ROOT / "admin/src/views/AdminRechargeSettings.vue").read_text(encoding="utf-8")
    admin_merchants = (PROJECT_ROOT / "admin/src/views/AdminMerchants.vue").read_text(encoding="utf-8")
    end_users = (PROJECT_ROOT / "admin/src/views/EndUsers.vue").read_text(encoding="utf-8")
    kamis = (PROJECT_ROOT / "admin/src/views/Kamis.vue").read_text(encoding="utf-8")
    kami_batches = (PROJECT_ROOT / "admin/src/views/KamiBatches.vue").read_text(encoding="utf-8")

    assert "confirm_text" in commercial_api
    assert "data: { confirm_text" in commercial_api
    assert "deletePaymentChannelQrCode(channel, confirmText)" in commercial_api
    assert "getAdminAuditLogs" in commercial_api
    assert "deleteApp(appId, data = {})" in admin_api
    assert "method: 'delete'" in admin_api
    assert "data" in admin_api

    assert "确认删除应用" in apps
    assert "confirm_text: confirmText" in apps
    assert "deleteApp(row.app_id, { confirm_text: confirmText })" in apps

    assert "confirm_text" in points_api
    assert "grantEndUserQuota(userId, data)" in points_api
    assert "grantEndUserAppAuthorization(userId, data)" in points_api
    assert "revokeEndUserAppAuthorization(userId, authorizationId, data)" in points_api
    assert "method: 'delete'" in points_api

    for text in (
        "确认审核入账",
        "确认驳回订单",
        "确认标记异常",
        "确认关闭订单",
        "确认清理凭证",
    ):
        assert text in admin_orders
    assert "markRechargeOrderAbnormal" in admin_orders
    assert "handleMarkAbnormal" in admin_orders
    assert "confirm_text: confirmText" in admin_orders

    for text in (
        "确认修改充值配置",
        "确认删除二维码",
    ):
        assert text in admin_settings
    assert "payload.append('confirm_text', confirmText)" in admin_settings
    assert "deletePaymentChannelQrCode(channelForm.channel, confirmText)" in admin_settings
    assert "deleteRechargeOption(row.id, { confirm_text: confirmText })" in admin_settings
    assert "deleteBonusRule(row.id, { confirm_text: confirmText })" in admin_settings

    assert "确认调整额度" in admin_merchants
    assert "确认授权应用" in admin_merchants
    assert "confirm_text: confirmText" in admin_merchants
    assert "确认取消授权" in admin_merchants
    assert "revokeEndUserAppAuthorization(currentMerchant.value.id, row.id, { confirm_text: confirmText })" in admin_merchants

    assert "确认删除用户" in end_users
    assert "confirm_text: confirmText" in end_users
    assert "deleteEndUsers({" in end_users

    assert "confirm_text" in kami_api
    assert "deleteKamiSpec(specId, data" in kami_api
    assert "确认删除卡密" in kamis
    assert "deleteKamis({ ...payload, confirm_text: confirmText })" in kamis
    assert "确认删除卡密" in kami_batches
    assert "deleteKamiSpec(variant.id, { confirm_text: confirmText })" in kami_batches
    assert "deleteKamiSpec(row.id, { confirm_text: confirmText })" in kami_batches
    assert "确认删除批次" in kami_batches
    assert "payload.cascade_kamis = true" in kami_batches
    assert "deleteKamiBatch(row.id, payload)" in kami_batches
    assert "批次已删除，并清理" in kami_batches


def test_kami_batches_ignores_stale_route_app_id_before_loading_child_resources():
    kami_batches = (PROJECT_ROOT / "admin/src/views/KamiBatches.vue").read_text(encoding="utf-8")

    assert "isKnownAppId" in kami_batches
    assert "normalizeSelectedAppId" in kami_batches
    assert "routeAppId && isKnownAppId(routeAppId)" in kami_batches
    assert "routeAppId && routeAppId !== queryParams.app_id" in kami_batches
    assert "query: queryParams.app_id ? { app_id: queryParams.app_id } : {}" in kami_batches


def test_kamis_list_ignores_stale_route_app_id_before_loading_child_resources():
    kamis = (PROJECT_ROOT / "admin/src/views/Kamis.vue").read_text(encoding="utf-8")

    assert "isKnownAppId" in kamis
    assert "normalizeSelectedAppId" in kamis
    assert "routeAppId && isKnownAppId(routeAppId)" in kamis
    assert "routeAppWasStale" in kamis
    assert "path: '/admin/kamis/list'" in kamis
    assert "query: queryParams.app_id ? { app_id: queryParams.app_id } : {}" in kamis


def test_commercial_phase1_corrections_keep_identity_and_quota_scope_clear():
    auth_api = (PROJECT_ROOT / "admin/src/api/auth.js").read_text(encoding="utf-8")
    store = (PROJECT_ROOT / "admin/src/stores/user.js").read_text(encoding="utf-8")
    login = (PROJECT_ROOT / "admin/src/views/Login.vue").read_text(encoding="utf-8")
    layout = (PROJECT_ROOT / "admin/src/layouts/MainLayout.vue").read_text(encoding="utf-8")
    router = (PROJECT_ROOT / "admin/src/router/index.js").read_text(encoding="utf-8")
    end_users = (PROJECT_ROOT / "admin/src/views/EndUsers.vue").read_text(encoding="utf-8")
    merchant_dashboard = (PROJECT_ROOT / "admin/src/views/MerchantDashboard.vue").read_text(encoding="utf-8")
    admin_merchants = (PROJECT_ROOT / "admin/src/views/AdminMerchants.vue").read_text(encoding="utf-8")

    assert "sharedRegister" in auth_api
    assert "userRegister" in store
    assert "registerVisible" in login
    assert "registerForm" in login

    assert "index: '/admin/commercial', label:" not in layout
    assert "index: '/admin/commercial/quota-transactions'" in layout
    assert "index: '/admin/commercial/merchants'" in layout
    assert "path: 'commercial/quota-transactions'" in router
    assert "path: 'commercial/merchants'" in router

    assert "showQuotaDialog" not in end_users
    assert "showAppAuthorizationDialog" not in end_users
    assert "grantEndUserQuota" not in end_users
    assert "grantEndUserAppAuthorization" not in end_users
    assert "grantEndUserQuota" in admin_merchants
    assert "grantEndUserAppAuthorization" in admin_merchants
    assert "quota_type: 'kami_issue'" in admin_merchants
    assert "app_create" not in admin_merchants
    assert "recharge_balance" not in admin_merchants
    assert "app_create_balance" not in merchant_dashboard
    assert "recharge_balance" not in merchant_dashboard


def test_issue_pricing_admin_entry_and_api_are_visible():
    router = (PROJECT_ROOT / "admin/src/router/index.js").read_text(encoding="utf-8")
    layout = (PROJECT_ROOT / "admin/src/layouts/MainLayout.vue").read_text(encoding="utf-8")
    commercial_api = (PROJECT_ROOT / "admin/src/api/commercial.js").read_text(encoding="utf-8")
    issue_pricing = (PROJECT_ROOT / "admin/src/views/AdminIssuePricing.vue").read_text(encoding="utf-8")

    assert "path: 'commercial/issue-pricing'" in router
    assert "AdminIssuePricing" in router
    assert "index: '/admin/commercial/issue-pricing'" in layout
    assert "\u53d1\u5361\u989d\u5ea6\u914d\u7f6e" in layout
    assert "/admin/commercial/issue-pricing/rules" in commercial_api
    assert "getIssuePricingRules" in commercial_api
    assert "saveIssuePricingRule" in commercial_api
    assert "deleteIssuePricingRule" in commercial_api
    assert "\u786e\u8ba4\u4fee\u6539\u53d1\u5361\u989d\u5ea6" in issue_pricing
    assert "global_self_app" in issue_pricing
    assert "global_authorized_app" in issue_pricing
    assert "authorized_spec" in issue_pricing
    assert "user_self_app" in issue_pricing
    assert "user_authorized_spec" in issue_pricing
    assert "remote-method=\"searchMerchants\"" in issue_pricing
    assert "remote-method=\"searchSpecs\"" in issue_pricing
    assert "merchantLoading" in issue_pricing
    assert "specLoading" in issue_pricing
    assert "getKamiSpecs({ app_id: appId" in issue_pricing


def test_issue_pricing_admin_page_uses_business_pricing_language():
    issue_pricing = (PROJECT_ROOT / "admin/src/views/AdminIssuePricing.vue").read_text(encoding="utf-8")

    assert "发卡场景" in issue_pricing
    assert "扣费范围" in issue_pricing
    assert "生效预览" in issue_pricing
    assert "命中顺序" in issue_pricing
    assert "用户自建应用发卡" in issue_pricing
    assert "管理员授权应用发卡" in issue_pricing
    assert "指定用户 + 指定规格扣费" in issue_pricing
    assert "pricingScenario" in issue_pricing
    assert "pricingScope" in issue_pricing
    assert "effectivePreview" in issue_pricing
    assert ':value="option.value"' in issue_pricing
    assert ':label="option.value"' not in issue_pricing


def test_merchant_issue_preview_shows_pricing_rule_source():
    merchant_batches = (PROJECT_ROOT / "admin/src/views/MerchantBatches.vue").read_text(encoding="utf-8")

    assert "issuePreview?.unit_cost" in merchant_batches
    assert "issuePreview?.pricing_source" in merchant_batches
    assert "pricingLabel" in merchant_batches
    assert "用户授权规格专属" in merchant_batches


def test_phase2_finance_page_has_reviewed_at_income_scope_and_exports():
    router = (PROJECT_ROOT / "admin/src/router/index.js").read_text(encoding="utf-8")
    layout = (PROJECT_ROOT / "admin/src/layouts/MainLayout.vue").read_text(encoding="utf-8")
    finance_api = (PROJECT_ROOT / "admin/src/api/finance.js").read_text(encoding="utf-8")
    finance_view = (PROJECT_ROOT / "admin/src/views/AdminFinance.vue").read_text(encoding="utf-8")

    assert "/admin/commercial/finance" in layout
    assert "\u8d22\u52a1\u8fd0\u8425" in layout
    assert "path: 'commercial/finance'" in router
    assert "AdminFinance" in router
    assert "/admin/commercial/finance/summary" in finance_api
    assert "/admin/commercial/finance/merchant-ranking" in finance_api
    assert "/admin/commercial/recharge-orders/export" in finance_api
    assert "/admin/commercial/quota-transactions/export" in finance_api
    assert "\u5ba1\u6838\u901a\u8fc7\u65f6\u95f4" in finance_view
    assert "reviewed_at" in finance_view
    assert "\u5bfc\u51fa\u8ba2\u5355\u6d41\u6c34" in finance_view
    assert "\u5bfc\u51fa\u989d\u5ea6\u6d41\u6c34" in finance_view
    assert "\u9000\u6b3e" not in finance_view
    assert "\u51b2\u6b63" not in finance_view


def test_phase2_merchant_card_search_export_and_batch_stats_are_visible():
    merchant_api = (PROJECT_ROOT / "admin/src/api/merchant.js").read_text(encoding="utf-8")
    admin_kamis = (PROJECT_ROOT / "admin/src/views/Kamis.vue").read_text(encoding="utf-8")
    merchant_cards = (PROJECT_ROOT / "admin/src/views/MerchantCards.vue").read_text(encoding="utf-8")
    merchant_batches = (PROJECT_ROOT / "admin/src/views/MerchantBatches.vue").read_text(encoding="utf-8")

    assert "/merchant/kamis" in merchant_api
    assert "/merchant/kamis/export" in merchant_api
    assert "exportMerchantKamis" in merchant_api
    assert "\u6279\u6b21\u53f7" in merchant_cards
    assert "SDK 测试" in merchant_cards
    assert "生成卡密" in merchant_cards
    assert "openSdkTest" in merchant_cards
    assert "goGenerateKamis" in merchant_cards
    assert "generateDialogVisible" in merchant_cards
    assert "loadBatchStats" in merchant_cards
    assert "selectedBatch" in merchant_cards
    assert "handleGenerate" in merchant_cards
    assert "getMerchantBatches" in merchant_cards
    assert "appendMerchantBatchKamis" in merchant_cards
    assert "previewMerchantKamis" in merchant_cards
    assert "issuePreview" in merchant_cards
    assert "balance_before" in merchant_cards
    assert "balance_after" in merchant_cards
    assert "can_issue" in merchant_cards
    assert "previewLoading" in merchant_cards
    assert "deleteMerchantKamis" in merchant_api
    assert "ElMessage.warning('请先选择应用')" in merchant_cards
    assert "router.push({ path: '/merchant/batches'" not in merchant_cards
    assert ':disabled="!query.app_id"' not in merchant_cards
    assert "\u5bfc\u51fa" in merchant_cards
    assert "normalizedParams(false)" in merchant_cards
    assert "\u4f4e\u989d\u5ea6\u63d0\u9192" not in merchant_batches
    assert "lowBalanceWarning" not in merchant_batches
    assert "unused_count" in merchant_batches
    assert "active_count" in merchant_batches
    assert "device_bound_count" in merchant_batches
    assert "if (queryParams.keyword) params.keyword = queryParams.keyword" in admin_kamis


def test_admin_merchants_username_drilldown_exposes_apps_users_and_quick_actions():
    admin_merchants = (PROJECT_ROOT / "admin/src/views/AdminMerchants.vue").read_text(encoding="utf-8")
    admin_merchant_detail = (PROJECT_ROOT / "admin/src/views/AdminMerchantDetail.vue").read_text(encoding="utf-8")
    merchant_batches = (PROJECT_ROOT / "admin/src/views/MerchantBatches.vue").read_text(encoding="utf-8")
    commercial_api = (PROJECT_ROOT / "admin/src/api/commercial.js").read_text(encoding="utf-8")
    router = (PROJECT_ROOT / "admin/src/router/index.js").read_text(encoding="utf-8")

    assert "getCommercialMerchantDetail" in commercial_api
    assert "url: `/admin/commercial/merchants/${merchantId}/detail`" in commercial_api
    assert "path: 'commercial/merchants/:merchantId/detail'" in router
    assert "path: 'commercial/merchants/:merchantId/batches'" in router
    assert "router.push({ name: 'AdminMerchantDetail'" in admin_merchants
    assert "merchantDetailVisible" not in admin_merchants
    assert "<el-drawer" not in admin_merchant_detail
    assert "merchantDetailTabs" in admin_merchant_detail
    assert "self_owned_apps" in admin_merchant_detail
    assert "authorized_apps" in admin_merchant_detail
    assert "usage_users" in admin_merchant_detail
    assert "showBatchesForApp" in admin_merchant_detail
    assert "showGenerateForApp" in admin_merchant_detail
    assert "goAppInterfaces" in admin_merchant_detail
    assert "openEditApp" in admin_merchant_detail
    assert "handleDeleteApp" in admin_merchant_detail
    assert "AdminMerchantBatches" in router
    assert "getCommercialMerchantBatchApps" in commercial_api
    assert "isAdminMerchantScope" in merchant_batches
    assert "getCommercialMerchantBatchApps(scopedMerchantId.value)" in merchant_batches
    assert "batchManagementRoute" in merchant_batches
    assert "showGenerateForApp(row)" in admin_merchant_detail
    assert "showBatchesForApp(row)" in admin_merchant_detail
    assert "path: '/admin/kamis/batches'" not in admin_merchant_detail
    assert "path: '/admin/kamis/list'" not in admin_merchant_detail
    assert "App Secret" not in admin_merchant_detail


def test_admin_global_batch_page_uses_admin_owned_app_scope():
    admin_api = (PROJECT_ROOT / "admin/src/api/admin.js").read_text(encoding="utf-8")
    kami_batches = (PROJECT_ROOT / "admin/src/views/KamiBatches.vue").read_text(encoding="utf-8")

    assert "export function getApps(params = {})" in admin_api
    assert "params" in admin_api.split("export function getApps", 1)[1].split("}", 1)[0]
    assert "getApps({ owner_scope: 'admin' })" in kami_batches


def test_phase2_ops_center_has_safe_backup_and_cleanup_controls():
    router = (PROJECT_ROOT / "admin/src/router/index.js").read_text(encoding="utf-8")
    layout = (PROJECT_ROOT / "admin/src/layouts/MainLayout.vue").read_text(encoding="utf-8")
    ops_api = (PROJECT_ROOT / "admin/src/api/ops.js").read_text(encoding="utf-8")
    ops_view = (PROJECT_ROOT / "admin/src/views/AdminOps.vue").read_text(encoding="utf-8")

    assert "/admin/ops" in layout
    assert "\u8fd0\u7ef4\u4e2d\u5fc3" in layout
    assert "path: 'ops'" in router
    assert "AdminOps" in router
    assert "/admin/ops/backups" in ops_api
    assert "/admin/ops/uploads/proofs/cleanup" in ops_api
    assert "\u786e\u8ba4\u521b\u5efa\u5907\u4efd" in ops_view
    assert "\u786e\u8ba4\u4e0b\u8f7d\u5907\u4efd" in ops_view
    assert "\u786e\u8ba4\u6e05\u7406\u51ed\u8bc1" in ops_view
    assert "shell" not in ops_view.lower()


def test_phase2_audit_page_is_admin_only_and_visible():
    router = (PROJECT_ROOT / "admin/src/router/index.js").read_text(encoding="utf-8")
    layout = (PROJECT_ROOT / "admin/src/layouts/MainLayout.vue").read_text(encoding="utf-8")
    audit_api = (PROJECT_ROOT / "admin/src/api/audit.js").read_text(encoding="utf-8")
    audit_view = (PROJECT_ROOT / "admin/src/views/AdminAuditLogs.vue").read_text(encoding="utf-8")

    assert "/admin/commercial/audit-logs" in layout
    assert "\u64cd\u4f5c\u5ba1\u8ba1" in layout
    assert "path: 'commercial/audit-logs'" in router
    assert "AdminAuditLogs" in router
    assert "/admin/commercial/audit-logs" in audit_api
    assert "\u7ba1\u7406\u5458" in audit_view
    assert "\u64cd\u4f5c\u7c7b\u578b" in audit_view
    assert "\u64cd\u4f5c\u7ed3\u679c" in audit_view
    assert "deleteAdminAudit" not in audit_view
    assert "method: 'delete'" not in audit_api


def test_audit_logs_render_localized_time_action_and_resource_labels():
    audit_view = (PROJECT_ROOT / "admin/src/views/AdminAuditLogs.vue").read_text(encoding="utf-8")

    assert "formatBeijingTime" in audit_view
    assert "formatOptionalTime(row.created_at)" in audit_view
    assert "resourceTypeText(row.resource_type)" in audit_view
    assert "resourceTypeText(currentLog.resource_type)" in audit_view
    assert "targetUserText(row)" in audit_view
    assert "targetUserText(currentLog)" in audit_view

    for token in (
        "delete_kami_batch",
        "delete_kami",
        "delete_app",
        "kami_batch",
        "kami_spec",
        "app",
    ):
        assert token in audit_view


def test_admin_end_users_use_admin_owned_app_scope_only():
    end_users = (PROJECT_ROOT / "admin/src/views/EndUsers.vue").read_text(encoding="utf-8")

    assert "getApps({ owner_scope: 'admin' })" in end_users
    assert "getApps()" not in end_users
