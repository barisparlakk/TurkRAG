import React, { useState, useEffect, useRef } from 'react'
import { api } from '../api/client.js'

const ALLOWED_EXTENSIONS = new Set(['pdf', 'docx', 'txt', 'xlsx', 'xls', 'csv'])

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
  if (status === 'completed')  return { cls: 'badge-success', label: 'Tamam' }
  if (status === 'failed')     return { cls: 'badge-error',   label: 'Hata'  }
  if (status === 'error')      return { cls: 'badge-error',   label: 'Hata'  }
  if (status === 'pending')    return { cls: 'badge-warning', label: 'Sırada' }
  return                              { cls: 'badge-warning', label: 'İşleniyor' }
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

function formatBytes(bytes = 0) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  const value = bytes / 1024 ** index
  return `${value.toFixed(value >= 10 || index === 0 ? 0 : 1)} ${units[index]}`
}

function validateUploadFiles(fileList) {
  const accepted = []
  const rejected = []

  Array.from(fileList || []).forEach((file) => {
    const ext = file.name?.split('.').pop()?.toLowerCase() || ''
    if (!ALLOWED_EXTENSIONS.has(ext)) {
      rejected.push({ name: file.name || 'isimsiz dosya', reason: 'desteklenmeyen tür' })
      return
    }
    if (file.size === 0) {
      rejected.push({ name: file.name || 'isimsiz dosya', reason: 'boş dosya' })
      return
    }
    accepted.push(file)
  })

  return { accepted, rejected }
}

export function DocumentUpload() {
  const [documents, setDocuments] = useState([])
  const [jobs, setJobs] = useState([])
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadSummary, setUploadSummary] = useState(null)
  const [error, setError] = useState(null)
  const [lastJob, setLastJob] = useState(null)
  const fileInputRef = useRef()
  const pollRef = useRef()

  const loadDocuments = async () => {
    try {
      const [docs, recentJobs] = await Promise.all([
        api.listDocuments(),
        api.listJobs(12),
      ])
      setDocuments(docs || [])
      setJobs(recentJobs || [])
    } catch {}
  }

  useEffect(() => {
    loadDocuments()
    pollRef.current = setInterval(loadDocuments, 5000)
    return () => clearInterval(pollRef.current)
  }, [])

  const handleFiles = async (files) => {
    if (!files?.length) return
    if (uploading) return
    const { accepted, rejected } = validateUploadFiles(files)
    const acceptedBytes = accepted.reduce((sum, file) => sum + file.size, 0)
    setError(null)
    setLastJob(null)
    setUploadSummary({
      accepted: accepted.length,
      rejected,
      bytes: acceptedBytes,
      completed: 0,
    })
    if (fileInputRef.current) fileInputRef.current.value = ''
    if (!accepted.length) return

    setUploading(true); setUploadProgress(0)
    for (let i = 0; i < accepted.length; i++) {
      try {
        setUploadProgress(Math.round(((i + 0.5) / accepted.length) * 100))
        const result = await api.uploadDocument(accepted[i])
        if (result?.job_id) setLastJob(result)
        setUploadProgress(Math.round(((i + 1) / accepted.length) * 100))
        setUploadSummary((prev) => prev ? { ...prev, completed: prev.completed + 1 } : prev)
      } catch (e) {
        setError(`Yükleme hatası (${accepted[i].name}): ${e.message}`)
      }
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
    <div className="document-workspace">
      <div className="view-header document-header">
        <div>
          <h2>Belge İndeksi</h2>
          <p>Yükleme, parçalama ve sorgulanabilir kaynak durumları</p>
        </div>
        <span>{documents.filter((doc) => doc.status === 'ready').length}/{documents.length}</span>
      </div>

      <div className="ingestion-board">
        <div
          className={`upload-zone ${dragging ? 'dragging' : ''} ${uploading ? 'disabled' : ''}`}
          onDragOver={(e) => { e.preventDefault(); if (!uploading) setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files) }}
          onClick={() => { if (!uploading) fileInputRef.current?.click() }}
        >
          <div className="upload-icon">
            <IconUpload />
          </div>
          <div className="upload-copy">
            <div className="upload-title">
              {uploading ? 'Yükleme devam ediyor' : dragging ? 'İndeks kuyruğuna bırak' : 'Yeni kaynak ekle'}
            </div>
            <div className="upload-meta">
              PDF, DOCX, TXT, XLSX, XLS, CSV · boş dosyalar atlanır
            </div>
          </div>
          <button className="btn btn-primary" type="button" disabled={uploading}>
            {uploading ? 'Yükleniyor' : 'Dosya seç'}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.txt,.xlsx,.xls,.csv"
            multiple
            style={{ display: 'none' }}
            onChange={(e) => handleFiles(e.target.files)}
          />
        </div>

        <div className="pipeline-strip">
          {['Yükleme', 'Ayrıştırma', 'Parçalama', 'Vektör + BM25', 'Hazır'].map((step, i) => (
            <div key={step} className="pipeline-step">
              <span>{String(i + 1).padStart(2, '0')}</span>
              <strong>{step}</strong>
            </div>
          ))}
        </div>
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

      {uploadSummary && (
        <div className={`upload-summary ${uploadSummary.rejected.length ? 'has-skips' : ''}`}>
          <div>
            <strong>
              {uploading
                ? `${uploadSummary.completed}/${uploadSummary.accepted} dosya kuyruğa alındı`
                : uploadSummary.accepted
                  ? `${uploadSummary.accepted} dosya hazırlandı`
                  : 'Yüklenecek geçerli dosya yok'}
            </strong>
            <span>
              {uploadSummary.accepted
                ? `${formatBytes(uploadSummary.bytes)} doğrulandı`
                : 'Desteklenen türlerde ve boş olmayan dosyalar seçin'}
            </span>
          </div>
          {uploadSummary.rejected.length > 0 && (
            <details>
              <summary>{uploadSummary.rejected.length} dosya atlandı</summary>
              <ul>
                {uploadSummary.rejected.map((item) => (
                  <li key={`${item.name}-${item.reason}`}>{item.name}: {item.reason}</li>
                ))}
              </ul>
            </details>
          )}
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

      <div className="document-main-grid">
        <section>
          <div className="section-label">
            Kaynak kayıtları
          </div>

          {documents.length === 0 ? (
            <div className="empty-ledger">İndekste belge yok</div>
          ) : (
          <div className="document-ledger">
            {documents.map((doc) => {
              const s = statusStyle(doc.status)
              return (
                <div key={doc.id} className="document-row fade-in">
                  <div className="document-file-icon">
                    <IconFile />
                  </div>
                  <div className="document-row-main">
                    <div className="document-title-line">
                      <span>{doc.filename}</span>
                      <FileTypeTag filename={doc.filename} />
                    </div>
                    <small>{doc.chunk_count ?? 0} parça · {new Date(doc.created_at).toLocaleDateString('tr-TR')}</small>
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
        </section>

        <aside className="job-ledger">
          <div className="section-label">Son iş kayıtları</div>
          {jobs.length === 0 ? (
            <div className="empty-ledger">Kuyruk boş</div>
          ) : jobs.slice(0, 8).map((job) => (
            <div className="job-row" key={job.id}>
              <span>{job.filename}</span>
              <strong>{statusStyle(job.status).label}</strong>
              <small>{job.attempts}/{job.max_attempts} deneme</small>
            </div>
          ))}
        </aside>
      </div>
    </div>
  )
}
