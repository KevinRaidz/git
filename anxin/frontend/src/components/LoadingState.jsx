export default function LoadingState({ label = '正在加载' }) {
  return (
    <div className="loading-state" role="status">
      <span className="loading-bars" aria-hidden="true"><i /><i /><i /></span>
      <span>{label}</span>
    </div>
  )
}

export function ErrorState({ message, onRetry }) {
  return (
    <div className="error-state" role="alert">
      <strong>数据暂时不可用</strong>
      <span>{message}</span>
      {onRetry && <button className="btn btn-sm" type="button" onClick={onRetry}>重新加载</button>}
    </div>
  )
}
