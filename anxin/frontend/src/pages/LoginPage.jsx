import { Building2, HandHeart, LogIn, UserRound, UsersRound } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSession } from '../App'
import Brand from '../components/Brand'
import { useBodyClass } from '../hooks'
import { scrollToUnifiedSection } from '../unifiedSections'

const roles = [
  { id: 'elder', title: '我是老人', detail: '张桂芳 · 82 岁 · 今日平安打卡与求助', Icon: UserRound },
  { id: 'family', title: '我是子女', detail: '李伟 · 上海 · 远程查看母亲状态', Icon: UsersRound },
  { id: 'community', title: '我是社区', detail: '王芳 · 网格员 · 驾驶舱 / 三个清单 / 工单', Icon: Building2 },
  { id: 'volunteer', title: '我是志愿者', detail: '赵敏 · 银龄互助 · 接单探访', Icon: HandHeart },
]

export default function LoginPage({ embedded = false, onOpenAuth }) {
  useBodyClass(embedded ? null : 'login-body')
  const { login, session } = useSession()
  const navigate = useNavigate()
  const [pending, setPending] = useState('')

  const enter = async role => {
    if (!session?.authenticated) {
      if (embedded && onOpenAuth) onOpenAuth()
      else navigate('/login')
      return
    }
    setPending(role)
    if (embedded) scrollToUnifiedSection(role)
    try {
      const next = await login(role)
      if (!embedded) navigate(next.home)
    } finally {
      setPending('')
    }
  }

  const Root = embedded ? 'div' : 'main'

  return (
    <Root id={embedded ? undefined : 'main-content'} className="page login-page">
      <header className="login-header">
        <h1 className="login-brand"><Brand /></h1>
        <p className="muted login-subtitle">独居老人 AI 安全守护与社区关爱平台 · 演示登录</p>
        {embedded && <button className="login-account-button" type="button" onClick={onOpenAuth}><LogIn size={16} />账号登录 / 注册</button>}
      </header>
      <div className="login-main">
        <div className="role-grid">
          {roles.map(({ id, title, detail, Icon }) => (
            <div className="role-form" key={id}>
              <button className="card role-card" type="button" onClick={() => enter(id)} disabled={Boolean(pending)} aria-busy={pending === id}>
                <span className="role-icon" aria-hidden="true"><Icon size={34} strokeWidth={1.7} /></span>
                <strong>{title}</strong>
                <span className="muted">{detail}</span>
              </button>
            </div>
          ))}
        </div>
      </div>
      <p className="muted login-footer">中国大学生计算机设计大赛 · Web 应用与开发 · 演示数据为模拟生成</p>
    </Root>
  )
}
