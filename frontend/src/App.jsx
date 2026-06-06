import React, { useEffect, useState } from 'react'
import { api, clearAuth, setAuth, setAuthLostHandler } from './api.js'
import AuthPage from './components/AuthPage.jsx'
import IncidentForm from './components/IncidentForm.jsx'
import ResultView from './components/ResultView.jsx'
import HistoryPage from './components/HistoryPage.jsx'
import AdminPage from './components/AdminPage.jsx'
import './App.css'

export default function App() {
  const [sessionReady, setSessionReady] = useState(false)
  const [user, setUser]                 = useState(null)
  const [page, setPage]                 = useState('analyze')
  const [result, setResult]             = useState(null)
  const [loading, setLoading]           = useState(false)
  const [error, setError]               = useState(null)

  const isAdmin = user?.role === 'admin'

  useEffect(() => {
    let active = true

    async function bootstrapSession() {
      try {
        const me = await api.auth.me()
        if (!active) return
        setAuth(me)
        setUser(me)
      } catch {
        if (!active) return
        clearAuth()
        setUser(null)
      } finally {
        if (active) setSessionReady(true)
      }
    }

    setAuthLostHandler(() => {
      if (!active) return
      clearAuth()
      setUser(null)
      setResult(null)
      setError(null)
      setPage('analyze')
    })

    bootstrapSession()

    return () => {
      active = false
      setAuthLostHandler(null)
    }
  }, [])

  function handleAuth(userInfo) {
    setAuth(userInfo)
    setUser(userInfo)
    setError(null)
    setPage('analyze')
  }

  async function handleSubmit(payload) {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await api.analyze(payload)
      setResult(data)
      setPage('analyze')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  function openResult(r) {
    setResult(r)
    setPage('analyze')
  }

  async function logout() {
    try {
      await api.auth.logout()
    } catch {
      // Игнорируем — в finally всё равно очищаем локальное состояние.
    } finally {
      clearAuth()
      setUser(null)
      setResult(null)
      setError(null)
      setPage('analyze')
    }
  }

  if (!sessionReady) {
    return (
      <div className="app">
        <main className="app-main">
          <div className="alert">Проверка сессии…</div>
        </main>
      </div>
    )
  }

  if (!user) {
    return <AuthPage onAuth={handleAuth} />
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="logo">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <circle cx="14" cy="14" r="13" stroke="#4f8ef7" strokeWidth="2"/>
            <path d="M8 20 L14 8 L20 20" stroke="#4f8ef7" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            <path d="M10 16 H18" stroke="#4f8ef7" strokeWidth="2" strokeLinecap="round"/>
          </svg>
          <span>RCA Analyzer</span>
        </div>
        <nav className="app-nav">
          <button className={`nav-btn ${page === 'analyze' ? 'nav-btn--active' : ''}`} onClick={() => setPage('analyze')}>➕ Анализ</button>
          <button className={`nav-btn ${page === 'history' ? 'nav-btn--active' : ''}`} onClick={() => setPage('history')}>🗂 История</button>
          {isAdmin && (
            <button className={`nav-btn ${page === 'admin' ? 'nav-btn--active' : ''}`} onClick={() => setPage('admin')}>👥 Пользователи</button>
          )}
        </nav>
        <div className="header-right">
          <span className="header-user">
            {user.display_name}
          </span>
          <span className={`header-role-badge ${isAdmin ? 'header-role-badge--admin' : 'header-role-badge--user'}`}>
            {isAdmin ? 'Admin' : 'User'}
          </span>
          <button className="btn-logout" onClick={logout}>Выйти</button>
        </div>
      </header>

      <main className="app-main">
        {page === 'analyze' && (
          <>
            <IncidentForm onSubmit={handleSubmit} loading={loading} />
            {error && <div className="alert alert-error"><strong>Ошибка:</strong> {error}</div>}
            {result && <ResultView result={result} />}
          </>
        )}
        {page === 'history' && <HistoryPage onOpen={openResult} currentUser={user} />}
        {page === 'admin' && isAdmin && <AdminPage currentUser={user} />}
      </main>
    </div>
  )
}
