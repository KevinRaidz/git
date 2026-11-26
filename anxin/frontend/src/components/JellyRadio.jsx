'use client'
/* eslint-disable react-hooks/refs */

import { forwardRef, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { animate, motion, motionValue, useReducedMotion, useTransform } from 'motion/react'
import { NavLink } from 'react-router-dom'

import './JellyRadio.css'

const DEFAULT_ITEMS = ['Off', 'Low', 'Medium', 'High', 'Max']
const SIZES = { sm: [28, 12, 12], md: [36, 13, 16], lg: [44, 14, 20] }

const spring = (k, m, bounce) => ({
  type: 'spring',
  stiffness: k,
  damping: 2 * Math.sqrt(k * m) * (1 - bounce),
  mass: m,
})

const MotionNavLink = motion.create(NavLink)

const Chip = forwardRef(function Chip({ mv, as: Component = motion.button, children, ...rest }, ref) {
  const transform = useTransform(() => `translateX(${mv.x.get()}px) scale(${mv.sx.get()}, ${mv.sy.get()})`)
  return <Component ref={ref} style={{ transform }} {...rest}>{children}</Component>
})

export default function JellyRadio({
  items = DEFAULT_ITEMS,
  value,
  defaultValue,
  onChange,
  chipColor = '#27272a',
  activeColor = '#f5f5f5',
  textColor = '#f5f5f5',
  activeTextColor = '#18181b',
  size = 'md',
  gap = 8,
  radius = 18,
  swell = 0.2,
  barge = 6,
  shrink = 0.05,
  jelly = 1,
  bounce = 0.25,
  stagger = 22,
  stiffness = 580,
  disabled = false,
  ariaLabel = 'Options',
  navigation = false,
  className = '',
}) {
  const list = items.map(item => (typeof item === 'string' ? { value: item, label: item } : item))
  const [inner, setInner] = useState(() => defaultValue ?? list[0]?.value)
  const current = value ?? inner
  const at = list.findIndex(item => item.value === current)
  const reduce = useReducedMotion()
  const groupRef = useRef(null)
  const chipRefs = useRef([])
  const widths = useRef([])
  const mvs = useRef([])
  const applied = useRef(at)
  const cfg = useRef({})
  cfg.current = { swell, barge, shrink, jelly, bounce, stagger, stiffness, reduce, count: list.length }
  const [height, font, paddingX] = SIZES[size] ?? SIZES.md
  const itemsKey = list.map(item => item.value).join('|')

  const mvFor = index => {
    let mv = mvs.current[index]
    if (!mv) {
      mv = { x: motionValue(0), sx: motionValue(1), sy: motionValue(1) }
      mvs.current[index] = mv
    }
    return mv
  }

  const apply = (selected, instant) => {
    const config = cfg.current
    const group = groupRef.current
    const rtl = group ? getComputedStyle(group).direction === 'rtl' : false
    const push = selected < 0 ? 0 : ((widths.current[selected] ?? 0) * config.swell) / 2 + config.barge
    for (let index = 0; index < config.count; index += 1) {
      const mv = mvFor(index)
      const on = selected >= 0 && index === selected
      const far = selected < 0 ? 0 : Math.abs(index - selected)
      const direction = selected < 0 ? 0 : Math.sign(index - selected) * (rtl ? -1 : 1)
      const x = direction * push
      const scale = selected < 0 ? 1 : on ? 1 + config.swell : 1 - config.shrink
      if (instant || config.reduce) {
        mv.x.jump(x)
        mv.sx.jump(scale)
        mv.sy.jump(scale)
        continue
      }
      const k = config.stiffness * (1 - 0.12 * Math.min(far, 3))
      const inFlight = mv.x.isAnimating() || mv.sx.isAnimating() || mv.sy.isAnimating()
      const delay = inFlight ? 0 : (far * config.stagger) / 1000
      animate(mv.x, x, { ...spring(k, 0.9, config.bounce), delay })
      const jellyAmount = config.jelly
      animate(mv.sx, scale, {
        ...spring(k * (1 + 0.24 * jellyAmount), 0.9 - 0.1 * jellyAmount, Math.min(0.85, config.bounce + 0.3 * jellyAmount)),
        delay,
      })
      animate(mv.sy, scale, {
        ...spring(k * (1 - 0.14 * jellyAmount), 0.9 + 0.05 * jellyAmount, config.bounce),
        delay: delay + 0.05 * jellyAmount,
      })
    }
  }

  const measure = () => {
    const group = groupRef.current
    if (!group) return
    widths.current = chipRefs.current.map(element => element?.offsetWidth ?? 0)
    const chipHeight = chipRefs.current[0]?.offsetHeight ?? 0
    const maxWidth = Math.max(0, ...widths.current)
    group.style.setProperty('--jr-pad-x', `${Math.ceil((maxWidth * swell * 1.3) / 2 + barge) + 2}px`)
    group.style.setProperty('--jr-pad-y', `${Math.ceil((chipHeight * swell) / 2) + 2}px`)
  }

  useLayoutEffect(() => {
    const settle = () => {
      measure()
      apply(applied.current, true)
    }
    settle()
    const observer = new ResizeObserver(settle)
    if (groupRef.current) observer.observe(groupRef.current)
    document.fonts?.ready.then(settle)
    return () => observer.disconnect()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [itemsKey, size, gap, swell, barge, shrink])

  useEffect(() => {
    if (applied.current === at) return
    applied.current = at
    apply(at, false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [at])

  useEffect(() => () => mvs.current.forEach(mv => {
    mv.x.destroy()
    mv.sx.destroy()
    mv.sy.destroy()
  }), [])

  const commit = (index, instant) => {
    if (disabled || index === at || !list[index] || list[index].disabled) return
    applied.current = index
    apply(index, instant)
    if (value === undefined) setInner(list[index].value)
    onChange?.(list[index].value, index)
  }

  const stepFrom = (index, direction) => {
    const count = list.length
    let next = index
    for (let tries = 0; tries < count; tries += 1) {
      next = (next + direction + count) % count
      if (!list[next].disabled) return next
    }
    return index
  }

  const onKeyDown = (event, index) => {
    let next = null
    if (event.key === 'ArrowRight' || event.key === 'ArrowDown') next = stepFrom(index, 1)
    else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') next = stepFrom(index, -1)
    else if (event.key === 'Home') next = stepFrom(-1, 1)
    else if (event.key === 'End') next = stepFrom(list.length, -1)
    else if (event.key === ' ' || event.key === 'Enter') next = index
    if (next === null) return
    event.preventDefault()
    commit(next, true)
    chipRefs.current[next]?.focus()
  }

  return (
    <div
      ref={groupRef}
      role={navigation ? 'group' : 'radiogroup'}
      aria-label={ariaLabel}
      data-disabled={disabled ? '' : undefined}
      className={`jelly-radio${className ? ` ${className}` : ''}`}
      style={{
        '--jr-chip': chipColor,
        '--jr-active': activeColor,
        '--jr-text': textColor,
        '--jr-active-text': activeTextColor,
        '--jr-gap': `${gap}px`,
        '--jr-radius': `${radius}px`,
        '--jr-h': `${height}px`,
        '--jr-font': `${font}px`,
        '--jr-px': `${paddingX}px`,
      }}
    >
      {list.map((item, index) => (
        <Chip
          key={item.value}
          mv={mvFor(index)}
          ref={element => { chipRefs.current[index] = element }}
          as={navigation ? MotionNavLink : motion.button}
          to={navigation ? item.value : undefined}
          end={navigation || undefined}
          type={navigation ? undefined : 'button'}
          role={navigation ? undefined : 'radio'}
          aria-label={item.ariaLabel}
          aria-description={item.description}
          aria-checked={navigation ? undefined : index === at}
          tabIndex={navigation ? undefined : index === at || (at < 0 && index === 0) ? 0 : -1}
          disabled={disabled || Boolean(item.disabled)}
          className={`jelly-radio__chip${item.className ? ` ${item.className}` : ''}`}
          data-on={index === at ? 'true' : 'false'}
          onClick={event => commit(index, event.detail === 0)}
          onKeyDown={navigation ? undefined : event => onKeyDown(event, index)}
        >
          <span className="jelly-radio__skin">
            {item.content ? <span className="jelly-radio__content">{item.content}</span> : <>
              {item.icon ? <span className="jelly-radio__icon">{item.icon}</span> : null}
              <span className="jelly-radio__label">{item.label}</span>
              {item.description ? <span className="jelly-radio__description">{item.description}</span> : null}
            </>}
          </span>
        </Chip>
      ))}
    </div>
  )
}
