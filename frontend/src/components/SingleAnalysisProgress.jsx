/**
 * SingleAnalysisProgress — прогресс одиночного анализа через SSE.
 */
import { Card, Badge } from './ui/Card.jsx'
import { methodologyMeta } from '../lib/methodologies.js'

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
    <Card className={`my-4 p-5 ${
      isError
        ? 'ring-rose-500/30 bg-gradient-to-r from-rose-500/10 via-slate-900/60 to-slate-900/60'
        : 'ring-indigo-500/30 bg-gradient-to-r from-indigo-500/10 via-slate-900/60 to-slate-900/60'
    }`}>
      <div className="flex items-start justify-between gap-4 mb-4 flex-wrap">
        <div>
          <div className="text-xs font-bold uppercase tracking-wider text-indigo-400 mb-1">Анализ</div>
          <div className="flex items-center gap-2 text-lg font-bold text-white tracking-tight">
            <span className="text-lg leading-none" aria-hidden="true">{meta.icon}</span>
            {methodologyName || meta.name}
          </div>
        </div>
        <Badge tone={isError ? 'rose' : isDone ? 'emerald' : 'sky'}>
          {isError ? 'ошибка' : isDone ? 'готово' : 'в работе'}
        </Badge>
      </div>

      <div className="h-2 bg-slate-800 rounded-full overflow-hidden mb-4 border border-white/5" aria-label={`Прогресс ${percent}%`}>
        <div
          className={`h-full rounded-full transition-[width] duration-300 ${
            isError ? 'bg-gradient-to-r from-rose-500 to-amber-500' : 'bg-gradient-to-r from-indigo-500 to-emerald-500'
          }`}
          style={{ width: `${Math.max(0, Math.min(100, percent || 0))}%` }}
        />
      </div>

      <div className="flex items-center justify-between gap-2 flex-wrap">
        <span className="text-sm text-slate-400">{stageMessage}</span>
        <span className="text-sm font-semibold text-white tabular-nums">{percent}%</span>
      </div>
    </Card>
  )
}
