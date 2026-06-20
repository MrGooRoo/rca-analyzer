import React, { useState } from 'react'
import { useAuth } from '../context/AuthContext.jsx'
import { Button } from './ui/Button.jsx'
import { Input } from './ui/Field.jsx'
import { useToast } from './ui/Toast.jsx'

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
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-[400px] rounded-2xl bg-slate-900/60 ring-1 ring-slate-800 p-8 flex flex-col gap-6 shadow-xl shadow-black/20">
        {/* Logo */}
        <div className="flex items-center justify-center gap-2 text-xl font-bold tracking-tight text-white">
          <svg width="36" height="36" viewBox="0 0 28 28" fill="none">
            <circle cx="14" cy="14" r="13" stroke="#4f8ef7" strokeWidth="2"/>
            <path d="M8 20 L14 8 L20 20" stroke="#4f8ef7" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            <path d="M10 16 H18" stroke="#4f8ef7" strokeWidth="2" strokeLinecap="round"/>
          </svg>
          <span>RCA Analyzer</span>
        </div>

        {/* Tabs */}
        <div className="flex rounded-lg bg-slate-800 p-0.5 gap-0.5">
          <button
            type="button"
            onClick={() => { setMode('login'); setError(null) }}
            className={`flex-1 py-2 rounded-md text-sm font-medium transition-all ${
              mode === 'login'
                ? 'bg-slate-900 text-white shadow'
                : 'text-slate-400 hover:text-white'
            }`}
          >Вход</button>
          <button
            type="button"
            onClick={() => { setMode('register'); setError(null) }}
            className={`flex-1 py-2 rounded-md text-sm font-medium transition-all ${
              mode === 'register'
                ? 'bg-slate-900 text-white shadow'
                : 'text-slate-400 hover:text-white'
            }`}
          >Регистрация</button>
        </div>

        {/* Form */}
        <form className="flex flex-col gap-4" onSubmit={submit}>
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

          {error && (
            <div className="rounded-lg bg-rose-500/10 ring-1 ring-rose-500/30 text-rose-300 text-sm px-3 py-2.5">
              {error}
            </div>
          )}

          <Button type="submit" size="lg" loading={loading} className="mt-1">
            {mode === 'login' ? 'Войти' : 'Зарегистрироваться'}
          </Button>
        </form>
      </div>
    </div>
  )
}
