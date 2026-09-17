/**
 * Saving a picture from the chat, with or without the watermark.
 *
 * Every picture the app shows is served watermarked through /api/watermark.
 * The same route hands out the untouched file on ?watermark=false, so the
 * choice is made at the moment of saving, per picture, rather than up front
 * for everything: what is on screen always carries the mark, and the copy
 * that leaves the app is whichever the person asked for.
 */

const EXTENSION_BY_TYPE = {
  'image/png': 'png',
  'image/jpeg': 'jpg',
  'image/gif': 'gif',
  'image/webp': 'webp',
  'video/mp4': 'mp4',
  'video/webm': 'webm',
}

/** The unwatermarked variant of a proxied picture URL, or null if there is none. */
export function originalUrl(url) {
  if (!url || !url.includes('/api/watermark?')) return null
  if (/[?&]watermark=false\b/.test(url)) return url
  return `${url}&watermark=false`
}

/** Whether saving this picture is a choice at all (a clip or a branded piece is served as is). */
export function hasWatermarkChoice(url) {
  return originalUrl(url) !== null && !/[?&]watermark=false\b/.test(url)
}

/**
 * Fetch the bytes and save them under `baseName`, with the extension taken
 * from what actually arrived: the watermark route re-encodes stills as PNG,
 * while the original keeps its own format.
 *
 * A plain <a download> is only honoured same-origin; anywhere else the
 * browser quietly follows the link instead, which in a PWA means the service
 * worker answers the navigation with index.html and the app appears to
 * reload. A blob cannot be downgraded that way, and the filename is
 * guaranteed.
 */
export async function saveImage(url, baseName) {
  try {
    const res = await fetch(url)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const blob = await res.blob()
    const ext = EXTENSION_BY_TYPE[blob.type] || (baseName.match(/\.(\w+)$/) || [])[1] || 'png'
    const stem = baseName.replace(/\.\w+$/, '') || 'pepe'
    const objectUrl = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = objectUrl
    link.download = `${stem}.${ext}`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(objectUrl)
  } catch {
    // Opening it is still better than nothing; the reader can save by hand.
    window.open(url, '_blank', 'noopener')
  }
}
