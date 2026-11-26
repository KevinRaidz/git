import { useCallback, useEffect, useMemo, useState } from 'react'
import { Archive, Bell, ChartNoAxesCombined, Check, Download, FileUp, KeyRound, Plus, RefreshCw, Save, Shield, Users, X } from 'lucide-react'
import { api, post } from '../api'
import { useSession, useToast } from '../App'
import EChart from '../components/EChart'
import JellyRadio from '../components/JellyRadio'
import LoadingState from '../components/LoadingState'
import Modal from '../components/Modal'
import '../admin.css'

const roleLabels = { superadmin: '超级管理员', community: '社区管理员', volunteer: '志愿者', family: '家属', elder: '老人' }
const statusLabels = { active: '启用', disabled: '停用', online: '在线', offline: '离线', inactive: '停用', planned: '待安排', processing: '服务中', completed: '已完成', cancelled: '已取消' }
const columns = {
  templates: [['name', '通知模板'], ['audience_role', '发送对象'], ['category', '消息类型'], ['title', '消息标题'], ['enabled', '状态']],
  accounts: [['name', '姓名'], ['username', '账号'], ['role', '角色'], ['phone', '联系电话'], ['status', '状态']],
  elders: [['name', '老人'], ['age', '年龄'], ['address', '地址'], ['chronic', '病史'], ['allergy', '过敏信息'], ['risk_level', '风险']],
  family: [['family_name', '家属'], ['username', '账号'], ['elder_name', '绑定老人'], ['relation', '关系'], ['phone', '联系电话']],
  devices: [['code', '设备编号'], ['type', '类型'], ['location', '安装位置'], ['elder_name', '所属老人'], ['status', '在线状态'], ['last_reading', '最近读数']],
  services: [['elder_name', '老人'], ['category', '类别'], ['title', '服务内容'], ['assignee_name', '服务人员'], ['scheduled_at', '计划时间'], ['status', '状态']],
  messages: [['title', '标题'], ['category', '类型'], ['created_at', '发送时间'], ['read_at', '阅读状态']],
  logs: [['operator', '操作人'], ['role', '角色'], ['community_id', '社区'], ['module', '模块'], ['action', '操作'], ['object_ref', '数据对象'], ['created_at', '时间'], ['success', '结果'], ['failure_reason', '失败原因']],
  dictionary: [['category', '类别'], ['code', '编码'], ['label', '名称'], ['enabled', '状态'], ['sort_order', '顺序']],
}
const tabLabels = {
  accounts: '账号', elders: '老人档案', family: '家属关系', devices: '设备', services: '服务', messages: '消息', logs: '操作日志',
  templates: '通知模板', config: '系统配置', roles: '角色权限', dictionary: '数据字典', backups: '备份恢复',
}
const paths = {
  templates: '/api/admin/notification-templates',
  accounts: '/api/admin/users', elders: '/api/admin/elders', family: '/api/admin/family-links',
  devices: '/api/admin/devices', services: '/api/admin/services', messages: '/api/admin/messages',
  logs: '/api/admin/audit-logs', config: '/api/admin/config', roles: '/api/admin/roles',
  dictionary: '/api/admin/dictionary', backups: '/api/admin/backups',
}

function valueText(key, value) {
  if (key === 'role') return roleLabels[value] || value || '—'
  if (key === 'status') return statusLabels[value] || value || '—'
  if (key === 'success') return value ? '成功' : '失败'
  if (key === 'read_at') return value ? '已读' : '未读'
  if (key === 'enabled') return value ? '启用' : '停用'
  if (value === null || value === undefined || value === '') return '—'
  if (key === 'audience_role') return roleLabels[value] || (value === 'all' ? '所有账号' : value)
  return String(value)
}

export default function AdminPage() {
  const { session } = useSession()
  const toast = useToast()
  const admin = session?.role === 'superadmin'
  const tabPermission = { accounts: 'account.read', elders: 'elder.read', family: 'family.read', devices: 'device.read', services: 'service.read', messages: 'message.read', templates: 'message.write', logs: 'audit.read' }
  const tabs = (admin ? Object.keys(tabLabels) : ['accounts', 'elders', 'family', 'devices', 'services', 'messages', 'templates', 'logs'])
    .filter(tab => admin || session?.permissions?.includes(tabPermission[tab]))
  const tabWritePermission = { accounts: 'account.write', elders: 'elder.write', family: 'family.write', devices: 'device.write', services: 'service.write', messages: 'message.write', templates: 'message.write' }
  const canExport = admin || session?.permissions?.includes('data.export')
  const [active, setActive] = useState(tabs[0])
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState('')
  const [form, setForm] = useState({})
  const [editing, setEditing] = useState(null)
  const [support, setSupport] = useState({ elders: [], users: [] })
  const [templates, setTemplates] = useState([])
  const [historyDevice, setHistoryDevice] = useState(null)
  const [history, setHistory] = useState([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState('')
  const [backupInterval, setBackupInterval] = useState('24')

  const load = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const query = active === 'accounts' && filter ? `?q=${encodeURIComponent(filter)}` : active === 'elders' && filter ? `?name=${encodeURIComponent(filter)}` : ''
      const result = await api(`${paths[active]}${query}`)
      setData(result)
      if (active === 'backups' && result.schedule) setBackupInterval(String(result.schedule.interval_hours || 24))
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }, [active, filter])

  useEffect(() => {
    const timer = window.setTimeout(load, 0)
    return () => window.clearTimeout(timer)
  }, [load])
  useEffect(() => {
    if (!['accounts', 'elders', 'family', 'devices', 'services', 'messages'].includes(active)) return
    Promise.all([api('/api/admin/elders'), api('/api/admin/users')])
      .then(([elderResult, userResult]) => setSupport({ elders: elderResult.elders, users: userResult.users }))
      .catch(() => setSupport({ elders: [], users: [] }))
  }, [active])
  useEffect(() => {
    if (active !== 'messages' && active !== 'templates') return
    api('/api/admin/notification-templates').then(result => setTemplates(result.templates || [])).catch(() => setTemplates([]))
  }, [active])
  const setField = (key, value) => {
    if (key === 'template_id') {
      const template = templates.find(item => String(item.id) === value)
      return setForm(current => ({ ...current, template_id: value, ...(template ? {
        role: template.audience_role, user_id: '', title: template.title, body: template.body, category: template.category,
      } : {}) }))
    }
    setForm(current => ({ ...current, [key]: value }))
  }
  const fields = useMemo(() => {
    if (active === 'accounts') return [
      ...(!editing ? [{ key: 'username', label: '登录账号', required: true }, { key: 'password', label: '初始密码', required: !editing, type: 'password', placeholder: '留空自动生成' }] : []),
      { key: 'name', label: '姓名', required: true },
      { key: 'role', label: '角色', type: 'select', options: admin ? Object.entries(roleLabels) : [['volunteer', '志愿者'], ['family', '家属'], ['elder', '老人']] },
      { key: 'phone', label: '联系电话' },
      ...(form.role === 'elder' || editing?.role === 'elder' ? [{ key: 'elder_id', label: '绑定老人', type: 'select', options: support.elders.map(item => [String(item.id), item.name]) }] : []),
      ...(admin ? [{ key: 'community_id', label: '所属社区', type: 'number' }] : []),
    ]
    if (active === 'elders') return [
      { key: 'name', label: '姓名', required: true }, { key: 'age', label: '年龄', type: 'number' },
      { key: 'address', label: '居住地址' }, { key: 'chronic', label: '病史' }, { key: 'allergy', label: '过敏信息' },
      { key: 'emergency_contact', label: '紧急联系人' }, { key: 'emergency_phone', label: '联系人电话' },
      { key: 'risk_level', label: '风险等级', type: 'select', options: [['green', '平安'], ['yellow', '需关注'], ['red', '紧急']] },
      { key: 'live_alone', label: '独居状态', type: 'select', options: [['1', '独居'], ['0', '非独居']] },
    ]
    if (active === 'devices') return [
      ...(!editing ? [{ key: 'code', label: '设备编号' }] : []),
      { key: 'type', label: '设备类型', type: 'select', options: [['water', '智能水表'], ['electricity', '智能电表'], ['door', '门磁'], ['motion', '红外活动监测']] },
      { key: 'location', label: '安装位置' }, { key: 'elder_id', label: '绑定老人', type: 'select', options: [['', '未绑定'], ...support.elders.map(item => [String(item.id), item.name])] },
      { key: 'status', label: '设备状态', type: 'select', options: [['online', '在线'], ['offline', '离线'], ['inactive', '停用']] },
      { key: 'last_reading', label: '最近读数' },
    ]
    if (active === 'family') return [
      { key: 'user_id', label: '家属账号', type: 'select', options: support.users.filter(item => item.role === 'family').map(item => [String(item.id), `${item.name} · ${item.username}`]) },
      { key: 'elder_id', label: '绑定老人', type: 'select', options: support.elders.map(item => [String(item.id), item.name]) },
      { key: 'relation', label: '关系' }, { key: 'phone', label: '联系电话' },
      { key: 'emergency_contact', label: '紧急联系人', type: 'select', options: [['0', '否'], ['1', '是']] },
    ]
    if (active === 'services') return [
      { key: 'elder_id', label: '服务对象', type: 'select', options: support.elders.map(item => [String(item.id), item.name]) },
      { key: 'category', label: '服务类别', type: 'select', options: [['visit', '探访'], ['meal', '助餐'], ['medical', '助医'], ['housekeeping', '保洁']] },
      { key: 'title', label: '服务内容', required: true },
      { key: 'assignee_id', label: '指派志愿者', type: 'select', options: [['', '暂不指派'], ...support.users.filter(item => item.role === 'volunteer').map(item => [String(item.id), item.name])] },
      { key: 'scheduled_at', label: '计划时间', type: 'datetime-local' },
    ]
    if (active === 'templates') return [
      { key: 'name', label: '模板名称', required: true },
      { key: 'audience_role', label: '发送对象', type: 'select', options: [['all', '全部账号'], ...Object.entries(roleLabels).filter(([key]) => key !== 'superadmin')] },
      { key: 'category', label: '消息类型', type: 'select', options: [['notice', '社区公告'], ['alert', '预警通知'], ['service', '服务进展']] },
      { key: 'title', label: '消息标题', required: true }, { key: 'body', label: '消息内容', type: 'textarea', required: true },
    ]
    if (active === 'messages') return [
      { key: 'template_id', label: '套用通知模板', type: 'select', options: templates.map(item => [String(item.id), item.name]) },
      { key: 'role', label: '发送对象', type: 'select', options: [['all', '本社区全部账号'], ...Object.entries(roleLabels).filter(([key]) => key !== 'superadmin').map(([key, label]) => [key, label])] },
      { key: 'user_id', label: '指定个人账号', type: 'select', options: [['', '按角色发送'], ...support.users.map(item => [String(item.id), `${item.name} · ${item.username}`])] },
      { key: 'title', label: '消息标题', required: true }, { key: 'body', label: '消息内容', type: 'textarea', required: true },
      { key: 'category', label: '消息类别', type: 'select', options: [['notice', '公告'], ['alert', '预警'], ['service', '服务进展']] },
    ]
    if (active === 'dictionary') return [
      { key: 'category', label: '字典类别', required: true }, { key: 'code', label: '编码', required: true }, { key: 'label', label: '显示名称', required: true },
    ]
    return []
  }, [active, admin, editing, form.role, support, templates])

  const submit = async event => {
    event.preventDefault(); setBusy(true)
    try {
      const body = { ...form }
      if (body.elder_id === '') body.elder_id = null
      if (body.assignee_id === '') body.assignee_id = null
      delete body.template_id
      if (active === 'accounts' && !body.password) delete body.password
      let path = paths[active]
      let method = 'POST'
      if (editing) { path += `/${editing.id}`; method = 'PATCH'; delete body.username; delete body.password }
      await api(path, { method, body: JSON.stringify(body) })
      toast(editing ? '已保存修改' : '已创建')
      setForm({}); setEditing(null); await load()
      if (['accounts', 'elders', 'family', 'devices', 'services'].includes(active)) {
        const [elderResult, userResult] = await Promise.all([api('/api/admin/elders'), api('/api/admin/users')])
        setSupport({ elders: elderResult.elders, users: userResult.users })
      }
    } catch (e) { toast(e.message, 'error') }
    finally { setBusy(false) }
  }

  const beginEdit = item => {
    setEditing(item)
    setForm(Object.fromEntries(fields.map(field => [field.key, item[field.key] == null ? '' : String(item[field.key])])))
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const run = async (fn, message = '已完成') => {
    setBusy(true)
    try { await fn(); toast(message); await load() }
    catch (e) { toast(e.message, 'error') }
    finally { setBusy(false) }
  }

  const openHistory = async device => {
    setHistoryDevice(device)
    setHistory([])
    setHistoryError('')
    setHistoryLoading(true)
    try {
      const result = await api(`/api/admin/devices/${device.id}`)
      setHistory(result.history || [])
    } catch (e) { setHistoryError(e.message) }
    finally { setHistoryLoading(false) }
  }

  const historyOption = useMemo(() => {
    const points = [...history].reverse()
    return {
      grid: { left: 42, right: 18, top: 18, bottom: 32 },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', boundaryGap: false, data: points.map(item => item.recorded_at.slice(5, 16)) },
      yAxis: { type: 'value', name: points[0]?.unit || '', scale: true, splitLine: { lineStyle: { color: '#e5e9e1' } } },
      series: [{ type: 'line', smooth: 0.25, showSymbol: true, data: points.map(item => item.value), lineStyle: { color: '#4c8060', width: 2 }, itemStyle: { color: '#4c8060' }, areaStyle: { color: 'rgba(76,128,96,.12)' } }],
    }
  }, [history])

  const manageRow = item => {
    if (!admin && active !== 'messages' && !session?.permissions?.includes(tabWritePermission[active])) return null
    if (active === 'accounts') return <><button className="icon-button" title="编辑账号" aria-label="编辑账号" onClick={() => beginEdit(item)}><Users size={16} /></button><button className="icon-button" title="重置密码" aria-label="重置密码" onClick={() => run(async () => { const result = await post(`/api/admin/users/${item.id}/reset-password`); if (result.temporary_password) window.alert(`临时密码：${result.temporary_password}`) }, '已重置密码')}><KeyRound size={16} /></button><button className="icon-button" title={item.status === 'active' ? '停用账号' : '启用账号'} aria-label={item.status === 'active' ? '停用账号' : '启用账号'} onClick={() => run(() => api(`/api/admin/users/${item.id}`, { method: 'PATCH', body: JSON.stringify({ status: item.status === 'active' ? 'disabled' : 'active' }) }), '账号状态已更新')}><Archive size={16} /></button></>
    if (active === 'elders') return <><button className="icon-button" title="编辑档案" aria-label="编辑档案" onClick={() => beginEdit(item)}><Users size={16} /></button><button className="icon-button" title="归档老人" aria-label="归档老人" onClick={() => window.confirm(`确认归档 ${item.name} 的老人档案？`) && run(() => api(`/api/admin/elders/${item.id}`, { method: 'DELETE' }), '档案已归档')}><Archive size={16} /></button></>
    if (active === 'family') return <button className="icon-button" title="解绑家属" aria-label="解绑家属" onClick={() => window.confirm(`确认解绑 ${item.family_name} 与 ${item.elder_name}？操作将记录在日志中。`) && run(() => api(`/api/admin/family-links/${item.id}?confirm=1`, { method: 'DELETE' }), '已解除绑定')}><X size={16} /></button>
    if (active === 'devices') return <><button className="icon-button" title="编辑设备" aria-label="编辑设备" onClick={() => beginEdit(item)}><Shield size={16} /></button><button className="icon-button" title="停用设备" aria-label="停用设备" onClick={() => run(() => api(`/api/admin/devices/${item.id}`, { method: 'DELETE' }), '设备已停用')}><Archive size={16} /></button></>
    if (active === 'services') return <><button className="icon-button" title="编辑服务" aria-label="编辑服务" onClick={() => beginEdit(item)}><Users size={16} /></button>{item.status === 'planned' && <button className="icon-button" title="登记到场" aria-label="登记到场" onClick={() => run(() => post(`/api/admin/services/${item.id}/arrival`), '已登记到场')}><Check size={16} /></button>}{item.status !== 'completed' && <button className="icon-button" title="提交服务回执" aria-label="提交服务回执" onClick={() => { const receipt = window.prompt('服务回执'); if (receipt) run(() => post(`/api/admin/services/${item.id}/complete`, { receipt }), '服务已归档') }}><Archive size={16} /></button>}</>
    if (active === 'messages') return <button className="icon-button" disabled={Boolean(item.read_at)} title="标记已读" aria-label="标记已读" onClick={() => run(() => post(`/api/admin/messages/${item.id}/read`), '已标记已读')}><Bell size={16} /></button>
    if (active === 'dictionary') return <button className="icon-button" title="停用字典项" aria-label="停用字典项" onClick={() => run(() => api(`/api/admin/dictionary/${item.id}`, { method: 'DELETE' }), '字典项已停用')}><Archive size={16} /></button>
    if (active === 'templates') return <><button className="icon-button" title="编辑通知模板" aria-label="编辑通知模板" onClick={() => beginEdit(item)}><Users size={16} /></button><button className="icon-button" title="停用通知模板" aria-label="停用通知模板" onClick={() => run(() => api(`/api/admin/notification-templates/${item.id}`, { method: 'DELETE' }), '模板已停用')}><Archive size={16} /></button></>
    return null
  }

  const createBackup = () => run(async () => { const result = await post('/api/admin/backups'); setData(current => ({ ...current, backups: [{ filename: result.backup, created_at: new Date().toLocaleString(), size: 0 }, ...(current?.backups || [])] })) }, '已创建数据库备份')
  const saveBackupInterval = () => run(() => api('/api/admin/config', { method: 'PATCH', body: JSON.stringify({ backup_interval_hours: Number(backupInterval) }) }), '自动备份频率已更新')
  const exportCsv = kind => { window.location.href = `/api/admin/export/${kind}` }
  const importCsv = async event => {
    const file = event.target.files?.[0]
    if (!file) return
    const body = new FormData(); body.append('file', file)
    await run(() => api(`/api/admin/import/${active}`, { method: 'POST', body }), 'CSV 导入完成')
    event.target.value = ''
  }

  const selectedData = data?.[{ accounts: 'users', elders: 'elders', family: 'links', devices: 'devices', services: 'services', messages: 'messages', templates: 'templates', logs: 'logs', dictionary: 'entries', backups: 'backups' }[active]] || []
  const canWrite = admin || Boolean(tabWritePermission[active] && session?.permissions?.includes(tabWritePermission[active]))

  if (loading && !data) return <LoadingState label="正在加载管理数据" />

  return <div className="page admin-page">
    <header className="page-heading admin-heading"><div><span className="section-kicker">{admin ? '平台控制台' : '社区工作台'}</span><h1>{admin ? '系统管理' : '社区管理'}</h1><p>{session.user?.name} · {roleLabels[session.role]} · {session.user?.community_id ? `社区 ${session.user.community_id}` : '全平台数据'}</p></div><button className="btn btn-ghost" onClick={load} disabled={busy}><RefreshCw size={16} />刷新</button></header>
    <JellyRadio className="admin-tabs" items={tabs.map(tab => ({ value: tab, label: tabLabels[tab] }))} value={active} onChange={value => { setActive(value); setForm({}); setEditing(null) }} ariaLabel="管理模块" size="sm" gap={3} radius={8} swell={0.08} barge={3} shrink={0.02} />
    <section className="admin-toolbar" aria-label="模块操作">
      <div><h2>{tabLabels[active]}</h2><p>{active === 'logs' ? '审计日志仅可查询与导出' : active === 'family' ? '绑定变更需要记录；解绑需二次确认' : '数据按当前账号权限和范围返回'}</p></div>
      <div className="admin-tools">
        {['accounts', 'elders'].includes(active) && <label className="admin-search">搜索<input value={filter} onChange={event => setFilter(event.target.value)} placeholder="姓名或账号" /></label>}
        {canExport && ['elders', 'devices', 'services', 'logs'].includes(active) && <button className="btn btn-ghost" onClick={() => exportCsv(active)}><Download size={15} />导出 CSV</button>}
        {canWrite && ['elders', 'devices', 'services'].includes(active) && <label className="btn btn-ghost admin-upload"><FileUp size={15} />导入 CSV<input type="file" accept=".csv,text/csv" onChange={importCsv} /></label>}
        {active === 'backups' && <button className="btn" onClick={createBackup} disabled={busy}><Plus size={16} />创建备份</button>}
      </div>
    </section>
    {active === 'backups' && admin && <section className="admin-backup-schedule">
      <div><strong>自动备份</strong><p>下次备份按最近一次自动备份时间与间隔执行。</p>{data?.schedule?.last_automatic_backup_at && <small>最近自动备份：{data.schedule.last_automatic_backup_at}</small>}{data?.schedule?.last_error && <small className="admin-backup-error">最近一次备份失败：{data.schedule.last_error}</small>}</div>
      <form onSubmit={event => { event.preventDefault(); saveBackupInterval() }}><label>间隔（小时）<input type="number" min="1" max="8760" value={backupInterval} onChange={event => setBackupInterval(event.target.value)} /></label><button className="btn btn-ghost" disabled={busy}><Save size={15} />保存间隔</button></form>
    </section>}

    {fields.length > 0 && canWrite && <form className="admin-form" onSubmit={submit}>
      <div className="admin-form-title"><h3>{editing ? `修改${tabLabels[active]}` : `新增${tabLabels[active]}`}</h3>{editing && <button type="button" className="icon-button" title="取消编辑" aria-label="取消编辑" onClick={() => { setEditing(null); setForm({}) }}><X size={16} /></button>}</div>
      <div className="admin-fields">{fields.map(field => <label key={field.key} className={field.type === 'textarea' ? 'admin-field-wide' : ''}>{field.label}
        {field.type === 'select' ? <select required={field.required} value={form[field.key] ?? ''} onChange={event => setField(field.key, event.target.value)}><option value="">请选择</option>{field.options?.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
          : field.type === 'textarea' ? <textarea required={field.required} rows="3" value={form[field.key] ?? ''} onChange={event => setField(field.key, event.target.value)} />
            : <input type={field.type || 'text'} required={field.required} value={form[field.key] ?? ''} placeholder={field.placeholder} onChange={event => setField(field.key, event.target.value)} />}
      </label>)}</div>
      <div className="admin-submit-row"><button className="btn" type="submit" disabled={busy}><Plus size={15} />{editing ? '保存修改' : '创建'}</button></div>
    </form>}

    {active === 'config' && admin && <ConfigPanel key={JSON.stringify(data?.config || {})} config={data?.config || {}} onSave={values => run(() => api('/api/admin/config', { method: 'PATCH', body: JSON.stringify(values) }), '系统配置已保存')} />}
    {active === 'roles' && admin && <RolesPanel roles={data?.roles || []} onSave={(role, permissions) => run(() => api(`/api/admin/roles/${role}/permissions`, { method: 'PUT', body: JSON.stringify({ permissions }) }), '角色权限已更新')} onSaveScope={(role, scope) => run(() => api(`/api/admin/roles/${role}/scope`, { method: 'PUT', body: JSON.stringify({ scope }) }), '角色数据范围已更新')} />}
    {active === 'backups' && admin && <section className="admin-table-wrap"><div className="admin-table-scroll"><table className="table"><thead><tr><th>备份文件</th><th>创建时间</th><th>大小</th><th>操作</th></tr></thead><tbody>{(data?.backups || []).map(item => <tr key={item.filename}><td>{item.filename}</td><td>{item.created_at}</td><td>{Math.ceil(item.size / 1024)} KB</td><td className="admin-actions"><a className="icon-button" title="下载备份" aria-label="下载备份" href={`/api/admin/backups/${item.filename}`}><Download size={16} /></a><button className="icon-button" title="恢复备份" aria-label="恢复备份" onClick={() => window.confirm(`恢复 ${item.filename} 将替换当前数据库。系统会先自动创建恢复前备份，确认继续？`) && run(() => post('/api/admin/backups/restore?confirm=1', { filename: item.filename }), '数据库已恢复')}><RefreshCw size={16} /></button></td></tr>)}</tbody></table></div></section>}
    {active === 'config' && admin && <DictionaryEntryAction onCreate={() => { setActive('dictionary') }} />}

    {active !== 'config' && active !== 'roles' && active !== 'backups' && <section className="admin-table-wrap">
      {error && <div className="admin-error" role="alert">{error}<button className="icon-button" aria-label="重试加载" onClick={load}><RefreshCw size={15} /></button></div>}
      {loading && <p className="admin-loading">正在更新列表…</p>}
      <div className="admin-table-scroll"><table className="table"><thead><tr>{(columns[active] || []).map(([key, label]) => <th key={key}>{label}</th>)}{active === 'messages' && <th>内容</th>}{active === 'devices' && <th>历史</th>}<th>操作</th></tr></thead><tbody>
        {selectedData.map(item => <tr key={item.id}>{(columns[active] || []).map(([key]) => <td key={key}>{valueText(key, item[key])}</td>)}{active === 'messages' && <td className="admin-message-body">{item.body}</td>}{active === 'devices' && <td><button className="icon-button" title="查看设备读数趋势" aria-label={`查看 ${item.code} 的设备读数趋势`} onClick={() => openHistory(item)}><ChartNoAxesCombined size={16} /></button></td>}<td className="admin-actions">{manageRow(item)}</td></tr>)}
        {!selectedData.length && <tr><td colSpan={(columns[active]?.length || 1) + (active === 'messages' ? 1 : 0) + (active === 'devices' ? 1 : 0) + 1} className="admin-empty">{error ? '数据暂不可用' : '暂无记录'}</td></tr>}
      </tbody></table></div>
    </section>}
    <Modal open={Boolean(historyDevice)} title={historyDevice ? `${historyDevice.code} · 设备读数趋势` : '设备读数趋势'} onClose={() => setHistoryDevice(null)}>
      {historyLoading ? <p className="admin-loading">正在读取历史数据…</p>
        : historyError ? <p className="admin-error" role="alert">{historyError}</p>
          : history.length ? <><div className="device-history-meta"><span>{historyDevice?.elder_name || '未绑定老人'}</span><span>{history.length} 条读数</span><span>最近记录 {history[0].recorded_at}</span></div><EChart className="device-history-chart" option={historyOption} ariaLabel="设备历史读数趋势" /></>
            : <p className="admin-empty">暂无历史读数。模拟场景产生的有效在线读数会记录在此处。</p>}
    </Modal>
  </div>
}

function ConfigPanel({ config, onSave }) {
  const [values, setValues] = useState(config)
  return <form className="admin-config" onSubmit={event => { event.preventDefault(); onSave(values) }}>
    {Object.entries(values).map(([key, value]) => <label key={key}>{key}<input value={value} onChange={event => setValues(current => ({ ...current, [key]: event.target.value }))} /></label>)}
    <button className="btn" type="submit"><Save size={15} />保存配置</button>
  </form>
}

function RolesPanel({ roles, onSave, onSaveScope }) {
  const scopeOptions = {
    superadmin: [['all', '全平台']], community: [['community', '仅本社区']],
    volunteer: [['assigned', '仅指派任务']], family: [['linked', '仅已绑定老人']],
    elder: [['self', '仅本人档案']],
  }
  const [role, setRole] = useState('community')
  const current = roles.find(item => item.key === role)
  const [drafts, setDrafts] = useState({})
  const [scopeDrafts, setScopeDrafts] = useState({})
  const permissions = drafts[role] ?? (current?.permissions || []).join('\n')
  const scope = scopeDrafts[role] ?? current?.scope ?? 'community'
  return <form className="admin-config admin-role-config" onSubmit={event => { event.preventDefault(); onSave(role, permissions.split('\n').map(item => item.trim()).filter(Boolean)) }}>
    <label>角色<select value={role} onChange={event => setRole(event.target.value)}>{roles.map(item => <option key={item.key} value={item.key}>{roleLabels[item.key]}</option>)}</select></label>
    <label>数据范围<select value={scope} onChange={event => setScopeDrafts(values => ({ ...values, [role]: event.target.value }))}>{(scopeOptions[role] || []).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
    <button className="btn btn-ghost" type="button" onClick={() => onSaveScope(role, scope)}><Save size={15} />保存数据范围</button>
    <label>权限项<textarea rows="12" value={permissions} onChange={event => setDrafts(currentDrafts => ({ ...currentDrafts, [role]: event.target.value }))} /></label>
    <button className="btn" type="submit"><Save size={15} />保存角色权限</button>
  </form>
}

function DictionaryEntryAction({ onCreate }) {
  return <div className="admin-dictionary-link"><button className="btn btn-ghost" onClick={onCreate}>打开数据字典</button></div>
}
