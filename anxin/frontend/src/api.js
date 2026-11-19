export async function api(path, options = {}) {
  const response = await fetch(path, {
    cache: 'no-store',
    ...options,
    headers: options.body
      ? { 'Content-Type': 'application/json', ...options.headers }
      : options.headers,
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const error = new Error(data.message || data.msg || '请求失败，请稍后重试')
    error.code = data.code
    error.status = response.status
    throw error
  }
  return data
}

export function post(path, body = {}) {
  return api(path, { method: 'POST', body: JSON.stringify(body) })
}
