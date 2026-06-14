import React from 'react'
import './AnalysisSteps.css'

const STEPS = [
  { id: 1, label: 'Исходные данные', hint: 'Описание инцидента', target: 'step-data' },
  { id: 2, label: 'Методология', hint: 'Выбор подхода', target: 'step-method' },
  { id: 3, label: 'Результат', hint: 'Выводы и рекомендации', target: 'step-result' },
]

export default function AnalysisSteps({ current = 1, onNavigate }) {
  function go(step) {
    const targetId = STEPS.find(s => s.id === step)?.target
    if (targetId) {
      const el = document.getElementById(targetId)
      if (el) {
        // отступ 52px (хедер) + 52px (sticky степпер) чтобы якорь не уехал под панель
        const y = el.getBoundingClientRect().top + window.scrollY - 120
        window.scrollTo({ top: y, behavior: 'smooth' })
      }
    }
    if (onNavigate) onNavigate(step)
  }

  return (
    <div className="analysis-steps-sticky">
      <div className="analysis-steps" role="navigation" aria-label="Этапы анализа">
        <div className="analysis-steps__track" aria-hidden="true" />
        {STEPS.map((step, idx) => {
          const state =
            step.id < current ? 'done' :
            step.id === current ? 'active' : 'pending'
          // шаги 1 и 2 кликабельны пока не показан результат (current < 3)
          const clickable = step.id <= 2 && current < 3

          return (
            <div key={step.id} className={`analysis-step analysis-step--${state}`}>
              <button
                type="button"
                className="analysis-step__btn"
                onClick={() => clickable && go(step.id)}
                disabled={!clickable}
                aria-current={state === 'active' ? 'step' : undefined}
                title={clickable ? `Перейти к: ${step.label}` : undefined}
              >
                <span className="analysis-step__num">
                  {state === 'done' ? '✓' : step.id}
                </span>
                <span className="analysis-step__body">
                  <span className="analysis-step__label">{step.label}</span>
                  <span className="analysis-step__hint">{step.hint}</span>
                </span>
              </button>
              {idx < STEPS.length - 1 && (
                <span
                  className={`analysis-step__connector${state === 'done' ? ' analysis-step__connector--done' : ''}`}
                  aria-hidden="true"
                />
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
