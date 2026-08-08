import { motion } from 'framer-motion'
import { Sun, Moon } from 'lucide-react'

export default function ThemeToggle({ theme, toggle }) {
  const isDark = theme === 'dark'
  return (
    <button
      onClick={toggle}
      className={`relative p-2.5 rounded-xl transition-colors ${
        isDark ? 'bg-white/10 hover:bg-white/15' : 'bg-brand-100 hover:bg-brand-200'
      }`}
      aria-label="Toggle theme"
    >
      <motion.div
        initial={false}
        animate={{ rotate: isDark ? 0 : 180, scale: 1 }}
        transition={{ type: 'spring', stiffness: 200 }}
      >
        {isDark ? <Moon size={20} className="text-accent-light" /> : <Sun size={20} className="text-amber-500" />}
      </motion.div>
    </button>
  )
}
