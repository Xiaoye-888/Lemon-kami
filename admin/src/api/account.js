import request from '../utils/request'

const ROLE_BASE = {
  admin: '/admin',
  merchant: '/merchant'
}

function resolveBase(role) {
  return ROLE_BASE[role] || ROLE_BASE.admin
}

export function getCurrentAccountProfile(role) {
  return request({
    url: `${resolveBase(role)}/me`,
    method: 'get'
  })
}

export function updateCurrentAccountProfile(role, data) {
  return request({
    url: `${resolveBase(role)}/me`,
    method: 'put',
    data
  })
}

export function uploadCurrentAccountAvatar(role, file) {
  const formData = new FormData()
  formData.append('avatar_file', file)
  return request({
    url: `${resolveBase(role)}/me/avatar`,
    method: 'post',
    data: formData
  })
}

export function updateCurrentAccountPassword(role, data) {
  return request({
    url: `${resolveBase(role)}/me/password`,
    method: 'put',
    data
  })
}
