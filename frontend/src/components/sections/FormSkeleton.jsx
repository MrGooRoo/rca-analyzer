import React from 'react'

export default function FormSkeleton() {
  return (
    <div className="incident-form-skeleton" style={{ animation: 'fadeIn 0.3s ease' }}>
      {/* Steps skeleton */}
      <div className="incident-steps-skeleton" style={{
        display: 'flex', gap: 'var(--space-md)', marginBottom: 'var(--space-lg)'
      }}>
        {[1, 2, 3].map(i => (
          <div key={i} className="skeleton-block" style={{
            flex: 1, height: 48, borderRadius: 'var(--radius-md)',
            background: 'var(--bg-quaternary)', opacity: 1 - (i * 0.2)
          }} />
        ))}
      </div>

      {/* Title skeleton */}
      <div className="skeleton-block" style={{
        width: '40%', height: 24, marginBottom: 'var(--space-xl)',
        borderRadius: 'var(--radius-sm)', background: 'var(--bg-tertiary)'
      }} />

      {/* Card skeleton */}
      <div className="skeleton-card" style={{
        background: 'var(--bg-secondary)', borderRadius: 'var(--radius-xl)',
        padding: 'var(--space-xl)', marginBottom: 'var(--space-lg)'
      }}>
        {/* Header */}
        <div className="skeleton-block" style={{
          width: '30%', height: 20, marginBottom: 'var(--space-lg)',
          borderRadius: 'var(--radius-sm)', background: 'var(--bg-tertiary)'
        }} />
        {/* Choice grid */}
        <div style={{ display: 'flex', gap: 'var(--space-md)', marginBottom: 'var(--space-lg)' }}>
          {[1, 2].map(i => (
            <div key={i} className="skeleton-block" style={{
              flex: 1, height: 80, borderRadius: 'var(--radius-lg)',
              background: 'var(--bg-tertiary)', opacity: 0.6
            }} />
          ))}
        </div>
        {/* Fields */}
        {[1, 2, 3].map(i => (
          <div key={i} style={{ marginBottom: 'var(--space-md)' }}>
            <div className="skeleton-block" style={{
              width: '20%', height: 14, marginBottom: 'var(--space-xs)',
              borderRadius: 'var(--radius-sm)', background: 'var(--bg-tertiary)'
            }} />
            <div className="skeleton-block" style={{
              width: '100%', height: 40, borderRadius: 'var(--radius-md)',
              background: 'var(--bg-quaternary)'
            }} />
          </div>
        ))}
      </div>
    </div>
  )
}
