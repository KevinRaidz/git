import { useState } from 'react'
import { Link } from 'react-router-dom'
import { post } from '../api'
import { useToast } from '../App'
import LoadingState, { ErrorState } from '../components/LoadingState'
import Modal from '../components/Modal'
import { useApi } from '../hooks'

const lanes = [
  { id: 'pending', title: '待核实', tone: 'red', empty: '暂无待核实工单' },
  { id: 'dispatched', title: '已派单', tone: 'yellow', empty: '暂无已派工单' },
  { id: 'processing', title: '处置中', tone: 'blue', empty: '暂无处置中工单' },
  { id: 'follow_up', title: '待回访', tone: 'yellow', empty: '暂无待回访工单' },
  { id: 'closed', title: '已归档', tone: 'green', empty: '暂无已归档工单' },
]

export default function AlertsPage() {
  const { data, loading, error, reload } = useApi('/api/alerts', { interval: 5000 })
  const toast = useToast()
  const [dialog, setDialog] = useState(null)
  const [assignee, setAssignee] = useState('王芳')
  const [result, setResult] = useState('已上门核实，老人一切安好')
  const [followUp, setFollowUp] = useState('已电话回访，老人确认服务已完成')
  const [saving, setSaving] = useState(false)

  if (loading) return <LoadingState label="正在同步预警工单" />
  if (error && !data) return <ErrorState message={error} onRetry={reload} />

  const update = async (id, action, body = {}) => {
    setSaving(true)
    try {
      await post(`/api/alerts/${id}/${action}`, body)
      toast('工单状态已更新')
      setDialog(null)
      await reload()
    } catch (requestError) {
      toast(requestError.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  const actionFor = alert => {
    if (alert.status === 'pending') return <button className="btn btn-sm btn-blue" type="button" onClick={() => setDialog({ alert, action: 'dispatch' })}>派单</button>
    if (alert.status === 'dispatched') return <button className="btn btn-sm btn-blue" type="button" onClick={() => update(alert.id, 'process')}>开始处置</button>
    if (alert.status === 'processing') return <button className="btn btn-sm action-green" type="button" onClick={() => setDialog({ alert, action: 'close' })}>提交处置回执</button>
    if (alert.status === 'follow_up') return <button className="btn btn-sm action-green" type="button" onClick={() => setDialog({ alert, action: 'follow-up' })}>完成回访</button>
    return null
  }

  return (
    <div className="page alerts-page">
      <header className="page-heading compact"><div><span className="section-kicker">全流程留痕</span><h1>预警工单看板</h1><p>待核实 → 已派单 → 处置中 → 待回访 → 已归档，每 5 秒自动同步</p></div><Link className="btn btn-ghost" to="/demo/simulator">打开演示模拟器</Link></header>
      {error && <div className="inline-warning">数据刷新失败，正在自动重试</div>}
      <div className="alerts-board">
        {lanes.map(lane => {
          const items = (data?.alerts || []).filter(item => item.status === lane.id)
          return <section className="alert-lane" key={lane.id}><h2 className={`alert-lane-title tone-${lane.tone}`}>{lane.title}<span className="lane-count">{items.length}</span></h2><div className="alert-lane-list">{items.length ? items.map((alert, index) => <article className={`alert-item is-interactive level-${alert.level} alert-order`} style={{ '--order': Math.min(index, 7) }} key={alert.id}><div className="work-order-heading"><strong>{alert.elder_name}（{alert.age}岁）</strong><span>{alert.code}</span></div><p className="alert-reason">{alert.reason}</p>{alert.anomaly_percentile !== null && alert.anomaly_percentile !== undefined && <p className="a-meta">Isolation Forest · 异常分位 {Number(alert.anomaly_percentile).toFixed(1)}% · {alert.baseline_scope === 'personal' ? '个人基线' : '社区冷启动基线'}</p>}<p className="a-meta">{alert.created_at}{alert.assignee && ` · 负责人：${alert.assignee}`}</p>{alert.result && <p className="order-result">处置结果：{alert.result}</p>}<div className="alert-actions">{actionFor(alert)}</div></article>) : <p className="lane-empty">{lane.empty}</p>}</div></section>
        })}
      </div>
      <Modal open={Boolean(dialog)} title={dialog?.action === 'dispatch' ? '选择服务负责人' : dialog?.action === 'follow-up' ? '记录回访结果' : '填写处置结果'} onClose={() => setDialog(null)} actions={<><button className="btn btn-ghost" type="button" onClick={() => setDialog(null)}>取消</button><button className="btn" type="button" disabled={saving || (dialog?.action === 'close' && !result.trim()) || (dialog?.action === 'follow-up' && !followUp.trim())} onClick={() => dialog?.action === 'dispatch' ? update(dialog.alert.id, 'dispatch', { assignee }) : dialog?.action === 'follow-up' ? update(dialog.alert.id, 'follow-up', { result: followUp.trim(), satisfaction: 5 }) : update(dialog.alert.id, 'close', { result: result.trim() })}>{saving ? '正在保存' : dialog?.action === 'dispatch' ? '确认派单' : dialog?.action === 'follow-up' ? '完成回访' : '提交处置回执'}</button></>}>
        {dialog?.action === 'dispatch' ? <label className="field-label">负责人<select value={assignee} onChange={event => setAssignee(event.target.value)} autoFocus><option value="王芳">王芳 · 网格员 · 320m</option><option value="赵敏">赵敏 · 志愿者 · 450m</option><option value="物业老周">物业老周 · 600m</option></select></label> : dialog?.action === 'follow-up' ? <label className="field-label">回访记录<textarea rows="5" maxLength="300" value={followUp} onChange={event => setFollowUp(event.target.value)} autoFocus /></label> : <label className="field-label">处置结果<textarea rows="5" maxLength="300" value={result} onChange={event => setResult(event.target.value)} autoFocus /></label>}
      </Modal>
    </div>
  )
}
