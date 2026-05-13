import React, { useState, useEffect, useRef } from 'react'
import { api } from '../api/client.js'

export function DocumentUpload() {
  const [documents, setDocuments] = useState([])
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [error, setError] = useState(null)
  const fileInputRef = useRef()
  const pollRef = useRef()

  const loadDocuments = async () => {
    try {
      const docs = await api.listDocuments()
      setDocuments(docs || [])
    } catch (e) {
      console.error('Failed to load documents:', e)
    }
  }

  useEffect(() => {
    loadDocuments()
    // Poll for status updates every 5s while any doc is processing
    pollRef.current = setInterval(() => {
      loadDocuments()
    }, 5000)
    return () => clearInterval(pollRef.current)
  }, [])

  const handleFiles = async (files) => {
    if (!files || files.length === 0) return
    setError(null)
    setUploading(true)
    setUploadProgress(0)

    for (let i = 0; i < files.length; i++) {
      try {
        setUploadProgress(Math.round(((i + 0.5) / files.length) * 100))
        await api.uploadDocument(files[i])
        setUploadProgress(Math.round(((i + 1) / files.length) * 100))
      } catch (e) {
        setError(`Yükleme hatası: ${e.message}`)
      }
    }

    setUploading(false)
    setUploadProgress(0)
    await loadDocuments()
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    handleFiles(e.dataTransfer.files)
  }

  const handleDelete = async (docId) => {
    if (!confirm('Bu belgeyi silmek istediğinizden emin misiniz?')) return
    try {
      await api.deleteDocument(docId)
      setDocuments((prev) => prev.filter((d) => d.id !== docId))
    } catch (e) {
      setError(`Silme hatası: ${e.message}`)
    }
  }

  const statusColor = (status) => {
    if (status === 'ready') return { bg: '#e6f9ee', color: '#1a7a3a', label: 'Hazır' }
    if (status === 'error') return { bg: '#fde8e8', color: '#b91c1c', label: 'Hata' }
    return { bg: '#fff8e1', color: '#b45309', label: 'İşleniyor…' }
  }

  return (
    <div style={{ padding: '16px' }}>
      <h2 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '12px', color: '#1a1a1a' }}>Belge Yönetimi</h2>

      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        style={{
          border: `2px dashed ${dragging ? '#1a73e8' : '#cbd5e1'}`,
          borderRadius: '10px',
          padding: '28px 16px',
          textAlign: 'center',
          cursor: 'pointer',
          background: dragging ? '#e8f4fd' : '#f8fafc',
          transition: 'all 0.15s',
          marginBottom: '12px',
        }}
      >
        <div style={{ fontSize: '28px', marginBottom: '6px' }}>📄</div>
        <div style={{ fontSize: '14px', color: '#555' }}>
          PDF, DOCX veya TXT dosyalarını buraya sürükleyin
        </div>
        <div style={{ fontSize: '12px', color: '#999', marginTop: '4px' }}>veya tıklayarak seçin</div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.txt"
          multiple
          style={{ display: 'none' }}
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      {/* Upload progress */}
      {uploading && (
        <div style={{ marginBottom: '10px' }}>
          <div style={{ height: '6px', background: '#e0e0e0', borderRadius: '3px', overflow: 'hidden' }}>
            <div style={{ height: '100%', width: `${uploadProgress}%`, background: '#1a73e8', transition: 'width 0.3s' }} />
          </div>
          <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>Yükleniyor… {uploadProgress}%</div>
        </div>
      )}

      {error && (
        <div style={{ color: '#b91c1c', fontSize: '13px', marginBottom: '10px', padding: '8px', background: '#fde8e8', borderRadius: '6px' }}>
          {error}
        </div>
      )}

      {/* Document list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        {documents.length === 0 ? (
          <div style={{ textAlign: 'center', color: '#aaa', fontSize: '13px', padding: '16px' }}>
            Henüz yüklenmiş belge yok
          </div>
        ) : (
          documents.map((doc) => {
            const s = statusColor(doc.status)
            return (
              <div key={doc.id} style={{
                display: 'flex',
                alignItems: 'center',
                padding: '8px 10px',
                border: '1px solid #e0e0e0',
                borderRadius: '8px',
                background: '#fff',
                gap: '10px',
              }}>
                <span style={{ fontSize: '16px' }}>📎</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: '13px', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {doc.filename}
                  </div>
                  {doc.chunk_count && (
                    <div style={{ fontSize: '11px', color: '#999' }}>{doc.chunk_count} bölüm</div>
                  )}
                </div>
                <span style={{
                  background: s.bg,
                  color: s.color,
                  borderRadius: '12px',
                  padding: '2px 10px',
                  fontSize: '11px',
                  fontWeight: 600,
                  whiteSpace: 'nowrap',
                }}>
                  {s.label}
                </span>
                <button
                  onClick={() => handleDelete(doc.id)}
                  title="Sil"
                  style={{
                    border: 'none',
                    background: 'none',
                    cursor: 'pointer',
                    color: '#ccc',
                    fontSize: '16px',
                    padding: '2px 4px',
                    lineHeight: 1,
                  }}
                  onMouseEnter={(e) => e.target.style.color = '#e53e3e'}
                  onMouseLeave={(e) => e.target.style.color = '#ccc'}
                >
                  ×
                </button>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
