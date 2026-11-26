import { BellRing, CheckCircle2, Clock3 } from 'lucide-react'
import RoleLink from './RoleLink'
import { post } from '../api'
import { useToast } from '../App'

export default function FamilyCare({ notices = [], alerts = [], reload }) {
  const toast = useToast()
  const active = alerts[0]
  const unread = notices.filter(n => !n.read_at).length
  const read = async item => {
    try {
      if (item?.notice_type === 'message') await post(`/api/admin/messages/${item.id}/read`)
      else await post(`/api/care/notices/${item.id}/read`)
      await reload()
    }
    catch (e) { toast(e.message, 'error') }
  }
  return <section className="family-care">
    <div className="care-section-heading"><div><span className="section-kicker">家人的安心，来自看得见的回应</span><h2>关爱进展与消息</h2></div><span className="care-demo-label">{unread} 条未读 · 每 3 秒同步</span></div>
    {active && <div className="family-care-progress"><div><Clock3 size={22} /><strong>{active.status === 'closed' ? '最近一次关注已完成处置' : active.assignee ? `${active.assignee}正在跟进` : '社区已收到关注，等待安排人员'}</strong></div><p>{active.result || active.reason}</p>{active.status === 'closed' && alerts.some(a => a.status !== 'closed') && <p>另有未归档的关注事项，仍需继续核实。</p>}<RoleLink to={`/community/alerts?id=${active.id}`}>切换社区账号查看完整记录</RoleLink></div>}
    <div className="care-notices">{notices.length ? notices.slice(0, 6).map(n => <article key={`${n.notice_type || 'care'}-${n.id}`} className={n.read_at ? 'read' : 'unread'}><BellRing size={19} /><div><strong>{n.title}</strong><p>{n.body}</p><time>{n.created_at}</time></div>{n.read_at ? <span className="care-read"><CheckCircle2 size={15} />已读</span> : <button className="btn btn-ghost btn-sm" onClick={() => read(n)}>标为已读</button>}</article>) : <div className="care-empty"><BellRing /><p>还没有新的站内消息</p><RoleLink to="/demo/simulator">体验一次异常发现</RoleLink></div>}</div>
    <p className="care-footnote">这里显示实际保存的站内消息。当前未接入短信、电话或外部推送。</p>
  </section>
}
