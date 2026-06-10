/**
 * BowtieDiagram v7
 * Изменения: убрана SVG-визуализация, оставлен только «Список узлов».
 * Промпт: несколько барьеров на угрозу/последствие, реальный confidence.
 */
import React from 'react'
import './BowtieDiagram.css'

const P = {
  hazard:      { dot: '#a78bfa', label: 'Опасный фактор' },
  topEvent:    { dot: '#f87171', label: 'Топ-событие'    },
  threat:      { dot: '#fb923c', label: 'Угрозы'         },
  prevention:  { dot: '#facc15', label: 'Барьеры пред.'  },
  mitigation:  { dot: '#34d399', label: 'Барьеры смяг.'  },
  consequence: { dot: '#60a5fa', label: 'Последствия'    },
}

function parse(result) {
  const tree = result.causal_tree || []
  const by = c => tree.filter(n => n.category?.toUpperCase().includes(c))
  let hazards      = by('HAZARD')
  let topEvents    = by('TOP_EVENT')
  let threats      = by('THREAT')
  let prevention   = by('PREVENTION')
  let consequences = by('CONSEQUENCE')
  let mitigation   = by('MITIGATION')

  if (!threats.length)      threats      = result.root_causes || []
  if (!consequences.length) consequences = (result.immediate_causes || []).slice(1)
  if (!topEvents.length)    topEvents    = (result.immediate_causes || []).slice(0, 1)
  if (!prevention.length || !mitigation.length) {
    const c = result.contributing_causes || []
    if (!prevention.length) prevention = c.filter((_, i) => i % 2 === 0)
    if (!mitigation.length) mitigation = c.filter((_, i) => i % 2 !== 0)
  }
  return { hazards, topEvents, threats, prevention, consequences, mitigation }
}

function confColor(v) {
  if (v == null) return '#6b7280'
  if (v >= 0.7)  return '#34d399'
  if (v >= 0.4)  return '#facc15'
  return '#f87171'
}

function NodeList({ label, dot, nodes }) {
  if (!nodes || nodes.length === 0) return null
  return (
    <div className="bt-section">
      <div className="bt-section-label">
        <span className="bt-leg-dot" style={{ background: dot }} />
        {label}
      </div>
      {nodes.map((n, i) => (
        <div className="bt-raw-row" key={i}>
          <span className="bt-raw-text">{n?.text || '—'}</span>
          {n?.confidence != null && (
            <span className="bt-raw-conf" style={{ color: confColor(n.confidence) }}>
              {(n.confidence * 100).toFixed(0)}%
            </span>
          )}
        </div>
      ))}
    </div>
  )
}

export default function BowtieDiagram({ result }) {
  const { hazards, topEvents, threats, prevention, consequences, mitigation } = parse(result)

  return (
    <div className="bt-shell bt-shell--list">

      <div className="bt-legend">
        {Object.entries(P).map(([k, v]) => (
          <div className="bt-leg-item" key={k}>
            <div className="bt-leg-dot" style={{ background: v.dot }} />
            <span>{v.label}</span>
          </div>
        ))}
      </div>

      <div className="bt-list-grid">
        <NodeList label="Опасный фактор" dot={P.hazard.dot}      nodes={hazards}      />
        <NodeList label="Топ-событие"    dot={P.topEvent.dot}    nodes={topEvents}    />
        <NodeList label="Угрозы"         dot={P.threat.dot}      nodes={threats}      />
        <NodeList label="Барьеры пред."  dot={P.prevention.dot}  nodes={prevention}   />
        <NodeList label="Последствия"    dot={P.consequence.dot} nodes={consequences} />
        <NodeList label="Барьеры смяг."  dot={P.mitigation.dot}  nodes={mitigation}   />
      </div>

    </div>
  )
}
