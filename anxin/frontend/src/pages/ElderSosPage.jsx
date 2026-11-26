import { ArrowLeft, CheckCircle2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { post } from '../api'
import HoldButton from '../components/HoldButton'
import LoadingState, { ErrorState } from '../components/LoadingState'
import { useApi, useBodyClass } from '../hooks'

export default function ElderSosPage() {
  useBodyClass('elder-page sos-page')
  const { data, loading, error, reload } = useApi('/api/elder/home')
  const [stage, setStage] = useState('hold')
  const [count, setCount] = useState(5)
  const [notified, setNotified] = useState([])
  const sent = useRef(false)
  const navigate = useNavigate()

  useEffect(() => {
    if (stage !== 'count') return undefined
    if (count > 0) {
      const timer = window.setTimeout(() => setCount(value => value - 1), 1000)
      return () => window.clearTimeout(timer)
    }
    if (!sent.current) {
      sent.current = true
      post('/api/sos').then(result => {
        setNotified(result.notified || [])
        setStage('sent')
      }).catch(() => setStage('error'))
    }
    return undefined
  }, [stage, count])

  if (loading) return <LoadingState label="正在准备紧急求助" />
  if (error) return <ErrorState message={error} onRetry={reload} />

  return (
    <main id="main-content" className="sos-flow">
      {stage === 'hold' && (
        <section className="sos-stage active">
          <h1>请长按下方按钮呼救</h1>
          <HoldButton title="长按呼救" hint="按住 3 秒，进入求助确认" onComplete={() => setStage('count')} />
          <button className="sos-back-link" type="button" onClick={() => navigate('/elder/home')}><ArrowLeft /> 返回今日平安</button>
        </section>
      )}
      {stage === 'count' && (
        <section className="sos-stage active">
          <h1>即将发送求助</h1>
          <div className="sos-count-num" aria-live="assertive">{count}</div>
          <div className="sos-sub">秒后通知家人、社区与志愿者</div>
          <button className="sos-cancel" type="button" onClick={() => { setStage('hold'); setCount(5) }}>我没事，取消求助</button>
        </section>
      )}
      {stage === 'sent' && (
        <section className="sos-stage active" id="stage-sent">
          <CheckCircle2 className="sent-icon" size={72} aria-hidden="true" />
          <h1>求助已发送</h1>
          <p className="sos-sub">求助已记录，请保持电话畅通，等待社区确认</p>
          <div className="sos-notified">{notified.map(item => <div key={item}>{item}</div>)}</div>
          <div className="med-card">
            <h2>{data.elder.name} · 医疗信息卡</h2>
            <p><b>年龄</b>{data.elder.age} 岁</p>
            <p><b>慢病</b>{data.elder.chronic}</p>
            <p><b>血型</b>{data.elder.blood_type || '未知'}</p>
            <p><b>药物过敏</b>{data.elder.allergy || '无'}</p>
            <p><b>紧急联系人</b>{data.elder.emergency_contact}</p>
          </div>
          <button className="sos-cancel" type="button" onClick={() => navigate('/elder/home')}>返回今日平安</button>
        </section>
      )}
      {stage === 'error' && <ErrorState message="求助发送失败，请立即拨打 120" onRetry={() => { sent.current = false; setCount(0); setStage('count') }} />}
    </main>
  )
}
