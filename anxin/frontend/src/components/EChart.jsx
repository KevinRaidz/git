import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { AriaComponent, GridComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { useEffect, useRef } from 'react'

echarts.use([BarChart, LineChart, PieChart, GridComponent, TooltipComponent, AriaComponent, CanvasRenderer])

export default function EChart({ option, className = 'chart', ariaLabel }) {
  const ref = useRef(null)

  useEffect(() => {
    const chart = echarts.init(ref.current)
    const observer = new ResizeObserver(() => chart.resize())
    observer.observe(ref.current)
    return () => { observer.disconnect(); chart.dispose() }
  }, [])

  useEffect(() => {
    const chart = echarts.getInstanceByDom(ref.current)
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    chart?.setOption(reduceMotion ? { ...option, animation: false } : option, { notMerge: true })
  }, [option])

  return <div ref={ref} className={className} role="img" aria-label={ariaLabel} />
}
