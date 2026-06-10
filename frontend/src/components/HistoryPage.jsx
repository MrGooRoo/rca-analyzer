import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { api } from '../api.js'
import './HistoryPage.css'

const METHODOLOGY_LABELS = {
  ishikawa:     'Ishikawa',
  five_why:     '5 Почему',
  fta:          'FTA',
  rca_systemic: 'RCA',
  bowtie:       'Bowtie',
}

const SEVERITY_COLORS = {
  critical:  { bg: 'rgba(247,111,111,0.12)', color: '#f76f6f', label: 'Критический' },
  major:     { bg: 'rgba(247,185,85,0.12)',  color: '#f7b955', label: 'Тяжёлый' },
  moderate:  { bg: 'rgba(247,224,85,0.12)',  color: '#f7e055', label: 'Средний' },
  minor:     { bg: 'rgba(62,207,142,0.12)',  color: '#3ecf8e', label: 'Лёгкий' },
  near_miss: { bg: 'rgba(79,142,247,0.12)',  color: '#4f8ef7', label: 'Предпосылка' },
}

const PAGE_SIZE = 20

/**
 * Помечает каждую запись: isCompare=true если её incident_id
 * встречается у других записей в том же наборе.
 */
function markCompareItems(items) {
  const incidentCounts = {}
  for (const r of items) {
    const key = r.incident_id
    if (key) incidentCounts[key] = (incidentCounts[key] || 0) + 1
  }
  return items.map(r => ({
    ...r,
    isCompare: r.incident_id ? (incidentCounts[r.incident_id] > 1) : false,
  }))
}

export default function HistoryPage({ onOpen, onOpenComparison, currentUser }) {
  const isAdmin = currentUser?.role === 'admin'
  const [items, setItems]       = useState([])
  const [offset, setOffset]     = useState(0)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState(null)

  // Фильтры
  const [search, setSearch]         = useState('')
  const [filterMethod, setFilterMethod] = useState('') // methodology key | ''
  const [filterSeverity, setFilterSeverity] = useState('') // severity key | ''
  const [filterType, setFilterType] = useState('') // '' | 'single' | 'compare'

  const load = useCallback(async (off) => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.results.list(PAGE_SIZE, off)
      setItems(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load(0) }, [load])

  function prev() { const o = Math.max(0, offset - PAGE_SIZE); setOffset(o); load(o) }
  function next() { const o = offset + PAGE_SIZE; setOffset(o); load(o) }

  function resetFilters() {
    setSearch('')
    setFilterMethod('')
    setFilterSeverity('')
    setFilterType('')
  }

  const marked = useMemo(() => markCompareItems(items), [items])

  const filtered = useMemo(() => {
    let result = marked

    if (search.trim()) {
      const q = search.toLowerCase()
      result = result.filter(r =>
        r.summary?.toLowerCase().includes(q) ||
        r.result_id?.includes(q) ||
        r.incident?.title?.toLowerCase().includes(q)
      )
    }

    if (filterMethod) {
      result = result.filter(r => r.methodology === filterMethod)
    }

    if (filterSeverity) {
      result = result.filter(r => r.incident?.severity === filterSeverity)
    }

    if (filterType === 'single') {
      result = result.filter(r => !r.isCompare)
    } else if (filterType === 'compare') {
      result = result.filter(r => r.isCompare)
    }

    return result
  }, [marked, search, filterMethod, filterSeverity, filterType])

  const hasFilters = search || filterMethod || filterSeverity || filterType

  async function handleOpenCompareItem(result) {
    // Если это часть сравнения — загружаем полное сравнение по incident_id
    try {
      const comp = await api.compareResults(result.incident_id)
      onOpenComparison(comp)
    } catch {
      onOpen(result) // fallback: открыть как одиночный
    }
  }

  return (
    <div className="history">
      {/* ===== Толбар ===== */}
      <div className="history-toolbar">
        <h2 className="history-title">История анализов</h2>
        <button className="btn-refresh" onClick={() => load(offset)} disabled={loading}>
          {loading ? '…' : '↻'}
        </button>
      </div>

      {/* ===== Фильтры ===== */}
      <div className="history-filters">
        <input
          className="history-search"
          type="text"
          placeholder="🔍 Поиск по содержанию…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />

        <select
          className="history-filter-select"
          value={filterMethod}
          onChange={e => setFilterMethod(e.target.value)}
        >
          <option value="">Все методики</option>
          {Object.entries(METHODOLOGY_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>

        <select
          className="history-filter-select"
          value={filterSeverity}
          onChange={e => setFilterSeverity(e.target.value)}
        >
          <option value="">Все уровни</option>
          {Object.entries(SEVERITY_COLORS).map(([k, v]) => (
            <option key={k} value={k}>{v.label}</option>
          ))}
        </select>

        <select
          className="history-filter-select"
          value={filterType}
          onChange={e => setFilterType(e.target.value)}
        >
          <option value="">Все типы</option>
          <option value="single">Одиночные</option>
          <option value="compare">Сравнения</option>
        </select>

        {hasFilters && (
          <button className="btn-reset-filters" onClick={resetFilters}>
            ✕ Сбросить
          </button>
        )}
      </div>

      {/* ===== Ошибка ===== */}
      {error && (
        <div className="history-error">Ошибка загрузки: {error}</div>
      )}

      {/* ===== Пусто ===== */}
      {!loading && !error && filtered.length === 0 && (
        <div className="history-empty">
          <div className="history-empty-icon">📂</div>
          <p>{hasFilters ? 'Ничего не найдено. Попробуйте сбросить фильтры.' : 'История пуста. Запустите первый анализ.'}</p>
        </div>
      )}

      {/* ===== Плоский список ===== */}
      <div className="history-list">
        {filtered.map(result => (
          <HistoryCard
            key={result.result_id}
            result={result}
            onOpen={result.isCompare ? handleOpenCompareItem : onOpen}
            isAdmin={isAdmin}
            currentUserId={currentUser?.user_id}
          />
        ))}
      </div>

      {/* ===== Пагинация ===== */}
      {items.length === PAGE_SIZE && (
        <div className="history-pagination">
          <button className="btn-page" onClick={prev} disabled={offset === 0}>← Назад</button>
          <span className="page-info">Стр. {Math.floor(offset / PAGE_SIZE) + 1}</span>
          <button className="btn-page" onClick={next}>Вперёд →</button>
        </div>
      )}
    </div>
  )
}

function HistoryCard({ result, onOpen, isAdmin, currentUserId }) {
  const sev  = SEVERITY_COLORS[result.incident?.severity] || null
  const date = new Date(result.created_at).toLocaleString('ru-RU', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
  const isMine     = result.user_id === currentUserId
  const authorName = result.user_display_name || result.user_email || null

  return (
    <div
      className={`hcard ${result.isCompare ? 'hcard--compare' : ''}`}
      onClick={() => onOpen(result)}
    >
      <div className="hcard-left">
        <div className="hcard-top">

          {/* Методика */}
          <span className={`hcard-method ${result.isCompare ? 'hcard-method--compare' : ''}`}>
            {METHODOLOGY_LABELS[result.methodology] || result.methodology}
          </span>

          {/* Бейдж сравнения */}
          {result.isCompare && (
            <span className="hcard-compare-badge">⚖️ Сравнение</span>
          )}

          {/* Автор (admin) */}
          {isAdmin && authorName && (
            <span className={`hcard-author ${isMine ? 'hcard-author--self' : ''}`}>
              👤 {authorName}{isMine ? ' (вы)' : ''}
            </span>
          )}

          {/* Тяжесть */}
          {sev && (
            <span className="hcard-severity" style={{ background: sev.bg, color: sev.color }}>
              {sev.label}
            </span>
          )}

          <span className="hcard-date">{date}</span>
        </div>

        <p className="hcard-summary">{result.summary}</p>

        <div className="hcard-footer">
          <span className="hcard-id">#{result.result_id.slice(0, 8)}</span>
          <span className="hcard-stat">{result.recommendations?.length || 0} рек.</span>
          <span className="hcard-stat">{result.tokens_used} ток.</span>
          <span className="hcard-stat">{((result.confidence_avg || 0) * 100).toFixed(0)}% ув.</span>
        </div>
      </div>
      <div className="hcard-arrow">›</div>
    </div>
  )
}
