import React, { useState } from 'react'
import BowtieDiagram from './BowtieDiagram.jsx'
import { methodologyMeta, METHODOLOGY_LABELS } from '../lib/methodologies.js'
import { Badge, Card, CardBody } from './ui/Card.jsx'

const PRIORITY_COLORS = {
  high:   'bg-rose-500',
  medium: 'bg-amber-500',
  low:    'bg-emerald-500',
}

export default function CompareView({ comparison }) {
  const [activeTab, setActiveTab] = useState(
    comparison.results.length > 0 ? comparison.results[0].result_id : null
  )

  const activeResult = comparison.results.find(r => r.result_id === activeTab)
  const isBowtie = activeResult?.methodology === 'bowtie'

  return (
    <div className="space-y-4" id="step-result">
      {/* Заголовок */}
      <div className="flex items-center gap-2 text-xl font-semibold text-white">
        <span className="text-2xl">⚖️</span>
        Сравнение методологий
        <Badge tone="violet">{comparison.results.length} методик</Badge>
      </div>

      {/* Общая сводка */}
      {comparison.summary && (
        <Card>
          <CardBody>
            <div className="text-xs uppercase tracking-wider font-semibold text-indigo-400 mb-2">📋 Сводка сравнения</div>
            <p className="text-sm text-slate-300">{comparison.summary}</p>
          </CardBody>
        </Card>
      )}

      {/* Общие рекомендации */}
      {comparison.common_recommendations?.length > 0 && (
        <div className="space-y-3">
          <div className="text-xs uppercase tracking-wider font-semibold text-slate-400">
            🤝 Общие рекомендации ({comparison.common_recommendations.length})
          </div>
          <div className="space-y-3">
            {comparison.common_recommendations.map(r => (
              <div key={r.id} className="rounded-lg bg-slate-950/60 ring-1 ring-slate-800 p-3">
                <div className="flex items-center gap-2 text-sm mb-1">
                  <span className={`h-2 w-2 rounded-full ${PRIORITY_COLORS[r.priority] || 'bg-slate-500'}`} />
                  <span className="text-xs font-semibold uppercase text-slate-300">{r.priority}</span>
                  <span className="text-xs text-slate-400">{r.category}</span>
                  {r.responsible && <span className="text-xs text-slate-500">{r.responsible}</span>}
                </div>
                <p className="text-sm text-slate-300">{r.text}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Различающиеся причины */}
      {comparison.differing_causes && Object.keys(comparison.differing_causes).length > 0 && (
        <div className="space-y-3">
          <div className="text-xs uppercase tracking-wider font-semibold text-slate-400">⚡ Различающиеся выводы</div>
          <div className="grid gap-3 md:grid-cols-2">
            {Object.entries(comparison.differing_causes).map(([methodology, causes]) => (
              <div key={methodology} className="rounded-lg bg-slate-950/60 ring-1 ring-slate-800 p-3">
                <div className="mb-2">
                  <Badge tone={methodologyMeta(methodology).badgeTone}>{methodologyMeta(methodology).icon} {METHODOLOGY_LABELS[methodology] || methodology}</Badge>
                </div>
                <ul className="space-y-1.5 text-sm text-slate-300">
                  {causes.map((cause, i) => (
                    <li key={i} className="flex gap-2"><span className="text-indigo-400">▸</span>{cause}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Side-by-side результаты */}
      <div className="space-y-3">
        <div className="text-xs uppercase tracking-wider font-semibold text-slate-400">📊 Детальные результаты по каждой методике</div>

        {/* Табы */}
        <div className="flex gap-1 rounded-xl bg-slate-800 p-1">
          {comparison.results.map(r => (
            <button
              key={r.result_id}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center gap-1.5 min-w-0 ${
                r.result_id === activeTab
                  ? 'bg-slate-700 text-white shadow'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
              }`}
              onClick={() => setActiveTab(r.result_id)}
            >
              <span>{methodologyMeta(r.methodology).icon}</span>
              <span className="truncate">{METHODOLOGY_LABELS[r.methodology] || r.methodology}</span>
              <span className="text-xs text-slate-500">{(r.confidence_avg * 100).toFixed(0)}%</span>
            </button>
          ))}
        </div>

        {/* Активный результат */}
        {activeResult && (
          <div className="rounded-xl bg-slate-950/60 ring-1 ring-slate-800 p-4 space-y-4">
            <div className="flex items-center gap-3 text-xs flex-wrap">
              <div className="flex items-center gap-1"><span className="text-slate-500">Модель:</span><span className="text-slate-200 font-medium">{activeResult.model_used.split('/')[1] || activeResult.model_used}</span></div>
              <div className="flex items-center gap-1"><span className="text-slate-500">Токены:</span><span className="text-slate-200 font-medium">{activeResult.tokens_used}</span></div>
              <div className="flex items-center gap-1"><span className="text-slate-500">Уверенность:</span><span className="text-slate-200 font-medium">{(activeResult.confidence_avg * 100).toFixed(0)}%</span></div>
              <div className="flex items-center gap-1"><span className="text-slate-500">ID:</span><span className="text-slate-200 font-medium font-mono">#{activeResult.result_id.slice(0, 8)}</span></div>
            </div>

            <div className="rounded-xl bg-slate-900/60 ring-1 ring-slate-800 p-4 text-sm text-slate-300 italic">
              {activeResult.summary}
            </div>

            <CompareCausalTree result={activeResult} />

            {isBowtie && <BowtieDiagram result={activeResult} />}

            {activeResult.recommendations?.length > 0 && (
              <div className="space-y-3">
                <div className="text-xs uppercase tracking-wider font-semibold text-slate-400">
                  💡 Рекомендации ({activeResult.recommendations.length})
                </div>
                <div className="space-y-3">
                  {activeResult.recommendations.map(r => (
                    <div key={r.id} className="rounded-lg bg-slate-950/60 ring-1 ring-slate-800 p-3">
                      <div className="flex items-center gap-2 text-sm mb-1">
                        <span className={`h-2 w-2 rounded-full ${PRIORITY_COLORS[r.priority] || 'bg-slate-500'}`} />
                        <span className="text-xs font-semibold uppercase text-slate-300">{r.priority}</span>
                        <span className="text-xs text-slate-400">{r.category}</span>
                        {r.responsible && <span className="text-xs text-slate-500">{r.responsible}</span>}
                      </div>
                      <p className="text-sm text-slate-300">{r.text}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function CompareCausalTree({ result }) {
  const sections = [
    { key: 'root_causes',         label: 'Корневые причины',          color: '#f43f5e' },
    { key: 'contributing_causes', label: 'Способствующие факторы',  color: '#f59e0b' },
    { key: 'immediate_causes',    label: 'Непосредственные причины', color: '#6366f1' },
  ]
  const hasAny = sections.some(s => result[s.key]?.length > 0)
  if (!hasAny) return null

  return (
    <div className="space-y-4">
      {sections.map(s => {
        const nodes = result[s.key]
        if (!nodes?.length) return null
        return (
          <div key={s.key} className="space-y-2">
            <div className="text-xs uppercase tracking-wider font-semibold" style={{ color: s.color }}>{s.label}</div>
            {nodes.map(n => (
              <div key={n.id} className="rounded-lg bg-slate-950/60 ring-1 ring-slate-800 p-3">
                <div className="text-sm text-slate-200">{n.text}</div>
                <div className="flex items-center gap-2 mt-1">
                  <span className="inline-flex items-center rounded-md bg-slate-800 px-2 py-0.5 text-xs text-slate-400">{n.category}</span>
                  <span className="text-xs text-slate-500">{(n.confidence * 100).toFixed(0)}%</span>
                </div>
              </div>
            ))}
          </div>
        )
      })}
    </div>
  )
}
