import React, { useEffect, useState } from 'react'
import { api } from './api.js'
import { useAuth } from './context/AuthContext.jsx'
import { useToast } from './components/ui/Toast.jsx'
import { Button } from './components/ui/Button.jsx'
import AuthPage from './components/AuthPage.jsx'
import IncidentForm from './components/IncidentForm.jsx'
import ResultView from './components/ResultView.jsx'
import CompareView from './components/CompareView.jsx'
import HistoryPage from './components/HistoryPage.jsx'
import AdminPage from './components/AdminPage.jsx'
import './App.css'

export default function App() {
  const { user, loading: authLoading, logout: authLogout } = useAuth()
  const toast = useToast()

  // page: 'analyze' | 'history' | 'admin' | 'view'
  const [page, setPage]                 = useState('analyze')
  const [result, setResult]             = useState(null)
  const [comparison, setComparison]     = useState(null)
  // viewMode: { type: 'single', result } | { type: 'compare', comparison } | null
  const [viewMode, setViewMode]         = useState(null)
  const [loading, setLoading]           = useState(false)

  const isAdmin = user?.role === 'admin'

  // При потере сессии (user стал null) сбрасываем всё транзиентное состояние
  useEffect(() => {
    if (user === null) {
      setResult(null)
      setComparison(null)
      setViewMode(null)
      setPage('analyze')
    }
  }, [user])

  // === Single analysis ===
  async function handleSubmit(payload) {
    setLoading(true)
    setResult(null)
    setComparison(null)
    try {
      const data = await api.analyze(payload)
      setResult(data)
      setPage('analyze')
    } catch (e) {
      toast.error(e.message, 'Ошибка анализа')
    } finally {
      setLoading(false)
    }
  }

  // === Multi analysis ===
  async function handleSubmitMulti(payload) {
    setLoading(true)
    setResult(null)
    setComparison(null)
    try {
      const results = await api.analyzeMulti(payload)
      if (!results || results.length === 0) {
        toast.error('Не получено результатов анализа', 'Пустой ответ')
        return
      }
      const incidentId = results[0].incident_id
      const sessionId = results[0].session_id || null
      let comparisonData = null
      try {
        comparisonData = await api.compareResults(incidentId, sessionId)
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
      toast.error(e.message, 'Ошибка анализа')
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


  function startNewAnalysis() {
    setResult(null)
    setComparison(null)
    setViewMode(null)
    setPage('analyze')
  }

  async function logout() {
    try {
      await authLogout()
    } catch (e) {
      toast.error(e.message, 'Ошибка выхода')
    }
  }

  if (authLoading) {
    return (
      <div className="app">
        <main className="app-main">
          <div className="alert">Проверка сессии…</div>
        </main>
      </div>
    )
  }

  if (!user) {
    return <AuthPage />
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
          <Button
            variant="ghost"
            size="sm"
            className={page === 'analyze' ? 'app-nav-btn--active' : ''}
            onClick={goToAnalyze}
          >➕ Анализ</Button>
          <Button
            variant="ghost"
            size="sm"
            className={page === 'history' || page === 'view' ? 'app-nav-btn--active' : ''}
            onClick={goToHistory}
          >🗂 История</Button>
          {isAdmin && (
            <Button
              variant="ghost"
              size="sm"
              className={page === 'admin' ? 'app-nav-btn--active' : ''}
              onClick={() => setPage('admin')}
            >👥 Пользователи</Button>
          )}
        </nav>
        <div className="header-right">
          <span className="header-user">{user.display_name}</span>
          <span className={`header-role-badge ${isAdmin ? 'header-role-badge--admin' : 'header-role-badge--user'}`}>
            {isAdmin ? 'Admin' : 'User'}
          </span>
          <Button variant="secondary" size="sm" onClick={logout}>Выйти</Button>
        </div>
      </header>

      <main className="app-main">
        {page === 'analyze' && (
          <>
            {!result && !comparison && (
              <IncidentForm
                onSubmit={handleSubmit}
                onSubmitMulti={handleSubmitMulti}
                loading={loading}
              />
            )}

            {(result || comparison) && (
              <div className="analysis-result-toolbar">
                <div>
                  <div className="analysis-result-toolbar__eyebrow">Результат анализа</div>
                  <h2 className="analysis-result-toolbar__title">
                    {comparison ? 'Сравнение методик готово' : 'Анализ готов'}
                  </h2>
                  <p className="analysis-result-toolbar__text">
                    Форма скрыта, чтобы результат не смешивался с вводом. Для нового случая нажмите «Новый анализ».
                  </p>
                </div>
                <Button variant="primary" onClick={startNewAnalysis}>➕ Новый анализ</Button>
              </div>
            )}

            {comparison && <CompareView comparison={comparison} />}
            {!comparison && result && <ResultView result={result} onOpenResult={openResult} />}
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
            <div className="view-actions">
              <Button
                variant="secondary"
                size="sm"
                onClick={goToHistory}
              >
                ← Назад в историю
              </Button>
              <Button variant="primary" size="sm" onClick={startNewAnalysis}>➕ Новый анализ</Button>
            </div>
            {viewMode.type === 'single' && <ResultView result={viewMode.result} onOpenResult={openResult} />}
            {viewMode.type === 'compare' && <CompareView comparison={viewMode.comparison} />}
          </div>
        )}

        {page === 'admin' && isAdmin && <AdminPage currentUser={user} />}
      </main>
    </div>
  )
}
