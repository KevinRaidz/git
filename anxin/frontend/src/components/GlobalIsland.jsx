import { LogOut } from 'lucide-react'
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import Brand from './Brand'
import JellyRadio from './JellyRadio'
import RoleJellyNav from './RoleJellyNav'
import { isUnifiedPath, scrollToUnifiedSection, unifiedSections } from '../unifiedSections'

const roleNames = { elder: '老人', family: '子女', community: '社区', volunteer: '志愿者' }

function roleFromPath(pathname) {
  if (pathname.startsWith('/elder/')) return 'elder'
  if (pathname.startsWith('/family/')) return 'family'
  if (pathname.startsWith('/volunteer/')) return 'volunteer'
  if (pathname.startsWith('/community/') || pathname.startsWith('/demo/')) return 'community'
  return null
}

export default function GlobalIsland({ session, login, logout }) {
  const ref = useRef(null)
  const location = useLocation()
  const navigate = useNavigate()
  const onUnifiedPage = isUnifiedPath(location.pathname)
  const [activeSection, setActiveSection] = useState('home')
  const role = roleFromPath(location.pathname) || session?.role || 'community'
  const dark = location.pathname === '/community/dashboard' || (onUnifiedPage && activeSection === 'community')

  useEffect(() => {
    if (!onUnifiedPage) return undefined
    const update = event => setActiveSection(event.detail?.value || 'home')
    window.addEventListener('anxin:section-change', update)
    return () => window.removeEventListener('anxin:section-change', update)
  }, [onUnifiedPage])

  useLayoutEffect(() => {
    const island = ref.current
    if (!island) return undefined
    const updateOffset = () => {
      const offset = Math.ceil(island.getBoundingClientRect().height + 24)
      document.documentElement.style.setProperty('--island-offset', `${offset}px`)
      window.dispatchEvent(new CustomEvent('anxin:island-resize', { detail: { offset } }))
    }
    updateOffset()
    const observer = new ResizeObserver(updateOffset)
    observer.observe(island)
    return () => observer.disconnect()
  }, [])

  const glideToSection = selected => {
    setActiveSection(selected)
    scrollToUnifiedSection(selected)
    if (selected !== 'home') login(selected).catch(() => {})
  }

  const leave = async () => {
    await logout()
    navigate('/login')
  }

  if (session?.authenticated && session.account?.account_type === 'user') {
    return (
      <header className="user-account-bar" data-testid="user-account-bar">
        <Brand />
        <div className="family-account-actions">
          <span>{session.account.username} · {roleNames[session.role]}账号</span>
          <button className="icon-button" type="button" onClick={leave} title="退出登录" aria-label="退出登录">
            <LogOut size={17} />
          </button>
        </div>
      </header>
    )
  }

  return (
    <nav
      ref={ref}
      className={`topnav global-island${dark ? ' topnav-dashboard' : ''}`}
      aria-label="全局灵动岛"
      data-testid="global-island"
    >
      <div className="nav-brand">
        <Brand />
        <span className="brand-subtitle">独居老人守护平台</span>
      </div>
      {onUnifiedPage ? (
        <JellyRadio
          className="nav-links jelly-nav login-jelly-nav"
          items={unifiedSections}
          value={activeSection}
          onChange={glideToSection}
          chipColor="transparent"
          activeColor={dark ? 'rgba(255, 255, 255, .12)' : 'rgba(232, 115, 74, .16)'}
          textColor={dark ? '#8D9096' : '#5f584e'}
          activeTextColor={dark ? '#F4F4F5' : '#9f3f24'}
          size="sm"
          gap={4}
          radius={14}
          swell={0.14}
          barge={4}
          shrink={0.03}
          jelly={1.15}
          bounce={0.32}
          ariaLabel="角色快捷入口"
        />
      ) : <RoleJellyNav role={role} tone={dark ? 'dark' : 'light'} />}
      {!onUnifiedPage && (
        <div className="nav-user">
          {roleNames[role]}端
          <button className="icon-button" type="button" onClick={leave} title="退出登录" aria-label="退出登录">
            <LogOut size={17} />
          </button>
        </div>
      )}
    </nav>
  )
}
