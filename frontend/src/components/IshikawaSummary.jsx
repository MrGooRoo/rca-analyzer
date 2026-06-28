/**
 * IshikawaSummary — компактное представление результатов Исикава
 * в виде сетки категорий (по аналогии с sandbox).
 * Альтернатива SVG-диаграмме (IshikawaDiagram).
 */
import React from 'react'
import './IshikawaSummary.css'

const TIERS = [
  { key: 'root_causes',         label: 'Корневые причины',         color: '#f43f5e', short: 'Корневые' },
  { key: 'contributing_causes', label: 'Способствующие факторы',   color: '#f59e0b', short: 'Факторы' },
  { key: 'immediate_causes',    label: 'Непосредственные причины', color: '#6366f1', short: 'Непосредств.' },
]

export default function IshikawaSummary({ result }) {
  const sections = TIERS
    .map(s => ({ ...s, nodes: result[s.key] || [] }))
    .filter(s => s.nodes.length > 0)

  if (sections.length === 0) {
    return <div className="result-section-empty">Нет данных для сводки</div>
  }

  // Группируем по category внутри каждой секции
  function groupedByCategory(nodes) {
    const map = {}
    nodes.forEach(n => {
      const cat = n.category || 'Прочее'
      if (!map[cat]) map[cat] = []
      map[cat].push(n)
    })
    return map
  }

  return (
    <div className="sw-ishikawa">

      {/* Проблема */}
      <div className="sw-ishikawa__problem">
        <span className="sw-ishikawa__problem-icon">🐟</span>
        <span>{result.summary || 'Инцидент'}</span>
      </div>

      {/* Сетка категорий */}
      <div className="sw-ishikawa__grid">
        {sections.map(section => (
          <div key={section.key} className="sw-ishikawa__section">
            <div className="sw-ishikawa__section-header" style={{
              background: section.color + '18',
              borderColor: section.color + '40',
              color: section.color,
            }}>
              {section.label}
            </div>
            <div className="sw-ishikawa__section-body">
              {Object.entries(groupedByCategory(section.nodes)).map(([catName, nodes]) => (
                <div key={catName} className="sw-ishikawa__cat-group">
                  <div className="sw-ishikawa__cat-name" style={{ color: section.color }}>
                    {catName}
                  </div>
                  <ul className="sw-ishikawa__causes">
                    {nodes.map((n, i) => (
                      <li key={n.id || i} className="sw-ishikawa__cause">
                        <span className="sw-ishikawa__dot" style={{ background: section.color }} />
                        <span className="sw-ishikawa__cause-text">{n.text}</span>
                        {n.confidence != null && (
                          <span className="sw-ishikawa__conf">{(n.confidence * 100).toFixed(0)}%</span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
