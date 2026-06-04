/**
 * BowtieDiagram — SVG-диаграмма «бабочка» для методологии Bowtie.
 *
 * Структура result.causal_tree (по category):
 *   BOWTIE:HAZARD        — единственный узел-источник
 *   BOWTIE:TOP_EVENT     — центральный узел (бабочка)
 *   BOWTIE:THREAT        — левое крыло (threat nodes)
 *   BOWTIE:PREVENTION    — барьеры предотвращения на левом крыле
 *   BOWTIE:CONSEQUENCE   — правое крыло
 *   BOWTIE:MITIGATION    — барьеры смягчения на правом крыле
 *
 * Если LLM не заполнил category корректно, фаллбэк: root_causes→threats,
 * contributing_causes→barriers, immediate_causes→top_event+consequences.
 */

import React, { useState, useRef, useEffect } from 'react'
import './BowtieDiagram.css'

// ---- Палитра ---------------------------------------------------------------
const C = {
  hazard:       '#a78bfa',   // фиолетовый
  topEvent:     '#f76f6f',   // красный
  threat:       '#fb923c',   // оранжевый
  prevention:   '#facc15',   // жёлтый
  consequence:  '#60a5fa',   // голубой
  mitigation:   '#34d399',   // зелёный
  line:         '#3a3f5c',
  lineDegraded: '#f76f6f',
}

const NODE_W  = 160
const NODE_H  = 44
const R       = 6          // border-radius rect
const CENTER_Y_OFFSET = 0  // top_event центрирован

// ---- Парсер данных ------------------------------------------------------------
function parseBowtieData(result) {
  const tree = result.causal_tree || []

  const byCategory = (cat) =>
    tree.filter(n => n.category?.toUpperCase().includes(cat))

  // Попытка читать из causal_tree по category
  let hazards     = byCategory('HAZARD')
  let topEvents   = byCategory('TOP_EVENT')
  let threats     = byCategory('THREAT')
  let prevention  = byCategory('PREVENTION')
  let consequences= byCategory('CONSEQUENCE')
  let mitigation  = byCategory('MITIGATION')

  // Фаллбэк: если category не заполнен, берём из секций результата
  if (!threats.length)      threats      = result.root_causes         || []
  if (!prevention.length || !mitigation.length) {
    const contrib = result.contributing_causes || []
    if (!prevention.length)  prevention  = contrib.filter((_, i) => i % 2 === 0)
    if (!mitigation.length)  mitigation  = contrib.filter((_, i) => i % 2 !== 0)
  }
  if (!consequences.length) consequences = (result.immediate_causes   || []).slice(1)
  if (!topEvents.length)    topEvents    = (result.immediate_causes   || []).slice(0, 1)

  return { hazards, topEvents, threats, prevention, consequences, mitigation }
}

// ---- Геометрия ---------------------------------------------------------------
function buildLayout(data) {
  const { hazards, topEvents, threats, prevention, consequences, mitigation } = data

  const leftRows  = threats.length     || 1
  const rightRows = consequences.length || 1
  const rows      = Math.max(leftRows, rightRows)

  const VGAP     = 68    // вертикальный шаг между узлами
  const SVG_H    = Math.max(360, rows * VGAP + 160)
  const CY       = SVG_H / 2            // центральная Y

  // X-колонки (6 столбцов):
  // [threats] [prevention] [TOP_EVENT+HAZARD] [mitigation] [consequences]
  const COL = {
    threat:      80  + NODE_W / 2,
    prevention:  260 + NODE_W / 2,
    center:      440 + NODE_W / 2,
    mitigation:  620 + NODE_W / 2,
    consequence: 800 + NODE_W / 2,
  }
  const SVG_W = 1010

  // Генерик размещения списка по Y
  function spreadY(count) {
    if (count === 1) return [CY]
    const total = (count - 1) * VGAP
    return Array.from({ length: count }, (_, i) => CY - total / 2 + i * VGAP)
  }

  // Ноды c координатами
  const topNode = topEvents[0]
  const hazNode = hazards[0]

  const topPos = { x: COL.center, y: CY }

  const threatPos  = spreadY(threats.length).map((y, i) => ({ node: threats[i],      x: COL.threat,      y }))
  const prevPos    = spreadY(prevention.length).map((y, i) => ({ node: prevention[i],  x: COL.prevention, y }))
  const consPos    = spreadY(consequences.length).map((y, i) => ({ node: consequences[i], x: COL.consequence, y }))
  const mitiPos    = spreadY(mitigation.length).map((y, i) => ({ node: mitigation[i],  x: COL.mitigation, y }))

  return { topNode, hazNode, topPos, threatPos, prevPos, consPos, mitiPos, SVG_W, SVG_H, CY }
}

// ---- Главный компонент ----------------------------------------------------------
export default function BowtieDiagram({ result }) {
  const data   = parseBowtieData(result)
  const layout = buildLayout(data)
  const { topNode, hazNode, topPos, threatPos, prevPos, consPos, mitiPos, SVG_W, SVG_H, CY } = layout

  const [tooltip, setTooltip] = useState(null)  // { text, x, y }
  const svgRef = useRef(null)

  function showTip(e, node) {
    const rect = svgRef.current.getBoundingClientRect()
    setTooltip({
      text: `${node.text}\nУверенность: ${(node.confidence * 100).toFixed(0)}%`,
      x: e.clientX - rect.left,
      y: e.clientY - rect.top - 10,
    })
  }

  return (
    <div className="bowtie-wrap">
      <div className="bowtie-legend">
        {[
          { color: C.threat,      label: 'Yгрозы' },
          { color: C.prevention,  label: 'Барьеры предотвр.' },
          { color: C.topEvent,    label: 'Топ-событие' },
          { color: C.mitigation,  label: 'Барьеры смягч.' },
          { color: C.consequence, label: 'Последствия' },
          { color: C.hazard,      label: 'Опасный фактор' },
        ].map(l => (
          <span key={l.label} className="legend-item">
            <span className="legend-dot" style={{ background: l.color }} />
            {l.label}
          </span>
        ))}
      </div>

      <div className="bowtie-svg-wrap">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${SVG_W} ${SVG_H}`}
          width="100%"
          style={{ maxHeight: '520px' }}
          onMouseLeave={() => setTooltip(null)}
        >
          <defs>
            <marker id="arr" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
              <path d="M0,0 L0,6 L8,3 z" fill={C.line} />
            </marker>
            <filter id="glow">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
            </filter>
          </defs>

          {/* ========== ЛЕВЫЕ СТРЕЛКИ: threat → prevention → top_event ========== */}
          {threatPos.map((tp, i) => {
            const pp = prevPos[i] || prevPos[Math.floor(prevPos.length / 2)]
            return (
              <g key={`tl-${i}`}>
                <Line x1={tp.x + NODE_W/2} y1={tp.y} x2={pp.x - NODE_W/2} y2={pp.y} />
                <Line x1={pp.x + NODE_W/2} y1={pp.y} x2={topPos.x - NODE_W/2} y2={topPos.y} />
              </g>
            )
          })}
          {/* если барьеров больше чем угроз, дорисовываем доп. линии */}
          {prevPos.map((pp, i) => {
            if (i < threatPos.length) return null
            return (
              <g key={`pl-${i}`}>
                <Line x1={pp.x + NODE_W/2} y1={pp.y} x2={topPos.x - NODE_W/2} y2={topPos.y} />
              </g>
            )
          })}

          {/* ========== ПРАВЫЕ СТРЕЛКИ: top_event → mitigation → consequence ========== */}
          {consPos.map((cp, i) => {
            const mp = mitiPos[i] || mitiPos[Math.floor(mitiPos.length / 2)]
            return (
              <g key={`cr-${i}`}>
                {mp
                  ? <><Line x1={topPos.x + NODE_W/2} y1={topPos.y} x2={mp.x - NODE_W/2} y2={mp.y} />
                       <Line x1={mp.x + NODE_W/2} y1={mp.y} x2={cp.x - NODE_W/2} y2={cp.y} /></>
                  : <Line x1={topPos.x + NODE_W/2} y1={topPos.y} x2={cp.x - NODE_W/2} y2={cp.y} />
                }
              </g>
            )
          })}

          {/* ========== УЗЛЫ ========== */}

          {/* Threats */}
          {threatPos.map((tp, i) => (
            <NodeRect
              key={tp.node?.id || i}
              x={tp.x} y={tp.y}
              label={tp.node?.text || '?'}
              fill={C.threat}
              onHover={(e) => tp.node && showTip(e, tp.node)}
              onLeave={() => setTooltip(null)}
              degraded={tp.node?.confidence < 0.3}
            />
          ))}

          {/* Prevention barriers */}
          {prevPos.map((pp, i) => (
            <BarrierRect
              key={pp.node?.id || i}
              x={pp.x} y={pp.y}
              label={pp.node?.text || '?'}
              fill={C.prevention}
              onHover={(e) => pp.node && showTip(e, pp.node)}
              onLeave={() => setTooltip(null)}
              degraded={pp.node?.confidence < 0.3}
            />
          ))}

          {/* Hazard (над top_event) */}
          {hazNode && (
            <NodeRect
              x={topPos.x} y={topPos.y - 90}
              label={hazNode.text}
              fill={C.hazard}
              onHover={(e) => showTip(e, hazNode)}
              onLeave={() => setTooltip(null)}
            />
          )}

          {/* TOP EVENT — центральный узел */}
          <NodeRect
            x={topPos.x} y={topPos.y}
            label={topNode?.text || 'Топ-событие'}
            fill={C.topEvent}
            isCenter
            onHover={(e) => topNode && showTip(e, topNode)}
            onLeave={() => setTooltip(null)}
          />

          {/* Mitigation barriers */}
          {mitiPos.map((mp, i) => (
            <BarrierRect
              key={mp.node?.id || i}
              x={mp.x} y={mp.y}
              label={mp.node?.text || '?'}
              fill={C.mitigation}
              onHover={(e) => mp.node && showTip(e, mp.node)}
              onLeave={() => setTooltip(null)}
              degraded={mp.node?.confidence < 0.3}
            />
          ))}

          {/* Consequences */}
          {consPos.map((cp, i) => (
            <NodeRect
              key={cp.node?.id || i}
              x={cp.x} y={cp.y}
              label={cp.node?.text || '?'}
              fill={C.consequence}
              onHover={(e) => cp.node && showTip(e, cp.node)}
              onLeave={() => setTooltip(null)}
            />
          ))}

          {/* Тултип */}
          {tooltip && (
            <Tooltip x={tooltip.x} y={tooltip.y} text={tooltip.text} />
          )}
        </svg>
      </div>

      {/* Текстовый список для проверки */}
      <details className="bowtie-raw">
        <summary>Список узлов</summary>
        <div className="bowtie-raw-grid">
          {[  { label: 'Yгрозы', nodes: data.threats, color: C.threat },
              { label: 'Барьеры предотвр.', nodes: data.prevention, color: C.prevention },
              { label: 'Топ-событие', nodes: data.topEvents, color: C.topEvent },
              { label: 'Барьеры смягч.', nodes: data.mitigation, color: C.mitigation },
              { label: 'Последствия', nodes: data.consequences, color: C.consequence },
          ].map(col => (
            <div key={col.label}>
              <div className="raw-col-label" style={{ color: col.color }}>{col.label}</div>
              {col.nodes.map((n, i) => (
                <div key={n?.id || i} className="raw-node">
                  {n?.text}
                  <span className="raw-conf">{n ? (n.confidence * 100).toFixed(0) + '%' : ''}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      </details>
    </div>
  )
}

// ---- СВГ-примитивы ---------------------------------------------------------------

function Line({ x1, y1, x2, y2, degraded }) {
  return (
    <line
      x1={x1} y1={y1} x2={x2} y2={y2}
      stroke={degraded ? C.lineDegraded : C.line}
      strokeWidth={degraded ? 1.5 : 1.5}
      strokeDasharray={degraded ? '5 4' : undefined}
      markerEnd="url(#arr)"
      opacity={0.6}
    />
  )
}

function NodeRect({ x, y, label, fill, isCenter, onHover, onLeave, degraded }) {
  const w = isCenter ? NODE_W + 20 : NODE_W
  const h = isCenter ? NODE_H + 8  : NODE_H
  const textLines = wrapText(label, isCenter ? 22 : 20)
  const totalH = textLines.length * 16

  return (
    <g
      transform={`translate(${x - w/2}, ${y - h/2})`}
      onMouseEnter={onHover}
      onMouseLeave={onLeave}
      style={{ cursor: 'pointer' }}
    >
      <rect
        width={w} height={Math.max(h, totalH + 12)}
        rx={R} ry={R}
        fill={fill}
        opacity={degraded ? 0.45 : 0.88}
        filter={isCenter ? 'url(#glow)' : undefined}
        stroke={isCenter ? '#fff' : 'none'}
        strokeWidth={isCenter ? 1.5 : 0}
      />
      {textLines.map((line, i) => (
        <text
          key={i}
          x={w/2}
          y={Math.max(h, totalH + 12)/2 - (textLines.length - 1) * 8 + i * 16}
          textAnchor="middle"
          dominantBaseline="middle"
          fill="#fff"
          fontSize={isCenter ? 12 : 11}
          fontWeight={isCenter ? 700 : 500}
          fontFamily="system-ui, sans-serif"
        >{line}</text>
      ))}
    </g>
  )
}

function BarrierRect({ x, y, label, fill, onHover, onLeave, degraded }) {
  const w = 32
  const h = 80
  const textLines = wrapText(label, 12)

  return (
    <g
      transform={`translate(${x - w/2}, ${y - h/2})`}
      onMouseEnter={onHover}
      onMouseLeave={onLeave}
      style={{ cursor: 'pointer' }}
    >
      {/* Вертикальная планка-барьер */}
      <rect
        width={w} height={h}
        rx={3} ry={3}
        fill={fill}
        opacity={degraded ? 0.35 : 0.82}
        stroke={degraded ? C.lineDegraded : 'none'}
        strokeWidth={degraded ? 2 : 0}
        strokeDasharray={degraded ? '4 3' : undefined}
      />
      {textLines.map((line, i) => (
        <text
          key={i}
          x={w/2}
          y={h/2 - (textLines.length - 1) * 7 + i * 14}
          textAnchor="middle"
          dominantBaseline="middle"
          fill="#fff"
          fontSize={9.5}
          fontWeight={600}
          fontFamily="system-ui, sans-serif"
          transform={`rotate(-90, ${w/2}, ${h/2 - (textLines.length - 1) * 7 + i * 14})`}
        >{line}</text>
      ))}
    </g>
  )
}

function Tooltip({ x, y, text }) {
  const lines = text.split('\n')
  const w = Math.min(220, Math.max(...lines.map(l => l.length * 7)) + 20)
  const h = lines.length * 18 + 12

  return (
    <g transform={`translate(${Math.min(x, 800)}, ${Math.max(y - h, 4)})`} style={{ pointerEvents: 'none' }}>
      <rect width={w} height={h} rx={5} ry={5} fill="#1e2235" opacity={0.95} />
      {lines.map((l, i) => (
        <text key={i} x={10} y={16 + i * 18} fill="#e2e8f0" fontSize={11} fontFamily="system-ui, sans-serif">{l}</text>
      ))}
    </g>
  )
}

// ---- Утилита переноса текста --------------------------------------------------
function wrapText(text, maxChars) {
  if (!text) return ['']
  const words = text.split(' ')
  const lines = []
  let cur = ''
  for (const w of words) {
    if ((cur + ' ' + w).trim().length > maxChars && cur) {
      lines.push(cur.trim())
      cur = w
    } else {
      cur = (cur + ' ' + w).trim()
    }
  }
  if (cur) lines.push(cur.trim())
  return lines.slice(0, 4)  // макс 4 строки
}
