import assert from 'node:assert/strict'
import test from 'node:test'

import {
  DEFAULT_REQUEST_TIMEOUT_MS,
  isRetryableRequestError
} from '../src/utils/requestPolicy.js'


test('default API timeout fails visibly without a long page freeze', () => {
  assert.equal(DEFAULT_REQUEST_TIMEOUT_MS, 12000)
})


test('network blackholes and client timeouts are not retried', () => {
  assert.equal(isRetryableRequestError({
    code: 'ECONNABORTED',
    config: { method: 'get' }
  }), false)

  assert.equal(isRetryableRequestError({
    code: 'ERR_NETWORK',
    config: { method: 'get' }
  }), false)
})


test('only idempotent requests with an explicit transient response are retried', () => {
  assert.equal(isRetryableRequestError({
    config: { method: 'get' },
    response: { status: 503 }
  }), true)

  assert.equal(isRetryableRequestError({
    config: { method: 'post' },
    response: { status: 503 }
  }), false)

  assert.equal(isRetryableRequestError({
    config: { method: 'get' },
    response: { status: 500 }
  }), false)

  assert.equal(isRetryableRequestError({
    code: 'ERR_CANCELED',
    config: { method: 'get' },
    response: { status: 503 }
  }), false)
})
