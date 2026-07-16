/**
 * 点击位置彩色圆点飞散动效（轻量、pointer-events: none）
 */
const COLORS = [
  '#00d4ff',
  '#ff2d95',
  '#ffeb3b',
  '#ff4444',
  '#7c4dff',
  '#00e5a8',
  '#ff9f43',
  '#a78bfa',
  '#22d3ee',
  '#f472b6'
]

let lastBurst = 0

function shouldSkip(target) {
  if (!target || !target.closest) return true
  if (target.closest('.yz-no-burst')) return true
  if (target.closest('input, textarea, select, [contenteditable="true"]')) return true
  if (target.closest('.el-select__popper, .el-popper, .el-overlay, .el-message, .el-dialog__wrapper')) return true
  if (target.closest('canvas, video, iframe')) return true
  return false
}

function burstAt(x, y) {
  const now = performance.now()
  if (now - lastBurst < 140) return
  lastBurst = now

  const n = 12 + Math.floor(Math.random() * 8)
  const DURATION_SEC = 0.88
  const DURATION_MS = Math.round(DURATION_SEC * 1000) + 40
  const root = document.createElement('div')
  root.setAttribute('aria-hidden', 'true')
  root.className = 'yz-click-burst-root'
  root.style.cssText =
    'position:fixed;inset:0;pointer-events:none;z-index:10050;overflow:hidden;'
  document.body.appendChild(root)

  for (let i = 0; i < n; i++) {
    const el = document.createElement('div')
    const d = 4 + Math.random() * 9
    const c = COLORS[Math.floor(Math.random() * COLORS.length)]
    el.className = 'yz-click-burst-dot'
    el.style.cssText = [
      'position:absolute',
      `left:${x}px`,
      `top:${y}px`,
      `width:${d}px`,
      `height:${d}px`,
      'border-radius:50%',
      `background:${c}`,
      'opacity:0.95',
      'transform:translate(-50%,-50%) scale(1)',
      'will-change:transform,opacity',
      `transition:transform ${DURATION_SEC}s cubic-bezier(0.2,0.5,0.1,1),opacity ${DURATION_SEC}s ease-out`
    ].join(';')

    root.appendChild(el)

    const ang = Math.random() * Math.PI * 2
    const dist = 55 + Math.random() * 95
    const tx = Math.cos(ang) * dist
    const ty = Math.sin(ang) * dist

    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        el.style.transform = `translate(calc(-50% + ${tx}px), calc(-50% + ${ty}px)) scale(0.15)`
        el.style.opacity = '0'
      })
    })
  }

  setTimeout(() => {
    root.remove()
  }, DURATION_MS)
}

export function initClickBurst() {
  document.addEventListener(
    'click',
    (e) => {
      if (e.button !== 0) return
      if (shouldSkip(e.target)) return
      burstAt(e.clientX, e.clientY)
    },
    true
  )
}
