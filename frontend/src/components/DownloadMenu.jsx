import { useState } from 'react'
import { Download, Stamp } from 'lucide-react'
import { hasWatermarkChoice, originalUrl, saveImage } from '../lib/download'

/**
 * The download buttons under a picture: one with the watermark, one without.
 *
 * The choice sits here, at the moment of saving, because that is the only
 * moment it matters — what is shown in the chat always carries the mark. A
 * clip or a piece that already has the branding on it is served as it is,
 * so it gets a single plain button rather than a choice that changes nothing.
 *
 * `size` picks between the compact row inside a message and the larger bar
 * in the fullscreen viewer.
 */
export default function DownloadMenu({ url, baseName = 'pepe', size = 'sm', className = '' }) {
  const [saving, setSaving] = useState(null)

  if (!url) return null

  const save = async (which, target) => {
    if (saving) return
    setSaving(which)
    try {
      await saveImage(target, baseName)
    } finally {
      setSaving(null)
    }
  }

  const big = size === 'lg'
  const base = big
    ? 'flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold transition-colors disabled:opacity-60'
    : 'flex items-center gap-1 shrink-0 px-2 py-1 rounded-lg text-[10px] font-medium transition-colors disabled:opacity-60'
  const primary = big
    ? `${base} bg-accent text-white hover:bg-accent/90`
    : `${base} bg-accent/15 text-accent border border-accent/30 hover:bg-accent/25`
  const secondary = big
    ? `${base} bg-white/10 text-white hover:bg-white/20`
    : `${base} bg-white/5 text-brand-300 dark:text-brand-300 border border-white/10 hover:bg-white/10 hover:text-white`
  const icon = big ? 16 : 10

  if (!hasWatermarkChoice(url)) {
    return (
      <div className={`flex items-center gap-2 ${className}`} data-lightbox-ignore>
        <button type="button" onClick={() => save('plain', url)} disabled={!!saving} className={primary}>
          <Download size={icon} />
          {saving ? 'Saving...' : 'Download'}
        </button>
      </div>
    )
  }

  return (
    <div className={`flex items-center gap-2 flex-wrap ${className}`} data-lightbox-ignore>
      <button
        type="button"
        onClick={() => save('mark', url)}
        disabled={!!saving}
        className={primary}
        title="Save with the Professor Pepe watermark"
      >
        <Stamp size={icon} />
        {saving === 'mark' ? 'Saving...' : big ? 'Download with watermark' : 'With watermark'}
      </button>
      <button
        type="button"
        onClick={() => save('original', originalUrl(url))}
        disabled={!!saving}
        className={secondary}
        title="Save the picture as it is, without the watermark"
      >
        <Download size={icon} />
        {saving === 'original' ? 'Saving...' : big ? 'Download original' : 'Original'}
      </button>
    </div>
  )
}
