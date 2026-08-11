import { useEffect, useState } from 'react'
import { Download } from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_URL || ''

/**
 * Emote shortlist shown beside a generated social post.
 *
 * Deliberately a picker rather than an automatic attachment: an emote that
 * misses the mood reads worse under a post than no emote at all. The download
 * is separate too, because X renders no markdown — the file has to be attached
 * by hand, so the post text stays clean.
 */
export default function EmotePicker({ text }) {
  const [emotes, setEmotes] = useState([])
  const [selected, setSelected] = useState(null)

  useEffect(() => {
    let cancelled = false
    fetch(`${API_BASE}/api/emotes/suggest?text=${encodeURIComponent(text || '')}&limit=4`)
      .then((res) => (res.ok ? res.json() : { emotes: [] }))
      .then((data) => {
        if (!cancelled) setEmotes(data.emotes || [])
      })
      .catch(() => {
        if (!cancelled) setEmotes([])
      })
    return () => {
      cancelled = true
    }
  }, [text])

  if (!emotes.length) return null

  const active = selected || emotes[0]

  return (
    <div className="mt-2 pt-2 border-t border-white/5">
      <p className="text-[10px] uppercase tracking-wider text-brand-500 dark:text-brand-400 mb-1.5">
        Add an emote
      </p>
      <div className="flex items-center gap-2 flex-wrap">
        {emotes.map((emote) => (
          <button
            key={emote.name}
            onClick={() => setSelected(emote)}
            title={emote.name}
            className={`w-11 h-11 rounded-lg overflow-hidden border transition-colors ${
              active.name === emote.name
                ? 'border-accent bg-accent/10'
                : 'border-white/10 hover:border-accent/50'
            }`}
          >
            <img
              src={emote.preview_url}
              alt={emote.name}
              className="w-full h-full object-contain"
              loading="lazy"
            />
          </button>
        ))}

        <a
          href={active.download_url}
          download
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium bg-accent/15 text-accent border border-accent/30 hover:bg-accent/25 transition-colors"
        >
          <Download size={12} />
          Download GIF
        </a>
      </div>
      <p className="mt-1 text-[9px] text-brand-500 dark:text-brand-500">
        Downloads at 4x size, animation intact — attach it to the post yourself.
      </p>
    </div>
  )
}
