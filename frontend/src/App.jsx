import React, { useEffect, useRef, useState } from 'react'
import { api } from './api.js'
import { useAuth } from './context/AuthContext.jsx'
import { useToast } from './components/ui/Toast.jsx'
import { Button } from './components/ui/Button.jsx'
import AuthPage from './components/AuthPage.jsx'
import IncidentForm from './components/IncidentForm.jsx'
import AnalysisProgress from './components/AnalysisProgress.jsx'
import SingleAnalysisProgress from './components/SingleAnalysisProgress.jsx'
import ResultView from './components/ResultView.jsx'
import CompareView from './components/CompareView.jsx'
import HistoryPage from './components/HistoryPage.jsx'
import AdminPage from './components/AdminPage.jsx'
import AnalysisSteps from './components/AnalysisSteps.jsx'
import { methodologyMeta } from './lib/methodologies.js'
import './App.css'

export default function App() {
  const { user, loading: authLoading, logout: authLogout } = useAuth()
  const toast = useToast()

  const [page, setPage] = useState('analyze')
  const [result, setResult] = useState(null)
  const [comparison, setComparison] = useState(null)
  const [viewMode, setViewMode] = useState(null)
  const [loading, setLoading] = useState(false)
  const [multiProgressPayload, setMultiProgressPayload] = useState(null)
  const [analysisSignal, setAnalysisSignal] = useState(null)
  const [formDraft, setFormDraft] = useState(null)
  const [singleProgress, setSingleProgress] = useState(null)
  const analysisRunRef = useRef(0)
  const abortControllerRef = useRef(null)

  const isAdmin = user?.role === 'admin'

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
      setSingleProgress(null)
      setPage('analyze')
    }
  }, [user])

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
    setSingleProgress(null)
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

  async function handleSubmit(payload) {
    const controller = new AbortController()
    abortControllerRef.current?.abort()
    abortControllerRef.current = controller
    const runId = analysisRunRef.current + 1
    analysisRunRef.current = runId
    setAnalysisSignal(controller.signal)
    setLoading(true)
    setMultiProgressPayload(null)
    setSingleProgress({
      phase: 'running',
      stage: 'started',
      percent: 0,
      message: 'Запуск анализа…',
      methodologyName: methodologyMeta(payload.methodology).name,
      methodologyKey: payload.methodology,
    })
    setResult(null)
    setComparison(null)
    try {
      const data = await api.analyzeStream(payload, (event) => {
        if (analysisRunRef.current !== runId) return
        if (event.status === 'started') {
          setSingleProgress({
            phase: 'running',
            stage: 'started',
            percent: 0,
            message: 'Запуск анализа…',
            methodologyName: event.name,
            methodologyKey: event.methodology,
          })
        } else if (event.status === 'stage') {
          setSingleProgress(prev => ({
            ...prev,
            phase: 'running',
            stage: event.stage,
            percent: event.percent,
            message: event.message,
          }))
        }
      }, { signal: controller.signal })
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
        setSingleProgress(null)
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

  function openResult(r) {
    setViewMode({ type: 'single', result: r })
    setPage('view')
  }

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
    setSingleProgress(null)
    setFormDraft(null)
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

  const analysisStep = comparison || result ? 3 : loading ? 2 : 1

  const navActive = (id) =>
    id === 'analyze'
      ? page === 'analyze'
      : id === 'history'
        ? page === 'history' || page === 'view'
        : page === 'admin'

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="rounded-xl bg-slate-900/60 ring-1 ring-slate-800 px-6 py-4 text-sm text-slate-300">
          Проверка сессии…
        </div>
      </div>
    )
  }

  if (!user) {
    return <AuthPage />
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-slate-800/60 bg-slate-950/40 backdrop-blur-md">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16 gap-4">
            <div className="flex items-center gap-3 min-w-0">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 via-violet-500 to-purple-600 text-xl shadow-lg shadow-indigo-900/40">
                🔬
              </div>
              <div className="min-w-0">
                <div className="font-bold text-white tracking-tight truncate">
                  RCA Analyzer
                </div>
                <div className="text-[11px] text-slate-400 -mt-0.5 truncate">
                  Анализ корневых причин промышленных инцидентов
                </div>
              </div>
            </div>

            <nav className="flex items-center gap-1 rounded-xl bg-slate-900/60 ring-1 ring-slate-800 p-1">
              {[
                { id: 'analyze', label: 'Анализ', icon: '🚀' },
                { id: 'history', label: 'История', icon: '📚' },
              ].map((t) => (
                <button
                  key={t.id}
                  onClick={() => (t.id === 'analyze' ? goToAnalyze() : goToHistory())}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center gap-1.5 ${
                    navActive(t.id)
                      ? 'bg-indigo-500 text-white shadow'
                      : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
                  }`}
                >
                  <span>{t.icon}</span>
                  <span className="hidden sm:inline">{t.label}</span>
                </button>
              ))}
              {isAdmin && (
                <button
                  onClick={goToAdmin}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center gap-1.5 ${
                    navActive('admin')
                      ? 'bg-indigo-500 text-white shadow'
                      : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
                  }`}
                >
                  <span>👥</span>
                  <span className="hidden sm:inline">Пользователи</span>
                </button>
              )}
            </nav>

            <div className="flex items-center gap-3 shrink-0">
              <span className="hidden sm:inline text-sm text-slate-400 max-w-[160px] truncate">
                {user.display_name}
              </span>
              <span
                className={`text-xs font-semibold px-2 py-0.5 rounded-full uppercase tracking-wider ${
                  isAdmin
                    ? 'bg-amber-500/15 text-amber-400'
                    : 'bg-indigo-500/15 text-indigo-400'
                }`}
              >
                {isAdmin ? 'Admin' : 'User'}
              </span>
              <Button variant="secondary" size="sm" onClick={logout}>
                Выйти
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="flex-1">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-6 lg:py-10">
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
                  {loading && !multiProgressPayload && (
                    <>
                      <SingleAnalysisProgress progress={singleProgress} />
                      <div className="flex items-center justify-between gap-4 rounded-xl bg-slate-900/60 ring-1 ring-slate-800 p-4 shadow-sm mt-4">
                        <div>
                          <div className="text-sm font-bold text-white">Анализ выполняется</div>
                          <p className="text-xs text-slate-400 mt-0.5">
                            Можно отменить текущий запрос и вернуться к редактированию формы.
                          </p>
                        </div>
                        <Button variant="secondary" onClick={() => cancelCurrentAnalysis()}>
                          ⏹ Отменить анализ
                        </Button>
                      </div>
                    </>
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
                <div className="flex items-center justify-between gap-4 mb-6 rounded-xl ring-1 ring-indigo-500/30 p-4 bg-gradient-to-r from-indigo-500/10 via-slate-900/60 to-slate-900/60 shadow-md">
                  <h2 className="text-xl font-semibold text-white leading-tight flex flex-col gap-0.5">
                    <span className="text-xs font-bold uppercase tracking-wider text-indigo-400">
                      Результат анализа
                    </span>
                    {comparison ? 'Сравнение методик готово' : 'Анализ готов'}
                  </h2>
                  <Button variant="primary" onClick={startNewAnalysis}>
                    ➕ Новый анализ
                  </Button>
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
            <>
              <div className="flex flex-wrap gap-2 mb-4">
                <Button variant="secondary" size="sm" onClick={goToHistory}>
                  ← Назад в историю
                </Button>
                <Button variant="primary" size="sm" onClick={startNewAnalysis}>
                  ➕ Новый анализ
                </Button>
              </div>
              {viewMode.type === 'single' && (
                <ResultView result={viewMode.result} onOpenResult={openResult} />
              )}
              {viewMode.type === 'compare' && (
                <CompareView comparison={viewMode.comparison} />
              )}
            </>
          )}

          {page === 'admin' && isAdmin && <AdminPage currentUser={user} />}
        </div>
      </main>
    </div>
  )
}
