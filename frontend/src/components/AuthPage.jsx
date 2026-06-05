import React, { useState } from 'react'
import { api } from '../api.js'
import './AuthPage.css'

export default function AuthPage({ onAuth }) {
  const [mode, setMode]       = useState('login')
  const [email, setEmail]     = useState('')
  const [name, setName]       = useState('')
  const [pass, setPass]       = useState('')
  const [error, setError]     = useState(null)
  const [loading, setLoading] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const data = mode === 'login'
        ? await api.auth.login(email, pass)
        : await api.auth.register(email, name, pass)

      onAuth(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="auth-logo">
          <svg width="36" height="36" viewBox="0 0 28 28" fill="none">
            <circle cx="14" cy="14" r="13" stroke="#4f8ef7" strokeWidth="2"/>
            <path d="M8 20 L14 8 L20 20" stroke="#4f8ef7" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            <path d="M10 16 H18" stroke="#4f8ef7" strokeWidth="2" strokeLinecap="round"/>
          </svg>
          <span>RCA Analyzer</span>
        </div>

        <div className="auth-tabs">
          <button
            className={`auth-tab ${mode === 'login' ? 'auth-tab--active' : ''}`}
            onClick={() => { setMode('login'); setError(null) }}
          >Вход</button>
          <button
            className={`auth-tab ${mode === 'register' ? 'auth-tab--active' : ''}`}
            onClick={() => { setMode('register'); setError(null) }}
          >Регистрация</button>
        </div>

        <form className="auth-form" onSubmit={submit}>
          {mode === 'register' && (
            <label className="field">
              <span className="field-label">Имя</span>
              <input
                className="field-input"
                type="text"
                placeholder="Иванов Иван"
                value={name}
                onChange={e => setName(e.target.value)}
                required
                minLength={1}
              />
            </label>
          )}

          <label className="field">
            <span className="field-label">Email</span>
            <input
              className="field-input"
              type="email"
              placeholder="user@example.com"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </label>

          <label className="field">
            <span className="field-label">Пароль</span>
            <input
              className="field-input"
              type="password"
              placeholder="Минимум 6 символов"
              value={pass}
              onChange={e => setPass(e.target.value)}
              required
              minLength={6}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            />
          </label>

          {error && <div className="auth-error">{error}</div>}

          <button className="auth-submit" type="submit" disabled={loading}>
            {loading ? '…' : mode === 'login' ? 'Войти' : 'Зарегистрироваться'}
          </button>
        </form>
      </div>
    </div>
  )
}
