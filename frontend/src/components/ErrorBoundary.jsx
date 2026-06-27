import React from 'react'

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { error: null, info: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('[ErrorBoundary]', error, info)
    this.setState({ info })
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 24, maxWidth: 600, margin: '40px auto', background: '#fff', border: '2px solid red', borderRadius: 8 }}>
          <h2 style={{ color: 'red', marginTop: 0 }}>❌ Ошибка рендера</h2>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13, background: '#f5f5f5', padding: 12, borderRadius: 4 }}>
            {this.state.error?.message || String(this.state.error)}
          </pre>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 11, color: '#666', background: '#fafafa', padding: 12, borderRadius: 4, marginTop: 8 }}>
            {this.state.info?.componentStack || ''}
          </pre>
          <button onClick={() => window.location.reload()} style={{ marginTop: 16, padding: '8px 16px', cursor: 'pointer' }}>
            🔄 Перезагрузить
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
