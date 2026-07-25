import request from '../utils/request'

export function getFinanceSummary(params) {
  return request({
    url: '/admin/commercial/finance/summary',
    method: 'get',
    params
  })
}

export function getMerchantRechargeRanking(params) {
  return request({
    url: '/admin/commercial/finance/merchant-ranking',
    method: 'get',
    params
  })
}

export function exportRechargeOrders(params) {
  return request({
    url: '/admin/commercial/recharge-orders/export',
    method: 'get',
    params,
    responseType: 'blob'
  })
}

export function exportQuotaTransactions(params) {
  return request({
    url: '/admin/commercial/quota-transactions/export',
    method: 'get',
    params,
    responseType: 'blob'
  })
}
