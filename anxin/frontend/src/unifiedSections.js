export const unifiedSections = [
  { value: 'home', label: '首页' },
  { value: 'elder', label: '老人端' },
  { value: 'family', label: '子女端' },
  { value: 'community', label: '社区端' },
  { value: 'volunteer', label: '志愿者端' },
]

export const isUnifiedPath = pathname => pathname === '/' || pathname === '/login'

let scrollAnimation = 0

export function cancelUnifiedScrollAnimation() {
  window.cancelAnimationFrame(scrollAnimation)
  scrollAnimation = 0
}

export function scrollToUnifiedSection(value, behavior = 'smooth') {
  const scroller = document.querySelector('[data-unified-scroller]')
  const index = unifiedSections.findIndex(section => section.value === value)
  if (!scroller || index < 0) return false

  const maxScroll = Math.max(0, scroller.scrollHeight - scroller.clientHeight)
  const target = maxScroll * index / Math.max(1, unifiedSections.length - 1)
  const start = scroller.scrollTop
  const distance = target - start
  cancelUnifiedScrollAnimation()

  if (behavior === 'instant' || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    scroller.scrollTop = target
    return true
  }

  const duration = Math.min(1600, 760 + Math.abs(distance) / Math.max(1, maxScroll) * 720)
  const startedAt = performance.now()
  const ease = progress => 1 - Math.pow(1 - progress, 4)

  const step = now => {
    const progress = Math.min(1, (now - startedAt) / duration)
    scroller.scrollTop = start + distance * ease(progress)
    if (progress < 1) scrollAnimation = window.requestAnimationFrame(step)
  }

  scrollAnimation = window.requestAnimationFrame(step)
  return true
}
