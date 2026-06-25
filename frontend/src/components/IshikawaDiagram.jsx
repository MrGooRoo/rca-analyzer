import React, { useMemo } from 'react'

/**
 * Ishikawa (Fishbone) SVG Diagram
 *
 * Layout:
 *   Horizontal spine (→) with the problem/effect at right.
 *   Categories (root_causes, contributing_causes, immediate_causes)
 *   branch as angled "bones" above and below the spine.
 *   Each individual cause is a small nodule on its parent bone.
 */
const BONE_COLORS = {
  root_causes:         { fill: '#f43f5e', label: 'Корневые причины' },
  contributing_causes: { fill: '#f59e0b', label: 'Способствующие факторы' },
  immediate_causes:    { fill: '#6366f1', label: 'Непосредственные причины' },
}

function useThemeColors() {
  // Determine current theme from <html data-theme>
  if (typeof document === 'undefined') return { bg: '#000000', text: '#ffffff', spine: '#48484A' }
  const theme = document.documentElement.getAttribute('data-theme') || 'dark'
  const isDark = theme === 'dark'
  return {
    bg:    isDark ? '#1C1C1E' : '#FFFFFF',
    text:  isDark ? '#ffffff' : '#000000',
    spine: isDark ? '#48484A' : '#C6C6C8',
    muted: isDark ? '#8E8E93' : '#3C3C43',
  }
}

export default function IshikawaDiagram({ result }) {
  const colors = useThemeColors()

  // Collect bone data: { key, nodes }
  const sections = useMemo(() => {
    const entries = [
      { key: 'root_causes',         label: 'Корневые причины',         color: '#f43f5e' },
      { key: 'contributing_causes', label: 'Способствующие факторы', color: '#f59e0b' },
      { key: 'immediate_causes',    label: 'Непосредственные причины', color: '#6366f1' },
    ]
    return entries
      .map(s => ({ ...s, nodes: result[s.key] || [] }))
      .filter(s => s.nodes.length > 0)
  }, [result])

  if (sections.length === 0) {
    return <div className="result-section-empty">Нет данных для диаграммы Исикавы</div>
  }

  // SVG dimensions
  const W = 900
  const H = 400
  const SPINE_Y = H / 2
  const EFFECT_BOX_W = 130
  const EFFECT_BOX_H = 60
  const SPINE_END_X = W - 40
  const SPINE_START_X = 30
  const SPINE_LEN = SPINE_END_X - SPINE_START_X

  // Distribute bones along the spine left-to-right
  const totalBones = sections.reduce((sum, s) => sum + s.nodes.length, 0)
  const boneGap = totalBones > 1 ? SPINE_LEN / (totalBones + 1) : SPINE_LEN / 2

  let boneIndex = 0
  const bones = []
  sections.forEach(section => {
    section.nodes.forEach(node => {
      const x = SPINE_START_X + boneGap * (boneIndex + 1)
      const above = boneIndex % 2 === 0
      const yOff = above ? -60 : 60
      const yEnd = SPINE_Y + yOff
      bones.push({ x, yEnd, above, node, section })
      boneIndex++
    })
  })

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      style={{ width: '100%', maxHeight: `${H}px`, background: 'transparent' }}
      role="img"
      aria-label="Диаграмма Исикава (рыбья кость)"
    >
      <defs>
        <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
          <polygon points="0 0, 10 3.5, 0 7" fill={colors.text} />
        </marker>
        {sections.map(s => (
          <filter key={s.key} id={`glow-${s.key}`}>
            <feGaussianBlur stdDeviation="2" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        ))}
      </defs>

      {/* Background */}
      <rect x="0" y="0" width={W} height={H} fill={colors.bg} rx="12" opacity="0.95" />

      {/* Spine */}
      <line
        x1={SPINE_START_X} y1={SPINE_Y}
        x2={SPINE_END_X - EFFECT_BOX_W / 2 - 8} y2={SPINE_Y}
        stroke={colors.spine} strokeWidth="3" strokeLinecap="round"
      />
      {/* Arrow to effect */}
      <line
        x1={SPINE_END_X - EFFECT_BOX_W / 2 - 8} y1={SPINE_Y}
        x2={SPINE_END_X - 8} y2={SPINE_Y}
        stroke={colors.text} strokeWidth="3" markerEnd="url(#arrowhead)"
      />

      {/* Effect box */}
      <foreignObject x={SPINE_END_X - EFFECT_BOX_W / 2} y={SPINE_Y - EFFECT_BOX_H / 2} width={EFFECT_BOX_W} height={EFFECT_BOX_H}>
        <div style={{
          width: '100%', height: '100%',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'rgba(244, 63, 94, 0.15)',
          border: '2px solid rgba(244, 63, 94, 0.4)',
          borderRadius: '10px',
          fontSize: '13px', fontWeight: 600, color: colors.text,
          textAlign: 'center', padding: '4px',
          fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", sans-serif',
        }}>
          {result.summary || 'Инцидент'}
        </div>
      </foreignObject>

      {/* Bones */}
      {bones.map((bone, i) => {
        const { x, yEnd, above, node, section } = bone
        const color = BONE_COLORS[section.key]?.fill || '#666'
        const boneLen = Math.abs(yEnd - SPINE_Y) * 0.7
        const midX = x - (above ? -boneLen * 0.3 : boneLen * 0.3)
        const midY = SPINE_Y + (yEnd - SPINE_Y) * 0.6
        const textX = above ? x + 10 : x + 10
        const textY = above ? yEnd - 10 : yEnd + 16
        const labelX = above ? x + 10 : x + 10

        return (
          <g key={node.id || i}>
            {/* Main bone line */}
            <line
              x1={x} y1={SPINE_Y}
              x2={x + (above ? -boneLen * 0.15 : boneLen * 0.15)} y2={yEnd}
              stroke={color} strokeWidth="2.5" strokeLinecap="round"
              opacity="0.85"
            />

            {/* Category indicator dot at spine junction */}
            <circle cx={x} cy={SPINE_Y} r="4" fill={color} />

            {/* Bone label (cause text) */}
            <text
              x={x + (above ? 12 : 12)}
              y={above ? yEnd - 6 : yEnd + 14}
              fill={colors.text}
              fontSize="11"
              fontFamily="-apple-system, BlinkMacSystemFont, sans-serif"
              fontWeight="500"
            >
              {node.text.length > 50 ? node.text.slice(0, 47) + '…' : node.text}
            </text>

            {/* Category tag */}
            <rect
              x={x - (above ? 0 : 0) - 2}
              y={above ? yEnd - 38 : yEnd + 18}
              width={node.category ? node.category.length * 8 + 12 : 10}
              height="18"
              rx="9"
              fill={color}
              opacity="0.2"
            />
            {node.category && (
              <text
                x={x + 4}
                y={above ? yEnd - 26 : yEnd + 30}
                fill={color}
                fontSize="10"
                fontFamily="-apple-system, BlinkMacSystemFont, sans-serif"
                fontWeight="600"
              >
                {node.category}
              </text>
            )}

            {/* Confidence badge */}
            <text
              x={x + (above ? 0 : 0) - 2}
              y={above ? yEnd - 48 : yEnd + 42}
              fill={colors.muted}
              fontSize="9"
              fontFamily="-apple-system, BlinkMacSystemFont, sans-serif"
            >
              {(node.confidence * 100).toFixed(0)}%
            </text>
          </g>
        )
      })}
    </svg>
  )
}
