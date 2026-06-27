import React from 'react'
import { STEPS } from './formConstants.js'

export default function StepIndicator({ step, busy, onGoTo }) {
  return (
    <div className="incident-steps">
      {STEPS.map(s => {
        const isActive = step === s.num
        const isDone = step > s.num
        return (
          <button key={s.num} type="button"
            className={
              `incident-step${isActive ? ' incident-step--active' : ''}${isDone ? ' incident-step--done' : ''}`
            }
            onClick={() => isDone && onGoTo?.(s.num)}
            disabled={busy}>
            <span className="incident-step__icon">{isDone ? '✓' : s.icon}</span>
            <span className="incident-step__label">{s.label}</span>
          </button>
        )
      })}
      <div className="incident-steps__track">
        <div className="incident-steps__fill" style={{ width: `${((step - 1) / 2) * 100}%` }} />
      </div>
    </div>
  )
}
