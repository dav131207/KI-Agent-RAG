import { useSyncExternalStore } from 'react'

/**
 * One switch for the Professor Pepe watermark on every picture the app hands
 * out — random memes, rare pepes, community art and both shortlist pickers.
 *
 * On by default: a picture reposted from the chat should carry the mark. Off
 * is a deliberate choice and is remembered per browser, so someone who wants
 * the originals is not asked again on every draw. Kept outside React state
 * because the pickers fetch on their own and need the value at fetch time
 * without being handed it through every component in between.
 */
const KEY = 'professorPepe.watermark'

let enabled = (() => {
  try {
    return localStorage.getItem(KEY) !== 'off'
  } catch {
    return true
  }
})()

const listeners = new Set()

export function getWatermark() {
  return enabled
}

export function setWatermark(next) {
  enabled = Boolean(next)
  try {
    localStorage.setItem(KEY, enabled ? 'on' : 'off')
  } catch {
    // Storage can be unavailable; the switch still holds for this session.
  }
  listeners.forEach((fn) => fn())
}

export function useWatermark() {
  const value = useSyncExternalStore(
    (fn) => {
      listeners.add(fn)
      return () => listeners.delete(fn)
    },
    getWatermark,
    getWatermark,
  )
  return [value, setWatermark]
}
