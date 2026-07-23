import request from '../utils/request'

export function sharedLogin(data) {
  return request({
    url: '/auth/login',
    method: 'post',
    data
  })
}

export function getSharedLoginKey() {
  return request({
    url: '/auth/login/public-key',
    method: 'get'
  })
}
