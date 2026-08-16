import { useEffect, useState } from 'react'
import ShortlistPicker from './ShortlistPicker'

const API_BASE = import.meta.env.VITE_API_URL || ''

/**
 * Pepes shortlisted for a generated post.
 *
 * The post used to be handed whichever image ranked first, with no way to
 * disagree. Same reasoning as the community-art picker: the index matches on
 * substrings and its best guess is often not the author's, so the choice
 * belongs to the person publishing the post.
 */
export default function PepePicker({ topic, text }) {
  const [images, setImages] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetch(`${API_BASE}/api/images`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic, context: text, count: 4 }),
    })
      .then((res) => (res.ok ? res.json() : { images: [] }))
      .then((data) => {
        if (cancelled) return
        setImages(data.images || [])
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
  }, [topic, text])

  if (loading) {
    return (
      <div className="mt-2 pt-2 border-t border-white/5">
        <div className="h-32 rounded-lg bg-black/5 dark:bg-white/5 animate-pulse" />
      </div>
    )
  }

  return (
    <ShortlistPicker
      heading={`Pepes for this post — ${images.length} to choose from`}
      items={images}
      // The watermark route re-encodes everything it serves as PNG, so the
      // name follows what arrives, not what the source file was called.
      buildFilename={() => 'pepe.png'}
    />
  )
}
