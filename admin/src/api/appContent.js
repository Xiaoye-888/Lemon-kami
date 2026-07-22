import request from '../utils/request'

export function getAppNotices(appId) {
  return request({
    url: `/admin/apps/${appId}/notices`,
    method: 'get'
  })
}

export function createAppNotice(appId, data) {
  return request({
    url: `/admin/apps/${appId}/notices`,
    method: 'post',
    data
  })
}

export function updateAppNotice(appId, noticeId, data) {
  return request({
    url: `/admin/apps/${appId}/notices/${noticeId}`,
    method: 'put',
    data
  })
}

export function getAppVersions(appId, params) {
  return request({
    url: `/admin/apps/${appId}/updates`,
    method: 'get',
    params
  })
}

export function createAppVersion(appId, data) {
  return request({
    url: `/admin/apps/${appId}/updates`,
    method: 'post',
    data
  })
}

export function updateAppVersion(appId, versionId, data) {
  return request({
    url: `/admin/apps/${appId}/updates/${versionId}`,
    method: 'put',
    data
  })
}

export function deleteAppVersion(appId, versionId) {
  return request({
    url: `/admin/apps/${appId}/updates/${versionId}`,
    method: 'delete'
  })
}
