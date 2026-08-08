import { useState, useEffect } from 'react'
import { X, Download, Share } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

export default function MobileBanner() {
  const [show, setShow] = useState(false)
  const [deviceInfo, setDeviceInfo] = useState({ isIOS: false, isAndroid: false })

  useEffect(() => {
    // Check if running as standalone PWA
    const isStandalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone
    if (isStandalone) return

    const dismissed = localStorage.getItem('mobile_banner_dismissed')
    if (dismissed) return

    const ua = navigator.userAgent || navigator.vendor || window.opera
    const isIOS = /iPad|iPhone|iPod/.test(ua) && !window.MSStream
    const isAndroid = /android/i.test(ua)

    if (isIOS || isAndroid) {
      setDeviceInfo({ isIOS, isAndroid })
      setShow(true)
    }
  }, [])

  const handleClose = () => {
    localStorage.setItem('mobile_banner_dismissed', 'true')
    setShow(false)
  }

  if (!show) return null

  return (
    <AnimatePresence>
      <motion.div
        initial={{ y: -50, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: -50, opacity: 0 }}
        className="relative z-[60] w-full bg-accent text-white px-3 py-2 flex items-center justify-between gap-3 shadow-md"
      >
        <div className="flex-1 flex items-center gap-3">
          {deviceInfo.isIOS ? (
            <p className="text-xs sm:text-sm font-medium leading-tight">
              <strong>Installiere Professor Pepe:</strong> Tippe auf <Share size={14} className="inline mx-1" /> und dann "Zum Home-Bildschirm".
            </p>
          ) : (
            <div className="flex items-center gap-2 justify-between w-full">
              <p className="text-xs sm:text-sm font-medium leading-tight">
                Hol dir die Native Android App!
              </p>
              <a
                href="/app-release.apk"
                download
                className="flex items-center gap-1 bg-white/20 hover:bg-white/30 px-2 py-1 rounded text-xs font-bold transition-colors whitespace-nowrap"
              >
                <Download size={14} /> Download APK
              </a>
            </div>
          )}
        </div>
        <button onClick={handleClose} className="p-1 hover:bg-white/20 rounded-full transition-colors flex-shrink-0">
          <X size={16} />
        </button>
      </motion.div>
    </AnimatePresence>
  )
}
