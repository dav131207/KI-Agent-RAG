import { useState } from 'react'
import { Download } from 'lucide-react'

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
  const [downloading, setDownloading] = useState(false)

  if (!items?.length) return null

  const active = items.find((i) => i.id === selectedId) || items[0]

  /**
   * Save the picture.
   *
   * A plain <a download> is only honoured same-origin; anywhere else the
   * browser quietly ignores it and follows the link instead, which in a PWA
   * means the service worker answers the navigation with index.html and the
   * app appears to reload. Fetching the bytes and saving a blob cannot be
   * downgraded that way, and the filename is guaranteed.
   */
  const handleDownload = async () => {
    if (downloading) return
    setDownloading(true)
    try {
      const res = await fetch(active.url)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const blob = await res.blob()
      const objectUrl = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = objectUrl
      link.download = buildFilename(active)
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(objectUrl)
    } catch {
      // Opening it is still better than nothing; the reader can save by hand.
      window.open(active.url, '_blank', 'noopener')
    } finally {
      setDownloading(false)
    }
  }

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
        <button
          type="button"
          onClick={handleDownload}
          disabled={downloading}
          className="flex items-center gap-1 shrink-0 px-2 py-1 rounded-lg text-[10px] font-medium bg-accent/15 text-accent border border-accent/30 hover:bg-accent/25 transition-colors disabled:opacity-60"
        >
          <Download size={10} />
          {downloading ? 'Saving...' : 'Download'}
        </button>
      </div>
    </div>
  )
}
