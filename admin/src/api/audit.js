import request from '../utils/request'

export function getAdminAuditLogs(params) {
  return request({
    url: '/admin/commercial/audit-logs',
    method: 'get',
    params
  })
}
