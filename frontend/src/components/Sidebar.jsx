import { motion } from 'framer-motion'
import { PanelLeftClose, PanelLeft, Plus } from 'lucide-react'

export default function Sidebar({ topics, activeTopic, onSelect, isOpen, onToggle, isDark }) {
  return (
    <>
      {/* mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-40 md:hidden"
          onClick={onToggle}
        />
      )}

      <motion.aside
        initial={false}
        animate={{ width: isOpen ? 260 : 0, opacity: isOpen ? 1 : 0 }}
        transition={{ type: 'spring', stiffness: 300, damping: 30 }}
        className={`relative z-50 flex flex-col border-r overflow-hidden ${
          isDark ? 'bg-zen-900/80 border-white/10' : 'bg-white/80 border-zen-200'
        } backdrop-blur-xl`}
      >
        <div className="p-4 flex items-center justify-between">
          <span className="text-sm font-semibold uppercase tracking-wider text-zen-500 dark:text-zen-400">
            Topics
          </span>
          <button
            onClick={onToggle}
            className={`p-2 rounded-lg transition-colors ${
              isDark ? 'hover:bg-white/10' : 'hover:bg-zen-100'
            }`}
            aria-label="Collapse sidebar"
          >
            <PanelLeftClose size={18} />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto scrollbar-thin px-3 pb-4 space-y-1">
          {topics.map((topic, idx) => {
            const active = activeTopic.id === topic.id
            return (
              <motion.button
                key={topic.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: idx * 0.03 }}
                onClick={() => {
                  onSelect(topic)
                  if (window.innerWidth < 768) onToggle()
                }}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-left transition-all duration-200 group ${
                  active
                    ? 'bg-accent/10 text-accent-dark dark:text-accent-light ring-1 ring-accent/30'
                    : isDark
                    ? 'text-zen-300 hover:bg-white/5'
                    : 'text-zen-700 hover:bg-zen-100'
                }`}
              >
                <span className="text-lg">{topic.icon}</span>
                <span className="font-medium">{topic.label}</span>
                {active && (
                  <motion.div
                    layoutId="active-topic"
                    className="ml-auto w-1.5 h-1.5 rounded-full bg-accent"
                  />
                )}
              </motion.button>
            )
          })}
        </nav>

        <div className="p-4 border-t border-zen-200 dark:border-white/10">
          <button className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl border border-dashed border-zen-300 dark:border-zen-700 text-zen-500 dark:text-zen-400 hover:border-accent hover:text-accent transition-colors">
            <Plus size={16} />
            <span className="text-sm font-medium">New topic</span>
          </button>
        </div>
      </motion.aside>

      {/* floating expand button when collapsed */}
      {!isOpen && (
        <motion.button
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          onClick={onToggle}
          className={`fixed left-4 top-4 z-50 p-2.5 rounded-xl shadow-lg ${
            isDark ? 'bg-zen-900 border border-white/10' : 'bg-white border border-zen-200'
          }`}
          aria-label="Expand sidebar"
        >
          <PanelLeft size={20} />
        </motion.button>
      )}
    </>
  )
}
