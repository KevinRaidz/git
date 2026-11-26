/* eslint-disable react-refresh/only-export-components */
import { createContext, lazy, Suspense, useContext, useEffect, useMemo, useState } from 'react'
import { Link, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { api, post } from './api'
import AppShell from './components/AppShell'
import GlobalIsland from './components/WorkspaceNav'
import LoadingState from './components/LoadingState'
import { menuPermissionForPath, roles, roleForPath, signInUrl } from './auth'
const AlertsPage = lazy(() => import('./pages/CareCenterPage'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const ElderHomePage = lazy(() => import('./pages/ElderHomePage'))
const ElderSosPage = lazy(() => import('./pages/ElderSosPage'))
const EldersPage = lazy(() => import('./pages/EldersPage'))
const FamilyPage = lazy(() => import('./pages/FamilyPage'))
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'))
const SimulatorPage = lazy(() => import('./pages/SignalLabPage'))
const VolunteerPage = lazy(() => import('./pages/VolunteerPage'))
const SignInPage = lazy(() => import('./pages/SignInPage'))
const AdminPage = lazy(() => import('./pages/AdminPage'))
const ProfilePage = lazy(() => import('./pages/ProfilePage'))

const SessionContext = createContext(null)
const ToastContext = createContext(() => {})

export const useSession = () => useContext(SessionContext)
export const useToast = () => useContext(ToastContext)

function StandardPage({ children }) {
  return <AppShell>{children}</AppShell>
}

function RoleGate({ role, children }) {
  const { session } = useSession()
  const location = useLocation()
  const target = location.pathname + location.search
  if (!session?.role) return <Navigate replace to={signInUrl(role, target)} />
  const elevated = session.permissions?.includes('system.*')
  if (role && session.role !== role && !elevated) return <main id="main-content" className="auth-access"><h1>请使用{roles[role].label}账号进入</h1><p>你当前登录的是 {session.user?.name} · {roles[session.role]?.label}账号。切换身份后才能查看这个工作台。</p><div><Link className="btn" to={signInUrl(role, target)}>切换身份登录</Link><Link className="btn btn-ghost" to={session.home}>返回我的工作台</Link></div></main>
  const menuPermission = menuPermissionForPath(location.pathname)
  if (!elevated && !session.permissions?.includes(menuPermission)) return <main id="main-content" className="auth-access"><h1>当前账号没有此页面权限</h1><p>请联系系统管理员调整角色菜单权限。</p><Link className="btn btn-ghost" to={session.home}>返回我的工作台</Link></main>
  return children
}

export default function App() {
  const location = useLocation()
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)
  const [sessionError, setSessionError] = useState('')
  const [toast, setToast] = useState(null)

  useEffect(() => {
    api('/api/session')
      .then(setSession)
      .catch(() => setSessionError('暂时无法连接服务，请确认后端已启动后重试。'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    const expired = () => setSession(null)
    window.addEventListener('anxin:session-expired', expired)
    return () => window.removeEventListener('anxin:session-expired', expired)
  }, [])

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
    async login(credentials) {
      const next = await post('/api/session', credentials)
      setSession(next)
      return next
    },
    async logout() {
      await api('/api/session', { method: 'DELETE' })
      // 新文档清除旧工作台状态，避免路由守卫与退出重定向竞争。
      window.location.replace('/login')
    },
  }), [session, loading])

  if (loading) return <LoadingState label="正在确认登录状态" />
  if (sessionError) return <main className="auth-access"><h1>服务暂时未连接</h1><p>{sessionError}</p><button className="btn" onClick={() => window.location.reload()}>重新连接</button></main>

  const protect = (path, page, standard = true) => <RoleGate role={roleForPath(path)}>{standard ? <StandardPage>{page}</StandardPage> : page}</RoleGate>

  return (
    <SessionContext.Provider value={value}>
      <ToastContext.Provider value={showToast}>
        <a className="skip-link" href="#main-content">跳到主要内容</a>
        <GlobalIsland session={session} logout={value.logout} />
        <div className={`route-stage${location.pathname === '/community/dashboard' && session?.role === 'community' ? ' dashboard-stage' : ''}`}>
          <Suspense fallback={<LoadingState label="正在加载页面" />}>
            <Routes>
            <Route path="/" element={<Navigate replace to={session?.role ? session.home : '/login'} />} />
            <Route path="/login" element={<SignInPage />} />
            <Route path="/profile" element={<RoleGate><StandardPage><ProfilePage /></StandardPage></RoleGate>} />
            <Route path="/admin/console" element={protect('/admin/console', <AdminPage />)} />
            <Route path="/community/manage" element={protect('/community/manage', <AdminPage />)} />
            <Route path="/elder/home" element={protect('/elder/home', <ElderHomePage />, false)} />
            <Route path="/elder/sos" element={protect('/elder/sos', <ElderSosPage />, false)} />
            <Route path="/family/overview" element={protect('/family/overview', <FamilyPage />)} />
            <Route path="/community/dashboard" element={protect('/community/dashboard', <DashboardPage />, false)} />
            <Route path="/community/elders" element={protect('/community/elders', <EldersPage />)} />
            <Route path="/community/alerts" element={protect('/community/alerts', <AlertsPage />)} />
            <Route path="/volunteer/tasks" element={protect('/volunteer/tasks', <VolunteerPage />)} />
            <Route path="/demo/simulator" element={protect('/demo/simulator', <SimulatorPage />)} />
            <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </Suspense>
        </div>
        <div className={`app-toast${toast ? ' is-visible' : ''}`} data-tone={toast?.tone} role="status" aria-live="polite">
          {toast?.message || ''}
        </div>
      </ToastContext.Provider>
    </SessionContext.Provider>
  )
}
