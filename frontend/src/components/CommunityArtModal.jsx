import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Command, Image as ImageIcon, CornerDownLeft, Loader2 } from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_URL || ''

// null means "no filter". Videos are listed so uploaded clips stay reachable
// once a filter exists at all — a filter offering only stills and GIFs would
// leave them with no way in.
const MEDIA_FILTERS = [
  { id: null, label: 'All' },
  { id: 'image', label: 'Images' },
  { id: 'gif', label: 'GIFs' },
  { id: 'video', label: 'Videos' },
]

export default function CommunityArtModal({ isOpen, onClose, onSubmit, isDark }) {
  const [labels, setLabels] = useState([])
  const [search, setSearch] = useState('')
  const [media, setMedia] = useState(null)
  const [loading, setLoading] = useState(true)
  const inputRef = useRef(null)

  useEffect(() => {
    if (isOpen) {
      setSearch('')
      setMedia(null)
      setLoading(true)
      fetch(`${API_BASE}/api/community-art/labels`)
        .then(res => res.json())
        .then(data => {
          setLabels(data.labels || [])
          setLoading(false)
        })
        .catch(() => setLoading(false))

      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }, [isOpen])

  if (!isOpen) return null

  const countFor = (l) => (media ? l.media?.[media] || 0 : l.count)

  // Only offer a filter the library can actually satisfy, so nobody picks one
  // and lands on an empty list.
  const availableFilters = MEDIA_FILTERS.filter(
    (f) => !f.id || labels.some((l) => (l.media?.[f.id] || 0) > 0)
  )

  const filteredLabels = labels.filter(
    (l) => l.label.toLowerCase().includes(search.toLowerCase()) && countFor(l) > 0
  )

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      onClose()
      return
    }
    if (e.key === 'Enter' && filteredLabels.length > 0) {
      onSubmit(filteredLabels[0].label, media)
    }
  }

  const containerVariants = {
    hidden: { opacity: 0, scale: 0.98, y: -20 },
    visible: { opacity: 1, scale: 1, y: 0, transition: { duration: 0.2, ease: "easeOut" } },
    exit: { opacity: 0, scale: 0.98, y: 10, transition: { duration: 0.15 } }
  }

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-[100] flex items-start justify-center overflow-y-auto px-4 pt-[8vh] pb-8 sm:pt-[20vh]"
      >
        <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          className={`relative w-full max-w-lg overflow-hidden rounded-2xl shadow-2xl border ${
            isDark ? 'bg-brand-900 border-white/10 text-white shadow-black' : 'bg-white border-brand-200 text-brand-900'
          }`}
        >
          <div className={`px-4 py-2 text-[11px] uppercase tracking-widest font-bold flex gap-4 border-b ${isDark ? 'border-white/5 bg-white/5' : 'border-brand-100 bg-brand-50'}`}>
            <span className="text-accent flex items-center gap-1.5"><ImageIcon size={12}/> Select Category</span>
          </div>

          <div className="flex items-center px-5 py-4 gap-4">
            <Command className={`shrink-0 ${isDark ? 'text-brand-500' : 'text-brand-400'}`} size={20} />
            <input
              ref={inputRef}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Search category (e.g. Infographic)..."
              className={`flex-1 bg-transparent text-lg outline-none font-medium placeholder:font-normal ${
                isDark ? 'placeholder:text-brand-600' : 'placeholder:text-brand-400'
              }`}
            />
          </div>

          {!loading && availableFilters.length > 1 && (
            <div className={`flex flex-wrap gap-1.5 px-5 pb-3 -mt-1`}>
              {availableFilters.map((f) => (
                <button
                  key={f.id ?? 'all'}
                  onClick={() => setMedia(f.id)}
                  aria-pressed={media === f.id}
                  className={`px-3 py-1 rounded-full text-xs font-semibold transition-colors ${
                    media === f.id
                      ? 'bg-accent text-white'
                      : isDark
                        ? 'bg-white/5 text-brand-300 hover:bg-white/10'
                        : 'bg-brand-100 text-brand-600 hover:bg-brand-200'
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
          )}

          <div className={`max-h-[45vh] sm:max-h-[300px] min-h-[100px] overflow-y-auto border-t ${isDark ? 'border-white/5' : 'border-brand-100'} p-2`}>
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 size={24} className="animate-spin text-accent" />
              </div>
            ) : filteredLabels.length === 0 ? (
              <div className={`px-4 py-8 text-center text-sm ${isDark ? 'text-brand-500' : 'text-brand-400'}`}>
                {labels.length === 0
                  ? 'No approved community art available yet.'
                  : media
                    ? `No categories with ${MEDIA_FILTERS.find(f => f.id === media)?.label.toLowerCase()} found.`
                    : 'No categories found.'}
              </div>
            ) : (
              filteredLabels.map((l, idx) => (
                <button
                  key={l.label}
                  onClick={() => onSubmit(l.label, media)}
                  className={`w-full flex items-center justify-between gap-3 px-4 py-3 rounded-xl text-left transition-colors ${
                    idx === 0
                      ? isDark ? 'bg-white/10' : 'bg-brand-50'
                      : isDark ? 'hover:bg-white/5' : 'hover:bg-brand-50/50'
                  }`}
                >
                  <span className="font-medium truncate">{l.label}</span>
                  <span className="flex items-center gap-2 shrink-0">
                    <span className={`text-[11px] tabular-nums ${isDark ? 'text-brand-500' : 'text-brand-400'}`}>
                      {countFor(l)}
                    </span>
                    {idx === 0 && <span className={`text-[10px] flex items-center gap-1 px-2 py-1 rounded ${isDark ? 'bg-white/10 text-brand-300' : 'bg-brand-100 text-brand-600'}`}>Press <CornerDownLeft size={10}/></span>}
                  </span>
                </button>
              ))
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}
