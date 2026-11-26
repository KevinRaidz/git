const statusRows = [
  { id: 'pending', label: '待核实', tone: 'red', target: 1, direction: 'max' },
  { id: 'dispatched', label: '已派单', tone: 'yellow', target: 2, direction: 'max' },
  { id: 'processing', label: '处置中', tone: 'blue', target: 2, direction: 'max' },
  { id: 'closed', label: '已归档', tone: 'green', target: 4, direction: 'min' },
]

function getTargetState(value, target, direction) {
  const difference = value - target
  const reached = direction === 'max' ? difference <= 0 : difference >= 0

  if (difference === 0) return { label: '达标', reached: true }
  if (direction === 'max') {
    return reached
      ? { label: `余 ${Math.abs(difference)}`, reached }
      : { label: `超 ${difference}`, reached }
  }
  return reached
    ? { label: `超 ${difference}`, reached }
    : { label: `差 ${Math.abs(difference)}`, reached }
}

export default function WorkOrderBulletChart({ counts }) {
  return (
    <figure className="work-order-chart" aria-label="工单状态与阶段目标对比">
      <figcaption className="work-order-chart__caption">
        <span>当前工单 / 阶段目标</span>
        <span><i aria-hidden="true" />目标刻度</span>
      </figcaption>
      <div className="work-order-chart__rows">
        {statusRows.map((status, index) => {
          const value = Number(counts?.[status.id]) || 0
          const progress = Math.min(100, (value / (status.target * 1.2)) * 100)
          const targetState = getTargetState(value, status.target, status.direction)
          const targetLabel = `${status.direction === 'max' ? '≤' : '≥'} ${status.target}`

          return (
            <div
              className="work-order-bullet"
              data-status={status.id}
              key={status.id}
              style={{ '--bullet-progress': `${progress}%`, '--bullet-delay': `${index * 70}ms` }}
            >
              <div className={`work-order-bullet__label tone-${status.tone}`}>
                <i aria-hidden="true" />
                <span>{status.label}</span>
              </div>
              <div
                className="work-order-bullet__track"
                role="img"
                aria-label={`${status.label} ${value} 件，目标 ${targetLabel} 件`}
              >
                <i className="work-order-bullet__fill" aria-hidden="true" />
                <i className="work-order-bullet__target" aria-hidden="true" />
              </div>
              <div className="work-order-bullet__value">
                <b>{value}</b><span>件</span>
                <small>目标 {targetLabel}</small>
              </div>
              <span className="work-order-bullet__delta" data-reached={targetState.reached}>
                {targetState.label}
              </span>
            </div>
          )
        })}
      </div>
    </figure>
  )
}
