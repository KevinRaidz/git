export const roles = {
  superadmin: { label: '超级管理员', name: '系统管理员', username: 'admin_demo', home: '/admin/console' },
  elder: { label: '老人', name: '张桂芳', username: 'elder_demo', home: '/elder/home' },
  family: { label: '家属', name: '李伟', username: 'family_demo', home: '/family/overview' },
  community: { label: '社区', name: '王芳', username: 'community_demo', home: '/community/alerts' },
  volunteer: { label: '志愿者', name: '赵敏', username: 'volunteer_demo', home: '/volunteer/tasks' },
}

export function roleForPath(path) {
  if (path.startsWith('/admin/')) return 'superadmin'
  if (path.startsWith('/elder/')) return 'elder'
  if (path.startsWith('/family/')) return 'family'
  if (path.startsWith('/community/') || path.startsWith('/demo/')) return 'community'
  if (path.startsWith('/volunteer/')) return 'volunteer'
  return null
}

export function menuPermissionForPath(path) {
  if (path.startsWith('/admin/')) return 'menu.admin'
  if (path.startsWith('/community/') || path.startsWith('/demo/')) return 'menu.community'
  if (path.startsWith('/elder/')) return 'menu.elder'
  if (path.startsWith('/family/')) return 'menu.family'
  if (path.startsWith('/volunteer/')) return 'menu.volunteer'
  return 'profile.read'
}

export function signInUrl(role, next = '') {
  const params = new URLSearchParams()
  if (roles[role]) params.set('role', role)
  if (next.startsWith('/') && !next.startsWith('//')) params.set('next', next)
  return `/login${params.size ? `?${params}` : ''}`
}
