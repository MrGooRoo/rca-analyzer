import React, { useState } from 'react'
import BowtieDiagram from './BowtieDiagram.jsx'
import SimilarIncidentsPanel from './SimilarIncidentsPanel.jsx'
import { methodologyMeta, METHODOLOGY_LABELS } from '../lib/methodologies.js'
import { Button } from './ui/Button.jsx'
import { Badge } from './ui/Card.jsx'
import { api } from '../api.js'
import './ResultView.css'

const PRIORITY_COLORS = {
  high:   '#f76f6f',
  medium: '#f7b955',
  low:    '#3ecf8e',
}

export default function ResultView({ result, onOpenResult = null }) {
  const isBowtie = result.methodology === 'bowtie'
  const [tab, setTab]           = useState(isBowtie ? 'bowtie' : 'tree')
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

  return (
    <div className="result" id="step-result">
      <div className="result-header">
        <div className="result-title">
          <Badge tone={methodologyMeta(result.methodology).badgeTone}>{methodologyMeta(result.methodology).icon} {METHODOLOGY_LABELS[result.methodology] || result.methodology}</Badge>
          <span className="result-id">#{result.result_id ? result.result_id.slice(0, 8) : ''}</span>
        </div>
        <div className="result-header-right">
          <div className="result-stats">
            <Stat label="Токены" value={result.tokens_used} />
            <Stat label="Уверенность" value={(result.confidence_avg * 100).toFixed(0) + '%'} />
            <Stat label="Модель" value={(result.model_used || '').split('/')[1] || result.model_used || '—'} />
          </div>
          <div className="export-buttons">
            <Button
              variant="secondary"
              size="sm"
              loading={exporting === 'docx'}
              onClick={() => handleExport('docx')}
              disabled={!!exporting}
              leftIcon="⬇️"
            >
              DOCX
            </Button>
            <Button
              variant="secondary"
              size="sm"
              loading={exporting === 'pdf'}
              onClick={() => handleExport('pdf')}
              disabled={!!exporting}
              leftIcon="⬇️"
            >
              PDF
            </Button>
          </div>
        </div>
      </div>

      {exportError && (
        <div className="alert alert-error" style={{ marginBottom: '0.75rem' }}>
          <strong>Ошибка экспорта:</strong> {exportError}
        </div>
      )}

      <div className="summary-box">
        <p>{result.summary}</p>
      </div>

      <SimilarIncidentsPanel
        queryText={similarQueryText}
        excludeResultId={result.result_id}
        excludeIncidentId={result.incident_id}
        auto
        title="Похожие инциденты в истории"
        onOpenResult={onOpenResult}
      />

      <div className="tabs">
        {tabs.map(t => (
          <button
            key={t.id}
            className={`tab ${tab === t.id ? 'tab--active' : ''}`}
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
    { key: 'root_causes',         label: 'Корневые причины',       color: '#f76f6f' },
    { key: 'contributing_causes', label: 'Способствующие факторы', color: '#f7b955' },
    { key: 'immediate_causes',    label: 'Непосредственные причины', color: '#4f8ef7' },
  ]
  return (
    <div className="causal-tree">
      {sections.map(s => {
        const nodes = result[s.key]
        if (!nodes?.length) return null
        return (
          <div key={s.key} className="cause-section">
            <div className="cause-section-label" style={{ color: s.color }}>{s.label}</div>
            {nodes.map(n => (
              <div key={n.id} className="cause-node">
                <div className="cause-node-text">{n.text}</div>
                <div className="cause-node-meta">
                  <span className="tag">{n.category}</span>
                  <span className="confidence">{(n.confidence * 100).toFixed(0)}%</span>
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
    <div className="recs">
      {recs.map(r => (
        <div key={r.id} className="rec-card">
          <div className="rec-header">
            <span className="priority-dot" style={{ background: PRIORITY_COLORS[r.priority] || '#7b82a8' }} />
            <span className="rec-priority">{r.priority}</span>
            <span className="rec-category">{r.category}</span>
            {r.responsible && <span className="rec-resp">{r.responsible}</span>}
          </div>
          <p className="rec-text">{r.text}</p>
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
    <table className="meta-table">
      <tbody>
        {rows.map(([k, v]) => (
          <tr key={k}>
            <td className="meta-key">{k}</td>
            <td className="meta-val">{String(v)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function Stat({ label, value }) {
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
    </div>
  )
}
