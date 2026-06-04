import React, { useState, useEffect, useCallback } from 'react'
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

const PAGE_SIZE = 10

export default function HistoryPage({ onOpen }) {
  const [items, setItems]   = useState([])
  const [total, setTotal]   = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError]   = useState(null)
  const [search, setSearch] = useState('')

  const load = useCallback(async (off) => {
    setLoading(true)
    setError(null)
    try {
      const url = `/api/v1/results?limit=${PAGE_SIZE}&offset=${off}`
      const res = await fetch(url)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setItems(data)
      // API возвращает массив; если меньше PAGE_SIZE — это последняя страница
      if (off === 0) setTotal(data.length < PAGE_SIZE ? data.length : 999)
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

      {!loading && !error && filtered.length === 0 && (
        <div className="history-empty">
          <div className="history-empty-icon">📂</div>
          <p>{search ? 'Ничего не найдено по запросу' : 'История пуста. Запустите первый анализ.'}</p>
        </div>
      )}

      <div className="history-list">
        {filtered.map(r => (
          <HistoryCard key={r.result_id} result={r} onOpen={onOpen} />
        ))}
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

function HistoryCard({ result, onOpen }) {
  const sev = SEVERITY_COLORS[result.incident?.severity] || SEVERITY_COLORS.moderate
  const date = new Date(result.created_at).toLocaleString('ru-RU', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })

  return (
    <div className="hcard" onClick={() => onOpen(result)}>
      <div className="hcard-left">
        <div className="hcard-top">
          <span className="hcard-method">{METHODOLOGY_LABELS[result.methodology] || result.methodology}</span>
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
