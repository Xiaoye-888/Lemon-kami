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

export function saveRechargeOption(data) {
  return request({
    url: '/admin/commercial/recharge-options',
    method: 'post',
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

export function getRechargeOrders(params) {
  return request({
    url: '/admin/commercial/recharge-orders',
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

export function getCommercialQuotaTransactions(params) {
  return request({
    url: '/admin/commercial/quota-transactions',
    method: 'get',
    params
  })
}
