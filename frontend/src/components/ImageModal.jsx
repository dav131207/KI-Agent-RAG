import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Loader2, X } from 'lucide-react'

/**
 * Fullscreen viewer for any picture in the chat.
 *
 * The picture is sized by the viewport, never by its own pixels: a wide meme
 * on a phone used to run off both edges because nothing capped its width,
 * and the close button sat 40px above the frame, which on a tall picture was
 * off the top of the screen. The watermark route can take seconds for a
 * large file, so the frame shows it is waiting instead of staying black.
 *
 * Rendered into document.body. Inside the chat it sat in the message area's
 * own stacking context (z-10), where no z-index can climb past the header
 * (z-30) in the layer above: the header painted over the top of every
 * picture and over the close button, so a tall picture looked cut off and
 * could not be closed by the button.
 */
export default function ImageModal({ src, onClose }) {
  const [loaded, setLoaded] = useState(false)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    setLoaded(false)
    setFailed(false)
  }, [src])

  useEffect(() => {
    if (!src) return undefined
    const onKey = (e) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [src, onClose])

  return createPortal(
    <AnimatePresence>
      {src && (
        <motion.div
          key="lightbox"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          onClick={onClose}
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-[100] bg-black/85 backdrop-blur-sm flex items-center justify-center p-3 sm:p-6"
          style={{
            paddingTop: 'max(0.75rem, env(safe-area-inset-top))',
            paddingBottom: 'max(0.75rem, env(safe-area-inset-bottom))',
          }}
        >
          {/* Pinned to the viewport, not to the picture, so it is always on
              screen whatever the picture's shape. */}
          <button
            onClick={onClose}
            aria-label="Close"
            className="absolute top-3 right-3 z-10 p-2 rounded-full bg-black/50 text-white/90 hover:text-white hover:bg-black/70 transition-colors"
            style={{ top: 'max(0.75rem, env(safe-area-inset-top))' }}
          >
            <X size={22} />
          </button>

          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.95, opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={(e) => e.stopPropagation()}
            className="relative flex items-center justify-center max-w-full max-h-full"
          >
            {!loaded && !failed && (
              <div className="absolute inset-0 flex items-center justify-center">
                <Loader2 className="animate-spin text-white/70" size={32} />
              </div>
            )}
            {failed ? (
              <p className="px-6 py-4 rounded-xl bg-white/10 text-white/80 text-sm text-center">
                The image could not be loaded.
              </p>
            ) : (
              <img
                src={src}
                alt=""
                onLoad={() => setLoaded(true)}
                onError={() => setFailed(true)}
                className={`block max-w-full h-auto w-auto object-contain rounded-xl sm:rounded-2xl shadow-2xl select-none transition-opacity duration-200 ${
                  loaded ? 'opacity-100' : 'opacity-0'
                }`}
                style={{
                  // Both axes come from the viewport. The frame's own padding
                  // is subtracted so the corners never touch the screen edge.
                  maxHeight: 'calc(100dvh - 4rem)',
                  maxWidth: 'calc(100vw - 2rem)',
                  // Keeps the spinner's frame from collapsing to nothing
                  // while the bytes are still on their way.
                  minWidth: loaded ? undefined : '8rem',
                  minHeight: loaded ? undefined : '8rem',
                }}
                draggable={false}
              />
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  )
}
