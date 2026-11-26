export async function api(path, options = {}) {
  const response = await fetch(path, {
    cache: 'no-store',
    ...options,
    headers: options.body && !(options.body instanceof FormData)
      ? { 'Content-Type': 'application/json', ...options.headers }
      : options.headers,
  })
  const data = await response.json().catch(() => ({}))
  if (response.status === 401 && path !== '/api/session') window.dispatchEvent(new Event('anxin:session-expired'))
  if (!response.ok) throw new Error(data.message || data.msg || '请求失败，请稍后重试')
  return data
}

export function post(path, body = {}) {
  return api(path, { method: 'POST', body: JSON.stringify(body) })
}
