import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../api.js'
import { methodologyMeta, METHODOLOGY_LABELS } from '../lib/methodologies.js'
import { Card } from './ui/Card.jsx'
import { Button } from './ui/Button.jsx'
import { User, Calendar, MapPin, Building2, HelpCircle, Ribbon, Fish, TreePine, Cog } from 'lucide-react'
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

/**
 * Apple-style pill chip — переключаемый фильтр.
 */
function FilterChip({ label, active, color, onClick }) {
  return (
    <button
      type="button"
      className={`chip ${active ? 'chip--active' : ''}`}
      style={active && color ? { '--chip-accent': color, borderColor: color, background: color + '20' } : {}}
      onClick={onClick}
    >
      {label}
    </button>
  )
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
  const [filterAuthor, setFilterAuthor] = useState('')
  const [filterCompany, setFilterCompany] = useState('')

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
    if (filterAuthor) result = result.filter(i =>
      (i.user_display_name || i.user_email) === filterAuthor
    )
    if (filterCompany) result = result.filter(i => i.incident_company === filterCompany)
    return result
  }, [items, filterMethod, filterAuthor, filterCompany])

  // Вычисляем доступные опции для фильтров из результатов
  const availableMethods = useMemo(() => [...new Set(items.map(i => i.methodology))], [items])
  const availableAuthors = useMemo(() => {
    const set = new Set(items.map(i => i.user_display_name || i.user_email).filter(Boolean))
    return [...set]
  }, [items])
  const availableCompanies = useMemo(() => {
    const set = new Set(items.map(i => i.incident_company).filter(Boolean))
    return [...set]
  }, [items])

  const hasFilters = filterMethod || filterAuthor || filterCompany
  const hasAnyCompany = availableCompanies.length > 0

  function resetFilters() { setFilterMethod(''); setFilterAuthor(''); setFilterCompany('') }

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
          {/* Методики — Apple pill chips */}
          {availableMethods.length > 1 && (
            <div className="similar-panel__filter-group">
              <span className="similar-panel__filter-label">Методика</span>
              <div className="similar-panel__chips">
                <FilterChip label="Все" active={!filterMethod} onClick={() => setFilterMethod('')} />
                {availableMethods.map(m => {
                  const meta = methodologyMeta(m)
                  const colorMap = {
                    sky: 'var(--accent)',
                    rose: 'var(--color-error)',
                    emerald: 'var(--color-success)',
                    amber: 'var(--color-warning)',
                    violet: 'var(--system-purple)',
                  }
                  return (
                    <FilterChip
                      key={m}
                      label={METHODOLOGY_LABELS[m] || m}
                      active={filterMethod === m}
                      color={colorMap[meta.badgeTone] || 'var(--label-secondary)'}
                      onClick={() => setFilterMethod(filterMethod === m ? '' : m)}
                    />
                  )
                })}
              </div>
            </div>
          )}

          {/* Автор — Apple pill chips */}
          {availableAuthors.length > 1 && (
            <div className="similar-panel__filter-group">
              <span className="similar-panel__filter-label">Автор</span>
              <div className="similar-panel__chips">
                <FilterChip label="Все" active={!filterAuthor} onClick={() => setFilterAuthor('')} />
                {availableAuthors.map(a => (
                  <FilterChip
                    key={a}
                    label={a}
                    active={filterAuthor === a}
                    onClick={() => setFilterAuthor(filterAuthor === a ? '' : a)}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Компания — Apple pill chips (только если есть данные) */}
          {hasAnyCompany && (
            <div className="similar-panel__filter-group">
              <span className="similar-panel__filter-label">Компания</span>
              <div className="similar-panel__chips">
                <FilterChip label="Все" active={!filterCompany} onClick={() => setFilterCompany('')} />
                {availableCompanies.map(c => (
                  <FilterChip
                    key={c}
                    label={c}
                    active={filterCompany === c}
                    onClick={() => setFilterCompany(filterCompany === c ? '' : c)}
                  />
                ))}
              </div>
            </div>
          )}

          {hasFilters && (
            <Button type="button" variant="ghost" size="sm" className="similar-panel__reset" onClick={resetFilters}>
              ✕ Сбросить
            </Button>
          )}
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
        <span className={`similar-badge similar-badge--${scoreTone}`}>{percent}% похоже</span>
        <span className={`similar-badge similar-badge--${meta.badgeTone}`}>
          {(() => { const Ic = METHODOLOGY_ICONS_SIP[meta.icon]; return Ic ? <Ic size={12} /> : null; })()}
          {' '}{METHODOLOGY_LABELS[item.methodology] || item.methodology}
        </span>
        <span className="similar-badge similar-badge--slate">{date}</span>
        {author && <span className="similar-badge similar-badge--slate"><User size={12} /> {author}</span>}
        {item.incident_company && <span className="similar-badge similar-badge--slate"><Building2 size={12} /> {item.incident_company}</span>}
        {onOpen && <Button type="button" variant="ghost" size="sm" className="similar-card__open">Открыть →</Button>}
      </div>

      {hasIncidentContext && (
        <div className="similar-card__context">
          {item.incident_title && <div className="similar-card__context-title">{item.incident_title}</div>}
          {item.incident_description && <p className="similar-card__context-text">{item.incident_description}</p>}
          {(incidentDateStr || item.incident_location || item.incident_company) && (
            <div className="similar-card__context-meta">
              {incidentDateStr && <span><Calendar size={12} /> {incidentDateStr}</span>}
              {item.incident_location && <span><MapPin size={12} /> {item.incident_location}</span>}
              {item.incident_company && <span><Building2 size={12} /> {item.incident_company}</span>}
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
