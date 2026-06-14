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

const CSRF_COOKIE_NAME = 'csrf_token'
const CSRF_HEADER_NAME = 'X-CSRF-Token'
const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS'])

function readCsrfToken() {
  const match = document.cookie.match(
    new RegExp('(?:^|; )' + CSRF_COOKIE_NAME + '=([^;]*)'),
  )
  return match ? decodeURIComponent(match[1]) : null
}

async function ensureCsrf() {
  if (!readCsrfToken()) {
    await fetch('/api/v1/auth/csrf', {
      method: 'GET',
      credentials: 'include',
    })
  }
}

function withCsrf(headers, method) {
  if (SAFE_METHODS.has(method.toUpperCase())) return headers
  const token = readCsrfToken()
  if (token) headers[CSRF_HEADER_NAME] = token
  return headers
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
    if (err?.detail) {
      if (typeof err.detail === 'string') return err.detail
      if (Array.isArray(err.detail)) {
        return err.detail
          .map(e => `${e.loc?.join('.') || '?'}: ${e.msg}`)
          .join('; ')
      }
      try { return JSON.stringify(err.detail) } catch { return String(err.detail) }
    }
    try { return JSON.stringify(err) } catch { return String(err) }
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
    signal,
  } = options

  const response = await fetch(path, {
    method,
    headers: withCsrf(defaultHeaders(body), method),
    body: body !== undefined ? JSON.stringify(body) : undefined,
    credentials: 'include',
    signal,
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

async function exportResult(resultId, methodology, format = 'docx', retryOn401 = true) {
  const fmt = format === 'pdf' ? 'pdf' : 'docx'
  const response = await fetch(`/api/v1/results/${resultId}/export?format=${fmt}`, {
    method: 'GET',
    credentials: 'include',
  })

  if (response.status === 401 && retryOn401) {
    const refreshed = await tryRefresh()
    if (refreshed) return exportResult(resultId, methodology, fmt, false)
    notifyAuthLost()
  }

  if (!response.ok) {
    if (response.status === 401) notifyAuthLost()
    throw new Error(await readError(response))
  }

  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  const fallback = `rca_${methodology}_${resultId.slice(0, 8)}.${fmt}`

  a.href = url
  a.download = filenameFromDisposition(response.headers.get('content-disposition'), fallback)
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

async function exportDocx(resultId, methodology) {
  return exportResult(resultId, methodology, 'docx')
}

async function uploadFile(path, file, options = {}) {
  const {
    authRequired = true,
    retryOn401 = true,
  } = options

  const formData = new FormData()
  formData.append('file', file)

  const headers = {}
  const csrfToken = readCsrfToken()
  if (csrfToken) headers[CSRF_HEADER_NAME] = csrfToken

  const response = await fetch(path, {
    method: 'POST',
    headers,
    body: formData,
    credentials: 'include',
  })

  if (response.status === 401 && canAutoRefresh(path, authRequired, retryOn401)) {
    const refreshed = await tryRefresh()
    if (refreshed) {
      return uploadFile(path, file, { ...options, retryOn401: false })
    }
    notifyAuthLost()
  }

  if (!response.ok) {
    if (response.status === 401 && authRequired) {
      notifyAuthLost()
    }
    throw new Error(await readError(response))
  }

  return response.json()
}

async function uploadFileStream(path, file, onProgress, options = {}) {
  const {
    authRequired = true,
    retryOn401 = true,
  } = options

  const formData = new FormData()
  formData.append('file', file)

  const headers = {}
  const csrfToken = readCsrfToken()
  if (csrfToken) headers[CSRF_HEADER_NAME] = csrfToken

  const response = await fetch(path, {
    method: 'POST',
    headers,
    body: formData,
    credentials: 'include',
  })

  if (response.status === 401 && canAutoRefresh(path, authRequired, retryOn401)) {
    const refreshed = await tryRefresh()
    if (refreshed) {
      return uploadFileStream(path, file, onProgress, { ...options, retryOn401: false })
    }
    notifyAuthLost()
  }

  if (!response.ok) {
    if (response.status === 401 && authRequired) {
      notifyAuthLost()
    }
    throw new Error(await readError(response))
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let boundary = buffer.indexOf('\n\n')
    while (boundary !== -1) {
      const chunk = buffer.slice(0, boundary).trim()
      buffer = buffer.slice(boundary + 2)
      boundary = buffer.indexOf('\n\n')

      if (chunk.startsWith('data: ')) {
        try {
          const data = JSON.parse(chunk.slice(6))
          if (data.status === 'error') {
            throw new Error(data.message || 'Unknown error')
          }
          onProgress(data)
          if (data.status === 'done') {
            return data.result
          }
        } catch (e) {
          if (e.message !== 'Unexpected end of JSON input') {
            if (chunk.includes('"status": "error"')) throw e
          }
        }
      }
    }
  }
}

/**
 * analyzeMultiStream — SSE-поток прогресса анализа.
 *
 * onEvent(event) вызывается на каждое SSE-событие:
 *   { status: 'started',   total, methodologies }
 *   { status: 'progress',  methodology, name, done, total }
 *   { status: 'error_one', methodology, name, message, done, total }
 *   { status: 'done',      results }  ← возвращается из промиса
 *   { status: 'error',     message }  ← бросается как Error
 */
function querySimilarIncidents(text, options = {}) {
  // POST с текстом в теле: длинные описания в query string вызывали HTTP 431
  const payload = {
    text: String(text || '').slice(0, 5000),
    limit: options.limit || 5,
  }
  if (options.threshold !== undefined) payload.threshold = options.threshold
  if (options.excludeResultId) payload.exclude_result_id = options.excludeResultId
  if (options.excludeIncidentId) payload.exclude_incident_id = options.excludeIncidentId
  // Поля для исключения повторных анализов того же инцидента
  if (options.incidentTitle) payload.incident_title = options.incidentTitle
  if (options.incidentDescription) payload.incident_description = options.incidentDescription
  return req('POST', '/api/v1/incidents/similar', payload, { authRequired: true })
}

async function analyzeMultiStream(payload, onEvent, options = {}) {
  const {
    retryOn401 = true,
    signal,
  } = options

  const csrfToken = readCsrfToken()
  const headers = { 'Content-Type': 'application/json' }
  if (csrfToken) headers[CSRF_HEADER_NAME] = csrfToken

  const response = await fetch('/api/v1/analyze-multi-stream', {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
    credentials: 'include',
    signal,
  })

  if (response.status === 401 && retryOn401) {
    const refreshed = await tryRefresh()
    if (refreshed) return analyzeMultiStream(payload, onEvent, { retryOn401: false, signal })
    notifyAuthLost()
    throw new Error('Сессия истекла. Войдите заново.')
  }

  if (!response.ok) {
    if (response.status === 401) notifyAuthLost()
    throw new Error(await readError(response))
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let boundary = buffer.indexOf('\n\n')
    while (boundary !== -1) {
      const chunk = buffer.slice(0, boundary).trim()
      buffer = buffer.slice(boundary + 2)
      boundary = buffer.indexOf('\n\n')

      if (chunk.startsWith('data: ')) {
        let event
        try {
          event = JSON.parse(chunk.slice(6))
        } catch {
          continue
        }

        onEvent(event)

        if (event.status === 'done') return event.results
        if (event.status === 'error') throw new Error(event.message || 'Ошибка анализа')
      }
    }
  }
}

export const api = {
  auth: {
    register: async (email, display_name, password) => {
      await ensureCsrf()
      return req('POST', '/api/v1/auth/register', { email, display_name, password }, { retryOn401: false })
    },
    login: async (email, password) => {
      await ensureCsrf()
      return req('POST', '/api/v1/auth/login', { email, password }, { retryOn401: false })
    },
    me: () => req('GET', '/api/v1/auth/me', undefined, { authRequired: true }),
    refresh: () => req('POST', '/api/v1/auth/refresh', undefined, { retryOn401: false }),
    logout: () => req('POST', '/api/v1/auth/logout', undefined, { retryOn401: false }),
  },
  analyze: (payload, options = {}) => req('POST', '/api/v1/analyze', payload, { authRequired: true, ...options }),
  analyzeMulti: (payload, options = {}) => req('POST', '/api/v1/analyze-multi', payload, { authRequired: true, ...options }),
  analyzeMultiStream: (payload, onEvent, options = {}) => analyzeMultiStream(payload, onEvent, options),
  compareResults: (incidentId, sessionId) => {
    // Предпочитаем session_id; fallback на incident_id для обратной совместимости
    if (sessionId) {
      return req('GET', `/api/v1/results/compare?session_id=${encodeURIComponent(sessionId)}`, undefined, { authRequired: true })
    }
    return req('GET', `/api/v1/results/compare?incident_id=${encodeURIComponent(incidentId)}`, undefined, { authRequired: true })
  },
  similarIncidents: (text, options = {}) => querySimilarIncidents(text, options),
  uploadReport: (file) => uploadFile('/api/v1/upload-report', file, { authRequired: true }),
  uploadReportStream: (file, onProgress) => uploadFileStream('/api/v1/upload-report-stream', file, onProgress, { authRequired: true }),
  exportDocx,
  exportResult,
  results: {
    list: (limit = 20, offset = 0) =>
      req('GET', `/api/v1/results?limit=${limit}&offset=${offset}`, undefined, { authRequired: true }),
    get: (id) => req('GET', `/api/v1/results/${id}`, undefined, { authRequired: true }),
    delete: (id) => req('DELETE', `/api/v1/results/${id}`, undefined, { authRequired: true }),
  },
  sessions: {
    list: (limit = 20, offset = 0) =>
      req('GET', `/api/v1/sessions?limit=${limit}&offset=${offset}`, undefined, { authRequired: true }),
    get: (id) => req('GET', `/api/v1/sessions/${id}`, undefined, { authRequired: true }),
  },
  admin: {
    listUsers: () => req('GET', '/api/v1/admin/users', undefined, { authRequired: true }),
    setRole: (userId, role) =>
      req('PUT', `/api/v1/admin/users/${userId}/role`, { role }, { authRequired: true }),
  },
}
