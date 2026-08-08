import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useTheme } from './hooks/useTheme'
import AdminDashboard from './components/AdminDashboard'
import Chat from './components/Chat'
import MobileBanner from './components/MobileBanner'
import ParticlesBackground from './components/ParticlesBackground'
import WalletConnect from './components/WalletConnect'
import { trackEvent } from './lib/analytics'

const SUPPORT_ADDRESS = 'PhzpSqdSiMRNQ6ksCEDs4ufJtFfuyLCU9j'

function SupportModal({ isOpen, onClose }) {
  useEffect(() => {
    if (!isOpen) return
    const timer = setTimeout(onClose, 5000)
    return () => clearTimeout(timer)
  }, [isOpen, onClose])

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          key="support-modal"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm"
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            onClick={(e) => e.stopPropagation()}
            className="w-[90%] max-w-sm rounded-2xl bg-white dark:bg-brand-800 p-5 sm:p-6 shadow-2xl border border-brand-100 dark:border-white/10 text-center"
          >
            <h2 className="text-lg sm:text-xl font-bold mb-2">Support the Project</h2>
            <p className="text-xs sm:text-sm text-brand-500 dark:text-brand-400 mb-4">
              Help me fund this Project. Thanks in advance, fren!
            </p>
            <div className="font-mono text-[10px] sm:text-xs break-all bg-brand-100 dark:bg-brand-900 rounded-xl p-3 mb-3">
              {SUPPORT_ADDRESS}
            </div>
            <p className="text-accent text-xs sm:text-sm font-medium mb-4">Copied to clipboard!</p>
            <button
              onClick={onClose}
              className="btn-primary px-5 py-2 rounded-xl text-sm"
            >
              Close
            </button>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

export default function App() {
  const { isDark } = useTheme()
  const [showSupport, setShowSupport] = useState(false)
  const [showSplash, setShowSplash] = useState(true)

  useEffect(() => {
    const timer = setTimeout(() => setShowSplash(false), 2000)
    return () => clearTimeout(timer)
  }, [])

  const handleHeroClick = async () => {
    trackEvent('conversion', { conversion_type: 'support' })
    try {
      await navigator.clipboard.writeText(SUPPORT_ADDRESS)
    } catch {
      // ignore
    }
    setShowSupport(true)
  }

  const isAdmin = typeof window !== 'undefined' && window.location.pathname === '/admin'
  if (isAdmin) {
    return <AdminDashboard />
  }

  return (
    <>
      <AnimatePresence>
        {showSplash && (
          <motion.div
            key="splash"
            initial={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.8, ease: "easeInOut" }}
            className="fixed inset-0 z-[100] flex flex-col items-center justify-center bg-brand-900"
          >
            <motion.img
              src="/logo.png"
              alt="Loading"
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ 
                scale: [0.8, 1.05, 1],
                opacity: 1,
                rotate: [0, -5, 5, 0]
              }}
              transition={{ duration: 1.2, ease: "easeOut" }}
              className="w-32 h-32 md:w-48 md:h-48 object-contain drop-shadow-[0_0_25px_rgba(38,154,76,0.6)]"
            />
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.6, duration: 0.5 }}
              className="mt-8 flex items-center justify-center gap-2 mx-auto"
            >
              <div className="w-2.5 h-2.5 rounded-full bg-accent animate-bounce" style={{ animationDelay: '0ms' }} />
              <div className="w-2.5 h-2.5 rounded-full bg-accent animate-bounce" style={{ animationDelay: '150ms' }} />
              <div className="w-2.5 h-2.5 rounded-full bg-accent animate-bounce" style={{ animationDelay: '300ms' }} />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className={`min-h-screen transition-colors duration-500 flex flex-col ${isDark ? 'bg-brand-900 text-brand-50' : 'bg-brand-50 text-brand-900'}`}>
        <MobileBanner />
        <ParticlesBackground isDark={isDark} />
        <div className="flex-1 flex overflow-hidden">
        <main className="flex-1 flex flex-col relative">
          <header className="relative z-10 flex items-center justify-between md:grid md:grid-cols-[1fr_auto_1fr] gap-2 px-3 sm:px-4 md:px-6 py-2 bg-brand-800/70 dark:bg-brand-950/60 backdrop-blur-xl border-b border-brand-700/30 dark:border-white/5">
            <div className="hidden md:block" />

            <div
              onClick={handleHeroClick}
              className="flex items-center justify-center gap-2 md:gap-3 flex-1 md:flex-none min-w-0 cursor-pointer"
            >
              <motion.img
                src="/logo.png"
                alt="Professor Pepe Logo"
                initial={{ rotate: -10, scale: 0.8 }}
                animate={{ rotate: [0, 5, -5, 0], y: [0, -4, 0] }}
                transition={{
                  rotate: { duration: 6, repeat: Infinity, ease: 'easeInOut' },
                  y: { duration: 3, repeat: Infinity, ease: 'easeInOut' },
                  scale: { type: 'spring', stiffness: 200 },
                }}
                whileHover={{ scale: 1.1, rotate: 10 }}
                className="w-12 h-12 sm:w-14 sm:h-14 md:w-24 md:h-24 object-contain flex-shrink-0"
              />
              <div className="leading-tight text-center min-w-0">
                <h1 className="text-xl sm:text-2xl md:text-3xl font-black tracking-tight whitespace-nowrap">
                  <span className={isDark ? 'text-white' : 'text-brand-900'}>Professor</span>{' '}
                  <span className="text-accent">Pepe</span>
                </h1>
                <p className="text-[8px] sm:text-[9px] md:text-[10px] tracking-[0.12em] sm:tracking-[0.18em] md:tracking-[0.24em] text-brand-500 dark:text-brand-400 font-medium whitespace-nowrap">
                  Your daily dose of Intelligence
                </p>
              </div>
            </div>

            <div className="flex items-center justify-end">
              <WalletConnect />
            </div>
          </header>

          <SupportModal isOpen={showSupport} onClose={() => setShowSupport(false)} />

          <div className="flex-1 relative z-10 overflow-hidden">
            <Chat isDark={isDark} />
          </div>
        </main>
      </div>
    </div>
    </>
  )
}
