import { ArrowLeft, ArrowRight, Building2, Eye, EyeOff, HandHeart, LogIn, UserPlus, UserRound, UsersRound, X } from 'lucide-react'
import { createPortal } from 'react-dom'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSession } from '../App'
import Brand from './Brand'

const accountTypes = [
  { value: 'admin', title: '管理员', detail: '社区管理与服务调度', Icon: Building2 },
  { value: 'user', title: '普通用户', detail: '查看家人状态与服务进展', Icon: UserRound },
]
const userRoles = [
  { value: 'elder', title: '老人', detail: '平安状态与紧急求助', Icon: UserRound },
  { value: 'family', title: '子女', detail: '远程查看家人状态', Icon: UsersRound },
  { value: 'community', title: '社区', detail: '社区服务与事项协同', Icon: Building2 },
  { value: 'volunteer', title: '志愿者', detail: '查看探访与服务任务', Icon: HandHeart },
]

function registrationPrefill(identifier) {
  const value = identifier.trim()
  if (value.includes('@')) return { email: value }
  if (/^[+\d\s()-]{7,}$/.test(value)) return { phone: value }
  return { username: value }
}

export default function AuthDialog({ onClose }) {
  const { authenticate, register } = useSession()
  const navigate = useNavigate()
  const [mode, setMode] = useState('choice')
  const [step, setStep] = useState('role')
  const [accountType, setAccountType] = useState('')
  const [accountRole, setAccountRole] = useState('')
  const [identifier, setIdentifier] = useState('')
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [password, setPassword] = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [notFound, setNotFound] = useState(false)
  const [pending, setPending] = useState(false)

  useEffect(() => {
    const onKeyDown = event => {
      if (event.key === 'Escape' && !pending) onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [onClose, pending])

  const beginLogin = () => {
    setMode('login')
    setStep('role')
    setAccountType('')
    setAccountRole('')
    setError('')
    setNotFound(false)
  }

  const beginRegistration = (prefill = {}) => {
    setMode('register')
    setAccountRole(prefill.role || '')
    setUsername(prefill.username || '')
    setEmail(prefill.email || '')
    setPhone(prefill.phone || '')
    setPassword('')
    setPasswordConfirm('')
    setError('')
    setNotFound(false)
  }

  const finish = next => {
    onClose()
    navigate(next.home, { replace: true })
  }

  const submitLogin = async event => {
    event.preventDefault()
    setError('')
    setNotFound(false)
    setPending(true)
    try {
      finish(await authenticate({ account_type: accountType, role: accountRole, identifier, password }))
    } catch (requestError) {
      setError(requestError.message)
      setNotFound(requestError.code === 'USER_NOT_FOUND')
    } finally {
      setPending(false)
    }
  }

  const submitRegistration = async event => {
    event.preventDefault()
    setError('')
    setPending(true)
    try {
      finish(await register({
        username,
        email,
        phone,
        role: accountRole,
        password,
        password_confirm: passwordConfirm,
      }))
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setPending(false)
    }
  }

  return createPortal(
    <div className="auth-backdrop">
      <section className="auth-dialog" role="dialog" aria-modal="true" aria-labelledby="auth-title">
        <button className="auth-close icon-button" type="button" onClick={onClose} aria-label="关闭登录窗口"><X size={19} /></button>
        <div className="auth-dialog-brand"><Brand /></div>
        {mode === 'choice' && (
          <div className="auth-stage" key="choice">
            <span className="section-kicker">安芯账号</span>
            <h2 id="auth-title">欢迎回来</h2>
            <p className="auth-intro">登录以继续，或创建一个新账号。</p>
            <div className="auth-choice-list">
              <button className="auth-choice" type="button" onClick={beginLogin}>
                <span className="auth-choice-icon"><LogIn size={20} /></span>
                <span><b>登录账号</b><small>已有账号，继续使用</small></span>
                <ArrowRight size={18} />
              </button>
              <button className="auth-choice" type="button" onClick={() => beginRegistration()}>
                <span className="auth-choice-icon"><UserPlus size={20} /></span>
                <span><b>注册新账号</b><small>首次使用安芯</small></span>
                <ArrowRight size={18} />
              </button>
            </div>
          </div>
        )}

        {mode === 'login' && step === 'role' && (
          <div className="auth-stage" key="login-role">
            <button className="auth-back" type="button" onClick={() => setMode('choice')}><ArrowLeft size={15} />返回</button>
            <span className="section-kicker">账号登录 · 01</span>
            <h2 id="auth-title">选择账号身份</h2>
            <p className="auth-intro">请选择与账号对应的身份。</p>
            <div className="auth-role-options" role="radiogroup" aria-label="账号身份">
              {accountTypes.map(({ value, title, detail, Icon }) => (
                <button
                  className={`auth-role-option${accountType === value ? ' is-selected' : ''}`}
                  type="button"
                  role="radio"
                  aria-checked={accountType === value}
                  key={value}
                  onClick={() => setAccountType(value)}
                >
                  <Icon size={19} />
                  <span><b>{title}</b><small>{detail}</small></span>
                </button>
              ))}
            </div>
            <button className="btn auth-primary" type="button" disabled={!accountType} onClick={() => { setStep(accountType === 'user' ? 'user-role' : 'credentials'); setError('') }}>
              继续 <ArrowRight size={17} />
            </button>
          </div>
        )}

        {mode === 'login' && step === 'user-role' && (
          <div className="auth-stage" key="login-user-role">
            <button className="auth-back" type="button" onClick={() => { setStep('role'); setAccountRole('') }}><ArrowLeft size={15} />更换账号类型</button>
            <span className="section-kicker">普通用户登录 · 02</span>
            <h2 id="auth-title">选择使用身份</h2>
            <p className="auth-intro">请选择账号注册时绑定的角色。</p>
            <div className="auth-role-options" role="radiogroup" aria-label="用户角色">
              {userRoles.map(({ value, title, detail, Icon }) => (
                <button
                  className={`auth-role-option${accountRole === value ? ' is-selected' : ''}`}
                  type="button"
                  role="radio"
                  aria-checked={accountRole === value}
                  key={value}
                  onClick={() => setAccountRole(value)}
                >
                  <Icon size={19} />
                  <span><b>{title}</b><small>{detail}</small></span>
                </button>
              ))}
            </div>
            <button className="btn auth-primary" type="button" disabled={!accountRole} onClick={() => { setStep('credentials'); setError('') }}>
              继续 <ArrowRight size={17} />
            </button>
          </div>
        )}

        {mode === 'login' && step === 'credentials' && (
          <form className="auth-stage" key="login-credentials" onSubmit={submitLogin}>
            <button className="auth-back" type="button" onClick={() => { setStep(accountType === 'user' ? 'user-role' : 'role'); setError('') }}><ArrowLeft size={15} />更换身份</button>
            <span className="section-kicker">{accountType === 'admin' ? '管理员' : `${userRoles.find(role => role.value === accountRole)?.title}用户`}登录 · 03</span>
            <h2 id="auth-title">输入账号信息</h2>
            <label className="auth-field">邮箱、电话或用户名
              <input autoComplete="username" autoFocus value={identifier} onChange={event => setIdentifier(event.target.value)} placeholder="name@example.com" maxLength={128} required />
            </label>
            <label className="auth-field">密码
              <span className="auth-password-wrap">
                <input autoComplete="current-password" type={showPassword ? 'text' : 'password'} value={password} onChange={event => setPassword(event.target.value)} placeholder="输入密码" maxLength={128} required />
                <button className="auth-password-toggle" type="button" onClick={() => setShowPassword(value => !value)} aria-label={showPassword ? '隐藏密码' : '显示密码'}>{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button>
              </span>
            </label>
            {error && <div className="auth-error" role="alert">{error}</div>}
            {notFound && <button className="auth-inline-link" type="button" onClick={() => beginRegistration({ ...registrationPrefill(identifier), role: accountType === 'user' ? accountRole : '' })}>去注册新账号 <ArrowRight size={15} /></button>}
            <button className="btn auth-primary" type="submit" disabled={pending}>{pending ? '正在登录…' : '登录'} <ArrowRight size={17} /></button>
          </form>
        )}

        {mode === 'register' && (
          <form className="auth-stage auth-register-stage" key="register" onSubmit={submitRegistration}>
            <button className="auth-back" type="button" onClick={() => setMode('choice')}><ArrowLeft size={15} />返回</button>
            <span className="section-kicker">创建普通用户账号 · 01</span>
            <h2 id="auth-title">注册安芯账号</h2>
            <div className="auth-role-options auth-register-roles" role="radiogroup" aria-label="注册角色">
              {userRoles.map(({ value, title, detail, Icon }) => (
                <button
                  className={`auth-role-option${accountRole === value ? ' is-selected' : ''}`}
                  type="button"
                  role="radio"
                  aria-checked={accountRole === value}
                  key={value}
                  onClick={() => setAccountRole(value)}
                >
                  <Icon size={19} />
                  <span><b>{title}</b><small>{detail}</small></span>
                </button>
              ))}
            </div>
            <label className="auth-field">用户名
              <input autoComplete="username" autoFocus value={username} onChange={event => setUsername(event.target.value)} placeholder="设置用户名" minLength={2} maxLength={32} required />
            </label>
            <div className="auth-contact-fields">
              <label className="auth-field">邮箱 <span className="auth-optional">选填</span>
                <input autoComplete="email" type="email" value={email} onChange={event => setEmail(event.target.value)} placeholder="name@example.com" maxLength={128} />
              </label>
              <label className="auth-field">电话 <span className="auth-optional">选填</span>
                <input autoComplete="tel" type="tel" value={phone} onChange={event => setPhone(event.target.value)} placeholder="至少填写邮箱或电话" maxLength={24} />
              </label>
            </div>
            <label className="auth-field">密码
              <input autoComplete="new-password" type="password" value={password} onChange={event => setPassword(event.target.value)} placeholder="至少 8 位" minLength={8} maxLength={128} required />
            </label>
            <label className="auth-field">确认密码
              <input autoComplete="new-password" type="password" value={passwordConfirm} onChange={event => setPasswordConfirm(event.target.value)} placeholder="再次输入密码" minLength={8} maxLength={128} required />
            </label>
            {error && <div className="auth-error" role="alert">{error}</div>}
            <button className="btn auth-primary" type="submit" disabled={pending || !accountRole}>{pending ? '正在创建账号…' : '创建账号'} <ArrowRight size={17} /></button>
          </form>
        )}
        <footer className="auth-dialog-footer">
          <span>社区关爱，从安心开始</span>
          <button type="button" onClick={onClose}>暂不登录，体验演示</button>
        </footer>
      </section>
    </div>,
    document.body,
  )
}
