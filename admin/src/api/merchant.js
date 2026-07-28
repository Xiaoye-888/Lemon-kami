import request from '../utils/request'

export function getMerchantMe() {
  return request({
    url: '/merchant/me',
    method: 'get'
  })
}

export function getMerchantQuotas() {
  return request({
    url: '/merchant/quotas',
    method: 'get'
  })
}

export function getMerchantDashboard() {
  return request({
    url: '/merchant/dashboard',
    method: 'get'
  })
}

export function getMerchantQuotaTransactions(params) {
  return request({
    url: '/merchant/quota-transactions',
    method: 'get',
    params
  })
}

export function getMerchantRechargeConfig() {
  return request({
    url: '/merchant/recharge/config',
    method: 'get'
  })
}

export function previewMerchantRecharge(data) {
  return request({
    url: '/merchant/recharge/preview',
    method: 'post',
    data
  })
}

export function createMerchantRechargeOrder(data) {
  return request({
    url: '/merchant/recharge/orders',
    method: 'post',
    data
  })
}

export function createMerchantRechargeOrderUpload(data) {
  return request({
    url: '/merchant/recharge/orders/upload',
    method: 'post',
    data
  })
}

export function getMerchantRechargeOrders(params) {
  return request({
    url: '/merchant/recharge/orders',
    method: 'get',
    params
  })
}

export function cancelMerchantRechargeOrder(orderNo, data = {}) {
  return request({
    url: `/merchant/recharge/orders/${orderNo}/cancel`,
    method: 'post',
    data
  })
}

export function getMerchantApps() {
  return request({
    url: '/merchant/apps',
    method: 'get'
  })
}

export function createMerchantApp(data) {
  return request({
    url: '/merchant/apps',
    method: 'post',
    data
  })
}

export function getMerchantAppDetail(appId) {
  return request({
    url: `/merchant/apps/${appId}`,
    method: 'get'
  })
}

export function updateMerchantApp(appId, data) {
  return request({
    url: `/merchant/apps/${appId}`,
    method: 'put',
    data
  })
}

export function deleteMerchantApp(appId) {
  return request({
    url: `/merchant/apps/${appId}`,
    method: 'delete'
  })
}

export function getMerchantAppInterfaces(appId) {
  return request({
    url: `/merchant/apps/${appId}/interfaces`,
    method: 'get'
  })
}

export function updateMerchantAppInterface(appId, interfaceId, data) {
  return request({
    url: `/merchant/apps/${appId}/interfaces/${interfaceId}`,
    method: 'put',
    data
  })
}

export function getMerchantAppSpecs(appId, params) {
  return request({
    url: `/merchant/apps/${appId}/specs`,
    method: 'get',
    params
  })
}

export function createMerchantAppSpec(appId, data) {
  return request({
    url: `/merchant/apps/${appId}/specs`,
    method: 'post',
    data
  })
}

export function updateMerchantAppSpec(appId, specId, data) {
  return request({
    url: `/merchant/apps/${appId}/specs/${specId}`,
    method: 'put',
    data
  })
}

export function deleteMerchantAppSpec(appId, specId) {
  return request({
    url: `/merchant/apps/${appId}/specs/${specId}`,
    method: 'delete'
  })
}

export function issueMerchantKamis(appId, data) {
  return request({
    url: `/merchant/apps/${appId}/kamis/batch`,
    method: 'post',
    data
  })
}

export function previewMerchantKamis(appId, data) {
  return request({
    url: `/merchant/apps/${appId}/kamis/preview`,
    method: 'post',
    data
  })
}

export function getMerchantKamis(params) {
  return request({
    url: '/merchant/kamis',
    method: 'get',
    params
  })
}

export function exportMerchantKamis(params) {
  return request({
    url: '/merchant/kamis/export',
    method: 'get',
    params,
    responseType: 'blob'
  })
}

export function getMerchantAppKamis(appId) {
  return request({
    url: `/merchant/apps/${appId}/kamis`,
    method: 'get'
  })
}

export function getMerchantBatches(appId) {
  return request({
    url: `/merchant/apps/${appId}/batches`,
    method: 'get'
  })
}

export function getMerchantSpecBatches(specId) {
  return request({
    url: `/merchant/kami-specs/${specId}/batches`,
    method: 'get'
  })
}

export function getMerchantSpecKamis(specId, params) {
  return request({
    url: `/merchant/kami-specs/${specId}/kamis`,
    method: 'get',
    params
  })
}

export function getMerchantBatchKamis(batchId, params) {
  return request({
    url: `/merchant/batches/${batchId}/kamis`,
    method: 'get',
    params
  })
}

export function updateMerchantBatch(batchId, data) {
  return request({
    url: `/merchant/batches/${batchId}`,
    method: 'put',
    data
  })
}

export function deleteMerchantBatch(batchId) {
  return request({
    url: `/merchant/batches/${batchId}`,
    method: 'delete'
  })
}

export function appendMerchantBatchKamis(batchId, data) {
  return request({
    url: `/merchant/batches/${batchId}/append`,
    method: 'post',
    data
  })
}
