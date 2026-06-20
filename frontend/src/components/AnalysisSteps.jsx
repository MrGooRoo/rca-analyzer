import React from 'react'

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
    <div className="sticky top-[52px] z-50 -mx-4 sm:-mx-6 lg:-mx-8 mb-6 bg-slate-950/80 backdrop-blur-md border-b border-slate-800 shadow-sm"
      style={{}}>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
        {STEPS.map((step, idx) => {
          const state = allDone
            ? 'done'
            : step.id < current ? 'done'
            : step.id === current ? 'active'
            : 'pending'

          const clickable = step.id <= 2 && current < 3

          const numClass = {
            done: 'border-emerald-400 bg-emerald-500/10 text-emerald-400',
            active: 'border-indigo-400 bg-indigo-500/10 text-indigo-400 shadow-[0_0_0_3px_rgba(99,102,241,0.10)]',
            pending: 'border-slate-700 bg-slate-800 text-slate-500',
          }[state]

          const labelClass = {
            done: 'text-slate-400',
            active: 'text-white',
            pending: 'text-slate-500',
          }[state]

          return (
            <div key={step.id} className="flex items-center gap-3">
              <button
                type="button"
                className={`flex items-center gap-3 w-full text-left rounded-xl p-2 transition ${
                  clickable ? 'hover:bg-slate-800/60' : ''
                }`}
                onClick={() => clickable && go(step.id)}
                disabled={!clickable}
                aria-current={!allDone && state === 'active' ? 'step' : undefined}
                title={clickable ? `Перейти к: ${step.label}` : undefined}
              >
                <span className={`h-8 w-8 rounded-full flex items-center justify-center text-sm font-bold border-2 transition shrink-0 ${numClass}`}>
                  {state === 'done' ? '\u2713' : step.id}
                </span>
                <span className="flex flex-col gap-0.5 min-w-0">
                  <span className={`text-sm font-bold truncate ${labelClass}`}>{step.label}</span>
                  <span className="text-xs text-slate-500 truncate">{step.hint}</span>
                </span>
              </button>
              {idx < STEPS.length - 1 && (
                <span className={`hidden sm:block flex-[0_0_32px] h-0.5 rounded-full transition ${state === 'done' ? 'bg-emerald-400' : 'bg-slate-700'}`} aria-hidden="true" />
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
