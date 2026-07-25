import request from '../utils/request'

export function getOpsHealth() {
  return request({
    url: '/admin/ops/health',
    method: 'get'
  })
}

export function getOpsBackups(params) {
  return request({
    url: '/admin/ops/backups',
    method: 'get',
    params
  })
}

export function createOpsBackup(data) {
  return request({
    url: '/admin/ops/backups',
    method: 'post',
    data
  })
}

export function downloadOpsBackup(backupNo, data) {
  return request({
    url: `/admin/ops/backups/${backupNo}/download`,
    method: 'post',
    data,
    responseType: 'blob'
  })
}

export function cleanupProofUploads(data) {
  return request({
    url: '/admin/ops/uploads/proofs/cleanup',
    method: 'post',
    data
  })
}

export function getRecentErrorLogs(params) {
  return request({
    url: '/admin/ops/logs/recent-errors',
    method: 'get',
    params
  })
}
