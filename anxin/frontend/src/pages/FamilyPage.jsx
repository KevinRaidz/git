import { BellRing, Phone, Sparkles, Stethoscope, Utensils, WandSparkles } from 'lucide-react'
import { useMemo } from 'react'
import { useToast } from '../App'
import EChart from '../components/EChart'
import LoadingState, { ErrorState } from '../components/LoadingState'
import { useApi } from '../hooks'

const levelText = { green: '平安', yellow: '需关注', red: '紧急' }
const statusText = { pending: '待核实', dispatched: '已派单', processing: '处置中', closed: '已归档' }

export default function FamilyPage({ embedded = false }) {
  const { data, loading, error, reload } = useApi(`/api/family/overview${embedded ? '?preview=1' : ''}`)
  const toast = useToast()
  const scores = useMemo(() => data?.readings?.map(item => item.score) || [], [data])
  const average = scores.length ? scores.slice(0, -1).reduce((sum, value) => sum + value, 0) / Math.max(1, scores.length - 1) : 0
  const chartOption = useMemo(() => ({
    animationDuration: 500,
    grid: { left: 36, right: 8, top: 12, bottom: 24 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: { type: 'category', data: (data?.readings || []).map(item => item.day.slice(5)), axisLabel: { color: '#6B675C' } },
    yAxis: { type: 'value', axisLabel: { color: '#6B675C' }, splitLine: { lineStyle: { color: '#E8E2D6' } } },
    series: [{
      type: 'bar',
      barWidth: 22,
      data: scores.map(value => ({ value, itemStyle: { color: value < average * 0.7 ? '#D99A2B' : '#4C9A6A', borderRadius: [5, 5, 0, 0] } })),
    }],
  }), [data, scores, average])

  if (loading) return <LoadingState label="正在加载家人状态" />
  if (error) return <ErrorState message={error} onRetry={reload} />
  const { elder, events, alerts } = data

  return (
    <div className="page family-page">
      <section className="family-summary">
        <div className="profile-avatar" aria-hidden="true">桂</div>
        <div className="family-summary-copy">
          <div className="profile-heading"><h1>{elder.name}</h1><span className={`badge badge-${elder.risk_level}`}>{levelText[elder.risk_level]}</span></div>
          <p>{elder.age} 岁 · {elder.address} · 独居</p>
          <p className="muted">慢病：{elder.chronic} · 最近报平安：{elder.last_checkin || '今日尚未报平安'}</p>
        </div>
        <div className="summary-actions">
          <a className="btn" href={`tel:${elder.emergency_phone || ''}`}><Phone size={17} /> 打电话</a>
          <button className="btn btn-ghost" type="button" onClick={() => toast('提醒已发送给老人', 'info')}><BellRing size={17} /> 发提醒</button>
        </div>
      </section>

      <div className="grid-8-4">
        <section className="card">
          <div className="card-title">今日平安时间轴</div>
          <ul className="timeline">
            {events.length ? events.map(event => (
              <li className={event.kind === 'warn' ? 'warn' : ''} key={event.id}>
                <div className="t-time">{event.ts.slice(-5)}</div><div className="t-text">{event.icon} {event.text}</div>
              </li>
            )) : <li className="muted">今天还没有活动记录（数据每日 24 点后汇总）</li>}
          </ul>
          <p className="data-source">数据来源：门磁 / 智能水电表 / 红外活动监测（模拟数据）</p>
        </section>
        <section className="card">
          <div className="card-title">异常提醒</div>
          {alerts.length ? alerts.map(alert => (
            <article className={`alert-item level-${alert.level}`} key={alert.id}>
              <div className="a-main"><div className="a-title">{alert.reason}</div><div className="a-meta">{alert.created_at} · <span className={`status-chip status-${alert.status}`}>{statusText[alert.status]}</span>{alert.assignee && ` · ${alert.assignee}`}</div></div>
            </article>
          )) : <p className="empty-state">暂无异常，一切安好</p>}
          <div className="card-title mt-16">一周活动量</div>
          <EChart className="family-chart" option={chartOption} ariaLabel="一周活动量柱状图" />
        </section>
      </div>

      <section className="service-band">
        <div><span className="section-kicker">社区服务</span><h2>需要时，社区可以代为预约</h2></div>
        <div className="service-actions">
          <button type="button" onClick={() => toast('已提交社区助餐预约', 'info')}><Utensils />助餐</button>
          <button type="button" onClick={() => toast('已提交陪同就医预约', 'info')}><Stethoscope />助医</button>
          <button type="button" onClick={() => toast('已提交居室保洁预约', 'info')}><WandSparkles />保洁</button>
          <button type="button" onClick={() => toast('网格员将在工作时间联系您', 'info')}><Sparkles />其他</button>
        </div>
      </section>
    </div>
  )
}
