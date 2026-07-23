<template>
  <div class="recharge-page">
    <div class="page-toolbar">
      <h2>充值发卡额度</h2>
      <el-button :loading="loading" @click="loadConfig">刷新</el-button>
    </div>

    <section class="recharge-grid">
      <el-card shadow="never" class="panel">
        <template #header>支付方式</template>
        <el-radio-group v-model="form.channel" class="channel-list">
          <el-radio-button
            v-for="item in paymentChannels"
            :key="item.channel"
            :label="item.channel"
          >
            {{ item.display_name }}
          </el-radio-button>
        </el-radio-group>
        <div v-if="selectedChannel" class="qr-box">
          <img v-if="selectedChannel.qr_code_url" :src="selectedChannel.qr_code_url" alt="支付二维码" />
          <el-empty v-else description="管理员未配置二维码" />
        </div>
      </el-card>

      <el-card shadow="never" class="panel">
        <template #header>充值金额</template>
        <div class="option-grid">
          <button
            v-for="item in config.options"
            :key="item.id"
            type="button"
            :class="['amount-option', { active: form.option_id === item.id }]"
            @click="selectFixedOption(item)"
          >
            <strong>{{ item.amount }} 元</strong>
            <span>到账 {{ item.credit_quota }} 额度</span>
          </button>
        </div>
        <el-divider />
        <el-form label-width="96px">
          <el-form-item label="自定义金额">
            <el-input-number v-model="form.amount" :min="1" :max="1000000" style="width: 100%" @change="selectCustom" />
          </el-form-item>
          <el-form-item label="到账预览">
            <div class="preview-line">
              <span>基础 {{ customPreview.base_quota || 0 }}</span>
              <span>赠送 {{ customPreview.bonus_quota || 0 }}</span>
              <strong>合计 {{ customPreview.credit_quota || 0 }}</strong>
            </div>
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="form.remark" type="textarea" :rows="2" maxlength="200" />
          </el-form-item>
          <el-form-item label="支付凭证">
            <input type="file" accept="image/png,image/jpeg,image/webp" @change="handleProofFile" />
          </el-form-item>
        </el-form>
        <el-button type="primary" :loading="submitting" :disabled="!canSubmit" @click="submitOrder">提交充值订单</el-button>
      </el-card>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { createMerchantRechargeOrder, getMerchantRechargeConfig, previewMerchantRecharge } from '../api/merchant'

const loading = ref(false)
const submitting = ref(false)
const config = ref({ channels: [], options: [], bonus_rules: [] })
const customPreview = ref({})

const form = reactive({
  channel: '',
  mode: 'custom',
  option_id: null,
  amount: 10,
  remark: '',
  proof_image_data_url: ''
})

const paymentChannels = computed(() => config.value.channels || [])
const selectedChannel = computed(() => paymentChannels.value.find((item) => item.channel === form.channel))
const canSubmit = computed(() => form.channel && form.amount > 0 && form.proof_image_data_url)

function selectFixedOption(item) {
  form.mode = 'fixed'
  form.option_id = item.id
  form.amount = item.amount
  customPreview.value = {
    base_quota: item.credit_quota,
    bonus_quota: 0,
    credit_quota: item.credit_quota
  }
}

function selectCustom() {
  form.mode = 'custom'
  form.option_id = null
  loadPreview()
}

async function loadConfig() {
  loading.value = true
  try {
    const res = await getMerchantRechargeConfig()
    config.value = res.data || { channels: [], options: [], bonus_rules: [] }
    if (!form.channel && paymentChannels.value.length) form.channel = paymentChannels.value[0].channel
    await loadPreview()
  } finally {
    loading.value = false
  }
}

async function loadPreview() {
  if (form.mode !== 'custom' || !form.amount) return
  const res = await previewMerchantRecharge({ amount: form.amount, mode: 'custom' })
  customPreview.value = res.data || {}
}

function handleProofFile(event) {
  const file = event.target.files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    form.proof_image_data_url = String(reader.result || '')
  }
  reader.readAsDataURL(file)
}

async function submitOrder() {
  submitting.value = true
  try {
    const payload = {
      amount: form.amount,
      mode: form.mode,
      option_id: form.mode === 'fixed' ? form.option_id : null,
      channel: form.channel,
      remark: form.remark || null,
      proof_image_data_url: form.proof_image_data_url
    }
    await createMerchantRechargeOrder(payload)
    ElMessage.success('充值订单已提交')
    form.remark = ''
    form.proof_image_data_url = ''
  } finally {
    submitting.value = false
  }
}

watch(() => form.amount, () => {
  if (form.mode === 'custom') loadPreview()
})

onMounted(loadConfig)
</script>

<style scoped>
.recharge-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.page-toolbar h2 {
  margin: 0;
  font-size: 24px;
}

.recharge-grid {
  display: grid;
  grid-template-columns: minmax(320px, 420px) minmax(0, 1fr);
  gap: 16px;
}

.panel {
  border-radius: 8px;
}

.channel-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.qr-box {
  margin-top: 18px;
  min-height: 280px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fafc;
}

.qr-box img {
  max-width: 260px;
  max-height: 260px;
  object-fit: contain;
}

.option-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 10px;
}

.amount-option {
  min-height: 82px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #fff;
  color: #0f172a;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
}

.amount-option.active {
  border-color: #2f80ed;
  background: #eff6ff;
}

.preview-line {
  width: 100%;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

@media (max-width: 980px) {
  .recharge-grid {
    grid-template-columns: 1fr;
  }
}
</style>
