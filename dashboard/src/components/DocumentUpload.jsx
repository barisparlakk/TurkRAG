import React, { useState, useEffect, useRef } from 'react'
import { api } from '../api/client.js'

const IconUpload = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="16 16 12 12 8 16"/>
    <line x1="12" y1="12" x2="12" y2="21"/>
    <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"/>
  </svg>
)

const IconDelete = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="3 6 5 6 21 6"/>
    <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
    <path d="M10 11v6"/><path d="M14 11v6"/>
    <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
  </svg>
)

const IconFile = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
    <polyline points="14 2 14 8 20 8"/>
  </svg>
)

function statusStyle(status) {
  if (status === 'ready')      return { cls: 'badge-success', label: 'Hazır' }
  if (status === 'error')      return { cls: 'badge-error',   label: 'Hata'  }
  return                              { cls: 'badge-warning',  label: 'İşleniyor' }
}

function FileTypeTag({ filename }) {
  const ext = filename?.split('.').pop()?.toLowerCase() || ''
  const colors = {
    pdf:  ['#ef4444', '#fde8e8'],
    docx: ['#3b82f6', '#e8f0fe'],
    txt:  ['#10b981', '#e6f9ee'],
    xlsx: ['#16a34a', '#dcfce7'],
    xls:  ['#16a34a', '#dcfce7'],
    csv:  ['#f59e0b', '#fef3c7'],
  }
  const [color, bg] = colors[ext] || ['#8b93ad', 'var(--surface-3)']
  return (
    <span style={{
      fontSize: '10px', fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase',
      background: bg, color, borderRadius: 4, padding: '2px 6px',
    }}>
      {ext || 'file'}
    </span>
  )
}

export function DocumentUpload() {
  const [documents, setDocuments] = useState([])
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [error, setError] = useState(null)
  const [lastJob, setLastJob] = useState(null)
  const fileInputRef = useRef()
  const pollRef = useRef()

  const loadDocuments = async () => {
    try { setDocuments(await api.listDocuments() || []) } catch {}
  }

  useEffect(() => {
    loadDocuments()
    pollRef.current = setInterval(loadDocuments, 5000)
    return () => clearInterval(pollRef.current)
  }, [])

  const handleFiles = async (files) => {
    if (!files?.length) return
    setError(null); setUploading(true); setUploadProgress(0)
    for (let i = 0; i < files.length; i++) {
      try {
        setUploadProgress(Math.round(((i + 0.5) / files.length) * 100))
        const result = await api.uploadDocument(files[i])
        if (result?.job_id) setLastJob(result)
        setUploadProgress(Math.round(((i + 1) / files.length) * 100))
      } catch (e) { setError(`Yükleme hatası: ${e.message}`) }
    }
    setUploading(false); setUploadProgress(0)
    await loadDocuments()
  }

  const handleDelete = async (docId) => {
    if (!confirm('Bu belgeyi silmek istediğinizden emin misiniz?')) return
    try {
      await api.deleteDocument(docId)
      setDocuments((prev) => prev.filter((d) => d.id !== docId))
    } catch (e) { setError(`Silme hatası: ${e.message}`) }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div className="view-header">
        <h2>Belgeler</h2>
        <span>{documents.length}</span>
      </div>

      <div
        className={`upload-zone ${dragging ? 'dragging' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files) }}
        onClick={() => fileInputRef.current?.click()}
      >
        <div className="upload-icon">
          <IconUpload />
        </div>
        <div className="upload-title">
          {dragging ? 'Bırakın' : 'Dosya bırakın'}
        </div>
        <div className="upload-meta">
          PDF · DOCX · TXT · XLSX · CSV
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.txt,.xlsx,.xls,.csv"
          multiple
          style={{ display: 'none' }}
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      {uploading && (
        <div style={{
          background: 'var(--surface-1)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-md)', padding: '14px 16px',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-2)' }}>Yükleniyor…</span>
            <span style={{ fontSize: '12px', color: 'var(--accent-hover)', fontWeight: 600 }}>{uploadProgress}%</span>
          </div>
          <div style={{ height: 4, background: 'var(--surface-3)', borderRadius: 2, overflow: 'hidden' }}>
            <div style={{
              height: '100%', width: `${uploadProgress}%`,
              background: 'linear-gradient(90deg, var(--accent), var(--accent-hover))',
              borderRadius: 2, transition: 'width 0.3s ease',
            }} />
          </div>
        </div>
      )}

      {lastJob && !uploading && (
        <div className="admin-success">
          İşleme alındı: {lastJob.filename} · job {lastJob.job_id.slice(0, 8)}
        </div>
      )}

      {error && (
        <div style={{
          background: 'var(--error-muted)', border: '1px solid rgba(239,68,68,0.2)',
          color: 'var(--error)', fontSize: '13px',
          borderRadius: 'var(--radius-md)', padding: '10px 14px',
        }}>
          {error}
        </div>
      )}

      <div>
        <div className="section-label">
          Liste
        </div>

        {documents.length === 0 ? (
          <div style={{
            background: 'var(--surface-1)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius-md)', padding: '28px',
            textAlign: 'center', color: 'var(--text-3)', fontSize: '13px',
          }}>
            Belge yok
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {documents.map((doc) => {
              const s = statusStyle(doc.status)
              return (
                <div key={doc.id} className="fade-in" style={{
                  display: 'flex', alignItems: 'center', gap: '12px',
                  padding: '12px 14px',
                  background: 'var(--surface-1)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-md)',
                  transition: 'border-color 0.15s',
                }}
                  onMouseEnter={(e) => e.currentTarget.style.borderColor = 'var(--text-3)'}
                  onMouseLeave={(e) => e.currentTarget.style.borderColor = 'var(--border)'}
                >
                  <div style={{
                    width: 34, height: 34, flexShrink: 0,
                    background: 'var(--surface-2)', border: '1px solid var(--border)',
                    borderRadius: 8,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: 'var(--text-3)',
                  }}>
                    <IconFile />
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '3px' }}>
                      <span style={{ fontSize: '13.5px', fontWeight: 500, color: 'var(--text-1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {doc.filename}
                      </span>
                      <FileTypeTag filename={doc.filename} />
                    </div>
                    {doc.chunk_count && (
                      <div style={{ fontSize: '11px', color: 'var(--text-3)' }}>
                        {doc.chunk_count} bölüm
                      </div>
                    )}
                  </div>
                  <span className={`badge ${s.cls}`}>{s.label}</span>
                  <button
                    onClick={() => handleDelete(doc.id)}
                    className="btn btn-icon"
                    title="Sil"
                  >
                    <IconDelete />
                  </button>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
