import { useState, useEffect } from 'react';
import { apiClient } from '../api/client';

export default function AdminPanel() {
  const [tenants, setTenants] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [health, setHealth] = useState(null);
  const [newTenant, setNewTenant] = useState({ name: '', slug: '' });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    try {
      const [healthRes, docsRes] = await Promise.all([
        apiClient.get('/health'),
        apiClient.get('/documents'),
      ]);
      setHealth(healthRes.data);
      setDocuments(docsRes.data);
    } catch (err) {
      console.error('Failed to load admin data:', err);
    }
    setLoading(false);
  }

  async function createTenant(e) {
    e.preventDefault();
    try {
      await apiClient.post('/tenants', newTenant);
      setNewTenant({ name: '', slug: '' });
      loadData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to create tenant');
    }
  }

  if (loading) return <div className="p-4">Yükleniyor...</div>;

  return (
    <div className="p-4 space-y-6">
      <h2 className="text-xl font-bold">Yönetim Paneli</h2>

      {/* System Health */}
      <section className="border rounded p-4">
        <h3 className="font-semibold mb-2">Sistem Durumu</h3>
        {health && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
            <div className={`p-2 rounded ${health.status === 'healthy' ? 'bg-green-100' : 'bg-red-100'}`}>
              API: {health.status}
            </div>
            <div className={`p-2 rounded ${health.qdrant === 'connected' ? 'bg-green-100' : 'bg-red-100'}`}>
              Qdrant: {health.qdrant}
            </div>
            <div className={`p-2 rounded ${health.postgres === 'connected' ? 'bg-green-100' : 'bg-red-100'}`}>
              PostgreSQL: {health.postgres}
            </div>
            <div className={`p-2 rounded ${health.llm_available ? 'bg-green-100' : 'bg-yellow-100'}`}>
              LLM: {health.llm_available ? 'Hazır' : 'Yok'}
            </div>
          </div>
        )}
      </section>

      {/* Create Tenant */}
      <section className="border rounded p-4">
        <h3 className="font-semibold mb-2">Yeni Kiracı Oluştur</h3>
        <form onSubmit={createTenant} className="flex gap-2">
          <input
            type="text"
            placeholder="İsim"
            value={newTenant.name}
            onChange={(e) => setNewTenant({ ...newTenant, name: e.target.value })}
            className="border px-2 py-1 rounded text-sm"
            required
          />
          <input
            type="text"
            placeholder="slug (küçük harf)"
            value={newTenant.slug}
            onChange={(e) => setNewTenant({ ...newTenant, slug: e.target.value })}
            className="border px-2 py-1 rounded text-sm"
            required
          />
          <button type="submit" className="bg-blue-500 text-white px-3 py-1 rounded text-sm">
            Oluştur
          </button>
        </form>
      </section>

      {/* Document Status */}
      <section className="border rounded p-4">
        <h3 className="font-semibold mb-2">Belgeler ({documents.length})</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b">
                <th className="text-left p-1">Dosya</th>
                <th className="text-left p-1">Durum</th>
                <th className="text-left p-1">Parça</th>
                <th className="text-left p-1">Tarih</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr key={doc.id} className="border-b">
                  <td className="p-1">{doc.filename}</td>
                  <td className="p-1">
                    <span className={`px-1 rounded text-xs ${
                      doc.status === 'ready' ? 'bg-green-100' :
                      doc.status === 'processing' ? 'bg-yellow-100' : 'bg-red-100'
                    }`}>
                      {doc.status}
                    </span>
                  </td>
                  <td className="p-1">{doc.chunk_count ?? '-'}</td>
                  <td className="p-1">{new Date(doc.created_at).toLocaleDateString('tr-TR')}</td>
                </tr>
              ))}
              {documents.length === 0 && (
                <tr><td colSpan={4} className="p-2 text-center text-gray-500">Belge yok</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
