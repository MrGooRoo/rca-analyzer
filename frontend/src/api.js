/**
 * Централизованный API-клиент.
 * Хранит токен в памяти (не в localStorage — sandbox-ограничения).
 */

let _token = null
let _user  = null

export function setAuth(token, user) {
  _token = token
  _user  = user
}

export function clearAuth() {
  _token = null
  _user  = null
}

export function getUser() { return _user }
export function isAuthed() { return !!_token }

function headers(extra = {}) {
  const h = { 'Content-Type': 'application/json', ...extra }
  if (_token) h['Authorization'] = `Bearer ${_token}`
  return h
}

async function req(method, path, body) {
  const res = await fetch(path, {
    method,
    headers: headers(),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  auth: {
    register: (email, display_name, password) =>
      req('POST', '/api/v1/auth/register', { email, display_name, password }),
    login: (email, password) =>
      req('POST', '/api/v1/auth/login', { email, password }),
    me: () => req('GET', '/api/v1/auth/me'),
  },
  analyze: (payload) => req('POST', '/api/v1/analyze', payload),
  results: {
    list:   (limit = 20, offset = 0) => req('GET', `/api/v1/results?limit=${limit}&offset=${offset}`),
    get:    (id) => req('GET', `/api/v1/results/${id}`),
  },
}
