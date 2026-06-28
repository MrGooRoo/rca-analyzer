/**
 * FiveWhySummary — компактное представление результатов 5 Why
 * в виде линейного списка «вопрос→ответ» (по аналогии с sandbox).
 * Альтернатива SVG-дереву (FiveWhyTree).
 */
import React from 'react'
import './FiveWhySummary.css'

export default function FiveWhySummary({ result }) {
  const hasData = (result.immediate_causes?.length || result.contributing_causes?.length || result.root_causes?.length)

  if (!hasData) {
    return <div className="result-section-empty">Нет данных для сводки</div>
  }

  const sections = [
    { key: 'immediate',   label: 'Непосредственные причины',   nodes: result.immediate_causes,    color: '#6366f1' },
    { key: 'contributing',label: 'Способствующие факторы',     nodes: result.contributing_causes, color: '#f59e0b' },
    { key: 'root',        label: 'Корневые причины',           nodes: result.root_causes,         color: '#f43f5e' },
  ].filter(s => s.nodes?.length > 0)

  return (
    <div className="sw-5why">
      {/* Проблема */}
      <div className="sw-5why__problem">
        <div className="sw-5why__problem-text">{result.summary || 'Инцидент'}</div>
      </div>

      {sections.map((section, si) => (
        <div key={section.key} className="sw-5why__tier">
          {si > 0 && <div className="sw-5why__arrow">↓</div>}
          <div className="sw-5why__tier-label" style={{ color: section.color }}>
            Почему? — {section.label}
          </div>
          <div className="sw-5why__nodes">
            {section.nodes.map((node, i) => (
              <div key={node.id || i} className="sw-5why__item">
                <span className="sw-5why__num" style={{ background: section.color }}>{i + 1}</span>
                <div className="sw-5why__content">
                  <div className="sw-5why__text">{node.text}</div>
                  {(node.category || node.confidence != null) && (
                    <div className="sw-5why__meta">
                      {node.category && <span className="sw-5why__category" style={{ color: section.color }}>{node.category}</span>}
                      {node.confidence != null && (
                        <span className="sw-5why__confidence">{'★'.repeat(Math.round(node.confidence * 5)).padEnd(5, '☆')} {(node.confidence * 100).toFixed(0)}%</span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
