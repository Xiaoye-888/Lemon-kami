<template>
  <div class="audit-page">
    <div class="page-toolbar">
      <div>
        <h2>操作审计</h2>
        <p>管理员敏感操作、结果、对象和确认记录</p>
      </div>
      <div class="toolbar-actions">
        <el-input
          v-model="query.keyword"
          placeholder="管理员 / 用户 / 资源 / 摘要"
          clearable
          class="keyword-input"
          @keyup.enter="handleSearch"
        />
        <el-select v-model="query.action" clearable placeholder="操作类型" class="filter-select" @change="handleSearch">
          <el-option label="审核入账" value="approve_recharge_order" />
          <el-option label="驳回订单" value="reject_recharge_order" />
          <el-option label="标记异常" value="mark_recharge_abnormal" />
          <el-option label="关闭订单" value="expire_recharge_order" />
          <el-option label="调整额度" value="grant_issue_quota" />
          <el-option label="授权应用" value="grant_app_authorization" />
          <el-option label="取消授权" value="revoke_app_authorization" />
          <el-option label="修改充值配置" value="change_recharge_config" />
          <el-option label="清理凭证" value="cleanup_proof_files" />
          <el-option label="创建备份" value="create_ops_backup" />
          <el-option label="下载备份" value="download_ops_backup" />
          <el-option label="删除卡密批次" value="delete_kami_batch" />
          <el-option label="删除卡密/规格" value="delete_kami" />
          <el-option label="删除应用" value="delete_app" />
          <el-option label="删除收款码" value="delete_payment_qrcode" />
          <el-option label="修改发卡额度配置" value="change_issue_pricing" />
        </el-select>
        <el-select v-model="query.status" clearable placeholder="操作结果" class="result-select" @change="handleSearch">
          <el-option label="成功" value="success" />
          <el-option label="失败" value="failed" />
        </el-select>
        <el-button :icon="Refresh" :loading="loading" @click="loadLogs">刷新</el-button>
      </div>
    </div>

    <el-card shadow="never">
      <el-table :data="logs" v-loading="loading" border stripe>
        <el-table-column prop="created_at" label="时间" width="170">
          <template #default="{ row }">{{ formatOptionalTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="admin_username" label="管理员" width="130" show-overflow-tooltip />
        <el-table-column prop="action" label="操作类型" width="160">
          <template #default="{ row }">
            {{ actionText(row.action) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="操作结果" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small">
              {{ row.status === 'success' ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="target_username" label="对象用户" width="140" show-overflow-tooltip />
        <el-table-column prop="resource_type" label="资源类型" width="130">
          <template #default="{ row }">{{ resourceTypeText(row.resource_type) }}</template>
        </el-table-column>
        <el-table-column prop="resource_id" label="资源标识" width="150" show-overflow-tooltip />
        <el-table-column prop="summary" label="摘要" min-width="220" show-overflow-tooltip />
        <el-table-column prop="request_ip" label="IP" width="130" />
        <el-table-column label="详情" width="90" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="showDetail(row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="query.page"
        v-model:page-size="query.page_size"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        class="pagination"
        @size-change="loadLogs"
        @current-change="loadLogs"
      />
    </el-card>

    <el-dialog v-model="detailVisible" title="审计详情" width="720px">
      <el-descriptions v-if="currentLog" :column="1" border>
        <el-descriptions-item label="管理员">{{ currentLog.admin_username || '-' }}</el-descriptions-item>
        <el-descriptions-item label="操作类型">{{ actionText(currentLog.action) }}</el-descriptions-item>
        <el-descriptions-item label="操作结果">
          <el-tag :type="currentLog.status === 'success' ? 'success' : 'danger'">
            {{ currentLog.status === 'success' ? '成功' : '失败' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="确认范围">{{ currentLog.confirm_scope || '-' }}</el-descriptions-item>
        <el-descriptions-item label="对象用户">{{ currentLog.target_username || '-' }}</el-descriptions-item>
        <el-descriptions-item label="资源">{{ resourceTypeText(currentLog.resource_type) }} / {{ currentLog.resource_id || '-' }}</el-descriptions-item>
        <el-descriptions-item label="摘要">{{ currentLog.summary || '-' }}</el-descriptions-item>
        <el-descriptions-item label="错误">{{ currentLog.error_message || '-' }}</el-descriptions-item>
        <el-descriptions-item label="请求信息">
          <div class="wrap-text">{{ currentLog.request_ip || '-' }} / {{ currentLog.user_agent || '-' }}</div>
        </el-descriptions-item>
        <el-descriptions-item label="变更前">
          <pre>{{ formatJson(currentLog.before) }}</pre>
        </el-descriptions-item>
        <el-descriptions-item label="变更后">
          <pre>{{ formatJson(currentLog.after) }}</pre>
        </el-descriptions-item>
        <el-descriptions-item label="附加信息">
          <pre>{{ formatJson(currentLog.metadata) }}</pre>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { getAdminAuditLogs } from '../api/audit'
import { formatBeijingTime } from '../utils/datetime'

const loading = ref(false)
const logs = ref([])
const total = ref(0)
const detailVisible = ref(false)
const currentLog = ref(null)

const query = reactive({
  keyword: '',
  action: '',
  status: '',
  page: 1,
  page_size: 20
})

const actionLabels = {
  approve_recharge_order: '审核入账',
  reject_recharge_order: '驳回订单',
  mark_recharge_abnormal: '标记异常',
  expire_recharge_order: '关闭订单',
  grant_issue_quota: '调整额度',
  grant_app_authorization: '授权应用',
  revoke_app_authorization: '取消授权',
  change_recharge_config: '修改充值配置',
  cleanup_proof_files: '清理凭证',
  create_ops_backup: '创建备份',
  download_ops_backup: '下载备份',
  delete_kami_batch: '删除卡密批次',
  delete_kami: '删除卡密/规格',
  delete_app: '删除应用',
  delete_payment_qrcode: '删除收款码',
  change_issue_pricing: '修改发卡额度配置'
}

const resourceTypeLabels = {
  recharge_order: '充值订单',
  end_user: '发卡用户',
  app: '应用',
  kami: '卡密',
  kami_batch: '卡密批次',
  kami_spec: '卡密规格',
  payment_channel: '支付渠道',
  payment_channel_qrcode: '收款码',
  recharge_option: '充值选项',
  recharge_bonus_rule: '赠送规则',
  recharge_proof: '支付凭证',
  issue_pricing_rule: '发卡额度规则',
  ops_backup: '运维备份'
}

function normalizedQuery() {
  return {
    keyword: query.keyword || undefined,
    action: query.action || undefined,
    status: query.status || undefined,
    page: query.page,
    page_size: query.page_size
  }
}

async function loadLogs() {
  loading.value = true
  try {
    const res = await getAdminAuditLogs(normalizedQuery())
    logs.value = res.data?.items || []
    total.value = res.data?.total || 0
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  query.page = 1
  loadLogs()
}

function showDetail(row) {
  currentLog.value = row
  detailVisible.value = true
}

function actionText(action) {
  return actionLabels[action] || action || '-'
}

function resourceTypeText(resourceType) {
  return resourceTypeLabels[resourceType] || resourceType || '-'
}

function formatOptionalTime(value) {
  return value ? formatBeijingTime(value) : '-'
}

function formatJson(value) {
  if (!value) return '-'
  return JSON.stringify(value, null, 2)
}

onMounted(loadLogs)
</script>

<style scoped>
.audit-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.page-toolbar h2 {
  margin: 0;
  font-size: 24px;
  color: #0f172a;
}

.page-toolbar p {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 13px;
}

.toolbar-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.keyword-input {
  width: 260px;
}

.filter-select {
  width: 170px;
}

.result-select {
  width: 120px;
}

.pagination {
  margin-top: 18px;
  justify-content: flex-end;
}

.wrap-text,
pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: inherit;
}

@media (max-width: 820px) {
  .page-toolbar {
    align-items: stretch;
  }

  .toolbar-actions,
  .keyword-input,
  .filter-select,
  .result-select {
    width: 100%;
  }
}
</style>
