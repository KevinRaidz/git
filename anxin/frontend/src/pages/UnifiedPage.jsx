import { useEffect, useRef } from 'react'
import { useBodyClass } from '../hooks'
import { cancelUnifiedScrollAnimation, unifiedSections } from '../unifiedSections'
import DashboardPage from './DashboardPage'
import ElderHomePage from './ElderHomePage'
import FamilyPage from './FamilyPage'
import LoginPage from './LoginPage'
import VolunteerPage from './VolunteerPage'

export default function UnifiedPage() {
  useBodyClass('unified-body')
  const scrollerRef = useRef(null)
  const panelRefs = useRef([])

  useEffect(() => {
    const scroller = scrollerRef.current
    if (!scroller) return undefined
    let frame = 0
    let currentIndex = -1

    const updateScene = () => {
      frame = 0
      const maxScroll = Math.max(1, scroller.scrollHeight - scroller.clientHeight)
      const progress = Math.min(1, Math.max(0, scroller.scrollTop / maxScroll))
      const rawIndex = progress * (unifiedSections.length - 1)
      const activeIndex = Math.round(rawIndex)

      panelRefs.current.forEach((panel, index) => {
        if (!panel) return
        const offset = index - rawIndex
        const distance = Math.min(1, Math.abs(offset))
        const opacity = Math.pow(Math.max(0, 1 - distance), .68)
        const scale = 1 - distance * .12
        panel.style.setProperty('--scene-offset', offset.toFixed(4))
        panel.style.setProperty('--scene-scale', scale.toFixed(4))
        panel.style.opacity = opacity.toFixed(4)
        panel.style.filter = `blur(${(distance * 3).toFixed(2)}px)`
        panel.style.visibility = Math.abs(offset) >= 1.04 ? 'hidden' : 'visible'
        panel.style.zIndex = String(20 - Math.round(distance * 10))
        panel.style.pointerEvents = index === activeIndex ? 'auto' : 'none'
        panel.inert = index !== activeIndex
        panel.setAttribute('aria-hidden', String(index !== activeIndex))
      })

      if (activeIndex !== currentIndex) {
        currentIndex = activeIndex
        window.dispatchEvent(new CustomEvent('anxin:section-change', {
          detail: { value: unifiedSections[activeIndex].value },
        }))
      }
    }

    const onScroll = () => {
      if (!frame) frame = window.requestAnimationFrame(updateScene)
    }

    updateScene()
    scroller.addEventListener('scroll', onScroll, { passive: true })
    scroller.addEventListener('wheel', cancelUnifiedScrollAnimation, { passive: true })
    scroller.addEventListener('touchstart', cancelUnifiedScrollAnimation, { passive: true })
    window.addEventListener('resize', onScroll)
    return () => {
      scroller.removeEventListener('scroll', onScroll)
      scroller.removeEventListener('wheel', cancelUnifiedScrollAnimation)
      scroller.removeEventListener('touchstart', cancelUnifiedScrollAnimation)
      window.removeEventListener('resize', onScroll)
      cancelUnifiedScrollAnimation()
      if (frame) window.cancelAnimationFrame(frame)
    }
  }, [])

  return (
    <main id="main-content" ref={scrollerRef} className="unified-page" data-unified-scroller>
      <div className="unified-scroll-track">
        <div className="unified-scene-stage">
          <section ref={node => { panelRefs.current[0] = node }} id="section-home" className="unified-section unified-section-home" aria-label="首页">
            <LoginPage embedded />
          </section>
          <section ref={node => { panelRefs.current[1] = node }} id="section-elder" className="unified-section unified-section-elder" aria-label="老人端">
            <ElderHomePage embedded />
          </section>
          <section ref={node => { panelRefs.current[2] = node }} id="section-family" className="unified-section unified-section-family" aria-label="子女端">
            <FamilyPage />
          </section>
          <section ref={node => { panelRefs.current[3] = node }} id="section-community" className="unified-section unified-section-community" aria-label="社区端">
            <DashboardPage embedded />
          </section>
          <section ref={node => { panelRefs.current[4] = node }} id="section-volunteer" className="unified-section unified-section-volunteer" aria-label="志愿者端">
            <VolunteerPage />
          </section>
        </div>
      </div>
    </main>
  )
}
