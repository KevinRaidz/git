import { useLocation } from 'react-router-dom'
import JellyRadio from './JellyRadio'

const linksByRole = {
  superadmin: [
    { to: '/admin/console', label: '系统管理', permission: 'menu.admin' },
    { to: '/community/dashboard', label: '社区总览', permission: 'dashboard.read' },
    { to: '/community/elders', label: '老人档案', permission: 'elder.read' },
    { to: '/community/alerts', label: '关爱响应', permission: 'alert.read' },
  ],
  elder: [
    { to: '/elder/home', label: '今日平安', permission: 'menu.elder' },
    { to: '/elder/sos', label: '紧急求助', permission: 'elder.sos' },
  ],
  family: [{ to: '/family/overview', label: '家人总览', permission: 'menu.family' }],
  community: [
    { to: '/community/alerts', label: '关爱响应', permission: 'alert.read' },
    { to: '/community/elders', label: '老人档案', permission: 'elder.read' },
    { to: '/community/dashboard', label: '安全驾驶舱', permission: 'dashboard.read' },
    { to: '/community/manage', label: '社区管理', permission: 'menu.community' },
    { to: '/demo/simulator', label: '场景体验', permission: 'alert.write' },
  ],
  volunteer: [{ to: '/volunteer/tasks', label: '我的任务', permission: 'menu.volunteer' }],
}

export default function RoleJellyNav({ role, permissions = [], tone = 'light', className = '' }) {
  const location = useLocation()
  const links = (linksByRole[role] || linksByRole.community).filter(link =>
    permissions.includes('system.*') || permissions.includes(link.permission))
  if (!links.length) return null
  const dark = tone === 'dark'

  return (
    <JellyRadio
      className={`nav-links jelly-nav${className ? ` ${className}` : ''}`}
      items={links.map(link => ({ value: link.to, label: link.label }))}
      value={location.pathname}
      navigation
      onChange={() => {}}
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
      ariaLabel="工作台导航"
    />
  )
}
