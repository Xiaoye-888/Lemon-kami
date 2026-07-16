export const TYPE_OPTIONS = [
  { label: '小时卡', value: 'hour' },
  { label: '天卡', value: 'day' },
  { label: '周卡', value: 'week' },
  { label: '月卡', value: 'month' },
  { label: '季卡', value: 'quarter' },
  { label: '年卡', value: 'year' },
  { label: '永久卡', value: 'lifetime' },
  { label: '积分卡', value: 'points' },
  { label: '次数卡', value: 'times' }
]

export const TIME_UNIT_OPTIONS = {
  hour: '小时',
  hours: '小时',
  day: '天',
  days: '天',
  week: '周',
  weeks: '周',
  month: '月',
  months: '月',
  quarter: '季度',
  quarters: '季度',
  year: '年',
  years: '年'
}

export const AUTHORIZATION_OWNER_OPTIONS = [
  { label: '设备授权', value: 'device' },
  { label: '用户授权', value: 'user' },
  { label: '自动识别', value: 'auto' }
]

export const USER_BIND_MODE_OPTIONS = [
  { label: '不绑定用户', value: 'none' },
  { label: '自动识别绑定', value: 'auto' },
  { label: '必须绑定用户', value: 'required' }
]

export function getTypeText(type) {
  return TYPE_OPTIONS.find((item) => item.value === type)?.label || type || '-'
}

export function getAuthorizationOwnerText(value) {
  return AUTHORIZATION_OWNER_OPTIONS.find((item) => item.value === value)?.label || value || '设备授权'
}

export function getUserBindModeText(value) {
  if (value === 'optional') return '自动识别绑定'
  return USER_BIND_MODE_OPTIONS.find((item) => item.value === value)?.label || value || '不绑定用户'
}

export function getTimeUnitText(unit) {
  return TIME_UNIT_OPTIONS[unit] || unit || ''
}

export function isFixedTimeCard(type) {
  return ['hour', 'day', 'week', 'month', 'quarter', 'year', 'lifetime'].includes(type)
}

export function getMachineBindModeText(mode, maxBindDevices = 1) {
  const map = {
    no_limit: '不限制',
    one_card_one_device: '一机一码',
    one_card_multi_device: `一卡多机(${maxBindDevices || 3})`
  }
  return map[mode] || '一机一码'
}

export function getMachineTagType(mode) {
  const map = {
    no_limit: 'info',
    one_card_one_device: 'primary',
    one_card_multi_device: 'success'
  }
  return map[mode] || 'primary'
}

export function getStatusText(status) {
  const map = { unused: '未使用', active: '已使用', frozen: '已冻结' }
  return map[status] || status || '-'
}

export function getStatusType(status) {
  const map = { unused: 'info', active: 'success', frozen: 'danger' }
  return map[status] || ''
}

export function getValidityText(row) {
  if (!row) return '-'
  if (row.kami_type === 'points') return row.points_valid_days ? `${row.points_valid_days}天` : '永久'
  if (row.kami_type === 'times') return `${row.times_total || 0}次`
  if (row.kami_type === 'lifetime') return '永久'
  if (row.time_value) return `${row.time_value}${getTimeUnitText(row.time_unit)}`
  const fallback = {
    hour: '1小时',
    day: '1天',
    week: '7天',
    month: '30天',
    quarter: '90天',
    year: '365天'
  }
  return fallback[row.kami_type] || '-'
}

export function batchDetailColumnLabels(type) {
  const base = ['卡密', '状态', '创建时间']
  if (type === 'points') {
    return [
      ...base,
      '使用用户',
      '积分面额',
      '已兑换积分',
      '剩余积分',
      '兑换时间',
      '有效期',
      '备注'
    ]
  }
  if (type === 'times') {
    return [
      ...base,
      '使用用户',
      '绑定设备',
      '每卡次数',
      '已核销次数',
      '剩余次数',
      '最近核销时间',
      '最近验证时间',
      '备注'
    ]
  }
  return [
    ...base,
    '使用用户',
    '有效期',
    '机器码限制',
    '绑定设备',
    '最近验证时间',
    '备注'
  ]
}
