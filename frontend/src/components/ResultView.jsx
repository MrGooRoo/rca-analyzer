import React, { useState } from 'react'
import BowtieDiagram from './BowtieDiagram.jsx'
import './ResultView.css'

const METHODOLOGY_LABELS = {
  ishikawa:     'Ishikawa',
  five_why:     '5 Почему',
  fta:          'FTA',
  rca_systemic: 'RCA Системный',
  bowtie:       'Bowtie',
}

const PRIORITY_COLORS = {
  high:   '#f76f6f',
  medium: '#f7b955',
  low:    '#3ecf8e',
}

export default function ResultView({ result }) {
  const isBowtie = result.methodology === 'bowtie'
  const [tab, setTab] = useState(isBowtie ? 'bowtie' : 'tree')

  const tabs = isBowtie
    ? [
        { id: 'bowtie', label: '🦋 Диаграмма' },
        { id: 'recs',   label: `Рекомендации (${result.recommendations.length})` },
        { id: 'meta',   label: 'Мета' },
      ]
    : [
        { id: 'tree', label: 'Дерево причин' },
        { id: 'recs', label: `Рекомендации (${result.recommendations.length})` },
        { id: 'meta', label: 'Мета' },
      ]

  return (
    <div className="result">
      <div className="result-header">
        <div className="result-title">
          <span className="method-badge">{METHODOLOGY_LABELS[result.methodology] || result.methodology}</span>
          <span className="result-id">#{result.result_id.slice(0, 8)}</span>
        </div>
        <div className="result-stats">
          <Stat label="Токены" value={result.tokens_used} />
          <Stat label="Уверенность" value={(result.confidence_avg * 100).toFixed(0) + '%'} />
          <Stat label="Модель" value={result.model_used.split('/')[1] || result.model_used} />
        </div>
      </div>

      <div className="summary-box">
        <p>{result.summary}</p>
      </div>

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
