import request from '../utils/request'

export function getEndUserStats(params) {
  return request({
    url: '/admin/end-users/stats',
    method: 'get',
    params
  })
}

export function getEndUsers(params) {
  return request({
    url: '/admin/end-users',
    method: 'get',
    params
  })
}

export function updateEndUserStatus(userId, status) {
  return request({
    url: `/admin/end-users/${userId}/status`,
    method: 'put',
    params: { status }
  })
}

export function resetEndUserPassword(userId, data) {
  return request({
    url: `/admin/end-users/${userId}/password`,
    method: 'put',
    data
  })
}

export function exportEndUsers(params) {
  return request({
    url: '/admin/end-users/export',
    method: 'get',
    params,
    responseType: 'blob'
  })
}

export function deleteEndUsers(data) {
  return request({
    url: '/admin/end-users/delete',
    method: 'post',
    data
  })
}

export function grantAuthorization(data) {
  return request({
    url: '/admin/authorizations/grant',
    method: 'post',
    data
  })
}

export function getEndUserQuotas(userId) {
  return request({
    url: `/admin/end-users/${userId}/quotas`,
    method: 'get'
  })
}

export function grantEndUserQuota(userId, data) {
  return request({
    url: `/admin/end-users/${userId}/quotas/grant`,
    method: 'post',
    data
  })
}

export function getEndUserAppAuthorizations(userId) {
  return request({
    url: `/admin/end-users/${userId}/app-authorizations`,
    method: 'get'
  })
}

export function grantEndUserAppAuthorization(userId, data) {
  return request({
    url: `/admin/end-users/${userId}/app-authorizations`,
    method: 'post',
    data
  })
}

export function getEndUserKamis(userId, params) {
  return request({
    url: `/admin/end-users/${userId}/kamis`,
    method: 'get',
    params
  })
}
