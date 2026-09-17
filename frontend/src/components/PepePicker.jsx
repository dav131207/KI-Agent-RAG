import { useEffect, useState } from 'react'
import ShortlistPicker from './ShortlistPicker'

const API_BASE = import.meta.env.VITE_API_URL || ''

/**
 * Pepes shortlisted for a generated post, or for a picture the user asked for.
 *
 * The post used to be handed whichever image ranked first, with no way to
 * disagree. Same reasoning as the community-art picker: the index matches on
 * substrings and its best guess is often not the author's, so the choice
 * belongs to the person publishing the post. `search` marks the second use:
 * the topic is then an extracted term ("football"), not a command.
 */
export default function PepePicker({ topic, text, search = false }) {
  const [images, setImages] = useState([])
  const [matched, setMatched] = useState(true)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetch(`${API_BASE}/api/images`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      // A search ranks against its own term. The chat reply would otherwise
      // do the ranking, and it talks about the request, not the picture.
      body: JSON.stringify({ topic, context: search ? topic : text, count: 4 }),
    })
      .then((res) => (res.ok ? res.json() : { images: [] }))
      .then((data) => {
        if (cancelled) return
        setImages(data.images || [])
        setMatched(data.matched !== false)
        setLoading(false)
      })
      .catch(() => {
        if (cancelled) return
        setImages([])
        setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [topic, text, search])

  if (loading) {
    return (
      <div className="mt-2 pt-2 border-t border-white/5">
        <div className="h-32 rounded-lg bg-black/5 dark:bg-white/5 animate-pulse" />
      </div>
    )
  }

  // The index falls back to random pictures when a term matches nothing.
  // Four random Pepes under "playing football" must not be presented as
  // football; the heading says what happened.
  const heading = !search
    ? `Pepes for this post — ${images.length} to choose from`
    : !topic
      ? `${images.length} Pepes for you`
      : matched
        ? `Pepes for "${topic}" — ${images.length} to choose from`
        : `Nothing matched "${topic}" — ${images.length} random Pepes instead`

  return (
    <ShortlistPicker
      heading={heading}
      items={images}
      // The watermark route re-encodes everything it serves as PNG, so the
      // name follows what arrives, not what the source file was called.
      buildFilename={() => 'pepe.png'}
    />
  )
}
