/**
 * Централизованный API-клиент.
 * Access/refresh-токены живут в httpOnly cookie; во frontend хранится только user-info.
 */

let _user = null
let _authLostHandler = null
let _refreshPromise = null

export function setAuth(user) {
  _user = user
}

export function clearAuth() {
  _user = null
}

export function getUser() {
  return _user
}

export function isAuthed() {
  return !!_user
}

export function setAuthLostHandler(handler) {
  _authLostHandler = handler
}

function notifyAuthLost() {
  clearAuth()
  _authLostHandler?.()
}

function defaultHeaders(body) {
  return body !== undefined ? { 'Content-Type': 'application/json' } : {}
}

function isJsonResponse(response) {
  return response.headers.get('content-type')?.includes('application/json')
}

async function readError(response) {
  if (isJsonResponse(response)) {
    const err = await response.json().catch(() => null)
    if (err?.detail) return err.detail
  }
  const text = await response.text().catch(() => '')
  return text || `HTTP ${response.status}`
}

async function parseResponse(response, parseAs) {
  if (response.status === 204) return null
  if (parseAs === 'blob') return response.blob()
  if (parseAs === 'text') return response.text()
  if (!isJsonResponse(response)) return null
  return response.json()
}

function canAutoRefresh(path, authRequired, retryOn401) {
  if (!authRequired || !retryOn401) return false
  return ![
    '/api/v1/auth/login',
    '/api/v1/auth/register',
    '/api/v1/auth/refresh',
    '/api/v1/auth/logout',
  ].includes(path)
}

async function tryRefresh() {
  if (_refreshPromise) return _refreshPromise

  _refreshPromise = (async () => {
    const res = await fetch('/api/v1/auth/refresh', {
      method: 'POST',
      credentials: 'include',
    })
    if (!res.ok) return false

    const data = await res.json().catch(() => null)
    if (data?.user_id) {
      setAuth(data)
    }
    return true
  })().finally(() => {
    _refreshPromise = null
  })

  return _refreshPromise
}

async function req(method, path, body, options = {}) {
  const {
    parseAs = 'json',
    authRequired = false,
    retryOn401 = true,
  } = options

  const response = await fetch(path, {
    method,
    headers: defaultHeaders(body),
    body: body !== undefined ? JSON.stringify(body) : undefined,
    credentials: 'include',
  })

  if (response.status === 401 && canAutoRefresh(path, authRequired, retryOn401)) {
    const refreshed = await tryRefresh()
    if (refreshed) {
      return req(method, path, body, { ...options, retryOn401: false })
    }
    notifyAuthLost()
  }

  if (!response.ok) {
    if (response.status === 401 && authRequired) {
      notifyAuthLost()
    }
    throw new Error(await readError(response))
  }

  return parseResponse(response, parseAs)
}

function filenameFromDisposition(value, fallback) {
  if (!value) return fallback
  const match = value.match(/filename="?([^";]+)"?/i)
  return match?.[1] || fallback
}

async function exportDocx(resultId, methodology, retryOn401 = true) {
  const response = await fetch(`/api/v1/results/${resultId}/export`, {
    method: 'GET',
    credentials: 'include',
  })

  if (response.status === 401 && retryOn401) {
    const refreshed = await tryRefresh()
    if (refreshed) return exportDocx(resultId, methodology, false)
    notifyAuthLost()
  }

  if (!response.ok) {
    if (response.status === 401) notifyAuthLost()
    throw new Error(await readError(response))
  }

  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  const fallback = `rca_${methodology}_${resultId.slice(0, 8)}.docx`

  a.href = url
  a.download = filenameFromDisposition(response.headers.get('content-disposition'), fallback)
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

export const api = {
  auth: {
    register: (email, display_name, password) =>
      req('POST', '/api/v1/auth/register', { email, display_name, password }, { retryOn401: false }),
    login: (email, password) =>
      req('POST', '/api/v1/auth/login', { email, password }, { retryOn401: false }),
    me: () => req('GET', '/api/v1/auth/me', undefined, { authRequired: true }),
    refresh: () => req('POST', '/api/v1/auth/refresh', undefined, { retryOn401: false }),
    logout: () => req('POST', '/api/v1/auth/logout', undefined, { retryOn401: false }),
  },
  analyze: (payload) => req('POST', '/api/v1/analyze', payload, { authRequired: true }),
  exportDocx,
  results: {
    list: (limit = 20, offset = 0) =>
      req('GET', `/api/v1/results?limit=${limit}&offset=${offset}`, undefined, { authRequired: true }),
    get: (id) => req('GET', `/api/v1/results/${id}`, undefined, { authRequired: true }),
  },
}
