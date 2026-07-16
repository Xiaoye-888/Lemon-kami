import assert from 'node:assert/strict'
import { buildInterfaceDocHref, interfaceKeyToAnchor } from './interfaceDocs.js'

assert.equal(interfaceKeyToAnchor('user.register'), 'user-register')
assert.equal(interfaceKeyToAnchor('sdk.app_config'), 'sdk-app-config')
assert.equal(buildInterfaceDocHref('points.consume'), '/docs/api#points-consume')
assert.equal(
  buildInterfaceDocHref('admin.kamis.batch', 'https://example.com/panel'),
  'https://example.com/panel/docs/api#admin-kamis-batch'
)

console.log('interface docs link tests passed')
