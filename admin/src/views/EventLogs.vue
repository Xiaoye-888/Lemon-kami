<template>
  <div class="logs-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>事件日志</span>
          <el-button @click="loadLogs" :loading="loading">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>

      <!-- 筛选条件 -->
      <el-form :inline="true" :model="queryParams" class="filter-form">
        <el-form-item label="事件类型">
          <el-select
            v-model="queryParams.event_type"
            placeholder="全部"
            clearable
            style="width: 200px"
            @change="handleSearch"
          >
            <el-option-group label="使用与安全">
              <el-option label="管理员登录" value="admin_login" />
              <el-option label="卡密激活" value="activate" />
              <el-option label="卡密验证" value="verify" />
              <el-option label="心跳上报" value="heartbeat" />
            </el-option-group>
            <el-option-group label="管理端操作">
              <el-option label="创建应用" value="app_create" />
              <el-option label="删除应用" value="app_delete" />
              <el-option label="配置应用接口" value="app_interface_config" />
              <el-option label="创建批次" value="kami_batch_create" />
              <el-option label="删除批次" value="kami_batch_delete" />
              <el-option label="生成卡密" value="kami_generate" />
              <el-option label="删除卡密" value="kami_delete" />
              <el-option label="更新用户" value="user_update" />
              <el-option label="重置密码" value="password_reset" />
              <el-option label="删除用户" value="user_delete" />
            </el-option-group>
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="queryParams.status" placeholder="全部" clearable style="width: 120px" @change="handleSearch">
            <el-option label="成功" :value="1" />
            <el-option label="失败" :value="0" />
          </el-select>
        </el-form-item>
        <el-form-item label="应用ID">
          <el-input v-model="queryParams.app_id" placeholder="输入应用ID" clearable style="width: 180px" @keyup.enter="handleSearch" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 日志表格 -->
      <el-table
        :data="logs"
        v-loading="loading"
        element-loading-custom-class="yz-bounce"
        border
        stripe
      >
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="event_type" label="事件类型" width="110">
          <template #default="{ row }">
            <el-tag :type="getEventTypeTag(row.event_type)" size="small">
              {{ getEventTypeText(row.event_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="70">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">
              {{ row.status === 1 ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="message" label="消息" min-width="200" show-overflow-tooltip />
        <el-table-column prop="app_name" label="应用" width="120" show-overflow-tooltip />
        <el-table-column prop="kami_code" label="卡密" width="150" show-overflow-tooltip />
        <el-table-column prop="ip_address" label="IP" width="130" />
        <el-table-column prop="created_at" label="时间" width="160">
          <template #default="{ row }">
            {{ formatBeijingTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link @click="showDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="queryParams.page"
        v-model:page-size="queryParams.page_size"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadLogs"
        @current-change="loadLogs"
        style="margin-top: 20px; justify-content: flex-end"
      />
    </el-card>

    <!-- 详情对话框 -->
    <el-dialog v-model="detailVisible" title="日志详情" width="600px">
      <el-descriptions :column="1" border v-if="currentLog">
        <el-descriptions-item label="事件类型">
          <el-tag :type="getEventTypeTag(currentLog.event_type)">
            {{ getEventTypeText(currentLog.event_type) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="应用名称">{{ currentLog.app_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="应用ID">{{ currentLog.app_id }}</el-descriptions-item>
        <el-descriptions-item label="卡密">{{ currentLog.kami_code || '-' }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="currentLog.status === 1 ? 'success' : 'danger'">
            {{ currentLog.status === 1 ? '成功' : '失败' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="消息">{{ currentLog.message }}</el-descriptions-item>
        <el-descriptions-item label="IP地址">{{ currentLog.ip_address || '-' }}</el-descriptions-item>
        <el-descriptions-item label="设备UUID">{{ currentLog.device_uuid || '-' }}</el-descriptions-item>
        <el-descriptions-item label="User-Agent">
          <div style="word-break: break-all">{{ currentLog.user_agent || '-' }}</div>
        </el-descriptions-item>
        <el-descriptions-item label="额外数据">
          <pre v-if="currentLog.payload" style="margin: 0; white-space: pre-wrap;">{{ formatJson(currentLog.payload) }}</pre>
          <span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item label="时间">{{ formatBeijingTime(currentLog.created_at) }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import request from '../utils/request'
import { formatBeijingTime } from '../utils/datetime'

const loading = ref(false)
const logs = ref([])
const total = ref(0)
const detailVisible = ref(false)
const currentLog = ref(null)

const queryParams = reactive({
  event_type: '',  // 默认为空，显示全部
  app_id: '',
  status: null,
  page: 1,
  page_size: 20
})

// 加载日志
const loadLogs = async () => {
  loading.value = true
  try {
    const res = await request({
      url: '/admin/event-logs',
      method: 'get',
      params: queryParams
    })
    logs.value = res.data
    total.value = res.total
  } catch (error) {
    console.error('加载失败:', error)
    ElMessage.error('加载日志失败')
  } finally {
    loading.value = false
  }
}

// 搜索
const handleSearch = () => {
  queryParams.page = 1
  loadLogs()
}

// 重置
const handleReset = () => {
  queryParams.event_type = ''
  queryParams.app_id = ''
  queryParams.status = null
  queryParams.page = 1
  loadLogs()
}

// 显示详情
const showDetail = (row) => {
  currentLog.value = row
  detailVisible.value = true
}

// 格式化JSON
const formatJson = (jsonStr) => {
  try {
    return JSON.stringify(JSON.parse(jsonStr), null, 2)
  } catch {
    return jsonStr
  }
}

// 获取事件类型文本
const getEventTypeText = (type) => {
  const map = {
    admin_login: '管理员登录',
    activate: '卡密激活',
    verify: '卡密验证',
    heartbeat: '心跳上报',
    app_create: '创建应用',
    app_delete: '删除应用',
    app_interface_config: '配置应用接口',
    kami_batch_create: '创建批次',
    kami_batch_delete: '删除批次',
    kami_generate: '生成卡密',
    kami_delete: '删除卡密',
    user_update: '更新用户',
    password_reset: '重置密码',
    user_delete: '删除用户'
  }
  return map[type] || type
}

// 获取事件类型标签颜色
const getEventTypeTag = (type) => {
  const map = {
    admin_login: 'primary',
    activate: 'success',
    verify: 'warning',
    heartbeat: 'info',
    app_create: 'success',
    app_delete: 'danger',
    app_interface_config: 'primary',
    kami_batch_create: 'success',
    kami_batch_delete: 'danger',
    kami_generate: 'success',
    kami_delete: 'danger',
    user_update: 'primary',
    password_reset: 'warning',
    user_delete: 'danger'
  }
  return map[type] || ''
}

onMounted(() => {
  loadLogs()
})
</script>

<style scoped>
.logs-container {
  height: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.filter-form {
  margin-bottom: 20px;
}
</style>
