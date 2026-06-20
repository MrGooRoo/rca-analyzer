import React, { useState } from 'react'
import BowtieDiagram from './BowtieDiagram.jsx'
import SimilarIncidentsPanel from './SimilarIncidentsPanel.jsx'
import { methodologyMeta, METHODOLOGY_LABELS } from '../lib/methodologies.js'
import { Button } from './ui/Button.jsx'
import { Badge, Card, CardBody } from './ui/Card.jsx'
import { api } from '../api.js'

const PRIORITY_COLORS = {
  high:   'bg-rose-500',
  medium: 'bg-amber-500',
  low:    'bg-emerald-500',
}

export default function ResultView({ result, onOpenResult = null }) {
  const isBowtie = result.methodology === 'bowtie'
  const [tab, setTab] = useState(isBowtie ? 'bowtie' : 'tree')
  const [exporting, setExporting] = useState(null)
  const [exportError, setExportError] = useState(null)

  async function handleExport(format) {
    setExporting(format)
    setExportError(null)
    try {
      await api.exportResult(result.result_id, result.methodology, format)
    } catch (e) {
      setExportError(e?.message || 'Ошибка экспорта')
    } finally {
      setExporting(null)
    }
  }

  const recCount = result.recommendations?.length ?? 0

  const tabs = isBowtie
    ? [
        { id: 'bowtie', label: '🦋 Диаграмма' },
        { id: 'recs',   label: `Рекомендации (${recCount})` },
        { id: 'meta',   label: 'Мета' },
      ]
    : [
        { id: 'tree', label: 'Дерево причин' },
        { id: 'recs', label: `Рекомендации (${recCount})` },
        { id: 'meta', label: 'Мета' },
      ]

  const similarQueryText = [
    result.summary,
    ...(result.root_causes || []).map(n => n.text),
    ...(result.contributing_causes || []).map(n => n.text),
    ...(result.immediate_causes || []).map(n => n.text),
    ...(result.recommendations || []).map(r => r.text),
  ].filter(Boolean).join('\n')

  const meta = methodologyMeta(result.methodology)

  return (
    <div className="space-y-4" id="step-result">
      {/* Header */}
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <Badge tone={meta.badgeTone}>{meta.icon} {METHODOLOGY_LABELS[result.methodology] || result.methodology}</Badge>
          <span className="text-xs text-slate-500 font-mono">#{result.result_id ? result.result_id.slice(0, 8) : ''}</span>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-3 text-xs">
            <Stat label="Токены" value={result.tokens_used} />
            <Stat label="Уверенность" value={(result.confidence_avg * 100).toFixed(0) + '%'} />
            <Stat label="Модель" value={(result.model_used || '').split('/')[1] || result.model_used || '—'} />
          </div>
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" loading={exporting === 'docx'} onClick={() => handleExport('docx')} disabled={!!exporting} leftIcon="⬇️">DOCX</Button>
            <Button variant="secondary" size="sm" loading={exporting === 'pdf'} onClick={() => handleExport('pdf')} disabled={!!exporting} leftIcon="⬇️">PDF</Button>
          </div>
        </div>
      </div>

      {exportError && (
        <div className="rounded-lg bg-rose-500/10 ring-1 ring-rose-500/30 text-rose-300 text-sm px-3 py-2.5">
          <strong>Ошибка экспорта:</strong> {exportError}
        </div>
      )}

      {/* Summary */}
      <Card>
        <CardBody>
          <p className="text-sm text-slate-300 italic border-l-2 border-indigo-500/40 pl-3">
            {result.summary}
          </p>
        </CardBody>
      </Card>

      {/* Similar incidents */}
      <SimilarIncidentsPanel
        queryText={similarQueryText}
        excludeResultId={result.result_id}
        excludeIncidentId={result.incident_id}
        auto
        title="Похожие инциденты в истории"
        onOpenResult={onOpenResult}
      />

      {/* Tabs */}
      <div className="flex gap-1 rounded-xl bg-slate-800 p-1">
        {tabs.map(t => (
          <button
            key={t.id}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
              tab === t.id
                ? 'bg-slate-700 text-white shadow'
                : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
            }`}
            onClick={() => setTab(t.id)}
          >{t.label}</button>
        ))}
      </div>

      {tab === 'bowtie' && <BowtieDiagram result={result} />}
      {tab === 'tree'   && <CausalTree result={result} />}
      {tab === 'recs'   && <Recommendations recs={result.recommendations} />}
      {tab === 'meta'   && <Meta result={result} />}
    </div>
  )
}

function CausalTree({ result }) {
  const sections = [
    { key: 'root_causes',         label: 'Корневые причины',         color: '#f43f5e' },
    { key: 'contributing_causes', label: 'Способствующие факторы', color: '#f59e0b' },
    { key: 'immediate_causes',    label: 'Непосредственные причины', color: '#6366f1' },
  ]
  return (
    <div className="space-y-4">
      {sections.map(s => {
        const nodes = result[s.key]
        if (!nodes?.length) return null
        return (
          <div key={s.key} className="space-y-2">
            <div className="text-xs uppercase tracking-wider font-semibold" style={{ color: s.color }}>{s.label}</div>
            {nodes.map(n => (
              <div key={n.id} className="rounded-lg bg-slate-950/60 ring-1 ring-slate-800 p-3">
                <div className="text-sm text-slate-200">{n.text}</div>
                <div className="flex items-center gap-2 mt-1">
                  <span className="inline-flex items-center rounded-md bg-slate-800 px-2 py-0.5 text-xs text-slate-400">{n.category}</span>
                  <span className="text-xs text-slate-500">{(n.confidence * 100).toFixed(0)}%</span>
                </div>
              </div>
            ))}
          </div>
        )
      })}
    </div>
  )
}

function Recommendations({ recs }) {
  return (
    <div className="space-y-3">
      {recs.map(r => (
        <div key={r.id} className="rounded-lg bg-slate-950/60 ring-1 ring-slate-800 p-3">
          <div className="flex items-center gap-2 text-sm mb-1">
            <span className={`h-2 w-2 rounded-full ${PRIORITY_COLORS[r.priority] || 'bg-slate-500'}`} />
            <span className="text-xs font-semibold uppercase text-slate-300">{r.priority}</span>
            <span className="text-xs text-slate-400">{r.category}</span>
            {r.responsible && <span className="text-xs text-slate-500">{r.responsible}</span>}
          </div>
          <p className="text-sm text-slate-300">{r.text}</p>
        </div>
      ))}
    </div>
  )
}

function Meta({ result }) {
  const rows = [
    ['result_id',      result.result_id],
    ['methodology',    result.methodology],
    ['model_used',     result.model_used],
    ['tokens_used',    result.tokens_used],
    ['confidence_avg', result.confidence_avg],
    ['created_at',     result.created_at],
  ]
  return (
    <div className="overflow-hidden rounded-xl bg-slate-950/60 ring-1 ring-slate-800">
      <table className="w-full text-sm text-left">
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k} className="border-b border-slate-800 last:border-0">
              <td className="px-4 py-2.5 text-slate-400">{k}</td>
              <td className="px-4 py-2.5 text-slate-200 font-mono text-xs">{String(v)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Stat({ label, value }) {
  return (
    <div className="flex items-center gap-1">
      <span className="text-slate-500">{label}:</span>
      <span className="text-slate-200 font-medium">{value}</span>
    </div>
  )
}
