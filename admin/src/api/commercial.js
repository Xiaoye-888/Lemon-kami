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
