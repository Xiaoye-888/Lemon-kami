import request from '../utils/request'

export function getCommercialOverview() {
  return request({
    url: '/admin/commercial/overview',
    method: 'get'
  })
}

export function getRechargeConfig() {
  return request({
    url: '/admin/commercial/recharge-config',
    method: 'get'
  })
}

export function savePaymentChannel(data) {
  return request({
    url: '/admin/commercial/payment-channels',
    method: 'post',
    data
  })
}

export function savePaymentChannelWithUpload(data) {
  return request({
    url: '/admin/commercial/payment-channels/upload',
    method: 'post',
    data
  })
}

export function deletePaymentChannelQrCode(channel, confirmText) {
  return request({
    url: `/admin/commercial/payment-channels/${channel}/qrcode`,
    method: 'delete',
    params: { confirm_text: confirmText },
    data: { confirm_text: confirmText }
  })
}

export function saveRechargeOption(data) {
  return request({
    url: '/admin/commercial/recharge-options',
    method: 'post',
    data
  })
}

export function deleteRechargeOption(optionId, data = {}) {
  return request({
    url: `/admin/commercial/recharge-options/${optionId}`,
    method: 'delete',
    params: data,
    data
  })
}

export function saveBonusRule(data) {
  return request({
    url: '/admin/commercial/recharge-bonus-rules',
    method: 'post',
    data
  })
}

export function deleteBonusRule(ruleId, data = {}) {
  return request({
    url: `/admin/commercial/recharge-bonus-rules/${ruleId}`,
    method: 'delete',
    params: data,
    data
  })
}

export function getRechargeOrders(params) {
  return request({
    url: '/admin/commercial/recharge-orders',
    method: 'get',
    params
  })
}

export function getCommercialMerchants(params) {
  return request({
    url: '/admin/commercial/merchants',
    method: 'get',
    params
  })
}

export function getCommercialMerchantDetail(merchantId) {
  return request({
    url: `/admin/commercial/merchants/${merchantId}/detail`,
    method: 'get'
  })
}

export function getCommercialMerchantBatchApps(merchantId) {
  return request({
    url: `/admin/commercial/merchants/${merchantId}/batch-apps`,
    method: 'get'
  })
}

export function updateCommercialMerchantApp(merchantId, appId, data) {
  return request({
    url: `/admin/commercial/merchants/${merchantId}/apps/${appId}`,
    method: 'put',
    data
  })
}

export function deleteCommercialMerchantApp(merchantId, appId, data = {}) {
  return request({
    url: `/admin/commercial/merchants/${merchantId}/apps/${appId}`,
    method: 'delete',
    params: data,
    data
  })
}

export function getCommercialMerchantQuotas(merchantId) {
  return request({
    url: `/admin/commercial/merchants/${merchantId}/quotas`,
    method: 'get'
  })
}

export function getCommercialMerchantAppSpecs(merchantId, appId, params) {
  return request({
    url: `/admin/commercial/merchants/${merchantId}/apps/${appId}/specs`,
    method: 'get',
    params
  })
}

export function createCommercialMerchantAppSpec(merchantId, appId, data) {
  return request({
    url: `/admin/commercial/merchants/${merchantId}/apps/${appId}/specs`,
    method: 'post',
    data
  })
}

export function updateCommercialMerchantAppSpec(merchantId, appId, specId, data) {
  return request({
    url: `/admin/commercial/merchants/${merchantId}/apps/${appId}/specs/${specId}`,
    method: 'put',
    data
  })
}

export function deleteCommercialMerchantAppSpec(merchantId, appId, specId) {
  return request({
    url: `/admin/commercial/merchants/${merchantId}/apps/${appId}/specs/${specId}`,
    method: 'delete'
  })
}

export function issueCommercialMerchantKamis(merchantId, appId, data) {
  return request({
    url: `/admin/commercial/merchants/${merchantId}/apps/${appId}/kamis/batch`,
    method: 'post',
    data
  })
}

export function previewCommercialMerchantKamis(merchantId, appId, data) {
  return request({
    url: `/admin/commercial/merchants/${merchantId}/apps/${appId}/kamis/preview`,
    method: 'post',
    data
  })
}

export function getCommercialMerchantKamis(merchantId, params) {
  return request({
    url: `/admin/commercial/merchants/${merchantId}/kamis`,
    method: 'get',
    params
  })
}

export function exportCommercialMerchantKamis(merchantId, params) {
  return request({
    url: `/admin/commercial/merchants/${merchantId}/kamis/export`,
    method: 'get',
    params,
    responseType: 'blob'
  })
}

export function deleteCommercialMerchantKamis(merchantId, data) {
  return request({
    url: `/admin/commercial/merchants/${merchantId}/kamis/delete`,
    method: 'post',
    data
  })
}

export function getCommercialMerchantBatches(merchantId, appId) {
  return request({
    url: `/admin/commercial/merchants/${merchantId}/apps/${appId}/batches`,
    method: 'get'
  })
}

export function getCommercialMerchantSpecBatches(merchantId, specId) {
  return request({
    url: `/admin/commercial/merchants/${merchantId}/kami-specs/${specId}/batches`,
    method: 'get'
  })
}

export function getCommercialMerchantSpecKamis(merchantId, specId, params) {
  return request({
    url: `/admin/commercial/merchants/${merchantId}/kami-specs/${specId}/kamis`,
    method: 'get',
    params
  })
}

export function getCommercialMerchantBatchKamis(merchantId, batchId, params) {
  return request({
    url: `/admin/commercial/merchants/${merchantId}/batches/${batchId}/kamis`,
    method: 'get',
    params
  })
}

export function updateCommercialMerchantBatch(merchantId, batchId, data) {
  return request({
    url: `/admin/commercial/merchants/${merchantId}/batches/${batchId}`,
    method: 'put',
    data
  })
}

export function deleteCommercialMerchantBatch(merchantId, batchId) {
  return request({
    url: `/admin/commercial/merchants/${merchantId}/batches/${batchId}`,
    method: 'delete'
  })
}

export function appendCommercialMerchantBatchKamis(merchantId, batchId, data) {
  return request({
    url: `/admin/commercial/merchants/${merchantId}/batches/${batchId}/append`,
    method: 'post',
    data
  })
}

export function approveRechargeOrder(orderNo, data = {}) {
  return request({
    url: `/admin/commercial/recharge-orders/${orderNo}/approve`,
    method: 'post',
    data
  })
}

export function rejectRechargeOrder(orderNo, data = {}) {
  return request({
    url: `/admin/commercial/recharge-orders/${orderNo}/reject`,
    method: 'post',
    data
  })
}

export function markRechargeOrderAbnormal(orderNo, data = {}) {
  return request({
    url: `/admin/commercial/recharge-orders/${orderNo}/abnormal`,
    method: 'post',
    data
  })
}

export function expireRechargeOrder(orderNo, data = {}) {
  return request({
    url: `/admin/commercial/recharge-orders/${orderNo}/expire`,
    method: 'post',
    data
  })
}

export function cleanupRechargeProofs(data = {}) {
  return request({
    url: '/admin/commercial/recharge-proofs/cleanup',
    method: 'post',
    data
  })
}

export function getCommercialQuotaTransactions(params) {
  return request({
    url: '/admin/commercial/quota-transactions',
    method: 'get',
    params
  })
}

export function getAdminAuditLogs(params) {
  return request({
    url: '/admin/commercial/audit-logs',
    method: 'get',
    params
  })
}

export function getIssuePricingRules() {
  return request({
    url: '/admin/commercial/issue-pricing/rules',
    method: 'get'
  })
}

export function saveIssuePricingRule(data) {
  return request({
    url: '/admin/commercial/issue-pricing/rules',
    method: 'post',
    data
  })
}

export function deleteIssuePricingRule(ruleId, data = {}) {
  return request({
    url: `/admin/commercial/issue-pricing/rules/${ruleId}`,
    method: 'delete',
    data
  })
}
