import React, { useState } from 'react'
import BowtieDiagram from './BowtieDiagram.jsx'
import IshikawaDiagram from './IshikawaDiagram.jsx'
import FiveWhyTree from './FiveWhyTree.jsx'
import SimilarIncidentsPanel from './SimilarIncidentsPanel.jsx'
import { methodologyMeta, METHODOLOGY_LABELS } from '../lib/methodologies.js'
import { Button } from './ui/Button.jsx'
import { Badge, Card, CardBody } from './ui/Card.jsx'
import { api } from '../api.js'
import { Sparkles, Download, HelpCircle, Ribbon, Fish, TreePine, Cog, GitBranch } from 'lucide-react'
import './ResultView.css'

const PRIORITY_TONES = {
  high:   'rose',
  medium: 'amber',
  low:    'emerald',
}

const METHODOLOGY_ICONS_RV = {
  '❓': HelpCircle,
  '🎀': Ribbon,
  '🐟': Fish,
  '🌳': TreePine,
  '⚙️': Cog,
}

export default function ResultView({ result, onOpenResult = null }) {
  const isBowtie = result.methodology === 'bowtie'
  const isFishbone = result.methodology === 'fishbone'
  const isFiveWhy = result.methodology === '5whys'
  const [tab, setTab] = useState(
    isBowtie ? 'bowtie' : isFishbone ? 'fishbone' : 'tree'
  )

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
        { id: 'bowtie',   label: <><Sparkles size={14} /> Диаграмма</> },
        { id: 'recs',     label: `Рекомендации (${recCount})` },
        { id: 'meta',     label: 'Мета' },
      ]
    : isFishbone
    ? [
        { id: 'fishbone', label: <><Fish size={14} /> Исикава</> },
        { id: 'recs',     label: `Рекомендации (${recCount})` },
        { id: 'meta',     label: 'Мета' },
      ]
    : isFiveWhy
    ? [
        { id: 'tree',     label: <><GitBranch size={14} /> Дерево 5 Почему</> },
        { id: 'recs',     label: `Рекомендации (${recCount})` },
        { id: 'meta',     label: 'Мета' },
      ]
    : [
        { id: 'fishbone', label: <><Fish size={14} /> Исикава</> },
        { id: 'tree',     label: <><GitBranch size={14} /> Дерево</> },
        { id: 'recs',     label: `Рекомендации (${recCount})` },
        { id: 'meta',     label: 'Мета' },
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
    <div className="result-view" id="step-result">
      {/* Header */}
      <div className="result-view__header">
        <div className="result-view__header-left">
          <Badge tone={meta.badgeTone}>{(() => { const Ic = METHODOLOGY_ICONS_RV[meta.icon]; return Ic ? <Ic size={12} /> : null; })()} {METHODOLOGY_LABELS[result.methodology] || result.methodology}</Badge>
          <span className="result-view__result-id">#{result.result_id ? result.result_id.slice(0, 8) : ''}</span>
        </div>
        <div className="result-view__header-right">
          <div className="result-view__stats">
            <Stat label="Токены" value={result.tokens_used} />
            <Stat label="Уверенность" value={(result.confidence_avg * 100).toFixed(0) + '%'} />
            <Stat label="Модель" value={(result.model_used || '').split('/')[1] || result.model_used || '—'} />
          </div>
          <div className="result-view__actions">
            <Button variant="secondary" size="sm" loading={exporting === 'docx'} onClick={() => handleExport('docx')} disabled={!!exporting}><Download size={14} /> DOCX</Button>
            <Button variant="secondary" size="sm" loading={exporting === 'pdf'} onClick={() => handleExport('pdf')} disabled={!!exporting}><Download size={14} /> PDF</Button>
          </div>
        </div>
      </div>

      {exportError && (
        <div className="result-alert result-alert--error">
          <strong>Ошибка экспорта:</strong> {exportError}
        </div>
      )}

      {/* Summary */}
      <Card>
        <CardBody>
          <p className="result-summary">
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
      <div className="result-tabs">
        {tabs.map(t => (
          <button
            key={t.id}
            className={`result-tab ${tab === t.id ? 'result-tab--active' : ''}`}
            onClick={() => setTab(t.id)}
          >{t.label}</button>
        ))}
      </div>

      {tab === 'bowtie'   && <BowtieDiagram result={result} />}
      {tab === 'fishbone' && <IshikawaDiagram result={result} />}
      {tab === 'tree'     && <FiveWhyTree result={result} />}
      {tab === 'recs'     && <Recommendations recs={result.recommendations} />}
      {tab === 'meta'     && <Meta result={result} />}
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
    <div className="result-section">
      {sections.map(s => {
        const nodes = result[s.key]
        if (!nodes?.length) return null
        return (
          <div key={s.key} className="result-tree-group">
            <div className="result-tree-heading" style={{ color: s.color }}>{s.label}</div>
            {nodes.map(n => (
              <div key={n.id} className="result-card">
                <div className="result-card__text">{n.text}</div>
                <div className="result-card__meta">
                  <span className="result-card__category">{n.category}</span>
                  <span className="result-card__confidence">{(n.confidence * 100).toFixed(0)}%</span>
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
    <div className="result-section result-section--compact">
      {recs.map(r => (
        <div key={r.id} className="result-card">
          <div className="result-card__meta result-card__meta--recommendation">
            <span className={`result-priority result-priority--${PRIORITY_TONES[r.priority] || 'slate'}`} />
            <span className="result-card__priority">{r.priority}</span>
            <span className="result-card__category">{r.category}</span>
            {r.responsible && <span className="result-card__responsible">{r.responsible}</span>}
          </div>
          <p className="result-card__text">{r.text}</p>
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
    <div className="result-table">
      <table>
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k}>
              <td>{k}</td>
              <td>{String(v)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Stat({ label, value }) {
  return (
    <div className="result-stat">
      <span>{label}:</span>
      <strong>{value}</strong>
    </div>
  )
}
