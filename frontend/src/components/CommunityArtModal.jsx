import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Image as ImageIcon, Shuffle, Search, Stamp } from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_URL || ''

// null means "no filter". Videos are listed so uploaded clips stay reachable
// once a filter exists at all — a filter offering only stills and GIFs would
// leave them with no way in.
const MEDIA_FILTERS = [
  { id: null, label: 'Anything' },
  { id: 'image', label: 'Images' },
  { id: 'gif', label: 'GIFs' },
  { id: 'video', label: 'Videos' },
]

/**
 * Asks what kind of picture you are in the mood for, then draws one.
 *
 * It used to list every category in the library and make you pick one, which
 * turns a "show me something" command into a directory. You describe what you
 * are after instead — or nothing at all — and get a single piece back.
 */
const WATERMARK_PREF = 'communityArt.watermark'

// Remembered per browser: someone who wants the originals wants them every
// time, and re-flipping the switch on each draw would be the whole dialog.
function readWatermarkPref() {
  try {
    return localStorage.getItem(WATERMARK_PREF) !== 'off'
  } catch {
    return true
  }
}

export default function CommunityArtModal({ isOpen, onClose, onSubmit, isDark }) {
  const [labels, setLabels] = useState([])
  const [query, setQuery] = useState('')
  const [media, setMedia] = useState(null)
  const [watermark, setWatermark] = useState(readWatermarkPref)
  const inputRef = useRef(null)

  const toggleWatermark = () => {
    const next = !watermark
    setWatermark(next)
    try {
      localStorage.setItem(WATERMARK_PREF, next ? 'on' : 'off')
    } catch {
      // Storage can be unavailable; the switch still works for this draw.
    }
  }

  useEffect(() => {
    if (isOpen) {
      setQuery('')
      setMedia(null)
      fetch(`${API_BASE}/api/community-art/labels`)
        .then((res) => (res.ok ? res.json() : { labels: [] }))
        .then((data) => setLabels(data.labels || []))
        .catch(() => setLabels([]))

      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }, [isOpen])

  if (!isOpen) return null

  const submit = () => onSubmit(query.trim(), media, watermark)

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') onClose()
    if (e.key === 'Enter') submit()
  }

  // A handful of the best-regarded categories, as a hint at what the library
  // holds. Not the whole list — that was the thing being replaced.
  const suggestions = labels
    .filter((l) => (media ? (l.media?.[media] || 0) > 0 : l.count > 0))
    .slice(0, 6)

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
          initial={{ opacity: 0, scale: 0.98, y: -20 }}
          animate={{ opacity: 1, scale: 1, y: 0, transition: { duration: 0.2, ease: 'easeOut' } }}
          exit={{ opacity: 0, scale: 0.98, y: 10, transition: { duration: 0.15 } }}
          className={`relative w-full max-w-lg overflow-hidden rounded-2xl shadow-2xl border ${
            isDark ? 'bg-brand-900 border-white/10 text-white shadow-black' : 'bg-white border-brand-200 text-brand-900'
          }`}
        >
          <div className={`px-4 py-2 text-[11px] uppercase tracking-widest font-bold flex gap-4 border-b ${isDark ? 'border-white/5 bg-white/5' : 'border-brand-100 bg-brand-50'}`}>
            <span className="text-accent flex items-center gap-1.5">
              <ImageIcon size={12} /> Community Art
            </span>
          </div>

          <div className="p-5 space-y-4">
            <div className="flex items-center gap-3">
              <Search className={`shrink-0 ${isDark ? 'text-brand-500' : 'text-brand-400'}`} size={18} />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Funny, infographic, mining... or leave empty"
                className={`flex-1 bg-transparent text-lg outline-none font-medium placeholder:font-normal ${
                  isDark ? 'placeholder:text-brand-600' : 'placeholder:text-brand-400'
                }`}
              />
            </div>

            <div className="flex flex-wrap gap-1.5">
              {MEDIA_FILTERS.map((f) => (
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

            {suggestions.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5">
                <span className={`text-[10px] uppercase tracking-wider ${isDark ? 'text-brand-500' : 'text-brand-400'}`}>
                  In the library
                </span>
                {suggestions.map((l) => (
                  <button
                    key={l.label}
                    onClick={() => setQuery(l.label)}
                    className={`px-2 py-0.5 rounded-md text-[11px] transition-colors ${
                      isDark ? 'bg-white/5 hover:bg-white/10 text-brand-300' : 'bg-brand-50 hover:bg-brand-100 text-brand-600'
                    }`}
                  >
                    {l.label}
                  </button>
                ))}
              </div>
            )}

            {/* Videos never carry the watermark, so the switch would be a
                lie with that filter on. */}
            {media !== 'video' && (
              <label className="flex items-center justify-between gap-3 cursor-pointer select-none">
                <span className={`flex items-center gap-2 text-xs ${isDark ? 'text-brand-300' : 'text-brand-600'}`}>
                  <Stamp size={14} className={watermark ? 'text-accent' : 'opacity-50'} />
                  Professor Pepe watermark
                </span>
                <button
                  type="button"
                  role="switch"
                  aria-checked={watermark}
                  onClick={toggleWatermark}
                  className={`relative shrink-0 w-10 h-6 rounded-full transition-colors ${
                    watermark ? 'bg-accent' : isDark ? 'bg-white/15' : 'bg-brand-200'
                  }`}
                >
                  <span
                    className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${
                      watermark ? 'translate-x-4' : 'translate-x-0'
                    }`}
                  />
                </button>
              </label>
            )}

            <button
              onClick={submit}
              className="w-full py-2.5 rounded-lg bg-accent text-white font-bold flex items-center justify-center gap-2 shadow-lg shadow-accent/20"
            >
              <Shuffle size={15} />
              {query.trim() ? 'Show me one' : 'Surprise me'}
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}
