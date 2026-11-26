import { useEffect, useState } from 'react'
import { KeyRound, Save, UserRound } from 'lucide-react'
import { api, post } from '../api'
import { useSession, useToast } from '../App'
import LoadingState from '../components/LoadingState'
import { roles } from '../auth'
import '../admin.css'

export default function ProfilePage() {
  const { session } = useSession()
  const toast = useToast()
  const [profile, setProfile] = useState(null)
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api('/api/profile').then(result => {
      setProfile(result.user); setName(result.user.name); setPhone(result.user.phone || '')
    }).catch(error => toast(error.message, 'error'))
  }, [toast])

  const updateProfile = async event => {
    event.preventDefault(); setSaving(true)
    try {
      const result = await api('/api/profile', { method: 'PATCH', body: JSON.stringify({ name, phone }) })
      setProfile(result.user); toast('个人资料已更新')
    } catch (error) { toast(error.message, 'error') }
    finally { setSaving(false) }
  }

  const updatePassword = async event => {
    event.preventDefault(); setSaving(true)
    try {
      await post('/api/profile/password', { current_password: currentPassword, new_password: newPassword })
      setCurrentPassword(''); setNewPassword(''); toast('密码已更新')
    } catch (error) { toast(error.message, 'error') }
    finally { setSaving(false) }
  }

  if (!profile) return <LoadingState label="正在加载个人资料" />
  return <div className="page profile-page">
    <header className="page-heading"><div><span className="section-kicker">账号设置</span><h1>个人中心</h1><p>{roles[session.role]?.label} · {profile.username}</p></div></header>
    <section className="profile-section">
      <h2><UserRound size={19} />个人资料</h2>
      <form onSubmit={updateProfile}>
        <label>姓名<input required maxLength="80" value={name} onChange={event => setName(event.target.value)} /></label>
        <label>联系电话<input maxLength="40" value={phone} onChange={event => setPhone(event.target.value)} /></label>
        {profile.community_id && <p>所属社区：{profile.community_id}</p>}
        <button className="btn" disabled={saving}><Save size={15} />保存资料</button>
      </form>
    </section>
    <section className="profile-section">
      <h2><KeyRound size={19} />修改密码</h2>
      <form onSubmit={updatePassword}>
        <label>当前密码<input type="password" autoComplete="current-password" required value={currentPassword} onChange={event => setCurrentPassword(event.target.value)} /></label>
        <label>新密码<input type="password" autoComplete="new-password" minLength="10" maxLength="200" required value={newPassword} onChange={event => setNewPassword(event.target.value)} /></label>
        <button className="btn" disabled={saving}><KeyRound size={15} />更新密码</button>
      </form>
    </section>
  </div>
}
