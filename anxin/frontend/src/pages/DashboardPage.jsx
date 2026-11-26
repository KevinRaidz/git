import { ArrowLeft, Radio, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import EChart from '../components/EChart'
import WorkOrderBulletChart from '../components/WorkOrderBulletChart'
import { useApi, useBodyClass } from '../hooks'

const axis = {
  axisLabel: { color: '#85888E' },
  axisLine: { lineStyle: { color: '#34363A' } },
  splitLine: { lineStyle: { color: 'rgba(255,255,255,.08)' } },
}

export default function DashboardPage({ embedded = false }) {
  useBodyClass(embedded ? null : 'dashboard-page')
  const { data, loading, error } = useApi('/api/dashboard', { interval: 5000 })
  const [scale, setScale] = useState(1)
  const [viewportWidth, setViewportWidth] = useState(() => window.innerWidth)
  const [selected, setSelected] = useState(null)
  const [hovered, setHovered] = useState(null)
  const [paused, setPaused] = useState(false)

  useEffect(() => {
    const fit = () => {
      const islandOffset = Number.parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--island-offset')) || 88
      const width = embedded ? document.querySelector('.unified-page')?.clientWidth || window.innerWidth : window.innerWidth
      setViewportWidth(width)
      setScale(Math.min(width / 1920, Math.max(320, window.innerHeight - islandOffset) / 1080))
    }
    fit()
    window.addEventListener('resize', fit)
    window.addEventListener('anxin:island-resize', fit)
    return () => {
      window.removeEventListener('resize', fit)
      window.removeEventListener('anxin:island-resize', fit)
    }
  }, [embedded])

  const riskOption = useMemo(() => ({
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie', radius: ['58%', '78%'], center: ['50%', '50%'],
      label: { show: true, position: 'center', formatter: data ? `${data.kpi.total}\n在册老人` : '--', fontSize: 18, color: '#fff', lineHeight: 26 },
      data: data ? [
        { value: data.kpi.green, name: '平安', itemStyle: { color: '#4C9A6A' } },
        { value: data.kpi.yellow, name: '需关注', itemStyle: { color: '#E0A030' } },
        { value: data.kpi.red, name: '紧急', itemStyle: { color: '#D2453C' } },
      ] : [],
    }],
  }), [data])

  const trendOption = useMemo(() => ({
    grid: { left: 34, right: 10, top: 14, bottom: 24 },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: ['-24h', '-20h', '-16h', '-12h', '-8h', '-4h', '现在'], ...axis },
    yAxis: { type: 'value', ...axis },
    series: [{ type: 'line', smooth: 0.42, showSymbol: false, data: data ? [...data.trend, data.trend.at(-1) || 0] : [], areaStyle: { color: 'rgba(255,255,255,.11)' }, lineStyle: { color: '#D7D8DA', width: 2 } }],
  }), [data])

  const kpi = data?.kpi
  const visitPct = kpi ? Math.round((kpi.visit_done / kpi.visit_due) * 100) : 0
  const marquee = data?.recent_alerts?.map(item => `${item.created_at} ${item.elder}（${item.age}岁）${item.level === 'red' ? '【紧急】' : '【关注】'}${item.reason}${item.assignee ? ` → ${item.assignee}` : ''}`).join('   ◆   ') || '当前暂无预警，辖区状态平稳'
  const activePoint = hovered || selected
  const isPinned = activePoint && selected?.id === activePoint.id
  const Root = embedded ? 'div' : 'main'

  return (
    <Root id={embedded ? undefined : 'main-content'} className={`dashboard-viewport${embedded ? ' dashboard-viewport-embedded' : ''}`}>
      <div className="screen" style={{ transform: `scale(${scale})`, marginLeft: Math.max(0, (viewportWidth - 1920 * scale) / 2) }}>
        <header className="d-top">
          <h1><span>安芯</span>幸福里社区 · 安全驾驶舱</h1>
          <div className="meta">
            <span><i className="d-dot" />在线设备 <b>{kpi ? `${kpi.devices_online}/${kpi.devices_total}` : '--'}</b></span>
            <span>{data?.last_update || '--'}</span>
            <span className="d-connection" data-state={error ? 'error' : loading ? 'loading' : 'ready'}>{error ? '连接中断' : loading ? '正在连接' : '实时同步'}</span>
            <Link className="dashboard-exit" to="/community/alerts"><ArrowLeft size={17} /> 返回管理端</Link>
          </div>
        </header>

        <div className="d-left">
          <section className="panel"><h3>风险分级</h3><EChart option={riskOption} ariaLabel="辖区老人风险等级分布" /><div className="risk-legend"><div><i style={{ background: '#4C9A6A' }} />平安 <b>{kpi?.green ?? '--'}</b> 人</div><div><i style={{ background: '#E0A030' }} />需关注 <b>{kpi?.yellow ?? '--'}</b> 人</div><div><i style={{ background: '#D2453C' }} />紧急 <b>{kpi?.red ?? '--'}</b> 人</div></div></section>
          <section className="panel dashboard-visit"><h3>本周探访完成率</h3><div className="kpi-big">{visitPct}%</div><div className="visit-bar"><i style={{ width: `${visitPct}%` }} /></div><div>已访 {kpi?.visit_done ?? '--'} / 应访 {kpi?.visit_due ?? '--'}</div><div className="overdue-text">超期 3 户 · 每两周至少探访 1 次</div></section>
        </div>

        <section className="panel d-map">
          <h3>辖区老人点位（示意地图）</h3><div className="grid-bg" />
          <div className="map-layer">
            {(data?.points || []).map(point => (
              <button
                key={point.id}
                className={`map-dot ${point.level} ${selected?.id === point.id ? 'is-selected' : ''}`}
                type="button"
                style={{ left: `${point.x}%`, top: `${point.y}%` }}
                onPointerEnter={() => setHovered(point)}
                onPointerLeave={() => setHovered(current => current?.id === point.id ? null : current)}
                onFocus={() => setHovered(point)}
                onBlur={() => setHovered(current => current?.id === point.id ? null : current)}
                onClick={() => setSelected(point)}
                aria-label={`${point.name}，${point.age} 岁，${point.level === 'green' ? '平安' : point.level === 'yellow' ? '需关注' : '紧急'}`}
              />
            ))}
          </div>
          {activePoint && (
            <aside
              className={`dashboard-map-card tone-${activePoint.level} ${activePoint.x > 60 ? 'is-left' : ''} ${isPinned ? 'is-pinned' : ''}`}
              style={{ left: `${activePoint.x}%`, top: `clamp(96px, ${activePoint.y}%, calc(100% - 96px))` }}
              role={isPinned ? 'dialog' : 'tooltip'}
              aria-label="老人信息"
              aria-live="polite"
            >
              <div className="dashboard-map-card__heading">
                <div><Radio size={18} /><h3>老人信息</h3></div>
                {isPinned && <button type="button" onClick={() => setSelected(null)} aria-label="关闭老人信息"><X size={17} /></button>}
              </div>
              <div className="dashboard-map-card__identity">
                <strong>{activePoint.name}</strong>
                <span>{activePoint.age} 岁</span>
              </div>
              <div className="dashboard-map-card__status">
                <span>风险状态</span>
                <b><i />{activePoint.level === 'green' ? '平安' : activePoint.level === 'yellow' ? '需关注' : '紧急预警'}</b>
              </div>
            </aside>
          )}
          <div className="map-legend">● 平安 · ▲ 需关注 · ◉ 脉冲 = 实时预警（悬停查看，点击固定）</div>
        </section>

        <div className="d-right"><section className="panel"><h3>近 24h 预警趋势</h3><EChart option={trendOption} ariaLabel="过去 24 小时预警趋势" /></section><section className="panel dashboard-work-orders"><h3>工单状态</h3><WorkOrderBulletChart counts={data?.status_counts} /><div className="dashboard-response">平均响应时长 <b>6.4</b> 分钟（演示数据）</div></section></div>
        <div className="d-marquee" onPointerEnter={() => setPaused(true)} onPointerLeave={() => setPaused(false)}><span className="m-label">实时预警</span><div className="marquee-window"><div className={`marquee-track ${paused ? 'is-paused' : ''}`}>{marquee}</div></div></div>
      </div>
    </Root>
  )
}
