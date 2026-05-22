import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import App from './App.jsx'

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }
  static getDerivedStateFromError(error) {
    return { error }
  }
  render() {
    if (this.state.error) {
      return (
        <div style={{
          padding: '40px', fontFamily: 'monospace', background: '#fff1f0',
          minHeight: '100vh', color: '#c0392b',
        }}>
          <h2 style={{ marginBottom: 16 }}>Uygulama Hatası</h2>
          <pre style={{
            background: '#fff', border: '1px solid #fca5a5', padding: 16,
            borderRadius: 8, whiteSpace: 'pre-wrap', fontSize: 13,
          }}>
            {this.state.error.toString()}
            {'\n\n'}
            {this.state.error.stack}
          </pre>
        </div>
      )
    }
    return this.props.children
  }
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
)
