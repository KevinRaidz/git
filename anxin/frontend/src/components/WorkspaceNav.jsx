import { BellRing, Check, LogOut, RefreshCw, X } from 'lucide-react'
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import Brand from './Brand'
import RoleJellyNav from './RoleJellyNav'
import { roles } from '../auth'
import { api, post } from '../api'

export default function WorkspaceNav({ session, logout }) {
  const ref = useRef(null)
  const location = useLocation()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [inboxOpen, setInboxOpen] = useState(false)
  const [messages, setMessages] = useState([])
  const [inboxLoading, setInboxLoading] = useState(false)
  const role = session?.role
  const onLogin = location.pathname === '/login' || location.pathname === '/'
  const dark = role === 'community' && location.pathname === '/community/dashboard'
  useLayoutEffect(() => {
    const island = ref.current
    if (!island) return undefined
    const update = () => {
      document.documentElement.style.setProperty('--island-offset', `${Math.ceil(island.getBoundingClientRect().height + 24)}px`)
      window.dispatchEvent(new CustomEvent('anxin:island-resize'))
    }
    update()
    const observer = new ResizeObserver(update)
    observer.observe(island)
    return () => observer.disconnect()
  }, [])
  useEffect(() => {
    if (!role) return undefined
    let current = true
    api('/api/admin/messages').then(result => {
      if (current) setMessages(result.messages || [])
    }).catch(() => {})
    return () => { current = false }
  }, [role])
  const leave = async () => {
    setBusy(true); setError('')
    try { await logout() }
    catch { setError('退出未完成，请重试') }
    finally { setBusy(false) }
  }
  const toggleInbox = async () => {
    const next = !inboxOpen
    setInboxOpen(next)
    if (!next) return
    setInboxLoading(true)
    try { setMessages((await api('/api/admin/messages')).messages || []) }
    catch (requestError) { setError(requestError.message) }
    finally { setInboxLoading(false) }
  }
  const markRead = async message => {
    try {
      await post(`/api/admin/messages/${message.id}/read`)
      setMessages(current => current.map(item => item.id === message.id ? { ...item, read_at: new Date().toISOString() } : item))
    } catch (requestError) { setError(requestError.message) }
  }
  return <nav ref={ref} className={`topnav global-island workspace-nav${dark ? ' topnav-dashboard' : ''}`} aria-label="主导航" data-testid="global-island">
    <Link to={role && !onLogin ? session.home : '/login'} className="nav-brand" aria-label={role && !onLogin ? '返回我的工作台' : '返回登录首页'}><Brand /><span className="brand-subtitle">独居老人守护平台</span></Link>
    {!onLogin && role ? <><RoleJellyNav role={role} permissions={session.permissions || []} tone={dark ? 'dark' : 'light'} className="workspace-links" /><div className="workspace-user"><span className="workspace-avatar" aria-hidden="true">{session.user?.name?.slice(0, 1)}</span><div><strong>{session.user?.name}</strong><span>{roles[role]?.label}端 · 已登录</span></div><div className="workspace-inbox"><button className="workspace-inbox-trigger" onClick={toggleInbox} aria-label="站内消息" aria-expanded={inboxOpen} title="站内消息"><BellRing size={17} />{messages.some(item => !item.read_at) && <span>{messages.filter(item => !item.read_at).length}</span>}</button>{inboxOpen && <section className="workspace-inbox-panel" aria-label="站内消息"><header><strong>站内消息</strong><button className="icon-button" onClick={() => setInboxOpen(false)} aria-label="关闭消息" title="关闭"><X size={16} /></button></header>{inboxLoading ? <p className="workspace-inbox-empty">正在加载</p> : messages.length ? <ul>{messages.slice(0, 12).map(message => <li key={message.id} className={message.read_at ? 'is-read' : ''}><div><strong>{message.title}</strong><p>{message.body}</p><time>{message.created_at}</time></div>{!message.read_at && <button className="icon-button" title="标为已读" aria-label={`标记“${message.title}”已读`} onClick={() => markRead(message)}><Check size={16} /></button>}</li>)}</ul> : <p className="workspace-inbox-empty">暂无消息</p>}</section>}</div><Link className="workspace-profile" to="/profile" aria-label="个人中心" title="个人中心">个人</Link><Link className="workspace-switch" to="/login"><RefreshCw size={14} />切换身份</Link><button className="workspace-logout" disabled={busy} onClick={leave}><LogOut size={15} />{busy ? '退出中…' : '退出登录'}</button></div></> : <span className="workspace-login-label">{role ? '切换账号 · 登录新身份后进入对应工作台' : '欢迎使用 · 请先选择身份登录'}</span>}
    {error && <span className="workspace-nav-error" role="alert">{error}</span>}
  </nav>
}
