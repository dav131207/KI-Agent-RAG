import { useEffect, useState } from 'react'
import { Download } from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_URL || ''

// The watermark endpoint re-encodes stills and single-frame GIFs as PNG, so
// the download name has to follow what is actually served, not the upload.
const EXTENSIONS = { image: 'png', gif: 'gif', video: 'mp4' }

/**
 * Community art shortlisted for a generated post.
 *
 * A shortlist rather than one automatic attachment, for the same reason the
 * emote picker is one: art that misses the subject reads worse under a post
 * than no art at all, and only the author can judge that. The shortlist is
 * ranked against the finished post text, not the topic that was typed in —
 * the post is what people will actually read next to the picture.
 */
export default function CommunityArtPicker({ text }) {
  const [art, setArt] = useState([])
  const [matchedCount, setMatchedCount] = useState(0)
  const [selectedId, setSelectedId] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetch(`${API_BASE}/api/community-art/suggest?text=${encodeURIComponent(text || '')}&limit=4`)
      .then((res) => (res.ok ? res.json() : { art: [] }))
      .then((data) => {
        if (cancelled) return
        setArt(data.art || [])
        setMatchedCount(data.matched_count || 0)
        setLoading(false)
      })
      .catch(() => {
        if (cancelled) return
        setArt([])
        setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [text])

  if (loading) {
    return (
      <div className="mt-2 pt-2 border-t border-white/5">
        <div className="h-32 rounded-lg bg-black/5 dark:bg-white/5 animate-pulse" />
      </div>
    )
  }

  if (!art.length) return null

  const active = art.find((a) => a.id === selectedId) || art[0]

  return (
    <div className="mt-2 pt-2 border-t border-white/5">
      {/* Says how many of the row actually match, because the row is padded
          with well-rated pieces when few do — one suggestion is not a choice.
          Claiming all of them fit would be a lie the author cannot check. */}
      <p className="text-[10px] uppercase tracking-wider text-brand-500 dark:text-brand-400 mb-1.5">
        {matchedCount > 0
          ? `Community art — ${matchedCount} fitting this post`
          : 'Community art — nothing matched the text, showing the best rated'}
      </p>

      {active.media_type === 'video' ? (
        <video
          src={active.url}
          controls
          loop
          playsInline
          className="rounded-lg max-h-56 w-auto mx-auto shadow-sm"
        />
      ) : (
        <img
          src={active.url}
          alt={active.description || active.label}
          className="rounded-lg max-h-56 w-auto mx-auto shadow-sm"
        />
      )}

      {art.length > 1 && (
        <div className="flex items-center gap-2 flex-wrap mt-2">
          {art.map((piece) => (
            <button
              key={piece.id}
              onClick={() => setSelectedId(piece.id)}
              title={`${piece.matched ? 'Matches: ' : 'Alternative: '}${piece.description || piece.label}`}
              className={`relative w-12 h-12 rounded-lg overflow-hidden border transition-colors ${
                active.id === piece.id
                  ? 'border-accent bg-accent/10'
                  : piece.matched
                    ? 'border-accent/30 hover:border-accent/60'
                    : 'border-white/10 hover:border-accent/50'
              }`}
            >
              {piece.media_type === 'video' ? (
                <span className="w-full h-full flex items-center justify-center text-[9px] font-semibold text-brand-400">
                  MP4
                </span>
              ) : (
                <img
                  src={piece.url}
                  alt={piece.label}
                  className="w-full h-full object-cover"
                  loading="lazy"
                />
              )}
            </button>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between gap-3 mt-1.5">
        <p className="text-[9px] text-brand-500 dark:text-brand-500 truncate">
          {active.label}
          {active.description ? ` — ${active.description}` : ''}
        </p>
        {/* Same reason the emote download is separate: X renders no markdown,
            so the file has to be attached by hand and the post text stays
            clean. The extension follows the media type or the file saves
            under a name nothing can open. */}
        <a
          href={active.url}
          download={`${active.label.replace(/[^\w-]+/g, '_')}.${EXTENSIONS[active.media_type] || 'png'}`}
          className="flex items-center gap-1 shrink-0 px-2 py-1 rounded-lg text-[10px] font-medium bg-accent/15 text-accent border border-accent/30 hover:bg-accent/25 transition-colors"
        >
          <Download size={10} />
          Download
        </a>
      </div>
    </div>
  )
}
