/**
 * IshikawaSummary — сводка результатов Исикавы.
 *
 * Формат (как в sandbox):
 *   1. Вводный текст (summary)
 *   2. Центральная проблема (блок-баннер)
 *   3. Сетка 2×3 категорий 6M (Люди, Методы, Машины, Материалы, Измерения, Среда)
 *   4. Рекомендации
 */
import React from 'react'
import './IshikawaSummary.css'

/** Маппинг значений category из БД → отображаемое имя */
const CATEGORY_MAP = {
  человек:     'Люди',
  man:         'Люди',
  people:      'Люди',
  метод:       'Методы',
  method:      'Методы',
  process:     'Методы',
  машина:      'Машины',
  machine:     'Машины',
  equipment:   'Машины',
  материал:    'Материалы',
  material:    'Материалы',
  среда:       'Среда',
  environment: 'Среда',
  измерение:   'Измерения',
  measurement: 'Измерения',
  управление:  'Управление',
  management:  'Управление',
}

/** Канонический порядок категорий 6M */
const CANONICAL = ['Люди', 'Методы', 'Машины', 'Материалы', 'Измерения', 'Среда', 'Управление']

export default function IshikawaSummary({ result }) {
  const summary = result.summary || ''
  const problem = summary
  const recs = result.recommendations || []

  // Собираем все причины из contributing + root
  const allCauses = [
    ...(result.contributing_causes || []),
    ...(result.root_causes || []),
  ]

  // Группируем по отображаемому имени категории
  const groups = {}
  allCauses.forEach(n => {
    const rawCat = (n.category || '').trim().toLowerCase()
    const catName = CATEGORY_MAP[rawCat] || rawCat || 'Прочее'
    if (!groups[catName]) groups[catName] = []
    // Дедупликация по тексту
    if (!groups[catName].some(ex => ex.text === n.text)) {
      groups[catName].push(n)
    }
  })

  // Сортируем в каноническом порядке
  const sorted = Object.entries(groups).sort((a, b) => {
    const ia = CANONICAL.indexOf(a[0])
    const ib = CANONICAL.indexOf(b[0])
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
  })

  if (sorted.length === 0) {
    return <div className="result-section-empty">Нет данных для сводки</div>
  }

  return (
    <div className="sw-ishikawa">
      {/* 1. Вводный текст */}
      <div className="sw-ishikawa__summary">{summary}</div>

      {/* 2. Центральная проблема */}
      <div className="sw-ishikawa__problem">
        <div className="sw-ishikawa__fish-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <path d="M2 12C2 12 5 8 9 8C13 8 16 10 18 11C20 12 22 12 22 12C22 12 20 12 18 13C16 14 13 16 9 16C5 16 2 12 2 12Z"
              fill="currentColor" opacity="0.8"/>
            <circle cx="6" cy="12" r="1" fill="#0a0e17" />
          </svg>
        </div>
        {problem}
      </div>

      {/* 3. Сетка категорий 2×3 */}
      <div className="sw-ishikawa__grid">
        {sorted.map(([catName, nodes]) => (
          <div key={catName} className="sw-ishikawa__card">
            <div className="sw-ishikawa__card-title">{catName}</div>
            <ul className="sw-ishikawa__card-list">
              {nodes.map((n, i) => (
                <li key={n.id || i} className="sw-ishikawa__card-item">
                  <span className="sw-ishikawa__bullet">▶</span>
                  <span className="sw-ishikawa__card-text">{n.text}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      {/* 4. Рекомендации */}
      {recs.length > 0 && (
        <div className="sw-ishikawa__recs">
          <div className="sw-ishikawa__recs-title">РЕКОМЕНДАЦИИ</div>
          <div className="sw-ishikawa__recs-list">
            {recs.map((rec, i) => (
              <div key={rec.id || i} className="sw-ishikawa__rec-item">
                <div className="sw-ishikawa__rec-num">{i + 1}</div>
                <div className="sw-ishikawa__rec-text">{rec.text}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
