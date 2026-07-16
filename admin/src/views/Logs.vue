<template>
  <div class="logs-container">
    <el-card>
      <template #header>
        <span>行为日志</span>
      </template>

      <el-form :inline="true" :model="queryParams" class="filter-form">
        <el-form-item label="应用">
          <el-select v-model="queryParams.app_id" placeholder="选择应用" style="width: 200px">
            <el-option
              v-for="app in apps"
              :key="app.app_id"
              :label="app.name"
              :value="app.app_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="事件类型">
          <el-input v-model="queryParams.event_type" placeholder="如: login" clearable style="width: 150px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadLogs">查询</el-button>
        </el-form-item>
      </el-form>

      <el-table
        :data="logs"
        v-loading="loading"
        element-loading-custom-class="yz-bounce"
        border
        stripe
      >
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="kami_code" label="卡密" width="180" />
        <el-table-column prop="event_type" label="事件类型" width="150" />
        <el-table-column prop="payload" label="数据" min-width="250" show-overflow-tooltip />
        <el-table-column prop="created_at" label="时间" width="180">
          <template #default="{ row }">
            {{ formatBeijingTime(row.created_at) }}
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="queryParams.page"
        v-model:page-size="queryParams.page_size"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="loadLogs"
        style="margin-top: 20px; justify-content: flex-end"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getEventLogs } from '../api/device'
import { getApps } from '../api/admin'
import { formatBeijingTime } from '../utils/datetime'

const loading = ref(false)
const logs = ref([])
const apps = ref([])
const total = ref(0)

const queryParams = reactive({
  app_id: '',
  event_type: '',
  page: 1,
  page_size: 20
})

const loadApps = async () => {
  try {
    const res = await getApps()
    apps.value = res.data
    if (apps.value.length > 0) {
      queryParams.app_id = apps.value[0].app_id
    }
  } catch (error) {
    console.error('加载应用失败:', error)
  }
}

const loadLogs = async () => {
  if (!queryParams.app_id) return

  loading.value = true
  try {
    const res = await getEventLogs(queryParams)
    logs.value = res.data.items
    total.value = res.data.items.length
  } catch (error) {
    console.error('加载失败:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadApps()
  loadLogs()
})
</script>

<style scoped>
.logs-container {
  height: 100%;
}

.filter-form {
  margin-bottom: 20px;
}
</style>
