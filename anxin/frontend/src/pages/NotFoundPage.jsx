import { ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'
import Brand from '../components/Brand'

export default function NotFoundPage() {
  return (
    <main id="main-content" className="not-found">
      <Brand />
      <span className="not-found-code">404</span>
      <h1>没有找到这个页面</h1>
      <p>地址可能已经变更，请返回角色入口继续操作。</p>
      <Link className="btn" to="/login"><ArrowLeft size={17} />返回登录</Link>
    </main>
  )
}
