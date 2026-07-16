import request from '../utils/request'

// 批量生成卡密
export function batchCreateKamis(data) {
  return request({
    url: '/admin/kamis/batch',
    method: 'post',
    params: data
  })
}

// 获取卡密列表
export function getKamis(params) {
  return request({
    url: '/admin/kamis',
    method: 'get',
    params
  })
}

// 冻结卡密
export function getKamiBatches(params) {
  return request({
    url: '/admin/kamis/batches',
    method: 'get',
    params
  })
}

export function getKamiSpecs(params) {
  return request({
    url: '/admin/kami-specs',
    method: 'get',
    params
  })
}

export function createKamiSpec(data) {
  return request({
    url: '/admin/kami-specs',
    method: 'post',
    data
  })
}

export function updateKamiSpec(specId, data) {
  return request({
    url: `/admin/kami-specs/${specId}`,
    method: 'put',
    data
  })
}

export function deleteKamiSpec(specId) {
  return request({
    url: `/admin/kami-specs/${specId}`,
    method: 'delete'
  })
}

export function generateKamisForSpec(specId, data) {
  return request({
    url: `/admin/kami-specs/${specId}/generate`,
    method: 'post',
    data
  })
}

export function getKamiSpecBatches(specId, params) {
  return request({
    url: `/admin/kami-specs/${specId}/batches`,
    method: 'get',
    params
  })
}

export function getKamiSpecKamis(specId, params) {
  return request({
    url: `/admin/kami-specs/${specId}/kamis`,
    method: 'get',
    params
  })
}

export function createKamiBatch(data) {
  return request({
    url: '/admin/kamis/batches',
    method: 'post',
    data
  })
}

export function updateKamiBatch(batchId, data) {
  return request({
    url: `/admin/kamis/batches/${batchId}`,
    method: 'put',
    data
  })
}

export function deleteKamiBatch(batchId) {
  return request({
    url: `/admin/kamis/batches/${batchId}`,
    method: 'delete'
  })
}

export function exportKamis(params) {
  return request({
    url: '/admin/kamis/export',
    method: 'get',
    params,
    responseType: 'blob'
  })
}

export function deleteKamis(data) {
  return request({
    url: '/admin/kamis/delete',
    method: 'post',
    data
  })
}

export function freezeKami(kamiCode) {
  return request({
    url: `/admin/kamis/${kamiCode}/freeze`,
    method: 'put'
  })
}
