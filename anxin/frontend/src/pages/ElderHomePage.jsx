import { Home, Pill, Phone, Volume2 } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { post } from '../api'
import { useToast } from '../App'
import HoldButton from '../components/HoldButton'
import LoadingState, { ErrorState } from '../components/LoadingState'
import { useApi, useBodyClass } from '../hooks'

function speak(text) {
  if (!('speechSynthesis' in window)) return
  window.speechSynthesis.cancel()
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = 'zh-CN'
  utterance.rate = 0.85
  window.speechSynthesis.speak(utterance)
}

export default function ElderHomePage({ embedded = false }) {
  useBodyClass(embedded ? null : 'elder-page')
  const { data, loading, error, reload } = useApi('/api/elder/home')
  const toast = useToast()
  const navigate = useNavigate()

  if (loading) return <LoadingState label="正在加载今日状态" />
  if (error) return <ErrorState message={error} onRetry={reload} />

  const checkIn = async () => {
    if (data.checked_today) return
    try {
      await post('/api/checkin')
      toast('今日平安已记录')
      speak('已记录，家人知道您今天很好')
      await reload()
    } catch (requestError) {
      toast(requestError.message, 'error')
    }
  }

  const Root = embedded ? 'div' : 'main'

  return (
    <Root id={embedded ? undefined : 'main-content'} className="elder-layout">
      <div className="e-top">
        <button className="e-voice" type="button" aria-label="播放语音提示" onClick={() => speak('您可以对我说：我很好，或者，打电话给儿子')}>
          <Volume2 aria-hidden="true" />
        </button>
        <span className="e-weather">晴 · 18℃</span>
      </div>
      <div className="e-greet">
        <h1>早上好，{data.elder.name}</h1>
        <div className="e-date">{data.today} {data.weekday}</div>
      </div>
      <button className={`e-checkin ${data.checked_today ? 'done' : ''}`} type="button" onClick={checkIn}>
        {data.checked_today ? '今天已报平安' : '我 很 好 ✓'}
      </button>
      <div className="e-hint" aria-live="polite">
        {data.checked_today ? `已于 ${data.elder.last_checkin?.slice(-5)} 报平安，谢谢！` : '点一下上面的圆按钮，告诉家人您今天很好'}
      </div>
      <div className="e-cards">
        <button className="e-card" type="button" onClick={() => speak('早上八点，降压药一片，已经吃过啦')}><Pill /><span>吃药</span><small>8:00 已吃</small></button>
        <button className="e-card" type="button" onClick={() => navigate('/elder/sos')}><Phone /><span>打给他</span><small>儿子 李伟</small></button>
        <button className="e-card" type="button" onClick={() => speak('已呼叫社区网格员王芳，请稍等')}><Home /><span>找小王</span><small>社区 王芳</small></button>
      </div>
      <HoldButton title="紧急求助" hint="长按 3 秒，通知家人和社区" onComplete={() => navigate('/elder/sos')} />
    </Root>
  )
}
