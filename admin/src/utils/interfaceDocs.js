export const interfaceKeyToAnchor = (interfaceKey = '') => (
  String(interfaceKey)
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
)

export const buildInterfaceDocHref = (interfaceKey, origin = '') => {
  const anchor = interfaceKeyToAnchor(interfaceKey)
  const base = origin ? `${String(origin).replace(/\/+$/g, '')}/docs/api` : '/docs/api'
  return anchor ? `${base}#${anchor}` : base
}

export const openInterfaceDoc = (interfaceKey) => {
  window.open(buildInterfaceDocHref(interfaceKey, window.location.origin), '_blank', 'noopener,noreferrer')
}
