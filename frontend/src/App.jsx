import React, { useState } from 'react'
import { api, setAuth, clearAuth, getUser, isAuthed } from './api.js'
import AuthPage from './components/AuthPage.jsx'
import IncidentForm from './components/IncidentForm.jsx'
import ResultView from './components/ResultView.jsx'
import HistoryPage from './components/HistoryPage.jsx'
import './App.css'

export default function App() {
  const [authed, setAuthed]   = useState(false)
  const [page, setPage]       = useState('analyze')
  const [result, setResult]   = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)

  if (!authed) {
    return <AuthPage onAuth={() => setAuthed(true)} />
  }

  const user = getUser()

  async function handleSubmit(payload) {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await api.analyze(payload)
      setResult(data)
      setPage('analyze')
    } catch (e) {
      if (e.message.includes('401') || e.message.toLowerCase().includes('authenticated')) {
        clearAuth()
        setAuthed(false)
        return
      }
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  function openResult(r) {
    setResult(r)
    setPage('analyze')
  }

  function logout() {
    clearAuth()
    setAuthed(false)
    setResult(null)
    setPage('analyze')
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
        </nav>
        <div className="header-right">
          <span className="header-user">{user?.display_name}</span>
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
        {page === 'history' && <HistoryPage onOpen={openResult} />}
      </main>
    </div>
  )
}
