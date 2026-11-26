import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { BellRing, CheckCircle2, Clock3, ShieldCheck, UserRound, Activity } from 'lucide-react'
import { post } from '../api'
import { useToast } from '../App'
import LoadingState, { ErrorState } from '../components/LoadingState'
import Modal from '../components/Modal'
import JellyRadio from '../components/JellyRadio'
import { useApi } from '../hooks'
import RoleLink from '../components/RoleLink'

const steps = [['pending', '发现异常'], ['dispatched', '安排跟进'], ['processing', '到场核实'], ['closed', '结果归档']]
const statusText = { pending: '待核实', dispatched: '已派单', processing: '处置中', closed: '已归档' }
const filters = [['open', '待跟进'], ['overdue', '超时关注'], ['all', '全部记录']]

export default function CareCenterPage() {
  const { data, loading, error, reload } = useApi('/api/alerts', { interval: 3000 })
  const [params, setParams] = useSearchParams()
  const [filter, setFilter] = useState('open')
  const [dialog, setDialog] = useState(null)
  const [assignee, setAssignee] = useState('赵敏')
  const [result, setResult] = useState('已上门核实，老人目前安全，已联系家属并提醒按时服药。')
  const [saving, setSaving] = useState(false)
  const toast = useToast()
  if (loading) return <LoadingState label="正在同步关爱响应" />
  if (error && !data) return <ErrorState message={error} onRetry={reload} />
  const alerts = data?.alerts || []
  const items = alerts.filter(a => filter === 'all' || (filter === 'overdue' ? a.escalated : a.status !== 'closed'))
    .sort((a, b) => Number(b.escalated) - Number(a.escalated) || b.id - a.id)
  const selected = alerts.find(a => a.id === Number(params.get('id'))) || items[0]
  const current = steps.findIndex(([key]) => key === selected?.status)
  const update = async (action, body = {}) => {
    setSaving(true)
    try {
      await post(action === 'demo-timeout' ? `/api/care/alerts/${selected.id}/demo-timeout` : `/api/alerts/${selected.id}/${action}`, body)
      toast(action === 'demo-timeout' ? '已触发超时巡检，请查看催办记录' : '处理进度已保存，家属站内消息已更新')
      setDialog(null)
      await reload()
    } catch (e) { toast(e.message, 'error'); await reload() }
    finally { setSaving(false) }
  }
  return (
    <div className="page care-page">
      <header className="care-hero">
        <div><span className="care-eyebrow"><ShieldCheck size={17} /> 安芯 · 社区协同响应</span><h1>让每一次求助，<br />都有下文。</h1><p>从发现异常到上门回执，谁在跟进、进展如何，一眼看清。</p><div className="care-hero-actions"><Link className="btn" to="/demo/simulator">体验异常发现</Link><RoleLink className="care-text-link" to="/family/overview">切换家属账号查看消息</RoleLink></div></div>
        <div className="care-promise"><span>每个阶段，都有人接力</span><div><Activity size={19} /> 预警有依据</div><div><UserRound size={19} /> 任务有负责人</div><div><BellRing size={19} /> 超时有提醒</div><div><CheckCircle2 size={19} /> 结果有记录</div><small>本地演示 · 每 3 秒同步处理进度</small></div>
      </header>
      <section className="care-stats" aria-label="当前响应概况">
        {[['等待安排', alerts.filter(a => a.status === 'pending').length, '尽快确认并指定负责人'], ['正在跟进', alerts.filter(a => ['dispatched', 'processing'].includes(a.status)).length, '已派单或正在现场处置'], ['超时关注', alerts.filter(a => a.escalated).length, '已记录催办并通知社区'], ['完成归档', alerts.filter(a => a.status === 'closed').length, '回执可查询、过程可追溯']].map(([label, n, note]) => <article key={label}><span>{label}</span><strong>{n}<small> 项</small></strong><p>{note}</p></article>)}
      </section>
      <div className="care-section-heading"><div><span className="section-kicker">关爱响应中心</span><h2>预警工单看板</h2></div><RoleLink to="/volunteer/tasks" className="btn btn-ghost">切换志愿者账号</RoleLink></div>
      {error && <p role="status" className="inline-warning">同步暂时中断，正在重试；当前显示最近一次结果。</p>}
      <div className="care-workspace">
        <aside className="care-inbox">
          <JellyRadio className="care-filter" items={filters.map(([key, label]) => ({ value: key, label }))} value={filter} onChange={value => { setFilter(value); setParams({}) }} chipColor="transparent" activeColor="#fff" textColor="#737b70" activeTextColor="#294837" size="sm" gap={3} swell={0.09} barge={2} shrink={0.02} ariaLabel="筛选工单" />
          <p className="care-list-note">{items.length} 项记录 · 优先显示超时与最新事件</p>
          {items.length ? <JellyRadio
            className="care-case-list"
            items={items.map(alert => ({
              value: String(alert.id),
              label: `${alert.elder_name} ${statusText[alert.status]}`,
              ariaLabel: `${alert.elder_name} ${statusText[alert.status]}`,
              description: alert.reason,
              className: 'care-case',
              content: <>
                <span className="care-case-heading"><strong>{alert.elder_name}</strong><span className={`badge badge-${alert.level}`}>{alert.level === 'red' ? '紧急' : '关注'}</span></span>
                <span className="care-case-reason">{alert.reason}</span>
                <span className="care-case-meta"><span>{statusText[alert.status]}</span><span>{alert.escalated ? '已超时 · 请跟进' : alert.assignee || '等待安排负责人'}</span></span>
                <span className="care-case-code">{alert.code}</span>
              </>,
            }))}
            value={selected ? String(selected.id) : undefined}
            onChange={id => setParams({ id })}
            chipColor="transparent"
            activeColor="transparent"
            textColor="#354135"
            activeTextColor="#354135"
            size="md"
            gap={9}
            swell={0.025}
            barge={0}
            shrink={0.006}
            ariaLabel="工单列表"
          /> : <div className="care-empty"><ShieldCheck /><p>这里暂时没有需要跟进的事项</p><Link to="/demo/simulator">体验一次异常发现</Link></div>}
        </aside>
        {selected ? <section className="care-detail" aria-label="工单详情">
          <div className="care-detail-top"><div><span className="section-kicker">{selected.code}</span><h2>{selected.elder_name}的安全关注</h2><p>{selected.age} 岁 · {selected.address}</p></div><span className={`status-chip status-${selected.status}`}>{statusText[selected.status]}</span></div>
          <ol className="care-stepper">{steps.map(([key, label], i) => <li key={key} className={i <= current ? 'complete' : ''} aria-current={i === current ? 'step' : undefined}><span>{i < current || current === 3 ? <CheckCircle2 size={18} /> : i + 1}</span><b>{label}</b></li>)}</ol>
          <div className={`care-responsibility ${selected.escalated ? 'urgent' : ''}`}><Clock3 size={22} /><div><strong>{selected.status === 'closed' ? '本次关爱已完成' : selected.escalated ? '已超时，社区需要继续跟进' : selected.assignee ? `${selected.assignee}正在接力` : '等待社区安排跟进'}</strong><p>{selected.status === 'closed' ? `归档于 ${selected.closed_at}` : selected.due_at ? `本阶段截止：${selected.due_at} · 超时后生成一次催办消息` : '历史演示工单 · 未设置响应期限'}</p></div></div>
          <section className="care-evidence"><h3><Activity size={18} /> 为什么需要关注</h3><p>{selected.reason}</p><ul>{selected.evidence.map(text => <li key={text}>{text}</li>)}</ul><small>设备数据为模拟输入；异常信号需要人工核实，不能直接认定发生危险。</small></section>
          <section className="care-history"><h3>处理时间线</h3><ol>{selected.timeline.length ? selected.timeline.map(item => <li key={item.id}><span className="care-history-dot" /><div><div className="care-history-title"><strong>{item.action}</strong><time>{item.ts}</time></div><p>{item.detail}</p><small>{item.actor}</small></div></li>) : <li><span className="care-history-dot" /><div><strong>历史演示记录</strong><p>创建于 {selected.created_at}。早期阶段未记录操作时间，后续操作将自动留痕。</p></div></li>}</ol></section>
          {selected.result && <div className="care-receipt"><CheckCircle2 size={20} /><div><strong>上门服务回执</strong><p>{selected.result}</p></div></div>}
          <div className="care-detail-actions">{selected.status === 'pending' && <button className="btn" disabled={saving} onClick={() => setDialog('dispatch')}>安排人员跟进</button>}{selected.status === 'dispatched' && <button className="btn" disabled={saving} onClick={() => update('process')}>确认到场，开始核实</button>}{selected.status === 'processing' && <button className="btn action-green" disabled={saving} onClick={() => setDialog('close')}>填写回执并归档</button>}{selected.status === 'closed' && <span className="care-completed"><CheckCircle2 size={18} /> 已完成本次处置</span>}{selected.due_at && selected.status !== 'closed' && !selected.escalated && <button className="btn btn-ghost" disabled={saving} onClick={() => setDialog('timeout')}>演示超时提醒</button>}</div>
        </section> : <section className="care-detail care-empty"><ShieldCheck size={44} /><h2>每一份关注，都值得被回应</h2><p>选择左侧工单，查看判断依据与处理过程。</p></section>}
      </div>
      <p className="care-footnote">切换角色需要使用对应账号登录。消息保存在站内，未接入短信或电话服务。</p>
      <Modal open={Boolean(dialog)} title={dialog === 'dispatch' ? '安排服务负责人' : dialog === 'timeout' ? '演示超时提醒' : '填写上门服务回执'} onClose={() => setDialog(null)} actions={<><button className="btn btn-ghost" onClick={() => setDialog(null)}>取消</button><button className="btn" disabled={saving || (dialog === 'close' && !result.trim())} onClick={() => dialog === 'timeout' ? update('demo-timeout') : update(dialog, dialog === 'dispatch' ? { assignee } : { result })}>{saving ? '正在保存…' : '确认提交'}</button></>}>
        {dialog === 'dispatch' ? <label className="field-label">选择负责人<select value={assignee} onChange={e => setAssignee(e.target.value)}><option>赵敏</option><option>王芳</option><option>物业老周</option></select><small>赵敏为志愿者。派单后，可切换志愿者视角完成到场与回执。</small></label> : dialog === 'timeout' ? <p>将当前工单的本阶段期限设为现在，触发真实的超时检查。系统会保存催办记录，并向家属和社区写入站内消息。</p> : <label className="field-label">处置结果<textarea rows={5} maxLength={300} value={result} onChange={e => setResult(e.target.value)} /><small>请记录实际核实情况，回执将同步给家属。</small></label>}
      </Modal>
    </div>
  )
}
