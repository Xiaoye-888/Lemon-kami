"""Page-level QA contracts for UI structure, actions, and role boundaries.

These contracts intentionally live outside individual tests so every future
merchant/admin UI change has one place to update when a region, card, or
permission rule changes by design.
"""


def region(region_id, selector_token):
    return {"id": region_id, "selector_token": selector_token}


def action_group(group_id, tokens):
    return {"id": group_id, "tokens": list(tokens)}


def card_group(group_id, tokens):
    return {"id": group_id, "tokens": list(tokens)}


def table(table_id, columns):
    return {"id": table_id, "columns": list(columns)}


PAGE_CONTRACTS = [
    {
        "id": "layout.admin.navigation",
        "role": "admin",
        "route": "/admin/dashboard",
        "source": "admin/src/layouts/MainLayout.vue",
        "regions": [region("admin-menu", "const adminMenuItems = [")],
        "ordered_regions": [],
        "action_groups": [
            action_group(
                "admin-menu-order",
                (
                    "运营总览",
                    "发卡用户管理",
                    "充值订单审核",
                    "充值配置",
                    "发卡额度配置",
                    "财务运营",
                    "操作审计",
                    "运维中心",
                    "发卡额度流水",
                    "应用管理",
                    "卡密管理",
                    "设备管理",
                    "使用用户管理",
                    "管理员账号管理",
                    "事件日志",
                    "接口管理",
                    "接口文档",
                ),
            )
        ],
        "card_groups": [],
        "tables": [],
    },
    {
        "id": "layout.merchant.navigation",
        "role": "merchant",
        "route": "/merchant/dashboard",
        "source": "admin/src/layouts/MainLayout.vue",
        "regions": [region("merchant-menu", "const merchantMenuItems = [")],
        "ordered_regions": [],
        "action_groups": [
            action_group(
                "merchant-menu-order",
                (
                    "发卡工作台",
                    "充值发卡额度",
                    "我的订单",
                    "发卡额度流水",
                    "应用设置",
                    "我的应用",
                    "公告管理",
                    "版本更新",
                    "卡密管理",
                    "批次管理",
                    "我的卡密",
                    "设备记录",
                    "账号设置",
                ),
            )
        ],
        "card_groups": [],
        "tables": [],
    },
    {
        "id": "merchant.dashboard",
        "role": "merchant",
        "route": "/merchant/dashboard",
        "source": "admin/src/views/MerchantDashboard.vue",
        "regions": [
            region("toolbar", 'class="page-toolbar"'),
            region("metrics", 'class="metric-grid"'),
            region("notice-panel", 'class="workbench-panel notice-panel"'),
            region("quick-actions", 'class="workbench-panel action-panel"'),
            region("recent-lists", 'class="recent-grid"'),
        ],
        "ordered_regions": [
            region("toolbar", 'class="page-toolbar"'),
            region("metrics", 'class="metric-grid"'),
            region("notice-panel", 'class="workbench-panel notice-panel"'),
            region("quick-actions", 'class="workbench-panel action-panel"'),
            region("recent-lists", 'class="recent-grid"'),
        ],
        "card_groups": [
            card_group(
                "metric-card-data-order",
                (
                    "quota.value.balance",
                    "quota.value.total_granted",
                    "dashboard.value.apps?.total",
                    "dashboard.value.cards?.total",
                    "dashboard.value.orders?.pending_review",
                ),
            )
        ],
        "action_groups": [
            action_group(
                "quick-actions-order",
                (
                    "router.push('/merchant/recharge')",
                    "router.push('/merchant/apps')",
                    "router.push('/merchant/batches')",
                    "router.push('/merchant/cards')",
                ),
            )
        ],
        "tables": [
            table("recent-batches-columns", ("batch_no", "count", "kami_type", "created_at")),
            table("recent-orders-columns", ("order_no", "amount", "status", "created_at")),
        ],
    },
    {
        "id": "merchant.recharge",
        "role": "merchant",
        "route": "/merchant/recharge",
        "source": "admin/src/views/MerchantRecharge.vue",
        "regions": [
            region("toolbar", 'class="page-toolbar"'),
            region("two-column-grid", 'class="recharge-grid"'),
            region("amount-panel", 'class="panel amount-panel"'),
            region("payment-panel", 'class="panel payment-panel"'),
            region("submit-strip", 'class="submit-strip"'),
        ],
        "ordered_regions": [
            region("toolbar", 'class="page-toolbar"'),
            region("two-column-grid", 'class="recharge-grid"'),
            region("amount-panel", 'class="panel amount-panel"'),
            region("payment-panel", 'class="panel payment-panel"'),
        ],
        "card_groups": [
            card_group("amount-card-flow", ("option-grid", "amount-form", "自定义金额", "到账预览", "备注", "支付凭证")),
            card_group("payment-card-flow", ("paymentChannels", "selectedChannel", "qr-box", "submitSummary")),
        ],
        "action_groups": [
            action_group("toolbar-actions", ("loadConfig",)),
            action_group("submit-actions", ("canSubmit", "submitOrder")),
        ],
        "tables": [],
    },
    {
        "id": "merchant.orders",
        "role": "merchant",
        "route": "/merchant/orders",
        "source": "admin/src/views/MerchantOrders.vue",
        "regions": [region("toolbar", 'class="page-toolbar"'), region("orders-table", "<el-table")],
        "ordered_regions": [region("toolbar", 'class="page-toolbar"'), region("orders-table", "<el-table")],
        "card_groups": [],
        "action_groups": [action_group("toolbar-actions", ("loadOrders",))],
        "tables": [
            table(
                "orders-columns",
                ("订单号", "金额", "到账额度", "赠送额度", "状态", "提交时间", "审核时间", "拒绝原因", "操作"),
            )
        ],
    },
    {
        "id": "merchant.transactions",
        "role": "merchant",
        "route": "/merchant/transactions",
        "source": "admin/src/views/MerchantTransactions.vue",
        "regions": [region("toolbar", 'class="page-toolbar"'), region("transactions-table", "<el-table")],
        "ordered_regions": [region("toolbar", 'class="page-toolbar"'), region("transactions-table", "<el-table")],
        "card_groups": [],
        "action_groups": [action_group("toolbar-actions", ("loadTransactions",))],
        "tables": [
            table("transaction-columns", ("记录编号", "业务场景", "额度方向", "额度账户", "额度变动", "变动后", "关联对象", "时间", "操作"))
        ],
    },
    {
        "id": "merchant.apps",
        "role": "merchant",
        "route": "/merchant/apps",
        "source": "admin/src/views/MerchantApps.vue",
        "regions": [
            region("toolbar", 'class="page-toolbar"'),
            region("table-card", 'class="page-card"'),
            region("create-dialog", 'v-model="createDialogVisible"'),
            region("detail-dialog", 'v-model="detailDialogVisible"'),
            region("edit-dialog", 'v-model="editDialogVisible"'),
            region("delete-dialog", 'v-model="deleteDialogVisible"'),
            region("interfaces-dialog", 'v-model="interfacesDialogVisible"'),
            region("interface-config-dialog", 'v-model="interfaceConfigDialogVisible"'),
        ],
        "ordered_regions": [
            region("toolbar", 'class="page-toolbar"'),
            region("table-card", 'class="page-card"'),
            region("create-dialog", 'v-model="createDialogVisible"'),
            region("detail-dialog", 'v-model="detailDialogVisible"'),
            region("edit-dialog", 'v-model="editDialogVisible"'),
            region("delete-dialog", 'v-model="deleteDialogVisible"'),
            region("interfaces-dialog", 'v-model="interfacesDialogVisible"'),
            region("interface-config-dialog", 'v-model="interfaceConfigDialogVisible"'),
        ],
        "card_groups": [
            card_group("detail-fields", ("detailApp.name", "detailApp.app_id", "detailApp.is_owned", "detailApp.status", "formatBeijingTime(detailApp.created_at)", "maskedAppSecret", "maskedRsaPublicKey")),
            card_group("interface-config-schema", ("currentInterfaceSchema", "field.type === 'switch'", "field.type === 'number'", "canEditCurrentAppInterfaces")),
        ],
        "action_groups": [
            action_group("toolbar-actions", ("openCreateDialog", "loadApps")),
            action_group(
                "row-actions",
                ("openDetailDialog(row)", "openInterfacesDialog(row)", "showEditDialog(row)", "showDeleteDialog(row)"),
            ),
            action_group("detail-secret-actions", ("copyAppSecret", "copyRsaPublicKey", "goBatchWorkbench(detailApp)")),
            action_group("create-dialog-actions", ("createDialogVisible = false", "handleCreateApp")),
            action_group("interface-config-actions", ("interfaceConfigDialogVisible = false", "saveInterfaceConfig")),
        ],
        "tables": [
            table("apps-columns", ("应用名称", "App ID", "来源", "状态", "创建时间", "操作")),
            table("interfaces-columns", ("接口名称", "接口标识", "路径", "状态", "配置", "操作")),
        ],
    },
    {
        "id": "merchant.notices",
        "role": "merchant",
        "route": "/merchant/apps/notices",
        "source": "admin/src/views/AppNotices.vue",
        "regions": [
            region("card", 'class="page-card"'),
            region("filters", 'class="filters"'),
            region("notice-dialog", 'v-model="dialogVisible"'),
        ],
        "ordered_regions": [
            region("card", 'class="page-card"'),
            region("filters", 'class="filters"'),
            region("notice-dialog", 'v-model="dialogVisible"'),
        ],
        "card_groups": [
            card_group("merchant-route-guard", ("getContentApps", "isMerchantContentRoute", "canManageSelectedApp")),
        ],
        "action_groups": [
            action_group("notice-actions", ("openCreate", "openEdit(row)", "deleteNotice(row)", "saveNotice")),
        ],
        "tables": [
            table("notice-columns", ("ID", "公告标题", "公告内容", "级别", "状态", "启动弹窗", "只弹一次", "修订号", "更新时间", "操作"))
        ],
    },
    {
        "id": "merchant.versions",
        "role": "merchant",
        "route": "/merchant/apps/versions",
        "source": "admin/src/views/AppVersions.vue",
        "regions": [
            region("header", 'class="page-header"'),
            region("current-release", 'class="current-release"'),
            region("workspace", 'class="workspace-grid"'),
            region("release-form", 'class="release-form"'),
        ],
        "ordered_regions": [
            region("header", 'class="page-header"'),
            region("current-release", 'class="current-release"'),
            region("workspace", 'class="workspace-grid"'),
            region("release-form", 'class="release-form"'),
        ],
        "card_groups": [
            card_group("merchant-route-guard", ("getContentApps", "isMerchantContentRoute", "canManageSelectedApp")),
            card_group("windows-release-fields", ("WINDOWS_PLATFORM", "nextVersionCode", "confirmDialogPublish", "versionPayloadFromForm")),
        ],
        "action_groups": [
            action_group("version-actions", ("openCreate", "openEdit(row)", "publishDraft(row)", "archiveVersion(row)", "deleteVersion(row)", "saveVersion")),
        ],
        "tables": [
            table("version-columns", ("版本信息", "发布状态", "生效状态", "标题与说明", "发布时间", "操作"))
        ],
    },
    {
        "id": "merchant.batches.list",
        "role": "merchant",
        "route": "/merchant/batches",
        "source": "admin/src/views/MerchantBatches.vue",
        "regions": [
            region("list-shell", "admin-isomorphic-batch-workbench"),
            region("panel-header", 'class="yz-panel-header"'),
            region("filter-strip", 'class="yz-filter-strip"'),
            region("overview-cards", 'class="overview-strip"'),
            region("common-specs", "commonSpecs"),
            region("custom-specs", "customSpecs"),
        ],
        "ordered_regions": [
            region("panel-header", 'class="yz-panel-header"'),
            region("filter-strip", 'class="yz-filter-strip"'),
            region("overview-cards", 'class="overview-strip"'),
            region("common-specs", "常用规格"),
            region("custom-specs", "自定义规格"),
        ],
        "card_groups": [
            card_group("overview-card-order", ("specOverview.specs", "specOverview.batches", "specOverview.total", "specOverview.unused")),
        ],
        "action_groups": [
            action_group("toolbar-actions", ("loadAll", "openSpecDialog()")),
            action_group("filter-actions", ("handleAppChange", "handleTypeChange", "loadSpecs", "resetListFilters")),
            action_group("spec-row-actions", ("showGenerateForGroup(row)", "openSpecGroup(row)", "handleEditSpecGroup(row)", "handleDeleteSpecGroup(row)")),
        ],
        "tables": [
            table("spec-table-columns", ("规格", "类型", "策略数", "批次", "总数/已用/剩余", "状态", "用途备注", "操作"))
        ],
    },
    {
        "id": "merchant.batches.detail",
        "role": "merchant",
        "route": "/merchant/batches?batch_no=<batch>",
        "source": "admin/src/views/MerchantBatches.vue",
        "regions": [
            region("detail-shell", 'class="batch-detail-shell"'),
            region("overview-card", 'class="batch-overview-card"'),
            region("summary-cards", 'class="summary-metric-card"'),
            region("batches-panel", 'class="yz-admin-panel batches-panel"'),
            region("cards-panel", 'class="yz-admin-panel cards-panel"'),
        ],
        "ordered_regions": [
            region("detail-shell", 'class="batch-detail-shell"'),
            region("batches-panel", 'class="yz-admin-panel batches-panel"'),
            region("cards-panel", 'class="yz-admin-panel cards-panel"'),
        ],
        "card_groups": [
            card_group("summary-card-order", ("currentDetailTarget?.total_count", "currentDetailTarget?.unused_count", "usedCount(currentDetailTarget)")),
            card_group("identity-tags", ("getTypeText(currentDetailType)", "getValidityText(currentDetailTarget)", "currentDetailTarget?.source")),
        ],
        "action_groups": [
            action_group("spec-hero-actions", ("backFromDetail", "handleEditSpecGroup(selectedSpec)", "handleDeleteSpecGroup(selectedSpec)", "showGenerateForGroup(selectedSpec)")),
            action_group("batch-hero-actions", ("backFromDetail", "showBatchDialog(currentBatch)", "deleteBatch(currentBatch)")),
            action_group("batch-row-actions", ("openBatchDetail(row)", "showBatchDialog(row)", "deleteBatch(row)")),
            action_group("card-panel-actions", ("handleDetailExport", "handleDeleteSelectedDetail", "deleteMerchantKamis", "showAppendDialog(currentBatch)")),
        ],
        "tables": [
            table("batch-columns", ("批次名称", "类型", "权益", "剩余权益", "卡密有效期", "机器码限制", "总数/已用/剩余", "状态", "创建时间", "操作")),
            table("card-columns", ("卡密", "批次", "状态", "绑定关系", "设备策略", "创建时间", "使用用户", "备注")),
        ],
    },
    {
        "id": "merchant.cards",
        "role": "merchant",
        "route": "/merchant/cards",
        "source": "admin/src/views/MerchantCards.vue",
        "regions": [
            region("toolbar", 'class="page-toolbar"'),
            region("filter-strip", 'class="filter-strip"'),
            region("cards-table", "<el-table"),
            region("generate-dialog", 'v-model="generateDialogVisible"'),
        ],
        "ordered_regions": [
            region("toolbar", 'class="page-toolbar"'),
            region("filter-strip", 'class="filter-strip"'),
            region("cards-table", "<el-table"),
        ],
        "card_groups": [
            card_group("generate-preview", ("issuePreview?.can_issue", "issuePreview?.total_cost", "issuePreview?.balance_before", "issuePreview?.balance_after", "previewLoading")),
        ],
        "action_groups": [
            action_group("toolbar-actions", ("openSdkTest", "goGenerateKamis", "loadCards")),
            action_group("filter-actions", ("handleSearch", "handleReset", "handleExport")),
            action_group("generate-actions", ("previewMerchantKamis", "issuePreview", "loadBatchStats", "selectedBatch", "loadIssuePreview", "handleGenerate")),
        ],
        "tables": [
            table("cards-columns", ("卡密", "应用", "批次号", "类型", "状态", "绑定设备", "激活时间", "创建时间"))
        ],
        "forbidden_tokens": [
            "router.push({ path: '/merchant/batches'",
            "query: { app_id: query.app_id, action: 'generate' }",
            ':disabled="!query.app_id"',
        ],
    },
    {
        "id": "merchant.devices",
        "role": "merchant",
        "route": "/merchant/devices",
        "source": "admin/src/views/Devices.vue",
        "regions": [
            region("container", 'class="devices-container"'),
            region("filters", 'class="filter-form"'),
            region("table", "<el-table"),
        ],
        "ordered_regions": [
            region("container", 'class="devices-container"'),
            region("filters", 'class="filter-form"'),
            region("table", "<el-table"),
        ],
        "card_groups": [],
        "action_groups": [action_group("filter-actions", ("handleFilterChange",))],
        "tables": [
            table("device-columns", ("ID", "应用", "设备UUID", "指纹", "关联卡密", "用户名", "绑定关系", "设备策略", "IP地址", "IP数量", "风险等级", "操作"))
        ],
    },
    {
        "id": "merchant.account",
        "role": "merchant",
        "route": "/merchant/account",
        "source": "admin/src/views/MerchantAccount.vue",
        "regions": [
            region("toolbar", 'class="page-toolbar"'),
            region("account-grid", 'class="account-grid"'),
            region("summary-card", 'class="panel account-summary"'),
            region("permission-list", 'class="permission-list"'),
        ],
        "ordered_regions": [
            region("toolbar", 'class="page-toolbar"'),
            region("account-grid", 'class="account-grid"'),
            region("summary-card", 'class="panel account-summary"'),
            region("permission-list", 'class="permission-list"'),
        ],
        "card_groups": [
            card_group("profile-fields", ("profile.username", "profile.email", "profile.phone", "profile.created_at", "profile.last_login")),
            card_group("permission-fields", ("后台身份", "发卡额度", "应用权限")),
        ],
        "action_groups": [action_group("toolbar-actions", ("loadProfile",))],
        "tables": [],
    },
    {
        "id": "admin.batches.list",
        "role": "admin",
        "route": "/admin/kamis/batches",
        "source": "admin/src/views/KamiBatches.vue",
        "regions": [
            region("panel-header", 'class="yz-panel-header"'),
            region("filter-strip", 'class="yz-filter-strip"'),
            region("overview-cards", 'class="overview-strip"'),
            region("common-specs", "commonSpecs"),
            region("custom-specs", "customSpecs"),
        ],
        "ordered_regions": [
            region("panel-header", 'class="yz-panel-header"'),
            region("filter-strip", 'class="yz-filter-strip"'),
            region("overview-cards", 'class="overview-strip"'),
            region("common-specs", "常用规格"),
            region("custom-specs", "自定义规格"),
        ],
        "card_groups": [
            card_group("overview-card-order", ("specOverview.specs", "specOverview.batches", "specOverview.total", "specOverview.unused")),
        ],
        "action_groups": [
            action_group("toolbar-actions", ("loadSpecs", "showCreateSpecDialog")),
            action_group("spec-row-actions", ("showGenerateForGroup(row)", "openSpecGroup(row)", "handleEditSpecGroup(row)", "handleDeleteSpecGroup(row)")),
        ],
        "tables": [
            table("spec-table-columns", ("规格", "类型", "策略数", "批次", "总数/已用/剩余", "状态", "用途备注", "操作"))
        ],
    },
    {
        "id": "admin.batches.detail",
        "role": "admin",
        "route": "/admin/kamis/batches?batch_no=<batch>",
        "source": "admin/src/views/KamiBatches.vue",
        "regions": [
            region("detail-shell", 'class="batch-detail-shell"'),
            region("overview-card", 'class="batch-overview-card"'),
            region("summary-cards", 'class="summary-metric-card"'),
            region("batches-panel", 'class="yz-admin-panel batches-panel"'),
            region("cards-panel", 'class="yz-admin-panel cards-panel"'),
        ],
        "ordered_regions": [
            region("detail-shell", 'class="batch-detail-shell"'),
            region("batches-panel", 'class="yz-admin-panel batches-panel"'),
            region("cards-panel", 'class="yz-admin-panel cards-panel"'),
        ],
        "card_groups": [
            card_group("summary-card-order", ("currentDetailTarget?.total_count", "currentDetailTarget?.unused_count", "usedCount(currentDetailTarget)")),
        ],
        "action_groups": [
            action_group("spec-hero-actions", ("backFromDetail", "handleEditSpec(currentSpec)", "handleDeleteSpec(currentSpec)", "showGenerateDialog(currentSpec)")),
            action_group("batch-hero-actions", ("backFromDetail", "handleEditBatch(currentBatch)", "handleDeleteBatch(currentBatch)")),
            action_group("batch-row-actions", ("openBatchDetail(row)", "handleEditBatch(row)", "handleDeleteBatch(row)")),
            action_group("card-panel-actions", ("handleDetailExport", "handleDeleteSelectedDetail", "showAppendDialog")),
        ],
        "tables": [
            table("batch-columns", ("批次名称", "类型", "权益", "剩余权益", "卡密有效期", "机器码限制", "总数/已用/剩余", "状态", "操作")),
            table("card-columns", ("卡密", "批次", "状态", "绑定关系", "设备策略", "创建时间", "使用用户", "有效期", "机器码限制")),
        ],
    },
    {
        "id": "admin.merchants",
        "role": "admin",
        "route": "/admin/commercial/merchants",
        "source": "admin/src/views/AdminMerchants.vue",
        "regions": [
            region("toolbar", 'class="page-toolbar"'),
            region("filter-form", 'class="filter-form"'),
            region("merchant-table", "<el-table"),
            region("quota-dialog", 'v-model="quotaDialogVisible"'),
            region("app-auth-dialog", 'v-model="appAuthDialogVisible"'),
            region("merchant-detail-drawer", 'v-model="merchantDetailVisible"'),
        ],
        "ordered_regions": [
            region("toolbar", 'class="page-toolbar"'),
            region("filter-form", 'class="filter-form"'),
            region("merchant-table", "<el-table"),
            region("quota-dialog", 'v-model="quotaDialogVisible"'),
            region("app-auth-dialog", 'v-model="appAuthDialogVisible"'),
            region("merchant-detail-drawer", 'v-model="merchantDetailVisible"'),
        ],
        "card_groups": [],
        "action_groups": [
            action_group("row-actions", ("openMerchantDetail(row)", "openQuotaDialog(row)", "openAppAuthDialog(row)")),
            action_group("quota-dialog-actions", ("quotaDialogVisible = false", "submitIssueQuotaGrant")),
            action_group("app-auth-dialog-actions", ("appAuthDialogVisible = false", "submitAppAuthorization")),
        ],
        "tables": [
            table("merchant-columns", ("ID", "用户名", "邮箱", "手机号", "发卡额度", "累计入账", "状态", "注册时间", "最近登录", "操作"))
        ],
    },
    {
        "id": "admin.merchants.detail",
        "role": "admin",
        "route": "/admin/commercial/merchants/<id>/detail",
        "source": "admin/src/views/AdminMerchants.vue",
        "regions": [
            region("detail-drawer", 'v-model="merchantDetailVisible"'),
            region("detail-summary", 'class="merchant-detail-summary"'),
            region("detail-tabs", 'class="merchant-detail-tabs"'),
        ],
        "ordered_regions": [
            region("detail-drawer", 'v-model="merchantDetailVisible"'),
            region("detail-summary", 'class="merchant-detail-summary"'),
            region("detail-tabs", 'class="merchant-detail-tabs"'),
        ],
        "card_groups": [
            card_group("detail-data", ("merchantDetail.profile", "merchantDetail.quota", "merchantDetail.self_owned_apps", "merchantDetail.usage_users", "merchantDetail.authorized_apps")),
            card_group("detail-tab-order", ('name="self_owned_apps"', 'name="authorized_apps"', 'name="usage_users"')),
        ],
        "action_groups": [
            action_group("app-quick-actions", ("openMerchantAppKamis(row)", "openMerchantAppBatches(row)")),
        ],
        "tables": [
            table("self-owned-app-columns", ("应用名称", "App ID", "状态", "创建时间", "操作")),
            table("authorized-app-columns", ("应用名称", "App ID", "授权人", "授权时间", "操作")),
            table("usage-user-columns", ("用户名", "应用", "设备 UUID", "最近使用")),
        ],
        "forbidden_tokens": ["App Secret"],
    },
    {
        "id": "admin.recharge_orders",
        "role": "admin",
        "route": "/admin/commercial/recharge-orders",
        "source": "admin/src/views/AdminRechargeOrders.vue",
        "regions": [
            region("toolbar", 'class="page-toolbar"'),
            region("filters", 'class="filters"'),
            region("orders-table", "<el-table"),
            region("detail-drawer", 'v-model="detailVisible"'),
            region("proof-dialog", 'v-model="proofVisible"'),
        ],
        "ordered_regions": [
            region("toolbar", 'class="page-toolbar"'),
            region("filters", 'class="filters"'),
            region("orders-table", "<el-table"),
            region("detail-drawer", 'v-model="detailVisible"'),
            region("proof-dialog", 'v-model="proofVisible"'),
        ],
        "card_groups": [
            card_group("detail-business-fields", ("selectedOrder.base_quota", "selectedOrder.bonus_quota", "selectedOrder.credit_quota", "selectedOrder.reject_reason")),
        ],
        "forbidden_tokens": ["payment_snapshot", "preview_snapshot"],
        "action_groups": [
            action_group("toolbar-actions", ("handleCleanupProofs", "loadOrders")),
            action_group("row-actions", ("openDetail(row)", "handleApprove(row)", "handleReject(row)", "handleExpire(row)", "handleMarkAbnormal(row)")),
            action_group("drawer-actions", ("openProof(selectedOrder)", "handleApprove(selectedOrder)", "handleReject(selectedOrder)", "handleExpire(selectedOrder)", "handleMarkAbnormal(selectedOrder)")),
        ],
        "tables": [
            table("order-columns", ("订单号", "用户", "金额", "到账额度", "赠送额度", "支付渠道", "状态", "提交时间", "支付凭证", "操作"))
        ],
    },
    {
        "id": "admin.devices",
        "role": "admin",
        "route": "/admin/devices",
        "source": "admin/src/views/Devices.vue",
        "regions": [
            region("container", 'class="devices-container"'),
            region("filters", 'class="filter-form"'),
            region("table", "<el-table"),
        ],
        "ordered_regions": [
            region("container", 'class="devices-container"'),
            region("filters", 'class="filter-form"'),
            region("table", "<el-table"),
        ],
        "card_groups": [],
        "action_groups": [
            action_group("admin-row-actions", ("updateRisk(row, 0)", "updateRisk(row, 1)", "updateRisk(row, 2)")),
        ],
        "tables": [
            table("device-columns", ("ID", "应用", "设备UUID", "指纹", "关联卡密", "用户名", "绑定关系", "设备策略", "IP地址", "IP数量", "风险等级", "操作"))
        ],
    },
]


ROLE_PERMISSION_CONTRACTS = [
    {
        "id": "merchant_self_owned_app",
        "allowed": ["rename", "delete", "manage_interfaces", "manage_specs", "generate_batches", "delete_own_kamis"],
        "forbidden": ["read_admin_app_secret", "manage_other_merchant_apps"],
        "tests": [
            "test_merchant_app_detail_and_interface_management_follow_ownership_boundaries",
            "test_merchant_self_owned_specs_are_manageable_and_authorized_specs_are_read_only",
            "test_merchant_can_delete_own_issued_kamis_and_refund_source_quota",
        ],
    },
    {
        "id": "merchant_authorized_app",
        "allowed": ["read_interfaces", "read_specs", "generate_own_batches"],
        "forbidden": ["rename", "delete", "manage_interfaces", "manage_specs", "read_app_secret"],
        "tests": [
            "test_merchant_authorized_app_issue_requires_existing_spec_and_hides_secrets",
            "test_merchant_app_detail_and_interface_management_follow_ownership_boundaries",
        ],
    },
    {
        "id": "merchant_app_content_management",
        "allowed": ["manage_self_owned_notices", "manage_self_owned_versions", "read_authorized_notices", "read_authorized_versions"],
        "forbidden": ["manage_authorized_notices", "manage_authorized_versions", "merchant_access_to_admin_core_commercial_config"],
        "tests": ["test_merchant_notice_and_version_management_follows_app_ownership_boundaries"],
    },
    {
        "id": "merchant_authorized_batches_not_synced",
        "allowed": ["use_authorized_specs", "create_merchant_issued_batches"],
        "forbidden": ["list_admin_created_batches", "open_admin_created_batch_cards"],
        "tests": ["test_merchant_authorized_app_batches_are_issuer_scoped_not_synced_from_admin"],
    },
    {
        "id": "merchant_device_scope",
        "allowed": ["list_own_issued_devices"],
        "forbidden": ["list_admin_only_devices", "list_other_merchant_devices", "mutate_device_status"],
        "tests": ["test_admin_devices_require_admin_and_merchant_devices_are_scoped"],
    },
    {
        "id": "application_user_cannot_manage_quota",
        "allowed": ["legacy_login_scope_only"],
        "forbidden": ["merchant_quota_routes", "merchant_app_management", "merchant_batch_generation"],
        "tests": ["test_application_users_cannot_use_quota_or_app_management_routes"],
    },
    {
        "id": "admin_only_commercial_routes",
        "allowed": ["admin_review", "admin_authorize_apps", "admin_issue_quota", "admin_device_mutations"],
        "forbidden": ["merchant_access_to_admin_routes"],
        "tests": [
            "test_shared_login_routes_admin_and_merchant_roles",
            "test_admin_devices_require_admin_and_merchant_devices_are_scoped",
        ],
    },
]


VISUAL_REGION_CONTRACTS = [
    {
        "label": "merchant-apps-row-actions",
        "route": "/merchant/apps",
        "role": "merchant",
        "region": "merchant app table row action group",
        "baseline": "merchant-apps-row-actions.desktop.png",
    },
    {
        "label": "merchant-batches-spec-row-actions",
        "route": "/merchant/batches",
        "role": "merchant",
        "region": "merchant spec row action group",
        "baseline": "merchant-batches-spec-row-actions.desktop.png",
    },
    {
        "label": "merchant-batches-detail-summary",
        "route": "/merchant/batches",
        "role": "merchant",
        "region": "merchant batch/spec detail top summary cards",
        "baseline": "merchant-batches-detail-summary.desktop.png",
    },
    {
        "label": "merchant-batches-batch-row-actions",
        "route": "/merchant/batches",
        "role": "merchant",
        "region": "merchant batch detail row action group",
        "baseline": "merchant-batches-batch-row-actions.desktop.png",
    },
]


REQUIRED_BROWSER_CONTRACT_KEYS = (
    "pageContractMismatches",
    "action_groups",
    "tableColumnMismatches",
    "detailPanelMismatches",
    "detailSummaryMismatches",
    "merchantBatchSpecRowActionsRect",
    "merchantBatchBatchRowActionsRect",
    "merchantBatchDetailOpenedAsDrawer",
    "merchantBatchDetailUrlHasBatchNo",
)


DESIGN_ACCEPTANCE_RULES = [
    {
        "id": "page_information_architecture",
        "scope": "admin and merchant primary console routes, especially merchant dashboard/apps/batches",
        "blocks_on_failure": True,
        "verified_by": ["tests/test_page_contracts.py", "scripts/browser_cdp_sweep.mjs"],
    },
    {
        "id": "functional_region_order",
        "scope": "toolbars, filters, overview cards, content tables, detail panels, dialogs",
        "blocks_on_failure": True,
        "verified_by": ["tests/test_page_contracts.py::test_page_contracts_validate_regions_cards_tables_and_action_order"],
    },
    {
        "id": "card_metric_semantics",
        "scope": "merchant dashboard metrics and admin-isomorphic batch/spec detail summary metrics",
        "blocks_on_failure": True,
        "verified_by": ["tests/test_page_contracts.py", "scripts/browser_cdp_sweep.mjs detailSummaryMismatches"],
    },
    {
        "id": "button_order_and_density",
        "scope": "row actions, hero actions, toolbar actions, card-panel actions",
        "blocks_on_failure": True,
        "verified_by": ["tests/test_page_contracts.py", "tests/test_production_e2e_browser_qa.py", "scripts/browser_cdp_sweep.mjs action_groups"],
    },
    {
        "id": "table_column_parity",
        "scope": "merchant/admin batch list, batch detail, card detail, recharge orders, device lists",
        "blocks_on_failure": True,
        "verified_by": ["tests/test_page_contracts.py", "scripts/browser_cdp_sweep.mjs tableColumnMismatches"],
    },
    {
        "id": "role_permission_boundaries",
        "scope": "admin, merchant self-owned apps, merchant authorized apps, end-user route boundaries",
        "blocks_on_failure": True,
        "verified_by": ["tests/test_page_contracts.py::test_page_contracts_pin_role_permission_boundaries_to_existing_tests", "tests/test_commercial_phase1.py"],
    },
    {
        "id": "data_semantics",
        "scope": "time formatting, recharge detail redaction, interface config schemas, device IP/fingerprint scope, issue quota semantics",
        "blocks_on_failure": True,
        "verified_by": ["tests/test_frontend_static.py", "tests/test_commercial_phase1.py", "tests/test_unified_entitlements.py"],
    },
    {
        "id": "interaction_route_behavior",
        "scope": "open detail, create/edit/delete, generate batches, export, append, refresh, filter reset, protected route behavior",
        "blocks_on_failure": True,
        "verified_by": ["tests/test_frontend_static.py", "tests/test_production_e2e_browser_qa.py"],
    },
    {
        "id": "browser_visual_regression",
        "scope": "desktop visual baselines for merchant apps actions and merchant batch list/detail action/summary regions",
        "blocks_on_failure": True,
        "verified_by": ["tests/test_production_e2e_browser_qa.py", "tests/visual_baselines"],
    },
]
