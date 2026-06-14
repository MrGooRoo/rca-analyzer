import React from 'react'
import './AnalysisSteps.css'

const STEPS = [
  { id: 1, label: 'Исходные данные', hint: 'Описание инцидента', target: 'step-data' },
  { id: 2, label: 'Методология', hint: 'Выбор подхода', target: 'step-method' },
  { id: 3, label: 'Результат', hint: 'Выводы и рекомендации', target: 'step-result' },
]

export default function AnalysisSteps({ current = 1, onNavigate }) {
  function go(step) {
    if (!onNavigate) return
    const targetId = STEPS.find(s => s.id === step)?.target
    if (!targetId) return
    const el = document.getElementById(targetId)
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    onNavigate(step)
  }

  return (
    <div className="analysis-steps" role="navigation" aria-label="Этапы анализа">
      <div className="analysis-steps__track" aria-hidden="true" />
      {STEPS.map((step, idx) => {
        const state =
          step.id < current ? 'done' :
          step.id === current ? 'active' : 'pending'
        const clickable = step.id < 3 && current < 3 && !!onNavigate

        return (
          <div key={step.id} className={`analysis-step analysis-step--${state}`}>
            <button
              type="button"
              className="analysis-step__btn"
              onClick={() => clickable && go(step.id)}
              disabled={!clickable}
              aria-current={state === 'active' ? 'step' : undefined}
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
              <span className={`analysis-step__connector analysis-step__connector--${state}`} aria-hidden="true" />
            )}
          </div>
        )
      })}
    </div>
  )
}
