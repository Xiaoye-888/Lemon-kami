export const DEFAULT_REQUEST_TIMEOUT_MS = 12000
export const DEFAULT_REQUEST_RETRIES = 1
export const DEFAULT_REQUEST_RETRY_DELAY_MS = 350

const retryableMethods = new Set(['get', 'head', 'options'])
const retryableStatusCodes = new Set([502, 503, 504])

export function isRetryableRequestError(error) {
  const config = error?.config
  if (!config || !error.response || error.code === 'ERR_CANCELED') {
    return false
  }

  const method = String(config.method || 'get').toLowerCase()
  return retryableMethods.has(method) && retryableStatusCodes.has(error.response.status)
}
