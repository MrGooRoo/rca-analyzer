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
        const y = el.getBoundingClientRect().top + window.scrollY - 120
        window.scrollTo({ top: y, behavior: 'smooth' })
      }
    }
    if (onNavigate) onNavigate(step)
  }

  const allDone = current === 3

  return (
    <div className="analysis-steps">
      <div className="analysis-steps__inner">
        {STEPS.map((step, idx) => {
          const state = allDone
            ? 'done'
            : step.id < current ? 'done'
            : step.id === current ? 'active'
            : 'pending'

          const clickable = step.id <= 2 && current < 3

          return (
            <div key={step.id} className="analysis-step">
              <button
                type="button"
                className={`analysis-step__button ${clickable ? 'analysis-step__button--clickable' : ''}`}
                onClick={() => clickable && go(step.id)}
                disabled={!clickable}
                aria-current={!allDone && state === 'active' ? 'step' : undefined}
                title={clickable ? `Перейти к: ${step.label}` : undefined}
              >
                <span className={`analysis-step__number analysis-step__number--${state}`}>
                  {state === 'done' ? '\u2713' : step.id}
                </span>
                <span className="analysis-step__text">
                  <span className={`analysis-step__label analysis-step__label--${state}`}>{step.label}</span>
                  <span className="analysis-step__hint">{step.hint}</span>
                </span>
              </button>
              {idx < STEPS.length - 1 && (
                <span className={`analysis-step__divider analysis-step__divider--${state === 'done' ? 'done' : 'pending'}`} aria-hidden="true" />
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
