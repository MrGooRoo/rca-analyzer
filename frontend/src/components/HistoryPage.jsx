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
 * Группирует записи по incident_id.
 *
 * Результаты multi-анализа (сравнения методик) — это ОДНО исследование:
 * у них общий incident_id и одинаковые входные данные, отличается только
 * методика. Поэтому в истории они отображаются одной карточкой-группой.
 *
 * Возвращает массив элементов:
 *   { isCompare: false, result }                — одиночный анализ
 *   { isCompare: true, incidentId, results[] }  — сравнение (>= 2 результатов)
 * Порядок — по дате самого нового результата в группе.
 */
function groupByIncident(items) {
  const byIncident = new Map()
  for (const r of items) {
    const key = r.incident_id || r.result_id
    if (!byIncident.has(key)) byIncident.set(key, [])
    byIncident.get(key).push(r)
  }

  const groups = []
  for (const [incidentId, results] of byIncident) {
    if (results.length > 1) {
      // Сортируем результаты внутри группы по дате (стабильный порядок методик)
      results.sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
      groups.push({ isCompare: true, incidentId, results })
    } else {
      groups.push({ isCompare: false, result: results[0] })
    }
  }

  groups.sort((a, b) => {
    const lastA = a.isCompare ? a.results[a.results.length - 1] : a.result
    const lastB = b.isCompare ? b.results[b.results.length - 1] : b.result
    return new Date(lastB.created_at) - new Date(lastA.created_at)
  })
  return groups
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

  const groups = useMemo(() => groupByIncident(items), [items])

  const filtered = useMemo(() => {
    let result = groups

    // Хелпер: все результаты группы (1 для одиночного, N для сравнения)
    const resultsOf = g => (g.isCompare ? g.results : [g.result])

    if (search.trim()) {
      const q = search.toLowerCase()
      result = result.filter(g => resultsOf(g).some(r =>
        r.summary?.toLowerCase().includes(q) ||
        r.result_id?.includes(q) ||
        r.incident?.title?.toLowerCase().includes(q)
      ))
    }

    if (filterMethod) {
      // Группа подходит, если ХОТЯ БЫ одна из методик совпадает
      result = result.filter(g => resultsOf(g).some(r => r.methodology === filterMethod))
    }

    if (filterSeverity) {
      result = result.filter(g => resultsOf(g).some(r => r.incident?.severity === filterSeverity))
    }

    if (filterType === 'single') {
      result = result.filter(g => !g.isCompare)
    } else if (filterType === 'compare') {
      result = result.filter(g => g.isCompare)
    }

    return result
  }, [groups, search, filterMethod, filterSeverity, filterType])

  const hasFilters = search || filterMethod || filterSeverity || filterType

  async function handleOpenCompareGroup(group) {
    // Открыть сравнение целиком по incident_id
    try {
      const comp = await api.compareResults(group.incidentId)
      onOpenComparison(comp)
    } catch {
      onOpen(group.results[group.results.length - 1]) // fallback: самый свежий результат
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

      {/* ===== Список: одиночные карточки + группы сравнений ===== */}
      <div className="history-list">
        {filtered.map(group => group.isCompare ? (
          <CompareGroupCard
            key={group.incidentId}
            group={group}
            onOpenComparison={() => handleOpenCompareGroup(group)}
            onOpenResult={onOpen}
            isAdmin={isAdmin}
            currentUserId={currentUser?.user_id}
          />
        ) : (
          <HistoryCard
            key={group.result.result_id}
            result={group.result}
            onOpen={onOpen}
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
    <div className="hcard" onClick={() => onOpen(result)}>
      <div className="hcard-left">
        <div className="hcard-top">

          {/* Методика */}
          <span className="hcard-method">
            {METHODOLOGY_LABELS[result.methodology] || result.methodology}
          </span>

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

/**
 * Карточка-группа: ОДНО исследование, проанализированное несколькими методиками.
 * Клик по карточке открывает сравнение целиком; чипы методик
 * позволяют открыть конкретный результат отдельно.
 */
function CompareGroupCard({ group, onOpenComparison, onOpenResult, isAdmin, currentUserId }) {
  const { results } = group
  const newest = results[results.length - 1]
  const sev  = SEVERITY_COLORS[newest.incident?.severity] || null
  const date = new Date(newest.created_at).toLocaleString('ru-RU', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
  const isMine     = newest.user_id === currentUserId
  const authorName = newest.user_display_name || newest.user_email || null

  // Суммарные показатели по группе
  const totalRecs   = results.reduce((s, r) => s + (r.recommendations?.length || 0), 0)
  const totalTokens = results.reduce((s, r) => s + (r.tokens_used || 0), 0)
  const avgConf     = results.reduce((s, r) => s + (r.confidence_avg || 0), 0) / results.length

  function openSingle(e, r) {
    e.stopPropagation() // не открывать сравнение при клике по чипу
    onOpenResult(r)
  }

  return (
    <div className="hcard hcard--compare" onClick={onOpenComparison}>
      <div className="hcard-left">
        <div className="hcard-top">
          <span className="hcard-compare-badge">
            ⚖️ Сравнение · {results.length} методик{results.length >= 5 ? '' : 'и'}
          </span>

          {isAdmin && authorName && (
            <span className={`hcard-author ${isMine ? 'hcard-author--self' : ''}`}>
              👤 {authorName}{isMine ? ' (вы)' : ''}
            </span>
          )}

          {sev && (
            <span className="hcard-severity" style={{ background: sev.bg, color: sev.color }}>
              {sev.label}
            </span>
          )}

          <span className="hcard-date">{date}</span>
        </div>

        <p className="hcard-summary">{newest.summary}</p>

        {/* Чипы методик: клик открывает конкретный результат */}
        <div className="hcard-method-chips">
          {results.map(r => (
            <button
              key={r.result_id}
              className="hcard-method-chip"
              title={`Открыть результат ${METHODOLOGY_LABELS[r.methodology] || r.methodology}`}
              onClick={e => openSingle(e, r)}
            >
              {METHODOLOGY_LABELS[r.methodology] || r.methodology}
            </button>
          ))}
        </div>

        <div className="hcard-footer">
          <span className="hcard-id">#{group.incidentId.slice(0, 8)}</span>
          <span className="hcard-stat">{totalRecs} рек.</span>
          <span className="hcard-stat">{totalTokens} ток.</span>
          <span className="hcard-stat">{(avgConf * 100).toFixed(0)}% ув.</span>
        </div>
      </div>
      <div className="hcard-arrow">›</div>
    </div>
  )
}
