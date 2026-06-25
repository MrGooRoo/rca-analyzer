import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../api.js'
import { methodologyMeta, METHODOLOGY_LABELS } from '../lib/methodologies.js'
import { Badge, Card } from './ui/Card.jsx'
import { Button } from './ui/Button.jsx'
import { Input, Select } from './ui/Field.jsx'
import { User, Calendar, MapPin, Link as LinkIcon, HelpCircle, Ribbon, Fish, TreePine, Cog } from 'lucide-react'
import './SimilarIncidentsPanel.css'

const METHODOLOGY_ICONS_SIP = {
  '❓': HelpCircle,
  '🎀': Ribbon,
  '🐟': Fish,
  '🌳': TreePine,
  '⚙️': Cog,
}

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
      <section className={`similar-panel ${compact ? 'similar-panel--compact' : 'similar-panel--spaced'}`}>
        <div className="similar-panel__header">
          <div>
            <h3 className="similar-panel__title">{title}</h3>
            <p className="similar-panel__description">Заполните описание — затем можно найти похожие случаи в истории.</p>
          </div>
          <Button type="button" variant="outline" disabled>Найти</Button>
        </div>
      </section>
    )
  }

  return (
    <section className={`similar-panel ${compact ? 'similar-panel--compact' : 'similar-panel--spaced'}`}>
      <div className="similar-panel__header">
        <div>
          <h3 className="similar-panel__title">{title}</h3>
          <p className="similar-panel__description">Поиск идёт по summary, причинам и рекомендациям ранее сохранённых RCA-результатов.</p>
        </div>
        {!auto && (
          <Button type="button" variant="outline" onClick={load} disabled={!canSearch || disabled} loading={loading}>
            Найти похожие
          </Button>
        )}
      </div>

      {searched && items.length > 0 && (
        <div className="similar-panel__filters">
          <Select className="similar-filter similar-filter--method" value={filterMethod} onChange={e => setFilterMethod(e.target.value)}>
            <option value="">Все методики</option>
            {availableMethods.map(m => <option key={m} value={m}>{METHODOLOGY_LABELS[m] || m}</option>)}
          </Select>
          <Input type="date" className="similar-filter similar-filter--date" value={filterDateFrom} onChange={e => setFilterDateFrom(e.target.value)} aria-label="Дата от" />
          <span className="similar-filter__dash">—</span>
          <Input type="date" className="similar-filter similar-filter--date" value={filterDateTo} onChange={e => setFilterDateTo(e.target.value)} aria-label="Дата до" />
          {hasFilters && <Button type="button" variant="danger" size="sm" onClick={resetFilters}>✕ Сбросить</Button>}
        </div>
      )}

      {loading && <div className="similar-panel__status">Поиск похожих инцидентов…</div>}
      {error && <div className="similar-panel__alert similar-panel__alert--error">Ошибка поиска: {error}</div>}

      {!loading && !error && searched && filtered.length === 0 && (
        <div className="similar-panel__status">{hasFilters ? 'Ничего не найдено с текущими фильтрами.' : 'Похожих инцидентов пока не найдено.'}</div>
      )}

      {!loading && !error && filtered.length > 0 && (
        <div className="similar-panel__list">
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
    <Card className={`similar-card ${onOpen ? 'similar-card--clickable' : ''}`} onClick={onOpen}>
      <div className="similar-card__badges">
        <Badge tone={scoreTone}>{percent}% похоже</Badge>
        <Badge tone={meta.badgeTone}>{(() => { const Ic = METHODOLOGY_ICONS_SIP[meta.icon]; return Ic ? <Ic size={12} /> : null; })()} {METHODOLOGY_LABELS[item.methodology] || item.methodology}</Badge>
        <Badge tone="slate">{date}</Badge>
        {author && <Badge tone="slate"><User size={12} /> {author}</Badge>}
        {onOpen && <Button type="button" variant="ghost" size="sm" className="similar-card__open">Открыть →</Button>}
      </div>

      {hasIncidentContext && (
        <div className="similar-card__context">
          {item.incident_title && <div className="similar-card__context-title">{item.incident_title}</div>}
          {item.incident_description && <p className="similar-card__context-text">{item.incident_description}</p>}
          {(incidentDateStr || item.incident_location) && (
            <div className="similar-card__context-meta">
              {incidentDateStr && <span><Calendar size={12} /> {incidentDateStr}</span>}
              {item.incident_location && <span><MapPin size={12} /> {item.incident_location}</span>}
            </div>
          )}
        </div>
      )}

      <p className="similar-card__summary">{item.summary}</p>
      {item.root_causes_preview?.length > 0 && (
        <div className="similar-card__section">
          <strong>Корневые причины:</strong>
          <ul>
            {item.root_causes_preview.map((text, idx) => <li key={idx}>{text}</li>)}
          </ul>
        </div>
      )}
      {item.recommendations_preview?.length > 0 && (
        <div className="similar-card__section">
          <strong>Рекомендации:</strong>
          <ul>
            {item.recommendations_preview.map((text, idx) => <li key={idx}>{text}</li>)}
          </ul>
        </div>
      )}
      <div className="similar-card__ids">
        <span>result #{item.result_id.slice(0, 8)}</span>
        <span>incident #{item.incident_id.slice(0, 8)}</span>
      </div>
    </Card>
  )
}
