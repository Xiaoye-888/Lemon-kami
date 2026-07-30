<template>
  <div class="devices-container">
    <el-card>
      <template #header>
        <span>设备管理</span>
      </template>

      <el-form :inline="true" :model="queryParams" class="filter-form">
        <el-form-item label="应用">
          <el-select v-model="queryParams.app_id" placeholder="全部应用" clearable style="width: 200px" @change="handleFilterChange">
            <el-option label="全部应用" value="" />
            <el-option
              v-for="app in apps"
              :key="app.app_id"
              :label="app.name"
              :value="app.app_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="搜索">
          <el-input
            v-model="queryParams.keyword"
            placeholder="搜索卡密/设备信息"
            clearable
            style="width: 240px"
            @keyup.enter="handleFilterChange"
            @clear="handleFilterChange"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleFilterChange">查询</el-button>
        </el-form-item>
      </el-form>

      <el-table
        :data="devices"
        v-loading="loading"
        element-loading-custom-class="yz-bounce"
        border
        stripe
      >
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="app_name" label="应用" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.app_name || row.app_id || '-' }}</template>
        </el-table-column>
        <el-table-column prop="device_name" label="设备名称" min-width="170" show-overflow-tooltip>
          <template #default="{ row }">
            {{ deviceInfoText(row.device_name) }}
          </template>
        </el-table-column>
        <el-table-column prop="device_model" label="设备型号" min-width="190" show-overflow-tooltip>
          <template #default="{ row }">
            {{ deviceInfoText(row.device_model) }}
          </template>
        </el-table-column>
        <el-table-column prop="device_id" label="设备 ID" min-width="250" show-overflow-tooltip>
          <template #default="{ row }">
            {{ deviceInfoText(row.device_id) }}
          </template>
        </el-table-column>
        <el-table-column label="关联卡密" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="device-code">{{ getDeviceKamiText(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="username" label="用户名" width="140">
          <template #default="{ row }">{{ row.username || '-' }}</template>
        </el-table-column>
        <el-table-column prop="binding_relation" label="绑定关系" width="120">
          <template #default="{ row }">{{ row.binding_relation || '-' }}</template>
        </el-table-column>
        <el-table-column prop="machine_bind_mode_text" label="设备策略" width="150">
          <template #default="{ row }">
            <span class="clickable-text" @click="openDeviceDetail(row)">{{ getDevicePolicyText(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="device_count" label="使用设备" width="110">
          <template #default="{ row }">
            {{ getDeviceCountText(row) }}
          </template>
        </el-table-column>
        <el-table-column prop="last_ip" label="IP地址" width="150">
          <template #default="{ row }">{{ row.last_ip || '-' }}</template>
        </el-table-column>
        <el-table-column prop="risk_level" label="风险等级" width="120">
          <template #default="{ row }">
            <el-tag :type="getRiskType(row.risk_level)">
              {{ getRiskText(row) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="!isMerchantConsole" label="操作" width="270" fixed="right">
          <template #default="{ row }">
            <el-button
              size="small"
              type="success"
              :disabled="!canManageDeviceRisk(row) || row.risk_level === 0"
              @click="updateRisk(row, 0)"
            >
              恢复正常
            </el-button>
            <el-button
              size="small"
              type="warning"
              :disabled="!canManageDeviceRisk(row) || row.risk_level === 1"
              @click="updateRisk(row, 1)"
            >
              警告
            </el-button>
            <el-button
              size="small"
              type="danger"
              :disabled="!canManageDeviceRisk(row) || row.risk_level === 2"
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

    <el-dialog v-model="deviceDetailVisible" :title="deviceDetailTitle" width="980px" class="device-detail-dialog">
      <div v-if="selectedDeviceGroup" class="detail-meta">
        <span>卡密 <strong>{{ getDeviceKamiText(selectedDeviceGroup) }}</strong></span>
        <span>策略 <strong>{{ getDevicePolicyText(selectedDeviceGroup) }}</strong></span>
        <span>总设备 <strong>{{ getDeviceCountText(selectedDeviceGroup) }}</strong></span>
        <span>其他设备 <strong>{{ getDetailDeviceCountText(selectedDeviceGroup) }}</strong></span>
      </div>
      <el-table :data="selectedDeviceItems" border stripe empty-text="暂无其他设备">
        <el-table-column label="设备名称" min-width="170" show-overflow-tooltip>
          <template #default="{ row: device }">{{ deviceInfoText(device.device_name) }}</template>
        </el-table-column>
        <el-table-column label="设备型号" min-width="190" show-overflow-tooltip>
          <template #default="{ row: device }">{{ deviceInfoText(device.device_model) }}</template>
        </el-table-column>
        <el-table-column label="设备 ID" min-width="250" show-overflow-tooltip>
          <template #default="{ row: device }">{{ deviceInfoText(device.device_id) }}</template>
        </el-table-column>
        <el-table-column label="IP地址" width="150">
          <template #default="{ row: device }">{{ device.last_ip || '-' }}</template>
        </el-table-column>
        <el-table-column label="风险等级" width="120">
          <template #default="{ row: device }">
            <el-tag :type="getRiskType(device.risk_level)">{{ getRiskText(device) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="!isMerchantConsole" label="操作" width="270" fixed="right">
          <template #default="{ row: device }">
            <el-button
              size="small"
              type="success"
              :disabled="!canManageDeviceRisk(device) || device.risk_level === 0"
              @click="updateRisk(device, 0)"
            >
              恢复正常
            </el-button>
            <el-button
              size="small"
              type="warning"
              :disabled="!canManageDeviceRisk(device) || device.risk_level === 1"
              @click="updateRisk(device, 1)"
            >
              警告
            </el-button>
            <el-button
              size="small"
              type="danger"
              :disabled="!canManageDeviceRisk(device) || device.risk_level === 2"
              @click="updateRisk(device, 2)"
            >
              黑名单
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getDevices, getMerchantDevices, updateDeviceRisk } from '../api/device'
import { getApps } from '../api/admin'
import { getMerchantApps } from '../api/merchant'

const loading = ref(false)
const devices = ref([])
const apps = ref([])
const total = ref(0)
const route = useRoute()
const isMerchantConsole = computed(() => route.path.startsWith('/merchant'))
const deviceDetailVisible = ref(false)
const selectedDeviceGroup = ref(null)
const selectedGroupKey = ref('')

const queryParams = reactive({
  app_id: '',  // 默认为空，显示全部
  keyword: '',
  page: 1,
  page_size: 20
})

const selectedDeviceItems = computed(() => selectedDeviceGroup.value?.device_items || [])
const deviceDetailTitle = computed(() => {
  const code = selectedDeviceGroup.value ? getDeviceKamiText(selectedDeviceGroup.value) : ''
  return code && code !== '-' ? `设备明细 - ${code}` : '设备明细'
})

const loadApps = async () => {
  try {
    const res = isMerchantConsole.value ? await getMerchantApps() : await getApps()
    apps.value = res.data
  } catch (error) {
    console.error('加载应用失败:', error)
    ElMessage.error('加载应用列表失败')
  }
}

const groupIdentity = (row) => row?.group_key || row?.kami_code || row?.id

const syncSelectedDeviceGroup = () => {
  if (!deviceDetailVisible.value || !selectedGroupKey.value) return
  const nextGroup = devices.value.find((row) => groupIdentity(row) === selectedGroupKey.value)
  if (nextGroup) selectedDeviceGroup.value = nextGroup
}

const loadDevices = async () => {
  loading.value = true
  try {
    const res = isMerchantConsole.value ? await getMerchantDevices(queryParams) : await getDevices(queryParams)
    devices.value = res.data.items || []
    total.value = res.data.total ?? devices.value.length
    syncSelectedDeviceGroup()
  } catch (error) {
    console.error('加载失败:', error)
    ElMessage.error('加载设备列表失败')
  } finally {
    loading.value = false
  }
}

const handleFilterChange = () => {
  queryParams.page = 1
  loadDevices()
}

const openDeviceDetail = (row) => {
  selectedDeviceGroup.value = row
  selectedGroupKey.value = groupIdentity(row)
  deviceDetailVisible.value = true
}

const deviceInfoText = (value) => value || '等待新版SDK上报'

const getDeviceKamiText = (row) => {
  const codes = Array.isArray(row?.kami_codes) ? row.kami_codes.filter(Boolean) : []
  if (codes.length === 1) return codes[0]
  if (codes.length > 1) return `${codes[0]} 等 ${codes.length} 个`
  return row?.kami_code || '-'
}

const getDevicePolicyText = (row) => row?.machine_bind_mode_text || '-'

const getDeviceCountText = (row) => {
  const count = row?.device_count ?? (Array.isArray(row?.device_items) ? row.device_items.length : 0)
  return count ? `${count}台` : '-'
}

const getDetailDeviceCountText = (row) => {
  const count = row?.detail_device_count ?? (Array.isArray(row?.device_items) ? row.device_items.length : 0)
  return `${count}台`
}

const getDeviceIdentityText = (row) => (
  row?.device_name || row?.device_model || row?.device_id || row?.last_ip || '该设备'
)

const canManageDeviceRisk = (row) => Number.isInteger(Number(row?.id))

const updateRisk = async (row, level) => {
  if (isMerchantConsole.value || !canManageDeviceRisk(row)) return
  const levelText = { 0: '恢复正常', 1: '警告', 2: '黑名单' }
  const targetText = getDeviceIdentityText(row)
  const confirmText = {
    0: `确定要将设备 "${targetText}" 恢复正常吗？`,
    1: `确定要将设备 "${targetText}" 设置为警告状态吗？`,
    2: `确定要将设备 "${targetText}" 加入黑名单吗？仅影响该设备/IP，不影响同一卡密的其他设备。`
  }

  try {
    await ElMessageBox.confirm(confirmText[level], '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: level === 2 ? 'warning' : 'info'
    })

    await updateDeviceRisk(row.id, level)
    ElMessage.success(`${levelText[level]}成功`)
    await loadDevices()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
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

.clickable-text {
  color: #2f7df6;
  cursor: pointer;
  line-height: 1.5;
}

.clickable-text:hover {
  color: #1b5fd6;
  text-decoration: underline;
}

.device-code {
  font-weight: 600;
}

.detail-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 24px;
  margin-bottom: 14px;
  color: #607089;
}

.detail-meta strong {
  color: #0f172a;
  font-weight: 700;
}
</style>
