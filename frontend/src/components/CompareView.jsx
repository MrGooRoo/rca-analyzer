import React, { useState } from 'react'
import BowtieDiagram from './BowtieDiagram.jsx'
import { methodologyMeta, METHODOLOGY_LABELS } from '../lib/methodologies.js'
import { Badge, Card, CardBody } from './ui/Card.jsx'
import './CompareView.css'

const PRIORITY_TONES = {
  high:   'rose',
  medium: 'amber',
  low:    'emerald',
}

export default function CompareView({ comparison }) {
  const [activeTab, setActiveTab] = useState(
    comparison.results.length > 0 ? comparison.results[0].result_id : null
  )

  const activeResult = comparison.results.find(r => r.result_id === activeTab)
  const isBowtie = activeResult?.methodology === 'bowtie'

  return (
    <div className="compare-view" id="step-result">
      {/* Заголовок */}
      <div className="compare-view__header">
        <span className="compare-view__icon">⚖️</span>
        <span className="compare-view__title">Сравнение методологий</span>
        <Badge tone="violet">{comparison.results.length} методик</Badge>
      </div>

      {/* Общая сводка */}
      {comparison.summary && (
        <Card>
          <CardBody>
            <div className="compare-view__section-label compare-view__section-label--indigo">📋 Сводка сравнения</div>
            <p className="compare-view__text">{comparison.summary}</p>
          </CardBody>
        </Card>
      )}

      {/* Общие рекомендации */}
      {comparison.common_recommendations?.length > 0 && (
        <div className="compare-view__section">
          <div className="compare-view__section-label">🤝 Общие рекомендации ({comparison.common_recommendations.length})</div>
          <div className="compare-view__cards">
            {comparison.common_recommendations.map(r => (
              <div key={r.id} className="compare-card">
                <div className="compare-card__meta">
                  <span className={`compare-priority compare-priority--${PRIORITY_TONES[r.priority] || 'slate'}`} />
                  <span className="compare-card__priority">{r.priority}</span>
                  <span className="compare-card__category">{r.category}</span>
                  {r.responsible && <span className="compare-card__responsible">{r.responsible}</span>}
                </div>
                <p className="compare-card__text">{r.text}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Различающиеся причины */}
      {comparison.differing_causes && Object.keys(comparison.differing_causes).length > 0 && (
        <div className="compare-view__section">
          <div className="compare-view__section-label">⚡ Различающиеся выводы</div>
          <div className="compare-view__grid">
            {Object.entries(comparison.differing_causes).map(([methodology, causes]) => (
              <div key={methodology} className="compare-card">
                <div className="compare-card__badge">
                  <Badge tone={methodologyMeta(methodology).badgeTone}>{methodologyMeta(methodology).icon} {METHODOLOGY_LABELS[methodology] || methodology}</Badge>
                </div>
                <ul className="compare-list">
                  {causes.map((cause, i) => (
                    <li key={i}><span className="compare-list__marker">▸</span>{cause}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Side-by-side результаты */}
      <div className="compare-view__section">
        <div className="compare-view__section-label">📊 Детальные результаты по каждой методике</div>

        {/* Табы */}
        <div className="compare-tabs">
          {comparison.results.map(r => (
            <button
              key={r.result_id}
              className={`compare-tab ${r.result_id === activeTab ? 'compare-tab--active' : ''}`}
              onClick={() => setActiveTab(r.result_id)}
            >
              <span className="compare-tab__icon">{methodologyMeta(r.methodology).icon}</span>
              <span className="compare-tab__label">{METHODOLOGY_LABELS[r.methodology] || r.methodology}</span>
              <span className="compare-tab__confidence">{(r.confidence_avg * 100).toFixed(0)}%</span>
            </button>
          ))}
        </div>

        {/* Активный результат */}
        {activeResult && (
          <div className="compare-result-card">
            <div className="compare-meta-row">
              <div className="compare-meta-row__item"><span>Модель:</span><strong>{activeResult.model_used.split('/')[1] || activeResult.model_used}</strong></div>
              <div className="compare-meta-row__item"><span>Токены:</span><strong>{activeResult.tokens_used}</strong></div>
              <div className="compare-meta-row__item"><span>Уверенность:</span><strong>{(activeResult.confidence_avg * 100).toFixed(0)}%</strong></div>
              <div className="compare-meta-row__item"><span>ID:</span><strong className="compare-meta-row__mono">#{activeResult.result_id.slice(0, 8)}</strong></div>
            </div>

            <div className="compare-summary">
              {activeResult.summary}
            </div>

            <CompareCausalTree result={activeResult} />

            {isBowtie && <BowtieDiagram result={activeResult} />}

            {activeResult.recommendations?.length > 0 && (
              <div className="compare-view__subsection">
                <div className="compare-view__section-label">💡 Рекомендации ({activeResult.recommendations.length})</div>
                <div className="compare-view__cards">
                  {activeResult.recommendations.map(r => (
                    <div key={r.id} className="compare-card">
                      <div className="compare-card__meta">
                        <span className={`compare-priority compare-priority--${PRIORITY_TONES[r.priority] || 'slate'}`} />
                        <span className="compare-card__priority">{r.priority}</span>
                        <span className="compare-card__category">{r.category}</span>
                        {r.responsible && <span className="compare-card__responsible">{r.responsible}</span>}
                      </div>
                      <p className="compare-card__text">{r.text}</p>
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
    { key: 'root_causes',         label: 'Корневые причины',          color: '#f43f5e' },
    { key: 'contributing_causes', label: 'Способствующие факторы',  color: '#f59e0b' },
    { key: 'immediate_causes',    label: 'Непосредственные причины', color: '#6366f1' },
  ]
  const hasAny = sections.some(s => result[s.key]?.length > 0)
  if (!hasAny) return null

  return (
    <div className="compare-view__subsection">
      {sections.map(s => {
        const nodes = result[s.key]
        if (!nodes?.length) return null
        return (
          <div key={s.key} className="compare-view__nodes">
            <div className="compare-view__node-heading" style={{ color: s.color }}>{s.label}</div>
            {nodes.map(n => (
              <div key={n.id} className="compare-card">
                <div className="compare-card__cause">{n.text}</div>
                <div className="compare-card__meta">
                  <span className="compare-node-category">{n.category}</span>
                  <span className="compare-node-confidence">{(n.confidence * 100).toFixed(0)}%</span>
                </div>
              </div>
            ))}
          </div>
        )
      })}
    </div>
  )
}
