import { useState } from 'react'
import { Link } from 'react-router-dom'
import JellyRadio from '../components/JellyRadio'
import LoadingState, { ErrorState } from '../components/LoadingState'
import { useApi } from '../hooks'

const levelText = { green: '平安', yellow: '需关注', red: '紧急' }
const categoryText = { meal: '助餐', medical: '助医', renovation: '适老化改造', housekeeping: '保洁' }

export default function EldersPage() {
  const [level, setLevel] = useState('')
  const { data, loading, error, reload } = useApi(`/api/elders?level=${level}`)
  if (loading) return <LoadingState label="正在加载三个清单" />
  if (error) return <ErrorState message={error} onRetry={reload} />

  const activeNeeds = data.needs.filter(item => item.status !== '已完成')
  const services = data.needs.filter(item => ['已转服务', '已完成'].includes(item.status))
  return (
    <div className="page">
      <header className="page-heading"><div><span className="section-kicker">社区精细治理</span><h1>三个清单</h1><p>一户一档、需求归集、服务闭环</p></div><Link className="btn" to="/community/alerts">查看预警工单</Link></header>
      <JellyRadio
        className="risk-filter-jelly"
        items={[
          { value: '', label: '全部' },
          { value: 'red', label: '紧急' },
          { value: 'yellow', label: '需关注' },
          { value: 'green', label: '平安' },
        ]}
        value={level}
        onChange={setLevel}
        chipColor="#ffffff"
        activeColor="#e8734a"
        textColor="#6b675c"
        activeTextColor="#ffffff"
        size="md"
        gap={6}
        radius={8}
        swell={0.16}
        barge={5}
        shrink={0.035}
        jelly={1.15}
        bounce={0.3}
        ariaLabel="按风险等级筛选"
      />
      <section className="data-section">
        <div className="section-heading"><div><span className="section-index">01</span><h2>老人档案清单</h2></div><span>{data.elders.length} 户</span></div>
        <div className="table-scroll"><table className="table"><thead><tr><th>姓名</th><th>年龄</th><th>住址</th><th>慢病</th><th>设备</th><th>风险</th><th>下次探访</th><th>操作</th></tr></thead><tbody>{data.elders.map(elder => <tr key={elder.id} className={elder.risk_level === 'red' ? 'row-red' : ''}><td><b>{elder.name}</b></td><td>{elder.age}</td><td>{elder.address}</td><td>{elder.chronic}</td><td>{elder.devices}</td><td><span className={`badge badge-${elder.risk_level}`}>{levelText[elder.risk_level]}</span></td><td>{elder.next_visit_due}</td><td><Link to="/community/alerts" className="btn btn-sm btn-ghost">派单</Link></td></tr>)}</tbody></table></div>
      </section>
      <section className="data-section">
        <div className="section-heading"><div><span className="section-index">02</span><h2>需求清单</h2></div><span>{activeNeeds.length} 项</span></div>
        <div className="table-scroll"><table className="table"><thead><tr><th>老人</th><th>类型</th><th>需求描述</th><th>紧急度</th><th>状态</th></tr></thead><tbody>{activeNeeds.map(item => <tr key={item.id}><td><b>{item.elder_name}</b></td><td>{categoryText[item.category] || item.category}</td><td>{item.descr}</td><td><span className={`status-chip ${item.urgency === 'high' ? 'status-pending' : ''}`}>{item.urgency === 'high' ? '高' : '普通'}</span></td><td><span className={`status-chip ${item.status === '已转服务' ? 'status-dispatched' : ''}`}>{item.status}</span></td></tr>)}</tbody></table></div>
      </section>
      <section className="data-section">
        <div className="section-heading"><div><span className="section-index">03</span><h2>服务清单</h2></div><span>{services.length} 项</span></div>
        <div className="table-scroll"><table className="table"><thead><tr><th>老人</th><th>服务内容</th><th>承接方</th><th>状态</th></tr></thead><tbody>{services.length ? services.map(item => <tr key={item.id}><td><b>{item.elder_name}</b></td><td>{item.descr}</td><td>{item.provider || '—'}</td><td><span className={`status-chip ${item.status === '已完成' ? 'status-closed' : 'status-processing'}`}>{item.status}</span></td></tr>) : <tr><td colSpan="4" className="muted">暂无在执行服务</td></tr>}</tbody></table></div>
        <p className="policy-note">“三个清单”依据：民政部、全国老龄办、中国老龄协会《关于深入开展特殊困难老年人探访关爱服务的通知》</p>
      </section>
    </div>
  )
}
