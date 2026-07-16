import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '../../..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')

const coreThemeFiles = [
  'src/assets/styles/theme.css',
  'src/layouts/MainLayout.vue',
  'src/views/Login.vue',
  'src/views/Kamis.vue',
  'src/views/Users.vue',
  'src/views/ApiDocs.vue',
  'src/views/NotFound.vue'
]

const forbiddenWarmTokens = [
  '#f97316',
  '#ea580c',
  '#c2410c',
  '#9a3412',
  '#fb923c',
  '#fff7ed',
  '#fffbeb',
  '#fdba74'
]

const themeCss = read('src/assets/styles/theme.css')
const mainLayout = read('src/layouts/MainLayout.vue')
const router = read('src/router/index.js')
const requestUtil = read('src/utils/request.js')
const cryptoUtil = read('src/utils/crypto.js')
const adminDockerignore = read('.dockerignore')
const usersView = read('src/views/Users.vue')
const kamisView = read('src/views/Kamis.vue')
const batchesView = read('src/views/KamiBatches.vue')
const appInterfacesView = read('src/views/AppInterfaces.vue')
const sdkExample = read('public/sdk/js_example.html')
const sdkClient = read('public/sdk/lemon-kami.js')
const packagedJsSdk = read('../sdk/js_sdk/lemon-kami.js')
const packagedJsCompleteSdk = read('../sdk/js_sdk/lemon-kami-complete.js')
const packagedPythonSdk = read('../sdk/python_sdk/lemon_kami.py')
const packagedJavaSdk = read('../sdk/java_sdk/src/main/java/com/lemon/kami/LemonKamiSDK.java')

assert.match(themeCss, /--yz-primary:\s*#2f80ed;/)
assert.match(themeCss, /--yz-surface-gradient:/)
assert.match(themeCss, /--yz-table-header:/)

for (const file of coreThemeFiles) {
  const content = read(file).toLowerCase()
  for (const token of forbiddenWarmTokens) {
    assert.equal(
      content.includes(token),
      false,
      `${file} still contains warm theme token ${token}`
    )
  }
}

assert.equal(
  /:deep\(\.el-table th\)[\s\S]*color:\s*white/i.test(usersView),
  false,
  'Users table header must not override the blue table theme with white text'
)
assert.equal(usersView.includes('#667eea'), false, 'Users page still contains legacy purple table header color')
assert.equal(usersView.includes('#764ba2'), false, 'Users page still contains legacy purple table header color')
assert.equal(mainLayout.includes('index="/points"'), false, 'Points management menu item should be removed')
assert.equal(mainLayout.includes('Coin,'), false, 'Unused Coin icon import should be removed')
assert.equal(router.includes("path: 'points'"), false, 'Points management route should be removed')
assert.equal(router.includes("name: 'Points'"), false, 'Points management route name should be removed')
assert.equal(router.includes('beforeEach((to, from, next)'), false, 'Router guard should use return-based navigation instead of deprecated next()')
assert.match(requestUtil, /headers\.Authorization\s*=\s*`Bearer \$\{token\}`/, 'Admin API requests should send token with Authorization header')
assert.equal(requestUtil.includes('token: token'), false, 'Admin API requests should not leak token through query params')
assert.equal(cryptoUtil.includes('/api/v1/admin/apps'), false, 'Crypto utilities should not make unauthenticated admin app-list requests')
assert.match(adminDockerignore, /!\.env\.production/, 'Frontend Docker build context should include .env.production')
assert.equal(kamisView.includes('sdk/js_example.html'), true, 'Kamis page should expose SDK scenario test entry')
assert.equal(kamisView.includes('openSdkTestScene'), true, 'Kamis page should provide SDK scenario test handler')
assert.equal(batchesView.includes('batch-name-link'), false, 'Batch names must not use stale batch-name-link styles')
assert.equal(batchesView.includes('max_bind_devices'), true, 'Batch management should expose max bind device configuration')
assert.equal(batchesView.includes('class="back-link"'), false, 'Batch detail should not render the old floating back-link strip')
assert.equal(batchesView.includes('deviceLimitEnabled'), true, 'Batch page should react to the device limit interface switch')
assert.equal(batchesView.includes('getAppInterfaces'), true, 'Batch page should load app interface switches')
assert.equal(batchesView.includes('绑定设备数'), true, 'Batch form should allow configuring multi-device bind count')
assert.equal(batchesView.includes('.batch-config-lines'), true, 'Batch table should keep type-specific config line styling')
assert.equal(kamisView.includes('row.max_bind_devices'), true, 'Kami list should display max bind device count')
assert.equal(appInterfacesView.includes('sdk.device_limit'), true, 'App interface config should expose device limit settings')
assert.match(sdkExample, /<select[^>]+id="appId"/, 'SDK example should use an App ID dropdown')
assert.equal(/<input[^>]+id="appId"/.test(sdkExample), false, 'SDK example should not use a free-text App ID input')
assert.match(sdkExample, /loadAppsForSdkTest/, 'SDK example should load apps from admin API')
assert.match(sdkExample, /localStorage\.getItem\('token'\)/, 'SDK example should reuse the admin login token')
assert.match(sdkExample, /\/api\/v1\/admin\/apps/, 'SDK example should fetch apps from the admin app list API')
assert.equal(sdkExample.includes('?token='), false, 'SDK example should not leak admin token through query params')
assert.match(sdkExample, /Authorization':\s*`Bearer \$\{token\}`|'Authorization':\s*"Bearer "|Authorization":\s*`Bearer \$\{token\}`/, 'SDK example should fetch admin apps with Authorization header')
assert.equal(/id="appSecret"/.test(sdkExample), false, 'SDK example should not render App Secret into the browser form')
assert.match(sdkExample, /\/api\/v1\/sdk\/client-token/, 'SDK example should exchange App Secret for a short-lived client token')
assert.match(sdkExample, /clientToken:\s*clientCredential\.client_token/, 'SDK example should initialize SDK with short-lived client token')
assert.match(sdkExample, /clientSecret:\s*clientCredential\.client_secret/, 'SDK example should initialize SDK with short-lived client secret')
assert.match(sdkClient, /releaseDevice/, 'SDK client should expose a releaseDevice method')
assert.match(sdkClient, /\/api\/v1\/sdk\/release-device/, 'SDK client should call the release-device API')
assert.match(sdkClient, /pagehide|beforeunload/, 'SDK client should release device slots when the page closes')
assert.match(packagedJsSdk, /releaseDevice/, 'Packaged JS SDK should expose releaseDevice')
assert.match(packagedJsSdk, /\/api\/v1\/sdk\/release-device/, 'Packaged JS SDK should call release-device')
assert.match(packagedJsCompleteSdk, /releaseDevice/, 'Complete JS SDK should expose releaseDevice')
assert.match(packagedPythonSdk, /def release_device/, 'Python SDK should expose release_device')
assert.match(packagedPythonSdk, /\/api\/v1\/sdk\/release-device/, 'Python SDK should call release-device')
assert.match(packagedJavaSdk, /releaseDevice/, 'Java SDK should expose releaseDevice')
assert.match(packagedJavaSdk, /\/api\/v1\/sdk\/release-device/, 'Java SDK should call release-device')

console.log('blue theme tests passed')
