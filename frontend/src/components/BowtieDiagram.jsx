/**
 * BowtieDiagram v6
 *
 * Fixes:
 *   1. Tooltip: position:fixed, смещение -50%/-100% + offset 12px над курсором,
 *      clamp чтобы не уходил за край viewport
 *   2. Барьеры (.bt-col--mid): justify-content:space-evenly, padding сверху/снизу
 *      чтобы первая карточка не выходила за canvas
 *   3. Центральная карточка: align-self:center в bt-col--top
 *   4. SVG: width/height берём offsetWidth/offsetHeight (без decimal),
 *      overflow:visible на svg и canvas для линий у краёв
 */
import React, { useRef, useState, useEffect, useCallback } from 'react'
import './BowtieDiagram.css'

const P = {
  hazard:      { bg:'rgba(167,139,250,.18)', border:'rgba(167,139,250,.5)',  dot:'#a78bfa', text:'#ede9fe' },
  topEvent:    { bg:'rgba(248,113,113,.22)', border:'rgba(248,113,113,.6)',  dot:'#f87171', text:'#fff1f2' },
  threat:      { bg:'rgba(251,146,60,.18)',  border:'rgba(251,146,60,.5)',   dot:'#fb923c', text:'#fff7ed' },
  prevention:  { bg:'rgba(250,204,21,.15)',  border:'rgba(250,204,21,.45)',  dot:'#facc15', text:'#fefce8' },
  mitigation:  { bg:'rgba(52,211,153,.15)',  border:'rgba(52,211,153,.45)',  dot:'#34d399', text:'#ecfdf5' },
  consequence: { bg:'rgba(96,165,250,.16)',  border:'rgba(96,165,250,.45)',  dot:'#60a5fa', text:'#eff6ff' },
}

const LEGEND = [
  ['threat','Угрозы'], ['prevention','Барьеры пред.'],
  ['topEvent','Топ-событие'], ['mitigation','Барьеры смяг.'],
  ['consequence','Последствия'], ['hazard','Опасный фактор'],
]

function parse(result) {
  const tree = result.causal_tree || []
  const by = c => tree.filter(n => n.category?.toUpperCase().includes(c))
  let hazards=by('HAZARD'), topEvents=by('TOP_EVENT'), threats=by('THREAT'),
      prevention=by('PREVENTION'), consequences=by('CONSEQUENCE'), mitigation=by('MITIGATION')
  if (!threats.length)      threats      = result.root_causes || []
  if (!consequences.length) consequences = (result.immediate_causes || []).slice(1)
  if (!topEvents.length)    topEvents    = (result.immediate_causes || []).slice(0, 1)
  if (!prevention.length || !mitigation.length) {
    const c = result.contributing_causes || []
    if (!prevention.length) prevention = c.filter((_,i) => i % 2 === 0)
    if (!mitigation.length) mitigation = c.filter((_,i) => i % 2 !== 0)
  }
  return { hazards, topEvents, threats, prevention, consequences, mitigation }
}

function relPt(el, side, base) {
  const r = el.getBoundingClientRect()
  return {
    x: (side === 'r' ? r.right : r.left) - base.left,
    y: r.top + r.height / 2 - base.top,
  }
}

function bez(x1, y1, x2, y2) {
  const d = Math.abs(x2 - x1) * 0.46
  return `M${x1} ${y1} C${x1+d} ${y1} ${x2-d} ${y2} ${x2} ${y2}`
}

export default function BowtieDiagram({ result }) {
  const { hazards, topEvents, threats, prevention, consequences, mitigation } = parse(result)
  const topEvent = topEvents[0]
  const hazard   = hazards[0]

  const canvasRef = useRef(null)
  const [lines, setLines] = useState([])
  const [size,  setSize]  = useState({ w: 0, h: 0 })
  const [tip,   setTip]   = useState(null)

  const recalc = useCallback(() => {
    const cv = canvasRef.current; if (!cv) return
    const base = cv.getBoundingClientRect()
    if (base.width < 10) return
    // offsetWidth/Height — целые числа, нет дробных артефактов
    setSize({ w: cv.offsetWidth, h: cv.offsetHeight })

    const q  = s => cv.querySelector(`[data-bt="${s}"]`)
    const topEl = q('top'); if (!topEl) return
    const tL = relPt(topEl, 'l', base)
    const tR = relPt(topEl, 'r', base)
    const nl = []

    threats.forEach((_, i) => {
      const th = q(`threat-${i}`); if (!th) return
      const thR = relPt(th, 'r', base)
      const pr  = q(`prev-${i}`) || q('prev-0')
      if (pr) {
        const pL = relPt(pr, 'l', base), pR = relPt(pr, 'r', base)
        nl.push({ d: bez(thR.x, thR.y, pL.x, pL.y), c: 'L' })
        nl.push({ d: bez(pR.x,  pR.y,  tL.x, tL.y), c: 'L' })
      } else {
        nl.push({ d: bez(thR.x, thR.y, tL.x, tL.y), c: 'L' })
      }
    })

    consequences.forEach((_, i) => {
      const co = q(`cons-${i}`); if (!co) return
      const coL = relPt(co, 'l', base)
      const mi  = q(`miti-${i}`) || q('miti-0')
      if (mi) {
        const mL = relPt(mi, 'l', base), mR = relPt(mi, 'r', base)
        nl.push({ d: bez(tR.x, tR.y, mL.x, mL.y),  c: 'R' })
        nl.push({ d: bez(mR.x, mR.y, coL.x, coL.y), c: 'R' })
      } else {
        nl.push({ d: bez(tR.x, tR.y, coL.x, coL.y), c: 'R' })
      }
    })

    setLines(nl)
  }, [threats.length, prevention.length, consequences.length, mitigation.length])

  useEffect(() => {
    let r1, r2
    r1 = requestAnimationFrame(() => { r2 = requestAnimationFrame(recalc) })
    const ro = new ResizeObserver(recalc)
    if (canvasRef.current) ro.observe(canvasRef.current)
    return () => { cancelAnimationFrame(r1); cancelAnimationFrame(r2); ro.disconnect() }
  }, [recalc])

  // Fix 1: тултип над курсором, не выходит за края viewport
  const tipStyle = tip ? (() => {
    const PAD = 12
    const W   = 240
    let x = tip.x - W / 2
    let y = tip.y - PAD
    x = Math.max(PAD, Math.min(x, window.innerWidth  - W   - PAD))
    y = Math.max(PAD, y)
    return { left: x, top: y, transform: 'translateY(-100%)' }
  })() : {}

  return (
    <div className="bt-shell">

      <div className="bt-legend">
        {LEGEND.map(([k, l]) => (
          <div className="bt-leg-item" key={k}>
            <div className="bt-leg-dot" style={{ background: P[k]?.dot }} />
            <span>{l}</span>
          </div>
        ))}
      </div>

      <div className="bt-canvas" ref={canvasRef}>

        {/* SVG слой под карточками */}
        <svg className="bt-svg"
          width={size.w || '100%'}
          height={size.h || 300}
          aria-hidden="true"
        >
          <defs>
            {['L','R'].map(s => (
              <marker key={s} id={`bt-arr-${s}`}
                markerWidth="6" markerHeight="6"
                refX="5" refY="3" orient="auto"
              >
                <path d="M0,0 L6,3 L0,6 Z"
                  fill={s === 'L' ? '#a78bfa' : '#34d399'} opacity=".65"/>
              </marker>
            ))}
          </defs>
          {lines.map((ln, i) => (
            <path key={i} d={ln.d}
              className={`bt-line bt-line--${ln.c}`}
              markerEnd={`url(#bt-arr-${ln.c})`}
            />
          ))}
        </svg>

        <div className="bt-cols">

          {/* 1: Угрозы */}
          <div className="bt-col">
            {hazard && (
              <Card node={hazard} pal={P.hazard} isHazard
                dataId="hazard" onTip={setTip} />
            )}
            {threats.map((n, i) => (
              <Card key={i} node={n} pal={P.threat}
                dataId={`threat-${i}`} onTip={setTip} />
            ))}
          </div>

          {/* 2: Барьеры пред. — fix 2: space-evenly + внутренний padding */}
          <div className="bt-col bt-col--mid">
            {prevention.map((n, i) => (
              <Card key={i} node={n} pal={P.prevention} isBarrier
                dataId={`prev-${i}`} onTip={setTip} />
            ))}
          </div>

          {/* 3: Топ-событие — fix 3: align-self:center на карточке */}
          <div className="bt-col bt-col--top">
            <Card
              node={topEvent || { text: 'Топ-событие', confidence: 1 }}
              pal={P.topEvent} isCenter
              dataId="top" onTip={setTip}
            />
          </div>

          {/* 4: Барьеры смяг. */}
          <div className="bt-col bt-col--mid">
            {mitigation.map((n, i) => (
              <Card key={i} node={n} pal={P.mitigation} isBarrier
                dataId={`miti-${i}`} onTip={setTip} />
            ))}
          </div>

          {/* 5: Последствия */}
          <div className="bt-col">
            {consequences.map((n, i) => (
              <Card key={i} node={n} pal={P.consequence}
                dataId={`cons-${i}`} onTip={setTip} />
            ))}
          </div>

        </div>
      </div>

      {/* Fix 1: тултип вне .bt-canvas, position:fixed, над курсором */}
      {tip && (
        <div className="bt-tip" style={tipStyle}>
          <div className="bt-tip-text">{tip.text}</div>
          {tip.conf != null && (
            <div className="bt-tip-meta">
              <span>Уверенность: {(tip.conf * 100).toFixed(0)}%</span>
              <span className="bt-tip-bar" style={{
                width: `${(tip.conf * 100).toFixed(0)}%`,
                background: tip.conf > 0.6 ? '#34d399' : tip.conf > 0.3 ? '#facc15' : '#f87171',
              }} />
            </div>
          )}
        </div>
      )}

      <details className="bt-raw">
        <summary>▸ Список узлов</summary>
        <div className="bt-raw-grid">
          {[
            ['Угрозы',      'threat',      threats],
            ['Бар. пред.',  'prevention',  prevention],
            ['Топ-событие', 'topEvent',    topEvents],
            ['Бар. смяг.',  'mitigation',  mitigation],
            ['Последствия', 'consequence', consequences],
          ].map(([lbl, k, nodes]) => (
            <div key={k}>
              <div className="bt-raw-label" style={{ color: P[k]?.dot }}>{lbl}</div>
              {nodes.map((n, i) => (
                <div className="bt-raw-row" key={i}>
                  <span>{n?.text}</span>
                  {n?.confidence != null && (
                    <span className="bt-raw-conf">{(n.confidence * 100).toFixed(0)}%</span>
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>
      </details>

    </div>
  )
}

function Card({ node, pal, isCenter, isBarrier, isHazard, dataId, onTip }) {
  const deg = node?.confidence != null && node.confidence < 0.3
  return (
    <div
      data-bt={dataId}
      className={
        'bt-card' +
        (isCenter  ? ' bt-card--c'   : '') +
        (isBarrier ? ' bt-card--b'   : '') +
        (isHazard  ? ' bt-card--h'   : '') +
        (deg       ? ' bt-card--deg' : '')
      }
      style={{ background: pal?.bg, borderColor: deg ? 'rgba(248,113,113,.5)' : pal?.border }}
      onMouseEnter={e => node && onTip({ text: node.text, conf: node.confidence, x: e.clientX, y: e.clientY })}
      onMouseMove={e  => node && onTip({ text: node.text, conf: node.confidence, x: e.clientX, y: e.clientY })}
      onMouseLeave={() => onTip(null)}
    >
      {isBarrier && <div className="bt-shield" style={{ background: pal?.dot }} />}
      <span className="bt-card-text" style={{ color: pal?.text }}>
        {node?.text || ''}
        {deg && <span className="bt-deg-mark" title="Низкая уверенность"> ⚠</span>}
      </span>
    </div>
  )
}
