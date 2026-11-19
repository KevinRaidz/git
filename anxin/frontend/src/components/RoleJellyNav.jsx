import { useLocation, useNavigate } from 'react-router-dom'
import JellyRadio from './JellyRadio'

const linksByRole = {
  elder: [
    { to: '/elder/home', label: '今日平安' },
    { to: '/elder/sos', label: '紧急求助' },
  ],
  family: [{ to: '/family/overview', label: '爸妈总览' }],
  community: [
    { to: '/community/dashboard', label: '安全驾驶舱' },
    { to: '/community/elders', label: '三个清单' },
    { to: '/community/alerts', label: '预警工单' },
    { to: '/demo/simulator', label: '演示模拟器' },
  ],
  volunteer: [{ to: '/volunteer/tasks', label: '我的任务' }],
}

export default function RoleJellyNav({ role, tone = 'light', className = '' }) {
  const location = useLocation()
  const navigate = useNavigate()
  const links = linksByRole[role] || linksByRole.community
  const dark = tone === 'dark'

  return (
    <JellyRadio
      className={`nav-links jelly-nav${className ? ` ${className}` : ''}`}
      items={links.map(link => ({ value: link.to, label: link.label }))}
      value={location.pathname}
      onChange={path => navigate(path)}
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
      ariaLabel="页面导航"
    />
  )
}
