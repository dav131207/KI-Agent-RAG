import { useState } from 'react'
import DownloadMenu from './DownloadMenu'

/**
 * A shortlist of pictures with a preview above and thumbnails below.
 *
 * Shared by the community-art and Pepe pickers, which differ only in where
 * their candidates come from.
 *
 * The wrapper carries data-lightbox-ignore: the message list opens a fullscreen
 * viewer for any <img> clicked inside a message, which meant picking a
 * thumbnail also threw the lightbox open over it. Selecting is not asking to
 * see it fullscreen — the preview right above is what answers that.
 */
export default function ShortlistPicker({ heading, items, buildFilename }) {
  const [selectedId, setSelectedId] = useState(null)

  if (!items?.length) return null

  const active = items.find((i) => i.id === selectedId) || items[0]

  return (
    <div className="mt-2 pt-2 border-t border-white/5" data-lightbox-ignore>
      <p className="text-[10px] uppercase tracking-wider text-brand-500 dark:text-brand-400 mb-1.5">
        {heading}
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
          alt={active.description || active.label || 'Preview'}
          className="rounded-lg max-h-56 w-auto mx-auto shadow-sm"
        />
      )}

      {items.length > 1 && (
        <div className="flex items-center gap-2 flex-wrap mt-2">
          {items.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setSelectedId(item.id)}
              title={item.description || item.label || ''}
              aria-pressed={active.id === item.id}
              className={`w-12 h-12 rounded-lg overflow-hidden border transition-colors ${
                active.id === item.id
                  ? 'border-accent bg-accent/10'
                  : item.matched
                    ? 'border-accent/30 hover:border-accent/60'
                    : 'border-white/10 hover:border-accent/50'
              }`}
            >
              {item.media_type === 'video' ? (
                <span className="w-full h-full flex items-center justify-center text-[9px] font-semibold text-brand-400">
                  MP4
                </span>
              ) : (
                <img
                  src={item.url}
                  alt={item.label || ''}
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
          {[active.label, active.description].filter(Boolean).join(' — ')}
        </p>
        {/* Same reason the emote download is separate: X renders no markdown,
            so the file has to be attached by hand and the post text stays
            clean. */}
        <DownloadMenu url={active.url} baseName={buildFilename(active)} />
      </div>
    </div>
  )
}
