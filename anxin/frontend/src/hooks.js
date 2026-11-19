import { useCallback, useEffect, useState } from 'react'
import { api } from './api'

export function useApi(path, { interval = 0 } = {}) {
  const [state, setState] = useState({ data: null, loading: true, error: '' })
  const load = useCallback(async () => {
    try {
      const data = await api(path)
      setState({ data, loading: false, error: '' })
      return data
    } catch (error) {
      setState(current => ({ ...current, loading: false, error: error.message }))
      return null
    }
  }, [path])

  useEffect(() => {
    load()
    if (!interval) return undefined
    const timer = window.setInterval(load, interval)
    return () => window.clearInterval(timer)
  }, [load, interval])

  return { ...state, reload: load }
}

export function useBodyClass(className = '') {
  useEffect(() => {
    if (!className) return undefined
    document.body.className = className
    return () => { document.body.className = '' }
  }, [className])
}
