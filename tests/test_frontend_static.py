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
    assert 'v-if="!isMerchantConsole"' in source


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
    assert "管理员 / 商户共用登录" in login
    assert "使用管理员或商户账号登录" in login
    assert "path: '/admin'" in router
    assert "path: '/merchant'" in router
    assert "MerchantDashboard" in router
    assert "AdminRechargeOrders" in router


def test_commercial_admin_and_merchant_navigation_entries_are_visible():
    layout = (PROJECT_ROOT / "admin/src/layouts/MainLayout.vue").read_text(encoding="utf-8")

    assert "商业版后台" in layout
    assert "商户控制台" in layout
    assert "充值订单" in layout
    assert "充值配置" in layout
    assert "发卡额度流水" in layout
    assert "我的订单" in layout
    assert "批次管理" in layout
    assert "我的卡密" in layout


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
    assert "payment_snapshot" in admin_orders
    assert "preview_snapshot" in admin_orders
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
    assert "deleteKamiBatch(row.id, { confirm_text: confirmText })" in kami_batches


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
    assert "\u5bfc\u51fa" in merchant_cards
    assert "normalizedParams(false)" in merchant_cards
    assert "\u4f4e\u989d\u5ea6\u63d0\u9192" in merchant_batches
    assert "lowBalanceWarning" in merchant_batches
    assert "unused_count" in merchant_batches
    assert "active_count" in merchant_batches
    assert "device_bound_count" in merchant_batches
    assert "if (queryParams.keyword) params.keyword = queryParams.keyword" in admin_kamis


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
    assert "delete" not in audit_view.lower()
