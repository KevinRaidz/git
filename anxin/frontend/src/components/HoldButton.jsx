import { PhoneCall } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

export default function HoldButton({ title, hint, onComplete, className = '' }) {
  const [progress, setProgress] = useState(0)
  const [pressing, setPressing] = useState(false)
  const timer = useRef(null)
  const duration = 3000

  const cancel = () => {
    window.clearInterval(timer.current)
    timer.current = null
    setPressing(false)
    setProgress(0)
  }

  const start = event => {
    event.preventDefault()
    if (timer.current) return
    setPressing(true)
    const startedAt = performance.now()
    timer.current = window.setInterval(() => {
      const next = Math.min(100, ((performance.now() - startedAt) / duration) * 100)
      setProgress(next)
      if (next >= 100) {
        window.clearInterval(timer.current)
        timer.current = null
        setPressing(false)
        onComplete()
      }
    }, 40)
  }

  useEffect(() => () => window.clearInterval(timer.current), [])

  const seconds = Math.max(1, Math.ceil((duration * (1 - progress / 100)) / 1000))
  return (
    <button
      className={`e-sos ${pressing ? 'is-pressing' : ''} ${className}`}
      type="button"
      aria-label={`长按三秒${title}`}
      onPointerDown={start}
      onPointerUp={cancel}
      onPointerLeave={cancel}
      onPointerCancel={cancel}
      onKeyDown={event => { if (event.key === ' ' || event.key === 'Enter') start(event) }}
      onKeyUp={event => { if (event.key === ' ' || event.key === 'Enter') cancel() }}
      onBlur={cancel}
    >
      <span className="progress" style={{ width: `${progress}%` }} aria-hidden="true" />
      <span className="e-sos-icon" aria-hidden="true"><PhoneCall /></span>
      <span className="e-sos-copy"><span className="e-sos-title">{title}</span><span className="e-sos-hint">{hint}</span></span>
      <span className="e-sos-timer" aria-hidden="true">{seconds} 秒</span>
    </button>
  )
}
