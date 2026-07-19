import test from 'node:test'
import assert from 'node:assert/strict'

import { copyTextToClipboard } from './clipboard.js'

const originalNavigator = globalThis.navigator
const originalDocument = globalThis.document

function setNavigator(value) {
  Object.defineProperty(globalThis, 'navigator', {
    value,
    configurable: true,
    writable: true,
  })
}

function createDocumentStub(execResult = true) {
  const appended = []
  const removed = []
  const created = []

  const documentStub = {
    body: {
      appendChild(element) {
        appended.push(element)
      },
      removeChild(element) {
        removed.push(element)
      },
    },
    createElement(tagName) {
      assert.equal(tagName, 'textarea')
      const element = {
        value: '',
        style: {},
        focused: false,
        selected: false,
        selectionRange: null,
        setAttribute(name, value) {
          this[name] = value
        },
        focus() {
          this.focused = true
        },
        select() {
          this.selected = true
        },
        setSelectionRange(start, end) {
          this.selectionRange = [start, end]
        },
      }
      created.push(element)
      return element
    },
    execCommand(command) {
      assert.equal(command, 'copy')
      return execResult
    },
  }

  return { documentStub, appended, removed, created }
}

test.afterEach(() => {
  Object.defineProperty(globalThis, 'navigator', {
    value: originalNavigator,
    configurable: true,
    writable: true,
  })
  Object.defineProperty(globalThis, 'document', {
    value: originalDocument,
    configurable: true,
    writable: true,
  })
})

test('copies through textarea fallback when Clipboard API is unavailable', async () => {
  setNavigator({})
  const { documentStub, appended, removed, created } = createDocumentStub()
  globalThis.document = documentStub

  await assert.doesNotReject(() => copyTextToClipboard('ABC-123'))

  assert.equal(created[0].value, 'ABC-123')
  assert.equal(created[0].selected, true)
  assert.deepEqual(created[0].selectionRange, [0, 7])
  assert.equal(appended[0], created[0])
  assert.equal(removed[0], created[0])
})

test('falls back to textarea copy when Clipboard API rejects', async () => {
  setNavigator({
    clipboard: {
      async writeText() {
        throw new Error('clipboard denied')
      },
    },
  })
  const { documentStub, created } = createDocumentStub()
  globalThis.document = documentStub

  await assert.doesNotReject(() => copyTextToClipboard('FALLBACK'))

  assert.equal(created[0].value, 'FALLBACK')
  assert.equal(created[0].selected, true)
})

test('throws and cleans up when all copy methods fail', async () => {
  setNavigator({})
  const { documentStub, removed, created } = createDocumentStub(false)
  globalThis.document = documentStub

  await assert.rejects(() => copyTextToClipboard('NOPE'), /copy failed/)

  assert.equal(removed[0], created[0])
})
