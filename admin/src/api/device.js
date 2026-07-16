import request from '../utils/request'

// 获取行为日志
export function getEventLogs(params) {
  return request({
    url: '/admin/logs',
    method: 'get',
    params
  })
}

// 获取设备列表
export function getDevices(params) {
  return request({
    url: '/admin/devices',
    method: 'get',
    params
  })
}

// 更新设备风险等级
export function updateDeviceRisk(deviceId, riskLevel) {
  return request({
    url: `/admin/devices/${deviceId}/risk`,
    method: 'put',
    params: { risk_level: riskLevel }
  })
}
