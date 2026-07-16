import request from '../utils/request'

// 管理员登录
export function login(data) {
  // 如果是加密数据，使用 POST body 传输
  if (data.encrypted) {
    return request({
      url: '/admin/login',
      method: 'post',
      data: data
    })
  }
  // 否则使用 params 传输（明文）
  return request({
    url: '/admin/login',
    method: 'post',
    params: data
  })
}

// 获取应用列表
export function getApps() {
  return request({
    url: '/admin/apps',
    method: 'get'
  })
}

// 创建应用
export function createApp(data) {
  return request({
    url: '/admin/apps',
    method: 'post',
    params: data
  })
}

// 更新应用状态
export function updateAppStatus(appId, status) {
  return request({
    url: `/admin/apps/${appId}`,
    method: 'put',
    params: { status }
  })
}

// 删除应用
export function deleteApp(appId) {
  return request({
    url: `/admin/apps/${appId}`,
    method: 'delete'
  })
}
