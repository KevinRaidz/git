import { Activity, BellRing, CheckCircle2, ShieldCheck, SlidersHorizontal } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { post } from '../api'
import { useToast } from '../App'
import JellyRadio from '../components/JellyRadio'

const scenarios = [
  { id: 'fall', title: '长时间无活动', detail: '连续 12 小时无活动、无开门、低用水', water: 0, door: 0, inactive_hours: 12, device_online: true, away: false },
  { id: 'no_water', title: '活动减少', detail: '6 小时无活动、门磁 1 次、低用水', water: 0, door: 1, inactive_hours: 6, device_online: true, away: false },
  { id: 'door_stuck', title: '设备离线', detail: '读数为零，先判断数据是否可信', water: 0, door: 0, inactive_hours: 36, device_online: false, away: false },
  { id: 'away', title: '老人已外出', detail: '同样没有活动，但已登记外出', water: 0, door: 0, inactive_hours: 12, device_online: true, away: true },
  { id: 'normal', title: '正常生活', detail: '有用水、有开门、有活动', water: 95, door: 8, inactive_hours: 1, device_online: true, away: false },
]

export default function SignalLabPage() {
  const [scenario, setScenario] = useState('fall')
  const [readings, setReadings] = useState(scenarios[0])
  const [pending, setPending] = useState(false)
  const [result, setResult] = useState(null)
  const toast = useToast()
  const select = item => { setScenario(item.id); setReadings(item); setResult(null) }
  const change = (key, value) => { setScenario('custom'); setReadings(old => ({ ...old, [key]: value })); setResult(null) }
  const trigger = async () => {
    setPending(true)
    try { const next = await post('/api/simulator/trigger', { scenario, readings }); setResult(next); toast(next.alert_id ? next.merged ? '已合并到正在处理的同类工单' : '预警已生成，家属和社区站内消息已保存' : '已完成判断，本次不生成预警') }
    catch (e) { toast(e.message, 'error') }
    finally { setPending(false) }
  }
  return (
    <div className="page care-page">
      <header className="care-hero simulator-hero"><div><span className="care-eyebrow"><Activity size={17} /> 安芯 · 异常发现体验</span><h1>看到异常，<br />也说清为什么。</h1><p>改变生活信号，观察系统如何区分安全关注、设备离线与正常外出。</p><div className="care-hero-actions"><Link to="/community/alerts" className="btn">进入关爱响应中心</Link></div></div><div className="care-promise"><span>IoT 数据模拟器</span><div>模拟生活信号</div><div>检查设备与外出状态</div><div>联合规则判断</div><div>生成预警与站内消息</div><small>读数入库 · 判断有依据 · 重复信号合并</small></div></header>
      <div className="care-section-heading"><div><span className="section-kicker">张桂芳 · 82 岁 · 独居</span><h2>用一个场景，体验完整响应</h2></div><span className="care-demo-label">模拟数据 / 本地演示</span></div>
      <JellyRadio className="care-scenarios" items={scenarios.map(item => ({ value: item.id, label: item.title, description: item.detail }))} value={scenario} onChange={value => select(scenarios.find(item => item.id === value))} disabled={pending} chipColor="#fff" activeColor="#ecf3e7" textColor="#3c4a38" activeTextColor="#355b3d" size="md" gap={12} swell={0.025} barge={0} shrink={0.008} ariaLabel="选择模拟场景" />
      <div className="care-simulator-grid"><section className="care-input-panel"><h3><SlidersHorizontal size={19} /> 调整观察信号</h3><p>用水与开门次数为今日累计。点击判断后，系统读取历史有效日均用水量作为个人基线。</p><fieldset disabled={pending}><div className="care-fields">{[['water', '今日累计用水量', 'L', 2000], ['door', '今日门磁开合', '次', 300], ['inactive_hours', '连续无活动时长', '小时', 168]].map(([key, label, unit, max]) => <label key={key}>{label}<div><input type="number" min={0} max={max} step={key === 'door' ? 1 : .5} value={readings[key]} onChange={e => change(key, e.target.value === '' ? '' : Number(e.target.value))} /><span>{unit}</span></div></label>)}</div><label className="care-check"><input type="checkbox" checked={readings.device_online} onChange={e => change('device_online', e.target.checked)} />设备在线，读数可用</label><label className="care-check"><input type="checkbox" checked={readings.away} onChange={e => change('away', e.target.checked)} />已登记外出（本次模拟输入）</label></fieldset><button className="btn care-run" disabled={pending} onClick={trigger}>{pending ? '正在计算并保存…' : '分析信号并生成判断'}</button><small>不会联系真实人员。所有通知仅写入本地站内消息。</small></section>
      <section className={`care-decision ${result?.level || 'neutral'}`} aria-live="polite">{result ? <><span className="section-kicker">本次判断结果</span><h2>{result.level ? <BellRing size={25} /> : <ShieldCheck size={25} />}{result.title}</h2><p className="care-rule">{result.msg}</p><h3>判断依据</h3><ul>{result.evidence.map(item => <li key={item}><CheckCircle2 size={17} />{item}</li>)}</ul><div className="care-decision-next"><strong>{result.alert_id ? result.merged ? '相同异常已合并，继续跟进已有工单' : '已生成工单，并通知家属与社区' : '本次没有新增工单'}</strong><p>{result.alert_id ? '下一步：社区安排人员、到场核实、上传回执。' : '本次判断不会关闭此前未处理的工单，已有关注仍需继续核实。'}</p>{result.alert_id && <Link className="btn" to={`/community/alerts?id=${result.alert_id}`}>查看这条工单</Link>}</div><small>{result.disclaimer}</small></> : <div className="care-decision-placeholder"><ShieldCheck size={52} /><h2>先理解信号，再发出提醒</h2><p>试试“长时间无活动”，再对比“设备离线”或“老人已外出”。同样是零读数，判断也可以不同。</p><div><span>数据可信度</span><span>个人生活基线</span><span>多信号联合</span></div></div>}</section></div>
      <section className="care-how"><h3>接下来，关注如何得到回应？</h3><div>{[['社区接到预警', '查看依据，安排服务负责人'], ['志愿者上门', '确认到场，填写核实情况'], ['家属收到进展', '站内查看派单、催办与回执']].map(([title, text]) => <article key={title}><strong>{title}</strong><p>{text}</p></article>)}</div></section>
    </div>
  )
}
