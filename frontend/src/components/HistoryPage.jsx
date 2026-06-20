import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { api } from '../api.js'
import { methodologyMeta, METHODOLOGY_LABELS } from '../lib/methodologies.js'
import { Badge, Card } from './ui/Card.jsx'
import { Button } from './ui/Button.jsx'
import { Input, Select } from './ui/Field.jsx'

const SEVERITY_MAP = {
  critical:  { tone: 'rose',    label: 'Критический' },
  major:     { tone: 'amber',   label: 'Тяжёлый' },
  moderate:  { tone: 'sky',     label: 'Средний' },
  minor:     { tone: 'emerald', label: 'Лёгкий' },
  near_miss: { tone: 'slate',   label: 'Предпосылка' },
}

const PAGE_SIZE = 20

function sessionsToHistoryGroups(sessions) {
  return (sessions || [])
    .map(session => {
      const results = [...(session.results || [])]
        .sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
        .map(r => ({
          ...r,
          session_id: r.session_id || session.id,
          user_id: r.user_id || session.user_id,
          user_display_name: r.user_display_name || session.user_display_name,
          user_email: r.user_email || session.user_email,
          incident: r.incident || {
            title: session.incident_title,
            description: session.incident_description,
            date: session.incident_date,
            location: session.incident_location,
            severity: session.incident_severity,
            type: session.incident_type,
          },
        }))
      if (results.length === 0) return null
      const first = results[0]
      const incidentId = first.incident_id || session.id
      if (results.length > 1) {
        return { isCompare: true, sessionId: session.id, incidentId, results, session }
      }
      return { isCompare: false, result: results[0], session }
    })
    .filter(Boolean)
}

export default function HistoryPage({ onOpen, onOpenComparison, currentUser }) {
  const isAdmin = currentUser?.role === 'admin'
  const [sessions, setSessions] = useState([])
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [filterMethod, setFilterMethod] = useState('')
  const [filterSeverity, setFilterSeverity] = useState('')
  const [filterType, setFilterType] = useState('')

  const load = useCallback(async (off) => {
    setLoading(true); setError(null)
    try { const data = await api.sessions.list(PAGE_SIZE, off); setSessions(data) }
    catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load(0) }, [load])

  function prev() { const o = Math.max(0, offset - PAGE_SIZE); setOffset(o); load(o) }
  function next() { const o = offset + PAGE_SIZE; setOffset(o); load(o) }
  function resetFilters() { setSearch(''); setFilterMethod(''); setFilterSeverity(''); setFilterType('') }

  const groups = useMemo(() => sessionsToHistoryGroups(sessions), [sessions])
  const filtered = useMemo(() => {
    let result = groups
    const resultsOf = g => (g.isCompare ? g.results : [g.result])
    if (search.trim()) {
      const q = search.toLowerCase()
      result = result.filter(g => resultsOf(g).some(r =>
        r.summary?.toLowerCase().includes(q) || r.result_id?.includes(q) || r.incident?.title?.toLowerCase().includes(q)
      ))
    }
    if (filterMethod) result = result.filter(g => resultsOf(g).some(r => r.methodology === filterMethod))
    if (filterSeverity) result = result.filter(g => resultsOf(g).some(r => r.incident?.severity === filterSeverity))
    if (filterType === 'single') result = result.filter(g => !g.isCompare)
    else if (filterType === 'compare') result = result.filter(g => g.isCompare)
    return result
  }, [groups, search, filterMethod, filterSeverity, filterType])

  const hasFilters = search || filterMethod || filterSeverity || filterType

  async function handleOpenCompareGroup(group) {
    try { const comp = await api.compareResults(group.incidentId, group.sessionId); onOpenComparison(comp) }
    catch { onOpen(group.results[group.results.length - 1]) }
  }

  return (
    <div className="space-y-6">
      {/* Toolbar */}
      <div className="flex items-center gap-4">
        <h2 className="text-2xl font-bold text-white tracking-tight flex-1">История анализов</h2>
        <Button type="button" variant="secondary" size="sm" onClick={() => load(offset)} disabled={loading}>
          {loading ? '…' : '↻'}
        </Button>
      </div>

      {/* Filters */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <Input type="text" placeholder="🔍 Поиск по содержанию…" value={search} onChange={e => setSearch(e.target.value)} />
        <Select value={filterMethod} onChange={e => setFilterMethod(e.target.value)}>
          <option value="">Все методики</option>
          {Object.entries(METHODOLOGY_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </Select>
        <Select value={filterSeverity} onChange={e => setFilterSeverity(e.target.value)}>
          <option value="">Все уровни</option>
          {Object.entries(SEVERITY_MAP).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </Select>
        <Select value={filterType} onChange={e => setFilterType(e.target.value)}>
          <option value="">Все типы</option>
          <option value="single">Одиночные</option>
          <option value="compare">Сравнения</option>
        </Select>
        {hasFilters && <Button type="button" variant="danger" size="sm" onClick={resetFilters}>✕ Сбросить</Button>}
      </div>

      {error && <div className="rounded-lg p-4 text-sm text-rose-300 bg-rose-500/10 ring-1 ring-rose-500/30">Ошибка загрузки: {error}</div>}

      {!loading && !error && filtered.length === 0 && (
        <div className="text-center py-16 text-slate-400">
          <div className="text-5xl mb-3">📂</div>
          <p className="text-base">{hasFilters ? 'Ничего не найдено. Попробуйте сбросить фильтры.' : 'История пуста. Запустите первый анализ.'}</p>
        </div>
      )}

      <div className="flex flex-col gap-3">
        {filtered.map(group => group.isCompare ? (
          <CompareGroupCard key={group.sessionId || group.incidentId} group={group} onOpenComparison={() => handleOpenCompareGroup(group)} onOpenResult={onOpen} isAdmin={isAdmin} currentUserId={currentUser?.user_id} />
        ) : (
          <HistoryCard key={group.result.result_id} result={group.result} onOpen={onOpen} isAdmin={isAdmin} currentUserId={currentUser?.user_id} />
        ))}
      </div>

      {sessions.length === PAGE_SIZE && (
        <div className="flex items-center justify-center gap-4 mt-6">
          <Button variant="secondary" size="sm" onClick={prev} disabled={offset === 0}>← Назад</Button>
          <span className="text-sm text-slate-400">Стр. {Math.floor(offset / PAGE_SIZE) + 1}</span>
          <Button variant="secondary" size="sm" onClick={next}>Вперёд →</Button>
        </div>
      )}
    </div>
  )
}

function HistoryCard({ result, onOpen, isAdmin, currentUserId }) {
  const sev = SEVERITY_MAP[result.incident?.severity] || null
  const date = new Date(result.created_at).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
  const isMine = result.user_id === currentUserId
  const authorName = result.user_display_name || result.user_email || null

  return (
    <Card className="p-5 cursor-pointer hover:ring-indigo-400 hover:shadow-md hover:-translate-y-0.5 transition flex items-center gap-4" onClick={() => onOpen(result)}>
      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap items-center gap-2 mb-2">
          <Badge tone="indigo">{METHODOLOGY_LABELS[result.methodology] || result.methodology}</Badge>
          {isAdmin && authorName && (
            <Badge tone={isMine ? 'sky' : 'slate'}>👤 {authorName}{isMine ? ' (вы)' : ''}</Badge>
          )}
          {sev && <Badge tone={sev.tone}>{sev.label}</Badge>}
          <span className="text-xs text-slate-400 ml-auto">{date}</span>
        </div>
        <p className="text-base text-slate-200 leading-relaxed line-clamp-2 mb-2">{result.summary}</p>
        <div className="flex flex-wrap gap-3 text-xs text-slate-500 font-mono">
          <span>#{result.result_id.slice(0, 8)}</span>
          <span>{result.recommendations?.length || 0} рек.</span>
          <span>{result.tokens_used} ток.</span>
          <span>{((result.confidence_avg || 0) * 100).toFixed(0)}% ув.</span>
        </div>
      </div>
      <span className="text-xl text-slate-500 hidden sm:block transition-transform">›</span>
    </Card>
  )
}

function CompareGroupCard({ group, onOpenComparison, onOpenResult, isAdmin, currentUserId }) {
  const { results } = group
  const newest = results[results.length - 1]
  const sev = SEVERITY_MAP[newest.incident?.severity] || null
  const date = new Date(newest.created_at).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
  const isMine = newest.user_id === currentUserId
  const authorName = newest.user_display_name || newest.user_email || null
  const totalRecs = results.reduce((s, r) => s + (r.recommendations?.length || 0), 0)
  const totalTokens = results.reduce((s, r) => s + (r.tokens_used || 0), 0)
  const avgConf = results.reduce((s, r) => s + (r.confidence_avg || 0), 0) / results.length

  function openSingle(e, r) { e.stopPropagation(); onOpenResult(r) }

  return (
    <Card className="p-5 cursor-pointer hover:ring-indigo-400 hover:shadow-md hover:-translate-y-0.5 transition border-l-4 border-l-violet-500 flex items-center gap-4" onClick={onOpenComparison}>
      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap items-center gap-2 mb-2">
          <Badge tone="violet">⚖️ Сравнение · {results.length} методик</Badge>
          {isAdmin && authorName && (
            <Badge tone={isMine ? 'sky' : 'slate'}>👤 {authorName}{isMine ? ' (вы)' : ''}</Badge>
          )}
          {sev && <Badge tone={sev.tone}>{sev.label}</Badge>}
          <span className="text-xs text-slate-400 ml-auto">{date}</span>
        </div>
        <p className="text-base text-slate-200 leading-relaxed line-clamp-2 mb-2">{newest.summary}</p>
        <div className="flex flex-wrap gap-2 mb-2">
          {results.map(r => (
            <Button key={r.result_id} type="button" variant="outline" size="sm" onClick={e => openSingle(e, r)}>
              {METHODOLOGY_LABELS[r.methodology] || r.methodology}
            </Button>
          ))}
        </div>
        <div className="flex flex-wrap gap-3 text-xs text-slate-500 font-mono">
          <span>#{(group.sessionId || group.incidentId).slice(0, 8)}</span>
          <span>{totalRecs} рек.</span>
          <span>{totalTokens} ток.</span>
          <span>{(avgConf * 100).toFixed(0)}% ув.</span>
        </div>
      </div>
      <span className="text-xl text-slate-500 hidden sm:block transition-transform">›</span>
    </Card>
  )
}
