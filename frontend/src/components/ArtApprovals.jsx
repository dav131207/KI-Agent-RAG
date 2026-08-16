import { useState, useEffect } from 'react'

const API_BASE = import.meta.env.VITE_API_URL || ''

export default function ArtApprovals({ token }) {
  const [artList, setArtList] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState('pending')

  useEffect(() => {
    fetchArt()
  }, [])

  const fetchArt = async () => {
    try {
      setLoading(true)
      const res = await fetch(`${API_BASE}/api/admin/community-art`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (!res.ok) throw new Error('Failed to fetch art')
      const data = await res.json()
      setArtList(data.art)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleUpdate = async (id, status, label) => {
    try {
      const res = await fetch(`${API_BASE}/api/admin/community-art/${id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ status, label })
      })
      if (!res.ok) throw new Error('Update failed')
      fetchArt()
    } catch (err) {
      alert(err.message)
    }
  }

  const handleDelete = async (id) => {
    if (!window.confirm('Are you sure you want to delete this art?')) return;
    try {
      const res = await fetch(`${API_BASE}/api/admin/community-art/${id}`, {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${token}`
        }
      })
      if (!res.ok) throw new Error('Delete failed')
      fetchArt()
    } catch (err) {
      alert(err.message)
    }
  }

  const filteredArt = artList.filter(a => a.status === filter)

  if (loading && artList.length === 0) {
    return <div className="p-4">Loading art...</div>
  }

  if (error) {
    return <div className="p-4 text-red-500">{error}</div>
  }

  return (
    <div className="bg-white dark:bg-brand-800 rounded-2xl shadow-sm border border-brand-100 dark:border-white/10 p-4 sm:p-6">
      <div className="flex gap-2 mb-6 border-b border-brand-100 dark:border-white/10 pb-4">
        {['pending', 'approved', 'rejected'].map(status => (
          <button
            key={status}
            onClick={() => setFilter(status)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              filter === status 
                ? 'bg-accent text-white' 
                : 'bg-brand-50 dark:bg-brand-700 text-brand-600 dark:text-brand-300 hover:bg-brand-100 dark:hover:bg-brand-600'
            }`}
          >
            {status.charAt(0).toUpperCase() + status.slice(1)} ({artList.filter(a => a.status === status).length})
          </button>
        ))}
      </div>

      {filteredArt.length === 0 ? (
        <p className="text-sm text-brand-500 py-8 text-center">No {filter} art found.</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredArt.map(art => (
            <div key={art.id} className="border border-brand-100 dark:border-white/10 rounded-xl overflow-hidden bg-brand-50/50 dark:bg-brand-900/50 flex flex-col">
              <div className="aspect-square bg-black/10 flex items-center justify-center relative group">
                <a href={art.status === 'approved' ? `${API_BASE}/community/${art.filename}` : `${API_BASE}/data/uploads/${art.filename}`} target="_blank" rel="noreferrer" className="w-full h-full flex items-center justify-center p-2">
                  {art.filename.match(/\.(mp4|webm)$/i) ? (
                    <video src={art.status === 'approved' ? `${API_BASE}/community/${art.filename}` : `${API_BASE}/data/uploads/${art.filename}`} controls className="max-w-full max-h-full rounded" />
                  ) : (
                    <img src={art.status === 'approved' ? `${API_BASE}/community/${art.filename}` : `${API_BASE}/data/uploads/${art.filename}`} alt="art" className="max-w-full max-h-full rounded object-contain" />
                  )}
                </a>
              </div>
              <div className="p-4 flex-1 flex flex-col gap-3">
                <div>
                  {/* Named by the model from the picture, not typed by whoever
                      uploaded it — that is what produced near-duplicate
                      categories. Still editable here, because correcting one
                      bad name is an approval decision like any other. */}
                  <label className="text-[10px] font-bold text-brand-500 uppercase">
                    Name <span className="font-normal normal-case opacity-60">— set automatically</span>
                  </label>
                  <input
                    defaultValue={art.label}
                    onBlur={(e) => {
                      if (e.target.value !== art.label) {
                        handleUpdate(art.id, art.status, e.target.value)
                      }
                    }}
                    className="w-full px-2 py-1 mt-1 bg-white dark:bg-brand-800 border border-brand-200 dark:border-white/10 rounded text-sm"
                  />
                </div>
                <div>
                  <label className="text-[10px] font-bold text-brand-500 uppercase">Description</label>
                  <p className="text-xs mt-1 text-brand-700 dark:text-brand-300 line-clamp-3" title={art.description}>
                    {art.description}
                  </p>
                </div>
                {art.status === 'approved' && (
                  <div>
                    <label className="text-[10px] font-bold text-brand-500 uppercase">Community</label>
                    <div className="flex items-center gap-3 mt-1 text-xs tabular-nums">
                      <span className="text-[#0ca30c]" title="Thumbs up">👍 {art.ups ?? 0}</span>
                      <span className="text-[#d03b3b]" title="Thumbs down">👎 {art.downs ?? 0}</span>
                      <span className="text-brand-500" title="Times shown">
                        {art.impressions ?? 0}× shown
                      </span>
                    </div>
                  </div>
                )}
                <div className="mt-auto pt-3 border-t border-brand-100 dark:border-white/10 flex flex-wrap gap-2">
                  {filter !== 'approved' && (
                    <button 
                      onClick={() => handleUpdate(art.id, 'approved', art.label)}
                      className="flex-1 px-3 py-1.5 bg-[#0ca30c] hover:bg-[#0ca30c]/90 text-white rounded font-medium text-xs transition-colors"
                    >
                      Approve
                    </button>
                  )}
                  {filter !== 'rejected' && (
                    <button 
                      onClick={() => handleUpdate(art.id, 'rejected', art.label)}
                      className="flex-1 px-3 py-1.5 bg-[#d03b3b] hover:bg-[#d03b3b]/90 text-white rounded font-medium text-xs transition-colors"
                    >
                      Reject
                    </button>
                  )}
                  {filter === 'approved' && (
                    <button 
                      onClick={() => handleUpdate(art.id, 'pending', art.label)}
                      className="flex-1 px-3 py-1.5 bg-brand-500 hover:bg-brand-600 text-white rounded font-medium text-xs transition-colors"
                    >
                      Unapprove
                    </button>
                  )}
                  <button 
                    onClick={() => handleDelete(art.id)}
                    className="flex-none px-3 py-1.5 bg-black hover:bg-gray-800 text-white rounded font-medium text-xs transition-colors"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
