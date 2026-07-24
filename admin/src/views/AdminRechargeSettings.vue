<template>
  <div class="settings-page">
    <div class="page-toolbar">
      <h2>充值配置</h2>
      <el-button type="primary" :loading="loading" @click="loadConfig">刷新</el-button>
    </div>

    <section class="settings-grid">
      <el-card shadow="never" class="panel">
        <template #header>支付二维码</template>
        <el-form :model="channelForm" label-width="96px">
          <el-form-item label="渠道">
            <el-select v-model="channelForm.channel" style="width: 100%">
              <el-option label="微信" value="wechat" />
              <el-option label="支付宝" value="alipay" />
            </el-select>
          </el-form-item>
          <el-form-item label="显示名称">
            <el-input v-model="channelForm.display_name" />
          </el-form-item>
          <el-form-item label="二维码地址">
            <el-input v-model="channelForm.qr_code_url" />
          </el-form-item>
          <el-form-item label="二维码图片">
            <div class="file-input-row">
              <input ref="qrFileInput" type="file" accept="image/png,image/jpeg,image/webp" @change="handleQrFile" />
              <span v-if="channelForm.qr_code_file" class="file-name">{{ channelForm.qr_code_file.name }}</span>
            </div>
            <div v-if="qrPreviewUrl || channelForm.qr_code_url" class="qr-preview">
              <img :src="qrPreviewUrl || channelForm.qr_code_url" alt="payment QR code" />
            </div>
          </el-form-item>
          <el-form-item label="收款备注">
            <el-input v-model="channelForm.remark" />
          </el-form-item>
          <el-button type="primary" :loading="savingChannel" @click="handleSavePaymentChannel">保存渠道</el-button>
        </el-form>
      </el-card>

      <el-card shadow="never" class="panel">
        <template #header>固定充值档位</template>
        <el-form :model="optionForm" label-width="96px">
          <el-form-item label="充值金额">
            <el-input-number v-model="optionForm.amount" :min="1" :max="1000000" style="width: 100%" />
          </el-form-item>
          <el-form-item label="到账额度">
            <el-input-number v-model="optionForm.credit_quota" :min="1" :max="100000000" style="width: 100%" />
          </el-form-item>
          <el-form-item label="排序">
            <el-input-number v-model="optionForm.sort_order" :min="0" :max="9999" style="width: 100%" />
          </el-form-item>
          <el-button type="primary" :loading="savingOption" @click="handleSaveRechargeOption">保存固定额度</el-button>
        </el-form>
      </el-card>

      <el-card shadow="never" class="panel">
        <template #header>自定义额度赠送</template>
        <el-form :model="bonusForm" label-width="96px">
          <el-form-item label="满多少元">
            <el-input-number v-model="bonusForm.threshold_amount" :min="1" :max="1000000" style="width: 100%" />
          </el-form-item>
          <el-form-item label="赠送额度">
            <el-input-number v-model="bonusForm.bonus_quota" :min="1" :max="100000000" style="width: 100%" />
          </el-form-item>
          <el-form-item label="排序">
            <el-input-number v-model="bonusForm.sort_order" :min="0" :max="9999" style="width: 100%" />
          </el-form-item>
          <el-button type="primary" :loading="savingBonus" @click="handleSaveBonusRule">保存赠送规则</el-button>
        </el-form>
      </el-card>
    </section>

    <section class="list-grid">
      <el-card shadow="never" class="panel">
        <template #header>当前支付渠道</template>
        <el-table :data="config.channels" size="small">
          <el-table-column prop="display_name" label="名称" />
          <el-table-column prop="channel" label="渠道" width="90" />
          <el-table-column prop="enabled" label="状态" width="90">
            <template #default="{ row }">{{ row.enabled ? '启用' : '停用' }}</template>
          </el-table-column>
        </el-table>
      </el-card>
      <el-card shadow="never" class="panel">
        <template #header>当前充值档位</template>
        <el-table :data="config.options" size="small">
          <el-table-column prop="label" label="展示" />
          <el-table-column prop="credit_quota" label="到账额度" width="100" />
        </el-table>
      </el-card>
      <el-card shadow="never" class="panel">
        <template #header>当前赠送规则</template>
        <el-table :data="config.bonus_rules" size="small">
          <el-table-column prop="threshold_amount" label="门槛" width="90" />
          <el-table-column prop="bonus_quota" label="赠送额度" width="110" />
        </el-table>
      </el-card>
    </section>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getRechargeConfig, saveBonusRule, savePaymentChannelWithUpload, saveRechargeOption } from '../api/commercial'

const loading = ref(false)
const savingChannel = ref(false)
const savingOption = ref(false)
const savingBonus = ref(false)
const config = ref({ channels: [], options: [], bonus_rules: [] })
const qrFileInput = ref(null)
const qrPreviewUrl = ref('')

const IMAGE_TYPES = new Set(['image/png', 'image/jpeg', 'image/webp'])
const MAX_QR_FILE_SIZE = 2 * 1024 * 1024

const channelForm = reactive({
  channel: 'wechat',
  display_name: '微信收款',
  qr_code_url: '',
  qr_code_file: null,
  remark: '',
  enabled: true,
  sort_order: 1
})

const optionForm = reactive({
  amount: 10,
  credit_quota: 10,
  enabled: true,
  sort_order: 1
})

const bonusForm = reactive({
  threshold_amount: 300,
  bonus_quota: 50,
  enabled: true,
  sort_order: 1
})

async function loadConfig() {
  loading.value = true
  try {
    const res = await getRechargeConfig()
    config.value = res.data || { channels: [], options: [], bonus_rules: [] }
  } finally {
    loading.value = false
  }
}

function clearQrPreview() {
  if (qrPreviewUrl.value) {
    URL.revokeObjectURL(qrPreviewUrl.value)
    qrPreviewUrl.value = ''
  }
}

function handleQrFile(event) {
  const file = event.target.files?.[0]
  if (!file) {
    channelForm.qr_code_file = null
    clearQrPreview()
    return
  }
  if (!IMAGE_TYPES.has(file.type)) {
    ElMessage.error('请上传 PNG/JPG/WebP 图片')
    event.target.value = ''
    channelForm.qr_code_file = null
    clearQrPreview()
    return
  }
  if (file.size > MAX_QR_FILE_SIZE) {
    ElMessage.error('支付二维码不能超过 2MB')
    event.target.value = ''
    channelForm.qr_code_file = null
    clearQrPreview()
    return
  }
  channelForm.qr_code_file = file
  clearQrPreview()
  qrPreviewUrl.value = URL.createObjectURL(file)
}

function channelPayloadFormData() {
  const payload = new FormData()
  payload.append('channel', channelForm.channel)
  payload.append('display_name', channelForm.display_name)
  payload.append('qr_code_url', channelForm.qr_code_url || '')
  payload.append('enabled', String(channelForm.enabled))
  payload.append('sort_order', String(channelForm.sort_order || 0))
  if (channelForm.remark) {
    payload.append('remark', channelForm.remark)
  }
  if (channelForm.qr_code_file) {
    payload.append('qr_code_file', channelForm.qr_code_file)
  }
  return payload
}

async function handleSavePaymentChannel() {
  savingChannel.value = true
  try {
    const res = await savePaymentChannelWithUpload(channelPayloadFormData())
    channelForm.qr_code_url = res.data?.qr_code_url || channelForm.qr_code_url
    channelForm.qr_code_file = null
    if (qrFileInput.value) qrFileInput.value.value = ''
    clearQrPreview()
    ElMessage.success('支付渠道已保存')
    await loadConfig()
  } finally {
    savingChannel.value = false
  }
}

async function handleSaveRechargeOption() {
  savingOption.value = true
  try {
    await saveRechargeOption(optionForm)
    ElMessage.success('固定充值档位已保存')
    await loadConfig()
  } finally {
    savingOption.value = false
  }
}

async function handleSaveBonusRule() {
  savingBonus.value = true
  try {
    await saveBonusRule(bonusForm)
    ElMessage.success('赠送规则已保存')
    await loadConfig()
  } finally {
    savingBonus.value = false
  }
}

onMounted(loadConfig)
onUnmounted(clearQrPreview)
</script>

<style scoped>
.settings-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.page-toolbar h2 {
  margin: 0;
  font-size: 24px;
}

.settings-grid,
.list-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.panel {
  border-radius: 8px;
}

.file-input-row {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.file-name {
  max-width: 220px;
  color: #475569;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.qr-preview {
  margin-top: 10px;
  width: 180px;
  height: 180px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fafc;
  display: flex;
  align-items: center;
  justify-content: center;
}

.qr-preview img {
  max-width: 160px;
  max-height: 160px;
  object-fit: contain;
}

@media (max-width: 1180px) {
  .settings-grid,
  .list-grid {
    grid-template-columns: 1fr;
  }
}
</style>
