import React, { useEffect, useState } from 'react'
import { api, clearAuth, setAuth, setAuthLostHandler } from './api.js'
import AuthPage from './components/AuthPage.jsx'
import IncidentForm from './components/IncidentForm.jsx'
import ResultView from './components/ResultView.jsx'
import CompareView from './components/CompareView.jsx'
import HistoryPage from './components/HistoryPage.jsx'
import AdminPage from './components/AdminPage.jsx'
import './App.css'

export default function App() {
  const [sessionReady, setSessionReady] = useState(false)
  const [user, setUser]                 = useState(null)
  // page: 'analyze' | 'history' | 'admin' | 'view'
  const [page, setPage]                 = useState('analyze')
  const [result, setResult]             = useState(null)
  const [comparison, setComparison]     = useState(null)
  // viewMode: { type: 'single', result } | { type: 'compare', comparison } | null
  const [viewMode, setViewMode]         = useState(null)
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
      setComparison(null)
      setViewMode(null)
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

  // === Single analysis ===
  async function handleSubmit(payload) {
    setLoading(true)
    setError(null)
    setResult(null)
    setComparison(null)
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

  // === Multi analysis ===
  async function handleSubmitMulti(payload) {
    setLoading(true)
    setError(null)
    setResult(null)
    setComparison(null)
    try {
      const results = await api.analyzeMulti(payload)
      if (!results || results.length === 0) {
        setError('Не получено результатов анализа')
        return
      }
      const incidentId = results[0].incident_id
      let comparisonData = null
      try {
        comparisonData = await api.compareResults(incidentId)
      } catch (compareErr) {
        console.warn('compareResults failed, showing raw results:', compareErr.message)
        comparisonData = {
          incident_id: incidentId,
          results: results,
          common_recommendations: [],
          differing_causes: {},
          summary: '',
        }
      }
      setComparison(comparisonData)
      setPage('analyze')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  // Открыть одиночный результат из истории — режим просмотра
  function openResult(r) {
    setViewMode({ type: 'single', result: r })
    setPage('view')
  }

  // Открыть сравнение из истории — режим просмотра
  function openComparison(comp) {
    setViewMode({ type: 'compare', comparison: comp })
    setPage('view')
  }

  function goToHistory() {
    setViewMode(null)
    setPage('history')
  }

  function goToAnalyze() {
    setViewMode(null)
    setPage('analyze')
  }

  async function logout() {
    try {
      await api.auth.logout()
    } catch {
      // ignore
    } finally {
      clearAuth()
      setUser(null)
      setResult(null)
      setComparison(null)
      setViewMode(null)
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
          <button
            className={`nav-btn ${page === 'analyze' ? 'nav-btn--active' : ''}`}
            onClick={goToAnalyze}
          >➕ Анализ</button>
          <button
            className={`nav-btn ${page === 'history' || page === 'view' ? 'nav-btn--active' : ''}`}
            onClick={goToHistory}
          >🗂 История</button>
          {isAdmin && (
            <button
              className={`nav-btn ${page === 'admin' ? 'nav-btn--active' : ''}`}
              onClick={() => setPage('admin')}
            >👥 Пользователи</button>
          )}
        </nav>
        <div className="header-right">
          <span className="header-user">{user.display_name}</span>
          <span className={`header-role-badge ${isAdmin ? 'header-role-badge--admin' : 'header-role-badge--user'}`}>
            {isAdmin ? 'Admin' : 'User'}
          </span>
          <button className="btn-logout" onClick={logout}>Выйти</button>
        </div>
      </header>

      <main className="app-main">
        {page === 'analyze' && (
          <>
            <IncidentForm
              onSubmit={handleSubmit}
              onSubmitMulti={handleSubmitMulti}
              loading={loading}
            />
            {error && <div className="alert alert-error"><strong>Ошибка:</strong> {error}</div>}
            {comparison && <CompareView comparison={comparison} />}
            {!comparison && result && <ResultView result={result} />}
          </>
        )}

        {page === 'history' && (
          <HistoryPage
            onOpen={openResult}
            onOpenComparison={openComparison}
            currentUser={user}
          />
        )}

        {page === 'view' && viewMode && (
          <div>
            <button
              className="btn-back"
              onClick={goToHistory}
              style={{ marginBottom: '1rem' }}
            >
              ← Назад в историю
            </button>
            {viewMode.type === 'single' && <ResultView result={viewMode.result} />}
            {viewMode.type === 'compare' && <CompareView comparison={viewMode.comparison} />}
          </div>
        )}

        {page === 'admin' && isAdmin && <AdminPage currentUser={user} />}
      </main>
    </div>
  )
}
