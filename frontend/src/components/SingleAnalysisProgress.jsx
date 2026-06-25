/**
 * SingleAnalysisProgress — прогресс одиночного анализа через SSE.
 */
import { Card, Badge } from './ui/Card.jsx'
import { methodologyMeta } from '../lib/methodologies.js'
import { HelpCircle, Ribbon, Fish, TreePine, Cog } from 'lucide-react'
import './SingleAnalysisProgress.css'

const METHODOLOGY_ICONS = {
  '❓': HelpCircle,
  '🎀': Ribbon,
  '🐟': Fish,
  '🌳': TreePine,
  '⚙️': Cog,
}

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
  const safePercent = Math.max(0, Math.min(100, percent || 0))

  return (
    <Card className={`single-analysis-progress ${isError ? 'single-analysis-progress--error' : 'single-analysis-progress--indigo'}`}>
      <div className="single-analysis-progress__header">
        <div className="single-analysis-progress__title-group">
          <div className="single-analysis-progress__eyebrow">Анализ</div>
          <div className="single-analysis-progress__title">
            <span className="single-analysis-progress__icon" aria-hidden="true">{(() => { const Ic = METHODOLOGY_ICONS[meta.icon]; return Ic ? <Ic size={14} /> : null; })()}</span>
            {methodologyName || meta.name}
          </div>
        </div>
        <Badge tone={isError ? 'rose' : isDone ? 'emerald' : 'sky'}>
          {isError ? 'ошибка' : isDone ? 'готово' : 'в работе'}
        </Badge>
      </div>

      <div className="single-analysis-progress__bar" aria-label={`Прогресс ${safePercent}%`}>
        <div
          className={`single-analysis-progress__bar-fill ${isError ? 'single-analysis-progress__bar-fill--error' : ''}`}
          style={{ width: `${safePercent}%` }}
        />
      </div>

      <div className="single-analysis-progress__footer">
        <span className="single-analysis-progress__message">{stageMessage}</span>
        <span className="single-analysis-progress__percent">{safePercent}%</span>
      </div>
    </Card>
  )
}
