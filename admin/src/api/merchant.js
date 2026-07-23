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

export function getMerchantRechargeOrders(params) {
  return request({
    url: '/merchant/recharge/orders',
    method: 'get',
    params
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

export function getMerchantAppSpecs(appId) {
  return request({
    url: `/merchant/apps/${appId}/specs`,
    method: 'get'
  })
}

export function issueMerchantKamis(appId, data) {
  return request({
    url: `/merchant/apps/${appId}/kamis/batch`,
    method: 'post',
    data
  })
}

export function getMerchantKamis(appId) {
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
