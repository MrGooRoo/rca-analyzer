/**
 * SingleAnalysisProgress — прогресс одиночного анализа через SSE.
 *
 * progress: { phase, stage, percent, message, methodologyName, methodologyKey }
 */

import { Card, Badge } from './ui/Card.jsx'
import { methodologyMeta } from '../lib/methodologies.js'
import './SingleAnalysisProgress.css'

const STAGE_LABELS = {
  started: 'Запуск анализа…',
  preparing: 'Подготовка промпта',
  llm: 'Генерация ответа модели',
  parsing: 'Обработка результата',
}

export default function SingleAnalysisProgress({ progress }) {
  if (!progress) return null

  const { phase, stage, percent, message, methodologyName, methodologyKey } = progress
  const meta = methodologyMeta(methodologyKey)
  const stageMessage = message || STAGE_LABELS[stage] || STAGE_LABELS.started

  const isError = phase === 'error'
  const isDone = phase === 'done'

  return (
    <Card className={`sap-root ${isError ? 'sap-root--error' : ''}`}>
      <div className="sap-header">
        <div>
          <div className="sap-eyebrow">Анализ</div>
          <div className="sap-title">
            <span className="sap-method-icon" aria-hidden="true">
              {meta.icon}
            </span>
            {methodologyName || meta.name}
          </div>
        </div>
        <Badge
          tone={isError ? 'rose' : isDone ? 'emerald' : 'sky'}
        >
          {isError ? 'ошибка' : isDone ? 'готово' : 'в работе'}
        </Badge>
      </div>

      <div className="sap-bar-track" aria-label={`Прогресс ${percent}%`}>
        <div
          className="sap-bar-fill"
          style={{ width: `${Math.max(0, Math.min(100, percent || 0))}%` }}
        />
      </div>

      <div className="sap-footer">
        <span className="sap-stage">{stageMessage}</span>
        <span className="sap-percent">{percent}%</span>
      </div>
    </Card>
  )
}
