/* eslint-disable react-refresh/only-export-components */
import { createContext, lazy, Suspense, useContext, useEffect, useMemo, useState } from 'react'
import { Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { api, post } from './api'
import AppShell from './components/AppShell'
import GlobalIsland from './components/GlobalIsland'
import LoadingState from './components/LoadingState'
import { isUnifiedPath } from './unifiedSections'
const AlertsPage = lazy(() => import('./pages/AlertsPage'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const ElderHomePage = lazy(() => import('./pages/ElderHomePage'))
const ElderSosPage = lazy(() => import('./pages/ElderSosPage'))
const EldersPage = lazy(() => import('./pages/EldersPage'))
const FamilyPage = lazy(() => import('./pages/FamilyPage'))
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'))
const SimulatorPage = lazy(() => import('./pages/SimulatorPage'))
const VolunteerPage = lazy(() => import('./pages/VolunteerPage'))
const UnifiedPage = lazy(() => import('./pages/UnifiedPage'))

const SessionContext = createContext(null)
const ToastContext = createContext(() => {})
const roleForPath = pathname => {
  if (pathname.startsWith('/elder/')) return 'elder'
  if (pathname.startsWith('/family/')) return 'family'
  if (pathname.startsWith('/volunteer/')) return 'volunteer'
  if (pathname.startsWith('/community/') || pathname.startsWith('/demo/')) return 'community'
  return null
}

export const useSession = () => useContext(SessionContext)
export const useToast = () => useContext(ToastContext)

function StandardPage({ children }) {
  return <AppShell>{children}</AppShell>
}

export default function App() {
  const location = useLocation()
  const navigate = useNavigate()
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState(null)

  useEffect(() => {
    api('/api/session').then(async current => {
      if (current.authenticated) {
        setSession(current)
        return
      }
      const initialRole = roleForPath(window.location.pathname) || 'community'
      const next = current.role === initialRole ? current : await post('/api/session', { role: initialRole })
      setSession(next)
    }).catch(() => setSession({ ok: true, role: null, authenticated: false })).finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (loading) return
    const isAdmin = session?.authenticated && session.account?.account_type === 'admin'
    if (session?.authenticated && session.account?.account_type === 'user'
      && (isUnifiedPath(location.pathname) || roleForPath(location.pathname) !== session.role)) {
      navigate(session.home, { replace: true })
      return
    }
    const expectedRole = roleForPath(location.pathname) || (!session?.role ? 'community' : null)
    if (!expectedRole || session?.role === expectedRole || isAdmin) return
    if (session?.authenticated) {
      navigate(session.home, { replace: true })
      return
    }
    post('/api/session', { role: expectedRole }).then(setSession).catch(() => {})
  }, [loading, location.pathname, navigate, session?.account?.account_type, session?.authenticated, session?.home, session?.role])

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'instant' })
  }, [location.pathname])

  const showToast = (message, tone = 'success', duration = 2600) => {
    const id = Date.now()
    setToast({ id, message, tone })
    window.setTimeout(() => setToast(current => current?.id === id ? null : current), duration)
  }

  const value = useMemo(() => ({
    session,
    loading,
    async login(role) {
      const next = await post('/api/session', { role })
      setSession(next)
      return next
    },
    async authenticate(credentials) {
      const next = await post('/api/auth/login', credentials)
      setSession(next)
      return next
    },
    async register(account) {
      const next = await post('/api/auth/register', account)
      setSession(next)
      return next
    },
    async logout() {
      const next = await api('/api/session', { method: 'DELETE' })
      setSession(next)
    },
  }), [session, loading])
  const routeRole = roleForPath(location.pathname)
  const isAdmin = session?.authenticated && session.account?.account_type === 'admin'
  const isRestrictedUser = session?.authenticated && session.account?.account_type === 'user'
  const routeReady = (!isRestrictedUser || (!isUnifiedPath(location.pathname) && routeRole === session.role))
    && (isUnifiedPath(location.pathname) || isAdmin || session?.role === routeRole)

  return (
    <SessionContext.Provider value={value}>
      <ToastContext.Provider value={showToast}>
        <a className="skip-link" href="#main-content">跳到主要内容</a>
        <GlobalIsland session={session} login={value.login} logout={value.logout} />
        <div className={`route-stage${location.pathname === '/community/dashboard' ? ' dashboard-stage' : ''}${location.pathname === '/' || location.pathname === '/login' ? ' unified-stage' : ''}${isRestrictedUser ? ' user-role-stage' : ''}`}>
          <Suspense fallback={<LoadingState label="正在加载页面" />}>
            {loading || !routeReady ? <LoadingState label="正在切换角色权限" /> : (
            <Routes>
            <Route path="/" element={<UnifiedPage />} />
            <Route path="/login" element={<UnifiedPage />} />
            <Route path="/elder/home" element={<ElderHomePage />} />
            <Route path="/elder/sos" element={<ElderSosPage />} />
            <Route path="/family/overview" element={<StandardPage><FamilyPage /></StandardPage>} />
            <Route path="/community/dashboard" element={<DashboardPage />} />
            <Route path="/community/elders" element={<StandardPage><EldersPage /></StandardPage>} />
            <Route path="/community/alerts" element={<StandardPage><AlertsPage /></StandardPage>} />
            <Route path="/volunteer/tasks" element={<StandardPage><VolunteerPage /></StandardPage>} />
            <Route path="/demo/simulator" element={<StandardPage><SimulatorPage /></StandardPage>} />
            <Route path="*" element={<NotFoundPage />} />
            </Routes>
            )}
          </Suspense>
        </div>
        <div className={`app-toast${toast ? ' is-visible' : ''}`} data-tone={toast?.tone} role="status" aria-live="polite">
          {toast?.message || ''}
        </div>
      </ToastContext.Provider>
    </SessionContext.Provider>
  )
}
