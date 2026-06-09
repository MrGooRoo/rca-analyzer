import React, { useState, useEffect, useCallback } from 'react'
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
 * Группирует результаты по incident_id.
 * Если у инцидента > 1 результата — это «Сравнение моделей».
 * Возвращает массив элементов вида:
 *   { type: 'single', result }  — одиночный анализ
 *   { type: 'compare', incidentId, results, incident, created_at } — группа сравнения
 */
function groupByIncident(items) {
  const map = new Map()
  for (const r of items) {
    const key = r.incident_id || r.result_id
    if (!map.has(key)) map.set(key, [])
    map.get(key).push(r)
  }

  const groups = []
  for (const [incidentId, results] of map) {
    if (results.length === 1) {
      groups.push({ type: 'single', result: results[0] })
    } else {
      // Сортируем по дате создания внутри группы
      results.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
      groups.push({
        type: 'compare',
        incidentId,
        results,
        incident: results[0].incident,
        created_at: results[0].created_at,
        summary: results[0].summary,
        user_id: results[0].user_id,
        user_display_name: results[0].user_display_name,
        user_email: results[0].user_email,
      })
    }
  }

  // Сортируем группы по дате последнего результата (новые вверху)
  groups.sort((a, b) => {
    const dateA = a.type === 'single' ? a.result.created_at : a.created_at
    const dateB = b.type === 'single' ? b.result.created_at : b.created_at
    return new Date(dateB) - new Date(dateA)
  })

  return groups
}

export default function HistoryPage({ onOpen, onOpenComparison, currentUser }) {
  const isAdmin = currentUser?.role === 'admin'
  const [items, setItems]     = useState([])
  const [offset, setOffset]   = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)
  const [search, setSearch]   = useState('')

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

  const filtered = search.trim()
    ? items.filter(r =>
        r.summary?.toLowerCase().includes(search.toLowerCase()) ||
        r.methodology?.includes(search.toLowerCase()) ||
        r.result_id?.includes(search)
      )
    : items

  const groups = groupByIncident(filtered)

  async function handleOpenComparison(group) {
    // Строим объект сравнения из группы: загружаем свежие данные с /compare
    try {
      const comp = await api.compareResults(group.incidentId)
      onOpenComparison(comp)
    } catch {
      // Если сравнение недоступно — fallback: показываем сырые результаты
      onOpenComparison({
        incident_id: group.incidentId,
        results: group.results,
        common_recommendations: [],
        differing_causes: {},
        summary: group.summary || '',
      })
    }
  }

  return (
    <div className="history">
      <div className="history-toolbar">
        <h2 className="history-title">История анализов</h2>
        <div className="history-search-wrap">
          <input
            className="history-search"
            type="text"
            placeholder="Поиск по содержанию…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <button className="btn-refresh" onClick={() => load(offset)} disabled={loading}>
          {loading ? '…' : '↻ Обновить'}
        </button>
      </div>

      {error && (
        <div className="history-error">Ошибка загрузки: {error}</div>
      )}

      {!loading && !error && groups.length === 0 && (
        <div className="history-empty">
          <div className="history-empty-icon">📂</div>
          <p>{search ? 'Ничего не найдено по запросу' : 'История пуста. Запустите первый анализ.'}</p>
        </div>
      )}

      <div className="history-list">
        {groups.map(group =>
          group.type === 'single'
            ? (
                <HistoryCard
                  key={group.result.result_id}
                  result={group.result}
                  onOpen={onOpen}
                  isAdmin={isAdmin}
                  currentUserId={currentUser?.user_id}
                />
              )
            : (
                <CompareCard
                  key={group.incidentId}
                  group={group}
                  onOpen={() => handleOpenComparison(group)}
                  isAdmin={isAdmin}
                  currentUserId={currentUser?.user_id}
                />
              )
        )}
      </div>

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
  const sev = SEVERITY_COLORS[result.incident?.severity] || SEVERITY_COLORS.moderate
  const date = new Date(result.created_at).toLocaleString('ru-RU', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })

  const isMine = result.user_id === currentUserId
  const authorName = result.user_display_name || result.user_email || null

  return (
    <div className="hcard" onClick={() => onOpen(result)}>
      <div className="hcard-left">
        <div className="hcard-top">
          <span className="hcard-method">{METHODOLOGY_LABELS[result.methodology] || result.methodology}</span>
          {isAdmin && authorName && (
            <span className={`hcard-author ${isMine ? 'hcard-author--self' : ''}`}>
              👤 {authorName}{isMine ? ' (вы)' : ''}
            </span>
          )}
          {result.incident?.severity && (
            <span
              className="hcard-severity"
              style={{ background: sev.bg, color: sev.color }}
            >{sev.label}</span>
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

function CompareCard({ group, onOpen, isAdmin, currentUserId }) {
  const sev = SEVERITY_COLORS[group.incident?.severity] || SEVERITY_COLORS.moderate
  const date = new Date(group.created_at).toLocaleString('ru-RU', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })

  const isMine = group.user_id === currentUserId
  const authorName = group.user_display_name || group.user_email || null
  const methodLabels = group.results
    .map(r => METHODOLOGY_LABELS[r.methodology] || r.methodology)
    .join(' · ')

  const totalRecs = group.results.reduce((acc, r) => acc + (r.recommendations?.length || 0), 0)
  const totalTokens = group.results.reduce((acc, r) => acc + (r.tokens_used || 0), 0)

  return (
    <div className="hcard hcard--compare" onClick={onOpen}>
      <div className="hcard-left">
        <div className="hcard-top">
          <span className="hcard-method hcard-method--compare">🔬 Сравнение моделей</span>
          <span className="hcard-compare-methods">{methodLabels}</span>
          {isAdmin && authorName && (
            <span className={`hcard-author ${isMine ? 'hcard-author--self' : ''}`}>
              👤 {authorName}{isMine ? ' (вы)' : ''}
            </span>
          )}
          {group.incident?.severity && (
            <span
              className="hcard-severity"
              style={{ background: sev.bg, color: sev.color }}
            >{sev.label}</span>
          )}
          <span className="hcard-date">{date}</span>
        </div>
        <p className="hcard-summary">{group.summary}</p>
        <div className="hcard-footer">
          <span className="hcard-id">#{group.incidentId.slice(0, 8)}</span>
          <span className="hcard-stat">{group.results.length} методики</span>
          <span className="hcard-stat">{totalRecs} рек.</span>
          <span className="hcard-stat">{totalTokens} ток.</span>
        </div>
      </div>
      <div className="hcard-arrow">›</div>
    </div>
  )
}
