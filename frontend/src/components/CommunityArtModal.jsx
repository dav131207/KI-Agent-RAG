import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Command, Image as ImageIcon, CornerDownLeft, Loader2 } from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_URL || ''

export default function CommunityArtModal({ isOpen, onClose, onSubmit, isDark }) {
  const [labels, setLabels] = useState([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const inputRef = useRef(null)

  useEffect(() => {
    if (isOpen) {
      setSearch('')
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

  const filteredLabels = labels.filter(l => l.toLowerCase().includes(search.toLowerCase()))

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      onClose()
      return
    }
    if (e.key === 'Enter' && filteredLabels.length > 0) {
      onSubmit(filteredLabels[0])
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
        className="fixed inset-0 z-[100] flex items-start justify-center pt-[20vh] px-4"
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

          <div className={`max-h-[300px] min-h-[100px] overflow-y-auto border-t ${isDark ? 'border-white/5' : 'border-brand-100'} p-2`}>
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 size={24} className="animate-spin text-accent" />
              </div>
            ) : filteredLabels.length === 0 ? (
              <div className={`px-4 py-8 text-center text-sm ${isDark ? 'text-brand-500' : 'text-brand-400'}`}>
                {labels.length === 0 ? 'No approved community art available yet.' : 'No categories found.'}
              </div>
            ) : (
              filteredLabels.map((l, idx) => (
                <button
                  key={l}
                  onClick={() => onSubmit(l)}
                  className={`w-full flex items-center justify-between px-4 py-3 rounded-xl text-left transition-colors ${
                    idx === 0 
                      ? isDark ? 'bg-white/10' : 'bg-brand-50' 
                      : isDark ? 'hover:bg-white/5' : 'hover:bg-brand-50/50'
                  }`}
                >
                  <span className="font-medium">{l}</span>
                  {idx === 0 && <span className={`text-[10px] flex items-center gap-1 px-2 py-1 rounded ${isDark ? 'bg-white/10 text-brand-300' : 'bg-brand-100 text-brand-600'}`}>Press <CornerDownLeft size={10}/></span>}
                </button>
              ))
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}
