import { CheckCircle2, MapPin, Navigation, Trophy } from 'lucide-react'
import { useState } from 'react'
import { post } from '../api'
import { useToast } from '../App'
import LoadingState, { ErrorState } from '../components/LoadingState'
import Modal from '../components/Modal'
import { useApi } from '../hooks'

const statusText = { dispatched: '已派单', processing: '处置中', closed: '已归档' }

export default function VolunteerPage({ embedded = false }) {
  const { data, loading, error, reload } = useApi(`/api/volunteer/tasks${embedded ? '?preview=1' : ''}`)
  const toast = useToast()
  const [dialog, setDialog] = useState(null)
  const [result, setResult] = useState('已上门探访，老人精神状态良好，已提醒按时服药')
  const [saving, setSaving] = useState(false)

  if (loading) return <LoadingState label="正在加载志愿任务" />
  if (error) return <ErrorState message={error} onRetry={reload} />

  const openArrival = task => {
    if (!navigator.geolocation) {
      setDialog({ task, action: 'arrive', location: '浏览器不支持定位，演示模式已放行' })
      return
    }
    toast('正在获取到场位置', 'info')
    navigator.geolocation.getCurrentPosition(
      position => setDialog({ task, action: 'arrive', location: `${position.coords.latitude.toFixed(4)}, ${position.coords.longitude.toFixed(4)}` }),
      () => setDialog({ task, action: 'arrive', location: '未获得定位授权，演示模式已放行' }),
      { timeout: 3500 },
    )
  }

  const save = async () => {
    setSaving(true)
    try {
      if (dialog.action === 'arrive') await post(`/api/alerts/${dialog.task.id}/process`)
      else await post(`/api/alerts/${dialog.task.id}/close`, { result: result.trim() })
      toast(dialog.action === 'arrive' ? '到场打卡成功' : '回执已上传并归档')
      setDialog(null)
      await reload()
    } catch (requestError) {
      toast(requestError.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="page volunteer-page">
      <section className="volunteer-profile">
        <div className="profile-avatar volunteer-avatar">赵</div>
        <div><span className="section-kicker">银龄互助志愿者</span><h1>赵敏</h1><p>本月已服务 12 次 · 积分 360 · 社区排名第 2</p></div>
        <Trophy size={38} aria-label="社区排名第二" />
      </section>
      <section className="task-section"><div className="section-heading"><div><span className="section-index">待办</span><h2>需要处理的任务</h2></div><span>{data.tasks.length} 项</span></div>
        <div className="task-list">{data.tasks.length ? data.tasks.map((task, index) => <article className={`task-item level-${task.level}`} key={task.id}><div className="task-topline"><div><strong>{task.elder_name}</strong><span>{task.age} 岁 · {task.level === 'red' ? '紧急' : '关注'}</span></div><span className={`status-chip status-${task.status}`}>{statusText[task.status]}</span></div><p className="task-address"><MapPin size={16} />{task.address} · 距您 {[320, 450, 780][index % 3]}m</p><p>{task.reason}</p><div className="task-actions">{task.status === 'dispatched' ? <button className="btn btn-blue" type="button" onClick={() => openArrival(task)}><MapPin size={17} />到场打卡</button> : <button className="btn action-green" type="button" onClick={() => setDialog({ task, action: 'finish' })}><CheckCircle2 size={17} />上传回执并归档</button>}<button className="btn btn-ghost" type="button" onClick={() => toast(`已准备导航至 ${task.address}`, 'info')}><Navigation size={17} />导航</button></div></article>) : <div className="empty-panel"><CheckCircle2 /><strong>当前没有待办任务</strong><span>新的社区派单会出现在这里</span></div>}</div>
      </section>
      <section className="task-section"><div className="section-heading"><div><span className="section-index">最近</span><h2>已完成服务</h2></div><span>{data.done.length} 项</span></div><div className="completed-list">{data.done.length ? data.done.map(task => <article key={task.id}><CheckCircle2 /><div><strong>{task.elder_name} · 已归档</strong><p>{task.result || '服务已完成'}</p></div></article>) : <p className="muted">暂无历史记录</p>}</div></section>
      <Modal open={Boolean(dialog)} title={dialog?.action === 'arrive' ? '确认到场打卡' : '上传服务回执'} onClose={() => setDialog(null)} actions={<><button className="btn btn-ghost" type="button" onClick={() => setDialog(null)}>取消</button><button className="btn" type="button" disabled={saving || (dialog?.action === 'finish' && !result.trim())} onClick={save}>{saving ? '正在提交' : '确认提交'}</button></>}>
        {dialog?.action === 'arrive' ? <div className="arrival-confirm"><MapPin /><p>确认已抵达 <b>{dialog.task.elder_name}</b> 家中？</p><span>定位：{dialog.location}</span></div> : <label className="field-label">服务回执<textarea rows="5" maxLength="300" value={result} onChange={event => setResult(event.target.value)} autoFocus /></label>}
      </Modal>
    </div>
  )
}
