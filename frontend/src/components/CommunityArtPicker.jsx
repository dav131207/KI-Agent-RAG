import { useEffect, useState } from 'react'
import ShortlistPicker from './ShortlistPicker'

const API_BASE = import.meta.env.VITE_API_URL || ''

// The watermark endpoint re-encodes stills and single-frame GIFs as PNG, so
// the download name has to follow what is actually served, not the upload.
const EXTENSIONS = { image: 'png', gif: 'gif', video: 'mp4' }

/**
 * Filename for a downloaded piece, built from its category.
 *
 * The category often names the format — "GIF", "GIF Reactions" — which the
 * extension already says, so a piece would save as GIF_Reactions.gif. The
 * format word is dropped when the extension repeats it.
 */
export function downloadName(label, mediaType) {
  const ext = EXTENSIONS[mediaType] || 'png'
  const base = (label || '')
    .replace(new RegExp(`\\b${ext}s?\\b`, 'gi'), ' ')
    .trim()
    .replace(/[^\w-]+/g, '_')
    .replace(/^_+|_+$/g, '')
  return `${base || 'community-art'}.${ext}`
}

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

  return (
    <ShortlistPicker
      // Says how many of the row actually match, because the row is padded
      // with well-rated pieces when few do — one suggestion is not a choice.
      // Claiming all of them fit would be a lie the author cannot check.
      heading={
        matchedCount > 0
          ? `Community art — ${matchedCount} fitting this post`
          : 'Community art — nothing matched the text, showing the best rated'
      }
      items={art}
      buildFilename={(item) => downloadName(item.label, item.media_type)}
    />
  )
}
