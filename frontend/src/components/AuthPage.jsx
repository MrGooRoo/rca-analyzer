import React, { useState } from 'react'
import { useAuth } from '../context/AuthContext.jsx'
import { Button } from './ui/Button.jsx'
import { Input } from './ui/Field.jsx'
import { useToast } from './ui/Toast.jsx'
import './AuthPage.css'

export default function AuthPage() {
  const { login, register } = useAuth()
  const toast = useToast()
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
      if (mode === 'login') {
        await login(email, pass)
        toast.success('Вы вошли в систему', 'Добро пожаловать')
      } else {
        await register(email, name, pass)
        toast.success('Учётная запись создана', 'Добро пожаловать')
      }
    } catch (err) {
      const message = err.message || 'Не удалось выполнить вход'
      setError(message)
      toast.error(message, mode === 'login' ? 'Ошибка входа' : 'Ошибка регистрации')
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
            type="button"
          >Вход</button>
          <button
            className={`auth-tab ${mode === 'register' ? 'auth-tab--active' : ''}`}
            onClick={() => { setMode('register'); setError(null) }}
            type="button"
          >Регистрация</button>
        </div>

        <form className="auth-form" onSubmit={submit}>
          {mode === 'register' && (
            <Input
              label="Имя"
              type="text"
              placeholder="Иванов Иван"
              value={name}
              onChange={e => setName(e.target.value)}
              required
              minLength={1}
            />
          )}

          <Input
            label="Email"
            type="email"
            placeholder="user@example.com"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
            autoComplete="email"
          />

          <Input
            label="Пароль"
            type="password"
            placeholder="Минимум 6 символов"
            value={pass}
            onChange={e => setPass(e.target.value)}
            required
            minLength={6}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
          />

          {error && <div className="auth-error">{error}</div>}

          <Button className="auth-submit" type="submit" loading={loading}>
            {mode === 'login' ? 'Войти' : 'Зарегистрироваться'}
          </Button>
        </form>
      </div>
    </div>
  )
}
