import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../api.js'
import { methodologyMeta, METHODOLOGY_LABELS } from '../lib/methodologies.js'
import { Badge, Card } from './ui/Card.jsx'
import { Button } from './ui/Button.jsx'
import { Input, Select } from './ui/Field.jsx'

function normalizeQuery(text) {
  return String(text || '').replace(/\s+/g, ' ').trim().slice(0, 5000)
}

export default function SimilarIncidentsPanel({
  queryText,
  excludeResultId = null,
  excludeIncidentId = null,
  incidentTitle = null,
  incidentDescription = null,
  disabled = false,
  auto = false,
  title = 'Похожие инциденты',
  compact = false,
  onOpenResult = null,
}) {
  const query = useMemo(() => normalizeQuery(queryText), [queryText])
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [searched, setSearched] = useState(false)
  const [filterMethod, setFilterMethod] = useState('')
  const [filterDateFrom, setFilterDateFrom] = useState('')
  const [filterDateTo, setFilterDateTo] = useState('')

  const canSearch = query.length >= 20

  const load = useCallback(async () => {
    if (!canSearch) return
    setLoading(true); setError(null); setSearched(true)
    try {
      const data = await api.similarIncidents(query, {
        limit: 10, excludeResultId, excludeIncidentId, incidentTitle, incidentDescription,
      })
      setItems(data || [])
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }, [canSearch, query, excludeResultId, excludeIncidentId, incidentTitle, incidentDescription])

  useEffect(() => { if (auto && canSearch && !disabled) load() }, [auto, canSearch, disabled, load])

  const filtered = useMemo(() => {
    let result = items
    if (filterMethod) result = result.filter(i => i.methodology === filterMethod)
    if (filterDateFrom) result = result.filter(i => new Date(i.created_at) >= new Date(filterDateFrom))
    if (filterDateTo) { const to = new Date(filterDateTo); to.setHours(23,59,59); result = result.filter(i => new Date(i.created_at) <= to) }
    return result
  }, [items, filterMethod, filterDateFrom, filterDateTo])

  const availableMethods = useMemo(() => [...new Set(items.map(i => i.methodology))], [items])
  const hasFilters = filterMethod || filterDateFrom || filterDateTo

  function resetFilters() { setFilterMethod(''); setFilterDateFrom(''); setFilterDateTo('') }

  async function handleOpenResult(item) {
    if (!onOpenResult) return
    try { const fullResult = await api.results.get(item.result_id); onOpenResult(fullResult) }
    catch { onOpenResult(item) }
  }

  if (!auto && !canSearch) {
    return (
      <section className={`${compact ? 'mt-4' : 'my-6'} p-6 rounded-2xl ring-1 ring-indigo-500/20 bg-gradient-to-br from-indigo-500/5 to-emerald-500/5`}>
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h3 className="text-lg font-semibold text-white mb-1">{title}</h3>
            <p className="text-sm text-slate-400 leading-relaxed">Заполните описание — затем можно найти похожие случаи в истории.</p>
          </div>
          <Button type="button" variant="outline" disabled>Найти</Button>
        </div>
      </section>
    )
  }

  return (
    <section className={`${compact ? 'mt-4' : 'my-6'} p-6 rounded-2xl ring-1 ring-indigo-500/20 bg-gradient-to-br from-indigo-500/5 to-emerald-500/5`}>
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h3 className="text-lg font-semibold text-white mb-1">{title}</h3>
          <p className="text-sm text-slate-400 leading-relaxed">Поиск идёт по summary, причинам и рекомендациям ранее сохранённых RCA-результатов.</p>
        </div>
        {!auto && (
          <Button type="button" variant="outline" onClick={load} disabled={!canSearch || disabled} loading={loading}>
            Найти похожие
          </Button>
        )}
      </div>

      {searched && items.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <Select className="min-w-[140px] flex-1" value={filterMethod} onChange={e => setFilterMethod(e.target.value)}>
            <option value="">Все методики</option>
            {availableMethods.map(m => <option key={m} value={m}>{METHODOLOGY_LABELS[m] || m}</option>)}
          </Select>
          <Input type="date" className="min-w-[120px] flex-1" value={filterDateFrom} onChange={e => setFilterDateFrom(e.target.value)} aria-label="Дата от" />
          <span className="text-sm text-slate-500">—</span>
          <Input type="date" className="min-w-[120px] flex-1" value={filterDateTo} onChange={e => setFilterDateTo(e.target.value)} aria-label="Дата до" />
          {hasFilters && <Button type="button" variant="danger" size="sm" onClick={resetFilters}>✕ Сбросить</Button>}
        </div>
      )}

      {loading && <div className="mt-4 rounded-lg p-4 text-sm text-slate-400 bg-slate-800/60">Поиск похожих инцидентов…</div>}
      {error && <div className="mt-4 rounded-lg p-4 text-sm text-rose-300 bg-rose-500/10 ring-1 ring-rose-500/30">Ошибка поиска: {error}</div>}

      {!loading && !error && searched && filtered.length === 0 && (
        <div className="mt-4 rounded-lg p-4 text-sm text-slate-400 bg-slate-800/60">{hasFilters ? 'Ничего не найдено с текущими фильтрами.' : 'Похожих инцидентов пока не найдено.'}</div>
      )}

      {!loading && !error && filtered.length > 0 && (
        <div className="mt-4 flex flex-col gap-4">
          {filtered.map(item => (
            <SimilarCard key={item.result_id} item={item} onOpen={onOpenResult ? () => handleOpenResult(item) : null} />
          ))}
        </div>
      )}
    </section>
  )
}

function SimilarCard({ item, onOpen = null }) {
  const date = new Date(item.created_at).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' })
  const percent = Math.round((item.similarity || 0) * 100)
  const author = item.user_display_name || item.user_email || null
  const meta = methodologyMeta(item.methodology)
  const incidentDateStr = item.incident_date ? new Date(item.incident_date).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' }) : null
  const scoreTone = percent >= 75 ? 'emerald' : percent >= 50 ? 'amber' : 'rose'
  const hasIncidentContext = item.incident_title || item.incident_description

  return (
    <Card className={`p-5 transition ${onOpen ? 'cursor-pointer hover:ring-indigo-400 hover:shadow-md hover:-translate-y-0.5' : ''}`} onClick={onOpen}>
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <Badge tone={scoreTone}>{percent}% похоже</Badge>
        <Badge tone={meta.badgeTone}>{meta.icon} {METHODOLOGY_LABELS[item.methodology] || item.methodology}</Badge>
        <Badge tone="slate">{date}</Badge>
        {author && <Badge tone="slate">👤 {author}</Badge>}
        {onOpen && <Button type="button" variant="ghost" size="sm" className="ml-auto">Открыть →</Button>}
      </div>

      {hasIncidentContext && (
        <div className="mb-4 p-4 rounded-lg bg-indigo-500/5 border-l-2 border-indigo-400">
          {item.incident_title && <div className="font-bold text-base text-white mb-1">{item.incident_title}</div>}
          {item.incident_description && <p className="text-sm text-slate-400 leading-relaxed">{item.incident_description}</p>}
          {(incidentDateStr || item.incident_location) && (
            <div className="mt-1 flex gap-4 text-xs text-slate-500">
              {incidentDateStr && <span>📅 {incidentDateStr}</span>}
              {item.incident_location && <span>📍 {item.incident_location}</span>}
            </div>
          )}
        </div>
      )}

      <p className="text-base text-slate-200 leading-relaxed">{item.summary}</p>
      {item.root_causes_preview?.length > 0 && (
        <div className="mt-4 text-sm text-slate-400">
          <strong className="text-white">Корневые причины:</strong>
          <ul className="mt-2 pl-6 list-disc">
            {item.root_causes_preview.map((text, idx) => <li key={idx} className="my-1">{text}</li>)}
          </ul>
        </div>
      )}
      {item.recommendations_preview?.length > 0 && (
        <div className="mt-4 text-sm text-slate-400">
          <strong className="text-white">Рекомендации:</strong>
          <ul className="mt-2 pl-6 list-disc">
            {item.recommendations_preview.map((text, idx) => <li key={idx} className="my-1">{text}</li>)}
          </ul>
        </div>
      )}
      <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-500 font-mono">
        <span>result #{item.result_id.slice(0, 8)}</span>
        <span>incident #{item.incident_id.slice(0, 8)}</span>
      </div>
    </Card>
  )
}
