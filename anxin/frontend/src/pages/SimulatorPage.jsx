import { Activity, DoorOpen, Droplets, ExternalLink } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { post } from '../api'
import { useToast } from '../App'

const scenarios = [
  { id: 'fall', title: '夜间跌倒', detail: '红外监测跌倒姿态，15 分钟未起身', level: 'red', Icon: Activity },
  { id: 'no_water', title: '全天无用水', detail: '用水 0L，门磁仅开合 1 次', level: 'yellow', Icon: Droplets },
  { id: 'door_stuck', title: '门磁 36 小时未动', detail: '夜间没有红外活动记录', level: 'yellow', Icon: DoorOpen },
]

export default function SimulatorPage() {
  const toast = useToast()
  const [pending, setPending] = useState('')
  const [result, setResult] = useState(null)

  const trigger = async scenario => {
    setPending(scenario)
    setResult(null)
    try {
      const data = await post('/api/simulator/trigger', { scenario })
      setResult(data)
      toast('演示场景已注入')
    } catch (error) {
      setResult({ ok: false, msg: error.message })
      toast(error.message, 'error')
    } finally {
      setPending('')
    }
  }

  return (
    <div className="page simulator-page">
      <header className="page-heading"><div><span className="section-kicker">答辩演示控制台</span><h1>IoT 数据模拟器</h1><p>注入模拟时序数据，验证预警、派单、处置和家属同步闭环。</p></div></header>
      <section className="scenario-grid">
        {scenarios.map(({ id, title, detail, level, Icon }) => <button className={`scenario-item level-${level}`} type="button" key={id} onClick={() => trigger(id)} disabled={Boolean(pending)} aria-busy={pending === id}><span className="scenario-icon"><Icon /></span><strong>{title}</strong><span>{detail}</span><small>{level === 'red' ? '生成红色紧急预警' : '生成黄色关注预警'}</small></button>)}
      </section>
      {pending && <div className="simulator-result loading-result">正在注入模拟数据…</div>}
      {result && <div className={`simulator-result ${result.ok ? 'success-result' : 'error-result'}`} role="status"><strong>{result.ok ? '场景已注入' : '注入失败'}</strong><p>{result.msg}</p>{result.ok && <div><Link to="/community/dashboard">查看驾驶舱 <ExternalLink size={15} /></Link><Link to="/community/alerts">查看工单看板 <ExternalLink size={15} /></Link></div>}</div>}
      <section className="demo-route"><span className="section-kicker">建议演示动线</span><ol><li><b>子女端总览</b><span>确认初始状态与活动轨迹</span></li><li><b>注入夜间跌倒</b><span>生成红色实时预警</span></li><li><b>社区驾驶舱</b><span>观察点位、趋势和跑马灯</span></li><li><b>预警工单看板</b><span>派单给志愿者赵敏</span></li><li><b>志愿者端</b><span>到场打卡、上传回执并归档</span></li></ol></section>
    </div>
  )
}
