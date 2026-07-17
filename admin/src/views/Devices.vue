<template>
  <div class="devices-container">
    <el-card>
      <template #header>
        <span>设备管理</span>
      </template>

      <el-form :inline="true" :model="queryParams" class="filter-form">
        <el-form-item label="应用">
          <el-select v-model="queryParams.app_id" placeholder="选择应用" style="width: 200px" @change="loadDevices">
            <el-option
              v-for="app in apps"
              :key="app.app_id"
              :label="app.name"
              :value="app.app_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadDevices">查询</el-button>
        </el-form-item>
      </el-form>

      <!-- 提示：未选择应用 -->
      <el-empty v-if="!queryParams.app_id" description="请先选择应用" />

      <!-- 设备表格 -->
      <el-table
        v-else
        :data="devices"
        v-loading="loading"
        element-loading-custom-class="yz-bounce"
        border
        stripe
      >
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="uuid" label="设备UUID" min-width="200" show-overflow-tooltip />
        <el-table-column prop="fingerprint" label="指纹" min-width="200" show-overflow-tooltip />
        <el-table-column prop="username" label="用户名" width="140">
          <template #default="{ row }">{{ row.username || '-' }}</template>
        </el-table-column>
        <el-table-column prop="binding_relation" label="绑定关系" width="120">
          <template #default="{ row }">{{ row.binding_relation || '-' }}</template>
        </el-table-column>
        <el-table-column prop="machine_bind_mode_text" label="设备策略" width="130">
          <template #default="{ row }">{{ row.machine_bind_mode_text || '-' }}</template>
        </el-table-column>
        <el-table-column prop="last_ip" label="IP地址" width="150" />
        <el-table-column prop="ip_count" label="IP数量" width="100" />
        <el-table-column prop="risk_level" label="风险等级" width="120">
          <template #default="{ row }">
            <el-tag :type="getRiskType(row.risk_level)">
              {{ getRiskText(row) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button 
              size="small" 
              type="success" 
              :disabled="row.risk_level === 0"
              @click="updateRisk(row, 0)"
            >
              恢复正常
            </el-button>
            <el-button 
              size="small" 
              type="warning" 
              :disabled="row.risk_level === 1"
              @click="updateRisk(row, 1)"
            >
              警告
            </el-button>
            <el-button 
              size="small" 
              type="danger" 
              :disabled="row.risk_level === 2"
              @click="updateRisk(row, 2)"
            >
              黑名单
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="queryParams.page"
        v-model:page-size="queryParams.page_size"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="loadDevices"
        style="margin-top: 20px; justify-content: flex-end"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getDevices, updateDeviceRisk } from '../api/device'
import { getApps } from '../api/admin'

const loading = ref(false)
const devices = ref([])
const apps = ref([])
const total = ref(0)

const queryParams = reactive({
  app_id: '',  // 默认为空，显示全部
  page: 1,
  page_size: 20
})

const loadApps = async () => {
  try {
    const res = await getApps()
    apps.value = res.data
    
    // 如果有应用且当前没有选择，自动选择第一个
    if (apps.value.length > 0 && !queryParams.app_id) {
      queryParams.app_id = apps.value[0].app_id
      // 自动加载设备
      await loadDevices()
    }
  } catch (error) {
    console.error('加载应用失败:', error)
    ElMessage.error('加载应用列表失败')
  }
}

const loadDevices = async () => {
  if (!queryParams.app_id) {
    devices.value = []
    total.value = 0
    return
  }
  
  loading.value = true
  try {
    const res = await getDevices(queryParams)
    devices.value = res.data.items || []
    total.value = res.data.total ?? devices.value.length
  } catch (error) {
    console.error('加载失败:', error)
    ElMessage.error('加载设备列表失败')
  } finally {
    loading.value = false
  }
}

const updateRisk = async (row, level) => {
  const levelText = { 0: '恢复正常', 1: '警告', 2: '黑名单' }
  const confirmText = {
    0: `确定要将设备 "${row.uuid}" 恢复正常吗？`,
    1: `确定要将设备 "${row.uuid}" 设置为警告状态吗？`,
    2: `确定要将设备 "${row.uuid}" 加入黑名单吗？这将禁止该设备使用所有卡密。`
  }
  
  try {
    await ElMessageBox.confirm(confirmText[level], '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: level === 2 ? 'warning' : 'info'
    })
    
    await updateDeviceRisk(row.id, level)
    ElMessage.success(`${levelText[level]}成功`)
    loadDevices()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('更新失败:', error)
      ElMessage.error('更新失败')
    }
  }
}

const getRiskText = (row) => {
  if (row?.risk_level_text) return row.risk_level_text
  const level = row?.risk_level
  const map = { 0: '正常', 1: '警告', 2: '黑名单' }
  return map[level] || '未知'
}

const getRiskType = (level) => {
  const map = { 0: 'success', 1: 'warning', 2: 'danger' }
  return map[level] || ''
}

onMounted(() => {
  loadApps()
  loadDevices()
})
</script>

<style scoped>
.devices-container {
  height: 100%;
}

.filter-form {
  margin-bottom: 20px;
}
</style>
