/**
 * BowtieDiagram v5
 * Линии рисуются через SVG внутри .bt-canvas.
 * .bt-canvas = position:relative, внутри него:
 *   • svg.bt-svg position:absolute inset:0 (z:0)
 *   • .bt-cols display:flex 5 колонок (z:1)
 * Смещения считаются один раз после mount через double-rAF.
 * Офсет берётся относительно .bt-canvas (а не viewport).
 *
 * v5 fixes:
 *   1. Tooltip смещён над курсор (translate -50% -100%) — не перекрывает карточку
 *   2. Колонки барьеров — justify-content: center вместо space-around
 *   3. Центральная карточка — выровнена строго по центру
 *   4. SVG overflow: visible + canvas overflow: visible — линии не обрезаются
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
  ['threat','Угрозы'],['prevention','Барьеры пред.'],
  ['topEvent','Топ-событие'],['mitigation','Барьеры смяг.'],
  ['consequence','Последствия'],['hazard','Опасный фактор'],
]

function parse(result) {
  const tree = result.causal_tree || []
  const by = c => tree.filter(n => n.category?.toUpperCase().includes(c))
  let hazards=by('HAZARD'), topEvents=by('TOP_EVENT'), threats=by('THREAT'),
      prevention=by('PREVENTION'), consequences=by('CONSEQUENCE'), mitigation=by('MITIGATION')

  if (!threats.length) threats = result.root_causes||[]
  if (!consequences.length) consequences = (result.immediate_causes||[]).slice(1)
  if (!topEvents.length) topEvents = (result.immediate_causes||[]).slice(0,1)
  if (!prevention.length||!mitigation.length) {
    const c = result.contributing_causes||[]
    if (!prevention.length) prevention = c.filter((_,i)=>i%2===0)
    if (!mitigation.length) mitigation = c.filter((_,i)=>i%2!==0)
  }
  return {hazards,topEvents,threats,prevention,consequences,mitigation}
}

function cx(el,side,base) {
  const r=el.getBoundingClientRect()
  return {
    x:(side==='r'?r.right:r.left)-base.left,
    y:r.top+r.height/2-base.top,
  }
}

function bez(x1,y1,x2,y2) {
  const d=Math.abs(x2-x1)*.48
  return `M${x1} ${y1} C${x1+d} ${y1} ${x2-d} ${y2} ${x2} ${y2}`
}

export default function BowtieDiagram({result}) {
  const {hazards,topEvents,threats,prevention,consequences,mitigation} = parse(result)
  const topEvent=topEvents[0], hazard=hazards[0]

  const canvasRef = useRef(null)
  const [lines, setLines] = useState([])
  const [size, setSize] = useState({w:0,h:0})
  const [tip, setTip] = useState(null)

  const recalc = useCallback(()=>{
    const cv = canvasRef.current; if(!cv) return
    const base = cv.getBoundingClientRect()
    if(base.width<10) return
    setSize({w:base.width, h:base.height})

    const q = s => cv.querySelector(`[data-bt="${s}"]`)
    const topEl = q('top'); if(!topEl) return
    const tL=cx(topEl,'l',base), tR=cx(topEl,'r',base)
    const nl=[]

    // Левая половина: угрозы → барьеры → центр
    threats.forEach((_,i)=>{
      const th=q(`threat-${i}`); if(!th) return
      const thR=cx(th,'r',base)
      const pr=q(`prev-${i}`)||q('prev-0')
      if(pr){
        const pL=cx(pr,'l',base), pR=cx(pr,'r',base)
        nl.push({d:bez(thR.x,thR.y,pL.x,pL.y),c:'L'})
        nl.push({d:bez(pR.x,pR.y,tL.x,tL.y), c:'L'})
      } else {
        nl.push({d:bez(thR.x,thR.y,tL.x,tL.y),c:'L'})
      }
    })

    // Правая половина: центр → барьеры → последствия
    consequences.forEach((_,i)=>{
      const co=q(`cons-${i}`); if(!co) return
      const coL=cx(co,'l',base)
      const mi=q(`miti-${i}`)||q('miti-0')
      if(mi){
        const mL=cx(mi,'l',base), mR=cx(mi,'r',base)
        nl.push({d:bez(tR.x,tR.y,mL.x,mL.y), c:'R'})
        nl.push({d:bez(mR.x,mR.y,coL.x,coL.y),c:'R'})
      } else {
        nl.push({d:bez(tR.x,tR.y,coL.x,coL.y),c:'R'})
      }
    })

    setLines(nl)
  },[threats.length,prevention.length,consequences.length,mitigation.length])

  useEffect(()=>{
    let r1,r2
    r1=requestAnimationFrame(()=>{ r2=requestAnimationFrame(recalc) })
    const ro=new ResizeObserver(recalc)
    if(canvasRef.current) ro.observe(canvasRef.current)
    return ()=>{ cancelAnimationFrame(r1); cancelAnimationFrame(r2); ro.disconnect() }
  },[recalc])

  return (
    <div className="bt-shell">

      {/* Легенда */}
      <div className="bt-legend">
        {LEGEND.map(([k,l])=>(
          <div className="bt-leg-item" key={k}>
            <div className="bt-leg-dot" style={{background:P[k]?.dot}}/>
            <span>{l}</span>
          </div>
        ))}
      </div>

      {/* Canvas: position:relative — относительно него считаются SVG-координаты */}
      <div className="bt-canvas" ref={canvasRef}>

        {/* SVG z:0 */}
        <svg className="bt-svg" width={size.w} height={size.h}>
          <defs>
            {['L','R'].map(s=>(
              <marker key={s} id={`bt-arr-${s}`} markerWidth="6" markerHeight="6"
                refX="5" refY="3" orient="auto-start-reverse">
                <path d="M0,0 L6,3 L0,6 Z"
                  fill={s==='L'?'#a78bfa':'#34d399'} opacity=".7"/>
              </marker>
            ))}
          </defs>
          {lines.map((ln,i)=>(
            <path key={i} d={ln.d}
              className={`bt-line bt-line--${ln.c}`}
              markerEnd={`url(#bt-arr-${ln.c})`}
            />
          ))}
        </svg>

        {/* 5 колонок z:1 */}
        <div className="bt-cols">

          {/* 1: Угрозы */}
          <div className="bt-col">
            {hazard && <Card node={hazard} pal={P.hazard} isHazard dataId="hazard" onTip={setTip}/>}
            {threats.map((n,i)=>(
              <Card key={i} node={n} pal={P.threat} dataId={`threat-${i}`} onTip={setTip}/>
            ))}
          </div>

          {/* 2: Барьеры пред. */}
          <div className="bt-col bt-col--mid">
            {prevention.map((n,i)=>(
              <Card key={i} node={n} pal={P.prevention} isBarrier dataId={`prev-${i}`} onTip={setTip}/>
            ))}
          </div>

          {/* 3: Топ-событие */}
          <div className="bt-col bt-col--top">
            <Card node={topEvent} pal={P.topEvent} isCenter dataId="top" onTip={setTip}/>
          </div>

          {/* 4: Барьеры смягч. */}
          <div className="bt-col bt-col--mid">
            {mitigation.map((n,i)=>(
              <Card key={i} node={n} pal={P.mitigation} isBarrier dataId={`miti-${i}`} onTip={setTip}/>
            ))}
          </div>

          {/* 5: Последствия */}
          <div className="bt-col">
            {consequences.map((n,i)=>(
              <Card key={i} node={n} pal={P.consequence} dataId={`cons-${i}`} onTip={setTip}/>
            ))}
          </div>

        </div>

        {/* Тултип — над курсором, не перекрывает карточки */}
        {tip && (
          <div className="bt-tip" style={{
            left: tip.x,
            top: tip.y - 8,
            transform: 'translate(-50%, -100%)'
          }}>
            <div className="bt-tip-text">{tip.text}</div>
            {tip.conf!=null && (
              <div className="bt-tip-meta">
                <span>Уверенность: {(tip.conf*100).toFixed(0)}%</span>
                <span className="bt-tip-bar" style={{
                  width:`${(tip.conf*100).toFixed(0)}%`,
                  background: tip.conf>.6?'#34d399':tip.conf>.3?'#facc15':'#f87171'
                }}/>
              </div>
            )}
          </div>
        )}

      </div>

      {/* Список узлов */}
      <details className="bt-raw">
        <summary>▸ Список узлов</summary>
        <div className="bt-raw-grid">
          {[
            ['Угрозы','threat',threats],
            ['Бар. пред.','prevention',prevention],
            ['Топ-событие','topEvent',topEvents],
            ['Бар. смяг.','mitigation',mitigation],
            ['Последствия','consequence',consequences],
          ].map(([lbl,k,nodes])=>(
            <div key={k}>
              <div className="bt-raw-label" style={{color:P[k]?.dot}}>{lbl}</div>
              {nodes.map((n,i)=>(
                <div className="bt-raw-row" key={i}>
                  <span>{n?.text}</span>
                  {n?.confidence!=null && <span className="bt-raw-conf">{(n.confidence*100).toFixed(0)}%</span>}
                </div>
              ))}
            </div>
          ))}
        </div>
      </details>

    </div>
  )
}

function Card({node, pal, isCenter, isBarrier, isHazard, dataId, onTip}) {
  const deg = node?.confidence!=null && node.confidence<0.3
  return (
    <div
      className={`bt-card${isCenter?' bt-card--c':''}${isBarrier?' bt-card--b':''}${isHazard?' bt-card--h':''}${deg?' bt-card--deg':''}`}
      style={{
        background: pal?.bg,
        borderColor: pal?.border,
        color: pal?.text,
      }}
      data-bt={dataId}
      onMouseEnter={e=>node&&onTip({text:node.text,conf:node.confidence,x:e.clientX,y:e.clientY})}
      onMouseMove={e=>node&&onTip({text:node.text,conf:node.confidence,x:e.clientX,y:e.clientY})}
      onMouseLeave={()=>onTip(null)}
    >
      {isBarrier &&
        <div className="bt-shield" style={{background:pal?.dot}}/>
      }
      <span className="bt-card-text">{node?.text||''}</span>
      {deg && <span className="bt-deg-mark">⚠</span>}
    </div>
  )
}
