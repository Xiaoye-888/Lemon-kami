export async function copyTextToClipboard(text) {
  const value = String(text ?? '')

  if (globalThis.navigator?.clipboard?.writeText) {
    try {
      await globalThis.navigator.clipboard.writeText(value)
      return
    } catch {
      // Some browsers expose Clipboard API but reject it on insecure origins.
    }
  }

  if (!globalThis.document?.body || typeof globalThis.document.createElement !== 'function') {
    throw new Error('copy failed')
  }

  const textarea = globalThis.document.createElement('textarea')
  textarea.value = value
  textarea.setAttribute?.('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.left = '-9999px'
  textarea.style.top = '-9999px'
  textarea.style.opacity = '0'

  globalThis.document.body.appendChild(textarea)
  try {
    textarea.focus?.()
    textarea.select?.()
    textarea.setSelectionRange?.(0, value.length)

    if (!globalThis.document.execCommand?.('copy')) {
      throw new Error('copy failed')
    }
  } finally {
    globalThis.document.body.removeChild(textarea)
  }
}
