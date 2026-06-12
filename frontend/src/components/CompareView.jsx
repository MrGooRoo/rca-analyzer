import React, { useState } from 'react'
import BowtieDiagram from './BowtieDiagram.jsx'
import { methodologyMeta, METHODOLOGY_LABELS } from '../lib/methodologies.js'
import { Badge } from './ui/Card.jsx'
import './CompareView.css'
import './ResultView.css'

const PRIORITY_COLORS = {
  high:   '#f76f6f',
  medium: '#f7b955',
  low:    '#3ecf8e',
}

export default function CompareView({ comparison }) {
  const [activeTab, setActiveTab] = useState(
    comparison.results.length > 0 ? comparison.results[0].result_id : null
  )

  const activeResult = comparison.results.find(r => r.result_id === activeTab)
  const isBowtie = activeResult?.methodology === 'bowtie'

  return (
    <div className="compare-view">
      {/* Заголовок */}
      <div className="compare-header">
        <h2 className="compare-title">
          <span className="compare-icon">⚖️</span>
          Сравнение методологий
          <span className="compare-badge">{comparison.results.length} методик</span>
        </h2>
      </div>

      {/* Общая сводка */}
      {comparison.summary && (
        <div className="compare-summary-box">
          <div className="compare-summary-title">📋 Сводка сравнения</div>
          <p className="compare-summary-text">{comparison.summary}</p>
        </div>
      )}

      {/* Общие рекомендации (из всех методик) */}
      {comparison.common_recommendations?.length > 0 && (
        <div className="compare-section">
          <div className="compare-section-title">
            🤝 Общие рекомендации ({comparison.common_recommendations.length})
          </div>
          <div className="recs">
            {comparison.common_recommendations.map(r => (
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
        </div>
      )}

      {/* Различающиеся причины */}
      {comparison.differing_causes && Object.keys(comparison.differing_causes).length > 0 && (
        <div className="compare-section">
          <div className="compare-section-title">⚡ Различающиеся выводы</div>
          <div className="differing-grid">
            {Object.entries(comparison.differing_causes).map(([methodology, causes]) => (
              <div key={methodology} className="differing-card">
                <div className="differing-card-header">
                  <Badge tone={methodologyMeta(methodology).badgeTone}>{methodologyMeta(methodology).icon} {METHODOLOGY_LABELS[methodology] || methodology}</Badge>
                </div>
                <ul className="differing-list">
                  {causes.map((cause, i) => (
                    <li key={i} className="differing-item">{cause}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Side-by-side результаты */}
      <div className="compare-section">
        <div className="compare-section-title">📊 Детальные результаты по каждой методике</div>

        {/* Табы методик */}
        <div className="compare-tabs">
          {comparison.results.map(r => (
            <button
              key={r.result_id}
              className={`compare-tab ${r.result_id === activeTab ? 'compare-tab--active' : ''}`}
              onClick={() => setActiveTab(r.result_id)}
            >
              <span className="compare-tab-icon">{methodologyMeta(r.methodology).icon}</span>
              <span className="compare-tab-label">
                {METHODOLOGY_LABELS[r.methodology] || r.methodology}
              </span>
              <span className="compare-tab-conf">
                {(r.confidence_avg * 100).toFixed(0)}%
              </span>
            </button>
          ))}
        </div>

        {/* Детальный результат активной методики */}
        {activeResult && (
          <div className="compare-result-panel">
            <div className="result-stats" style={{ marginBottom: '0.75rem' }}>
              <div className="stat">
                <span className="stat-label">Модель</span>
                <span className="stat-value">{activeResult.model_used.split('/')[1] || activeResult.model_used}</span>
              </div>
              <div className="stat">
                <span className="stat-label">Токены</span>
                <span className="stat-value">{activeResult.tokens_used}</span>
              </div>
              <div className="stat">
                <span className="stat-label">Уверенность</span>
                <span className="stat-value">{(activeResult.confidence_avg * 100).toFixed(0)}%</span>
              </div>
              <div className="stat">
                <span className="stat-label">ID</span>
                <span className="stat-value">#{activeResult.result_id.slice(0, 8)}</span>
              </div>
            </div>

            {/* Сводка конкретной методики */}
            <div className="summary-box">
              <p>{activeResult.summary}</p>
            </div>

            {/* Причины */}
            <CompareCausalTree result={activeResult} />

            {/* Bowtie диаграмма */}
            {isBowtie && (
              <div style={{ marginTop: '1rem' }}>
                <BowtieDiagram result={activeResult} />
              </div>
            )}

            {/* Рекомендации */}
            {activeResult.recommendations?.length > 0 && (
              <div style={{ marginTop: '1rem' }}>
                <div className="compare-subsection-title">
                  💡 Рекомендации ({activeResult.recommendations.length})
                </div>
                <div className="recs">
                  {activeResult.recommendations.map(r => (
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
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function CompareCausalTree({ result }) {
  const sections = [
    { key: 'root_causes',         label: 'Корневые причины',       color: '#f76f6f' },
    { key: 'contributing_causes', label: 'Способствующие факторы', color: '#f7b955' },
    { key: 'immediate_causes',    label: 'Непосредственные причины', color: '#4f8ef7' },
  ]

  const hasAny = sections.some(s => result[s.key]?.length > 0)
  if (!hasAny) return null

  return (
    <div className="causal-tree" style={{ marginTop: '0.5rem' }}>
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
