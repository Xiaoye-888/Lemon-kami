import request from '../utils/request'

export function createInterface(data) {
  return request({
    url: '/admin/interfaces',
    method: 'post',
    data
  })
}

export function getInterfaces(params) {
  return request({
    url: '/admin/interfaces',
    method: 'get',
    params
  })
}

export function getPublicInterfaceDocs(params) {
  return request({
    url: '/docs/interfaces',
    method: 'get',
    params
  })
}

export function updateInterface(interfaceId, data) {
  return request({
    url: `/admin/interfaces/${interfaceId}`,
    method: 'put',
    data
  })
}

export function getAppInterfaces(appId) {
  return request({
    url: `/admin/apps/${appId}/interfaces`,
    method: 'get'
  })
}

export function updateAppInterface(appId, interfaceId, data) {
  return request({
    url: `/admin/apps/${appId}/interfaces/${interfaceId}`,
    method: 'put',
    data
  })
}
