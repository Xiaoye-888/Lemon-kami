import assert from 'node:assert/strict'
import {
  batchDetailColumnLabels,
  getAuthorizationOwnerText,
  getTimeUnitText,
  getTypeText,
  getUserBindModeText
} from './kamiDisplay.js'

assert.equal(getTypeText('times'), '次数卡')
assert.equal(getTimeUnitText('month'), '月')
assert.equal(getTimeUnitText('months'), '月')
assert.equal(getTimeUnitText('day'), '天')
assert.equal(getAuthorizationOwnerText('device'), '设备授权')
assert.equal(getAuthorizationOwnerText('user'), '用户授权')
assert.equal(getAuthorizationOwnerText('auto'), '自动识别')
assert.equal(getUserBindModeText('none'), '不绑定用户')
assert.equal(getUserBindModeText('auto'), '自动识别绑定')
assert.equal(getUserBindModeText('optional'), '自动识别绑定')
assert.equal(getUserBindModeText('required'), '必须绑定用户')

assert.deepEqual(batchDetailColumnLabels('points'), [
  '卡密',
  '状态',
  '创建时间',
  '使用用户',
  '积分面额',
  '已兑换积分',
  '剩余积分',
  '兑换时间',
  '有效期',
  '备注'
])

assert.deepEqual(batchDetailColumnLabels('times'), [
  '卡密',
  '状态',
  '创建时间',
  '使用用户',
  '绑定设备',
  '每卡次数',
  '已核销次数',
  '剩余次数',
  '最近核销时间',
  '最近验证时间',
  '备注'
])

assert.ok(batchDetailColumnLabels('month').includes('有效期'))
assert.ok(batchDetailColumnLabels('month').includes('机器码限制'))

console.log('kamiDisplay tests passed')
