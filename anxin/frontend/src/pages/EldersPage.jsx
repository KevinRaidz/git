import { useState } from 'react'
import { Link } from 'react-router-dom'
import JellyRadio from '../components/JellyRadio'
import LoadingState, { ErrorState } from '../components/LoadingState'
import { useApi } from '../hooks'

const levelText = { green: '平安', yellow: '需关注', red: '紧急' }
const categoryText = { meal: '助餐', medical: '助医', renovation: '适老化改造', housekeeping: '保洁', visit: '探访关爱' }

export default function EldersPage() {
  const [level, setLevel] = useState('')
  const { data, loading, error, reload } = useApi(`/api/elders?level=${level}`)
  if (loading) return <LoadingState label="正在加载三个清单" />
  if (error) return <ErrorState message={error} onRetry={reload} />

  const activeNeeds = data.needs.filter(item => item.status !== '已完成')
  const serviceLinks = data.needs.filter(item => item.provider || item.source_alert_id)
  const latest = data.latest_reading
  return (
    <div className="page">
      <header className="page-heading"><div><span className="section-kicker">社区精细治理</span><h1>三个清单</h1><p>一户一档、需求归集、服务闭环</p></div><Link className="btn" to="/community/alerts">查看预警工单</Link></header>
      <section className="behavior-baseline-strip" aria-label="个性化行为基线状态">
        <div><span className="section-kicker">个性化行为基线</span><b>Isolation Forest</b></div>
        <div><span>基线范围</span><b>{data.baseline?.scope === 'community_cold_start' ? '社区冷启动' : '个人历史'}</b></div>
        <div><span>历史窗口</span><b>{data.baseline?.sample_count || 30} 个</b></div>
        <div><span>最近时序窗口</span><b>{latest ? `${latest.activity_minutes} 分钟活动 · ${latest.water_liters} L 用水` : '等待传感器数据'}</b></div>
      </section>
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
        <div className="section-heading"><div><span className="section-index">03</span><h2>服务资源清单</h2></div><span>{data.services.length} 项</span></div>
        <div className="table-scroll"><table className="table"><thead><tr><th>服务项目</th><th>类型</th><th>承接方</th><th>覆盖范围</th><th>剩余容量</th><th>联系电话</th></tr></thead><tbody>{data.services.map(item => <tr key={item.id}><td><b>{item.name}</b></td><td>{categoryText[item.category] || item.category}</td><td>{item.provider}</td><td>{item.area}</td><td>{item.available}/{item.capacity}</td><td>{item.contact || '—'}</td></tr>)}</tbody></table></div>
        <div className="section-heading service-links-heading"><div><span className="section-index">↳</span><h2>需求匹配记录</h2></div><span>{serviceLinks.length} 项</span></div>
        <div className="table-scroll"><table className="table"><thead><tr><th>老人</th><th>需求</th><th>承接方</th><th>来源</th><th>状态</th></tr></thead><tbody>{serviceLinks.length ? serviceLinks.map(item => <tr key={item.id}><td><b>{item.elder_name}</b></td><td>{item.descr}</td><td>{item.provider || '待匹配'}</td><td>{item.source_alert_id ? '异常预警联动' : '人工登记'}</td><td><span className={`status-chip ${item.status === '已完成' ? 'status-closed' : 'status-processing'}`}>{item.status}</span></td></tr>) : <tr><td colSpan="5" className="muted">暂无需求与服务匹配记录</td></tr>}</tbody></table></div>
        <p className="policy-note">“三个清单”依据：民政部、全国老龄办、中国老龄协会《关于深入开展特殊困难老年人探访关爱服务的通知》</p>
      </section>
    </div>
  )
}
