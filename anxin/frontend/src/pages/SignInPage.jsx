import { Building2, HandHeart, UserRound, UsersRound, LockKeyhole, CheckCircle2, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useSession } from '../App'
import { roles, roleForPath } from '../auth'
import JellyRadio from '../components/JellyRadio'

const icons = { superadmin: ShieldCheck, elder: UserRound, family: UsersRound, community: Building2, volunteer: HandHeart }
const descriptions = { superadmin: '账号、权限、数据与系统配置', elder: '报平安、发起紧急求助', family: '查看家人状态与处理进展', community: '核实预警、管理档案与服务', volunteer: '接收任务、到场与服务回执' }

export default function SignInPage() {
  const [params, setParams] = useSearchParams()
  const chosen = roles[params.get('role')] ? params.get('role') : 'elder'
  const account = roles[chosen]
  const { session, login } = useSession()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)
  const choose = role => {
    const next = new URLSearchParams(params)
    next.set('role', role)
    if (roleForPath(next.get('next') || '') !== role) next.delete('next')
    setParams(next, { replace: true })
    setUsername(''); setPassword(''); setError('')
  }
  const submit = async event => {
    event.preventDefault()
    setPending(true); setError('')
    try {
      const result = await login({ username, password, role: chosen })
      const next = params.get('next') || ''
      navigate(next.startsWith('/') && !next.startsWith('//') && roleForPath(next) === result.role ? next : result.home, { replace: true })
    } catch (e) { setError(e.message) }
    finally { setPending(false) }
  }
  return <main id="main-content" className="auth-page">
    <header className="auth-intro"><span className="care-eyebrow">安芯 · 独居老人守护平台</span><h1>一份关爱，<br />各司其职。</h1><p>选择你的身份，登录专属工作台。<br />每个人只看到自己需要的功能。</p><div className="auth-intro-note"><CheckCircle2 size={19} /><span>预警有依据 · 跟进有记录 · 家属看得见</span></div></header>
    <section className="auth-panel" aria-label="账号登录">
      <span className="section-kicker">欢迎使用安芯</span><h2>选择身份，登录工作台</h2><p className="auth-help">身份决定工作台内容，登录后顶部会显示当前账号。</p>
      <JellyRadio
        className="auth-roles"
        items={Object.entries(roles).map(([key, item]) => {
          const Icon = icons[key]
          return { value: key, label: item.label, ariaLabel: item.label, icon: <Icon size={23} />, description: descriptions[key] }
        })}
        value={chosen}
        onChange={choose}
        disabled={pending}
        chipColor="#fafbf7"
        activeColor="#ecf4e5"
        textColor="#596756"
        activeTextColor="#355b3d"
        size="md"
        gap={9}
        swell={0.035}
        barge={0}
        shrink={0.01}
        ariaLabel="选择登录身份"
      />
      <div className="auth-selected"><strong>{account.label}工作台</strong><span>{descriptions[chosen]}</span></div>
      {session?.role && <div className="auth-current">当前已登录：{session.user?.name} · {session.role_name}端。<Link to={session.home}>继续使用当前账号</Link></div>}
      <form onSubmit={submit}>
        <label>账号<input name="username" autoComplete="username" placeholder={`例如 ${account.username}`} value={username} onChange={e => setUsername(e.target.value)} disabled={pending} required maxLength={80} /></label>
        <label>密码<input name="password" type="password" autoComplete="current-password" placeholder="请输入密码" value={password} onChange={e => setPassword(e.target.value)} disabled={pending} required maxLength={200} /></label>
        {error && <p className="auth-error" role="alert">{error}</p>}
        <button type="submit" className="btn auth-submit" disabled={pending}><LockKeyhole size={18} />{pending ? '正在验证账号…' : `登录${account.label}工作台`}</button>
      </form>
      {session?.demo_login_enabled && <div className="auth-demo"><div><strong>先体验演示账号</strong><p>{account.name} · {account.username}<br />统一演示密码：Anxin2026!</p></div><button type="button" disabled={pending} onClick={() => { setUsername(account.username); setPassword('Anxin2026!'); setError('') }}>填入演示账号</button></div>}
      <p className="auth-bottom">演示数据用于体验流程。切换身份需重新登录，账号由服务端校验。</p>
    </section>
  </main>
}
