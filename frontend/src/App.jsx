import React, { useEffect, useRef, useState } from 'react'
import { api } from './api.js'
import { useAuth } from './context/AuthContext.jsx'
import { useToast } from './components/ui/Toast.jsx'
import { Button } from './components/ui/Button.jsx'
import AuthPage from './components/AuthPage.jsx'
import IncidentForm from './components/IncidentForm.jsx'
import AnalysisProgress from './components/AnalysisProgress.jsx'
import ResultView from './components/ResultView.jsx'
import CompareView from './components/CompareView.jsx'
import HistoryPage from './components/HistoryPage.jsx'
import AdminPage from './components/AdminPage.jsx'
import AnalysisSteps from './components/AnalysisSteps.jsx'
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
  const [multiProgressPayload, setMultiProgressPayload] = useState(null)
  const [analysisSignal, setAnalysisSignal] = useState(null)
  // Черновик формы — сохраняется при переходе в Историю и обратно
  const [formDraft, setFormDraft]       = useState(null)
  const analysisRunRef = useRef(0)
  const abortControllerRef = useRef(null)

  const isAdmin = user?.role === 'admin'

  // При потере сессии (user стал null) сбрасываем всё транзиентное состояние
  useEffect(() => {
    if (user === null) {
      analysisRunRef.current += 1
      setResult(null)
      setComparison(null)
      abortControllerRef.current?.abort()
      abortControllerRef.current = null
      setViewMode(null)
      setLoading(false)
      setMultiProgressPayload(null)
      setAnalysisSignal(null)
      setFormDraft(null)
      setPage('analyze')
    }
  }, [user])

  // Предупреждаем, если пользователь закрывает/обновляет вкладку во время анализа.
  useEffect(() => {
    if (!loading) return undefined

    function handleBeforeUnload(event) {
      event.preventDefault()
      event.returnValue = ''
    }

    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [loading])

  function cancelCurrentAnalysis({ notify = true } = {}) {
    abortControllerRef.current?.abort()
    abortControllerRef.current = null
    analysisRunRef.current += 1
    setLoading(false)
    setMultiProgressPayload(null)
    setAnalysisSignal(null)
    if (notify) {
      toast.info('Текущий запрос остановлен на стороне браузера.', 'Анализ отменён')
    }
  }

  function canLeaveAnalysis() {
    if (!loading) return true
    return window.confirm(
      'Анализ ещё идёт. Если перейти сейчас, текущий запрос будет отменён. Перейти?',
    )
  }

  function leaveAnalysisIfAllowed() {
    if (!canLeaveAnalysis()) return false
    if (loading) cancelCurrentAnalysis({ notify: false })
    return true
  }

  // === Single analysis ===
  async function handleSubmit(payload) {
    const controller = new AbortController()
    abortControllerRef.current?.abort()
    abortControllerRef.current = controller

    const runId = analysisRunRef.current + 1
    analysisRunRef.current = runId
    setAnalysisSignal(controller.signal)
    setLoading(true)
    setMultiProgressPayload(null)
    setResult(null)
    setComparison(null)
    try {
      const data = await api.analyze(payload, { signal: controller.signal })
      if (analysisRunRef.current !== runId) return
      setResult(data)
      setPage('analyze')
    } catch (e) {
      if (analysisRunRef.current !== runId || e.name === 'AbortError') return
      toast.error(e.message, 'Ошибка анализа')
    } finally {
      if (analysisRunRef.current === runId) {
        abortControllerRef.current = null
        setAnalysisSignal(null)
        setLoading(false)
      }
    }
  }

  async function showMultiResults(results, expectedRunId = null) {
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
    if (expectedRunId !== null && analysisRunRef.current !== expectedRunId) return
    setComparison(comparisonData)
    setPage('analyze')
  }

  // === Multi analysis ===
  async function handleSubmitMulti(payload) {
    const controller = new AbortController()
    abortControllerRef.current?.abort()
    abortControllerRef.current = controller

    analysisRunRef.current += 1
    setAnalysisSignal(controller.signal)
    setLoading(true)
    setResult(null)
    setComparison(null)
    setMultiProgressPayload(payload)
  }

  async function handleMultiProgressDone(results) {
    const runId = analysisRunRef.current
    try {
      await showMultiResults(results, runId)
    } catch (e) {
      if (analysisRunRef.current === runId && e.name !== 'AbortError') {
        toast.error(e.message || 'Не удалось собрать сравнение методик', 'Ошибка анализа')
      }
    } finally {
      if (analysisRunRef.current === runId) {
        abortControllerRef.current = null
        setAnalysisSignal(null)
        setLoading(false)
        setMultiProgressPayload(null)
      }
    }
  }

  function handleMultiProgressError(message, error) {
    if (error?.name !== 'AbortError') {
      toast.error(message || 'Не удалось выполнить сравнение методик', 'Ошибка анализа')
    }
    abortControllerRef.current = null
    setAnalysisSignal(null)
    setLoading(false)
    setMultiProgressPayload(null)
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
    if (!leaveAnalysisIfAllowed()) return
    setViewMode(null)
    setPage('history')
  }

  function goToAnalyze() {
    if (page !== 'analyze' && !leaveAnalysisIfAllowed()) return
    setViewMode(null)
    setPage('analyze')
  }

  function goToAdmin() {
    if (!leaveAnalysisIfAllowed()) return
    setViewMode(null)
    setPage('admin')
  }

  function startNewAnalysis() {
    abortControllerRef.current?.abort()
    abortControllerRef.current = null
    setResult(null)
    setComparison(null)
    setViewMode(null)
    setLoading(false)
    setMultiProgressPayload(null)
    setAnalysisSignal(null)
    setFormDraft(null)  // сброс черновика при явном «Новый анализ»
    setPage('analyze')
  }

  async function logout() {
    if (!leaveAnalysisIfAllowed()) return
    try {
      await authLogout()
    } catch (e) {
      toast.error(e.message, 'Ошибка выхода')
    }
  }

  // Этап анализа для степпера: 1 — ввод данных, 2 — анализ, 3 — результат
  const analysisStep = comparison || result ? 3 : loading ? 2 : 1

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
              onClick={goToAdmin}
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
            <AnalysisSteps
              current={analysisStep}
              onNavigate={(step) => {
                const ids = { 1: 'step-data', 2: 'step-method', 3: 'step-result' }
                const el = document.getElementById(ids[step])
                if (el) {
                  const y = el.getBoundingClientRect().top + window.scrollY - 120
                  window.scrollTo({ top: y, behavior: 'smooth' })
                }
              }}
            />
            {!result && !comparison && (
              <>
                <IncidentForm
                  onSubmit={handleSubmit}
                  onSubmitMulti={handleSubmitMulti}
                  loading={loading}
                  initialValues={formDraft}
                  onDraftChange={setFormDraft}
                />
                {loading && (
                  <div className="analysis-cancel-toolbar">
                    <div className="analysis-cancel-toolbar__content">
                      <div>
                        <div className="analysis-cancel-toolbar__title">Анализ выполняется</div>
                        <p className="analysis-cancel-toolbar__text">
                          Можно отменить текущий запрос и вернуться к редактированию формы.
                        </p>
                      </div>

                      {/* Простой индикатор прогресса для одиночного анализа */}
                      <div className="analysis-progress-simple">
                        <div className="analysis-progress-simple__bar">
                          <div className="analysis-progress-simple__fill" />
                        </div>
                        <span className="analysis-progress-simple__percent">В процессе…</span>
                      </div>
                    </div>

                    <Button variant="secondary" onClick={() => cancelCurrentAnalysis()}>
                      ⏹ Отменить анализ
                    </Button>
                  </div>
                )}
                {multiProgressPayload && (
                  <AnalysisProgress
                    payload={multiProgressPayload}
                    signal={analysisSignal}
                    onDone={handleMultiProgressDone}
                    onError={handleMultiProgressError}
                  />
                )}
              </>
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
