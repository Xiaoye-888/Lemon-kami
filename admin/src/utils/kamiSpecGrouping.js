const POLICY_ORDER = {
  one_card_one_device: 1,
  one_card_multi_device: 2,
  no_limit: 3
}

const numericFields = [
  'batch_count',
  'total_count',
  'unused_count',
  'active_count',
  'frozen_count',
  'expired_count',
  'redeemed_count',
  'times_remaining_total',
  'points_remaining_total'
]

export function getKamiSpecBenefitKey(row) {
  if (!row) return ''
  return [
    row.kami_type || '',
    row.points_amount || 0,
    row.points_valid_days || 0,
    row.times_total || 0,
    row.time_value || 0,
    row.time_unit || ''
  ].join('|')
}

function comparePolicy(a, b) {
  const orderA = POLICY_ORDER[a.machine_bind_mode] || 99
  const orderB = POLICY_ORDER[b.machine_bind_mode] || 99
  if (orderA !== orderB) return orderA - orderB
  if ((a.max_bind_devices || 0) !== (b.max_bind_devices || 0)) {
    return (a.max_bind_devices || 0) - (b.max_bind_devices || 0)
  }
  return String(a.id || '').localeCompare(String(b.id || ''))
}

function compareGroups(a, b) {
  if (a.spec_group !== b.spec_group) return a.spec_group === 'common' ? -1 : 1
  if ((a.sort_order || 0) !== (b.sort_order || 0)) return (a.sort_order || 0) - (b.sort_order || 0)
  if (a.kami_type !== b.kami_type) return String(a.kami_type).localeCompare(String(b.kami_type))
  return String(a.spec_name || '').localeCompare(String(b.spec_name || ''))
}

export function groupKamiSpecsByBenefit(rows = []) {
  const groups = new Map()

  rows.forEach((row) => {
    const key = getKamiSpecBenefitKey(row)
    if (!groups.has(key)) {
      groups.set(key, {
        ...row,
        id: key,
        benefit_key: key,
        default_spec_id: row.id,
        variant_count: 0,
        variants: [],
        has_disabled_variants: false
      })
      numericFields.forEach((field) => {
        groups.get(key)[field] = 0
      })
    }

    const group = groups.get(key)
    group.variants.push(row)
    group.variant_count += 1
    group.spec_group = group.spec_group === 'common' || row.spec_group === 'common' ? 'common' : 'custom'
    group.status = group.status === 1 || row.status === 1 ? 1 : 0
    group.has_disabled_variants = group.has_disabled_variants || row.status !== 1
    group.sort_order = Math.min(group.sort_order || 0, row.sort_order || 0)
    numericFields.forEach((field) => {
      group[field] += row[field] || 0
    })
  })

  return Array.from(groups.values()).map((group) => {
    group.variants = [...group.variants].sort(comparePolicy)
    const preferred = group.variants.find((item) => item.status === 1) || group.variants[0]
    group.default_spec_id = preferred?.id
    return group
  }).sort(compareGroups)
}
