import { motion, AnimatePresence } from 'framer-motion'
import { X } from 'lucide-react'

export default function ImageModal({ src, onClose }) {
  if (!src) return null

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        className="fixed inset-0 z-[100] bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
      >
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.9, opacity: 0 }}
          onClick={(e) => e.stopPropagation()}
          className="relative max-w-4xl max-h-[90vh]"
        >
          <button
            onClick={onClose}
            className="absolute -top-10 right-0 p-2 text-white/80 hover:text-white transition-colors"
          >
            <X size={24} />
          </button>
          <img
            src={src}
            alt="Full size"
            className="rounded-2xl shadow-2xl max-h-[85vh] object-contain"
          />
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}
