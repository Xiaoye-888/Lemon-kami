import request from '../utils/request'

export function isMerchantContentRoute() {
  return typeof window !== 'undefined' && window.location.pathname.startsWith('/merchant')
}

export function contentBasePath(appId, section) {
  if (section === 'notices') {
    return isMerchantContentRoute() ? `/merchant/apps/${appId}/notices` : `/admin/apps/${appId}/notices`
  }
  if (section === 'updates') {
    return isMerchantContentRoute() ? `/merchant/apps/${appId}/updates` : `/admin/apps/${appId}/updates`
  }
  return isMerchantContentRoute() ? `/merchant/apps/${appId}/${section}` : `/admin/apps/${appId}/${section}`
}

export function getContentApps() {
  return request({
    url: isMerchantContentRoute() ? '/merchant/apps' : '/admin/apps',
    method: 'get'
  })
}

export function getAppNotices(appId) {
  return request({
    url: contentBasePath(appId, 'notices'),
    method: 'get'
  })
}

export function createAppNotice(appId, data) {
  return request({
    url: contentBasePath(appId, 'notices'),
    method: 'post',
    data
  })
}

export function updateAppNotice(appId, noticeId, data) {
  return request({
    url: `${contentBasePath(appId, 'notices')}/${noticeId}`,
    method: 'put',
    data
  })
}

export function deleteAppNotice(appId, noticeId) {
  return request({
    url: `${contentBasePath(appId, 'notices')}/${noticeId}`,
    method: 'delete'
  })
}

export function getAppVersions(appId, params) {
  return request({
    url: contentBasePath(appId, 'updates'),
    method: 'get',
    params
  })
}

export function createAppVersion(appId, data) {
  return request({
    url: contentBasePath(appId, 'updates'),
    method: 'post',
    data
  })
}

export function updateAppVersion(appId, versionId, data) {
  return request({
    url: `${contentBasePath(appId, 'updates')}/${versionId}`,
    method: 'put',
    data
  })
}

export function deleteAppVersion(appId, versionId) {
  return request({
    url: `${contentBasePath(appId, 'updates')}/${versionId}`,
    method: 'delete'
  })
}
