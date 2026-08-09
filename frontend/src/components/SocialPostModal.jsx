import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Command, Globe, MessageSquare, Hash, ArrowRight, CornerDownLeft, Zap } from 'lucide-react'

const LANGUAGES = [
  'English', 'German', 'Spanish', 'French',
  'Mandarin', 'Arabic', 'Japanese', 'Russian', 'Hindi', 'Portuguese'
]

const PLATFORMS = [
  { id: 'Twitter', label: 'Twitter / X', desc: 'Short, punchy, high-engagement' },
  { id: 'Reddit', label: 'Reddit', desc: 'Long-form, analytical, community-focused' },
  { id: 'TikTok', label: 'TikTok', desc: 'Viral script, visual hooks, Gen-Z vibe' }
]

// Pure tones. Algorithm tactics live in the "Break the algo" command instead,
// so picking a voice and picking a growth tactic stay separate decisions.
const TONALITIES = [
  { id: 'Humorous', label: 'Humorous', desc: 'Sarcastic & witty meme style' },
  { id: 'Professional', label: 'Professional', desc: 'Direct, factual, and serious' },
  { id: 'Hype', label: 'Hype', desc: 'High energy, bullish sentiment' },
  { id: 'Educational', label: 'Educational', desc: 'Informative tech breakdown' },
  { id: 'Philosophical', label: 'Philosophical', desc: 'Abstract thoughts on decentralization' }
]

const TWITTER_STRATEGIES = [
  { id: 'Standard', label: 'Standard (In-Cluster)', desc: 'Classic Pepe style with cashtags' },
  { id: 'Brokerage', label: 'Brokerage (Cross-Cluster)', desc: 'Bridge Crypto history with Govtech/Tech. No cashtags' },
  { id: 'Mid-Tier Reply', label: 'Mid-Tier Reply', desc: 'High-value reply to a specific tweet' },
  { id: 'Engagement', label: 'Engagement (Weak Ties)', desc: 'Ask structural questions to provoke replies' },
  { id: 'Miner Synergy', label: 'Miner Synergy (Dogecoin/Scrypt)', desc: 'Focus on PoW, UTXO, and Scrypt merged mining' }
]

const ALGO_TACTICS = [
  { id: 'Bait Correction', label: 'Bait Correction', desc: "Cunningham's Law — a wrong-on-purpose take people rush to correct" },
  { id: 'Contrarian Take', label: 'Contrarian Take', desc: 'Defensible minority position that splits the room' },
  { id: 'Reply Bait', label: 'Reply Bait', desc: 'Open question that is cheap to answer and hard to scroll past' },
  { id: 'Rewatch Hook', label: 'Rewatch Hook', desc: 'Withhold the payoff so people watch or read twice' },
  { id: 'Bubble Break', label: 'Bubble Break', desc: 'Frame it for an adjacent community that is not already in crypto' }
]

const FORMATS = [
  { id: 'Single', label: 'Single Post', desc: 'One post, hard limit 280 characters' },
  { id: 'Thread', label: 'Thread', desc: 'Numbered thread, each part under 280 characters' }
]

// Steps are derived, not hardcoded: the format step only exists for Twitter and
// the third step swaps between tone and tactic depending on the command.
function buildSteps(mode, platform) {
  const steps = ['platform', 'language', mode === 'algo' ? 'tactic' : 'tone']
  if (platform === 'Twitter') steps.push('format')
  steps.push('topic')
  return steps
}

export default function SocialPostModal({ isOpen, onClose, onSubmit, isDark, mode = 'social' }) {
  const [stepIndex, setStepIndex] = useState(0)
  const [platform, setPlatform] = useState('')
  const [language, setLanguage] = useState('')
  const [choice, setChoice] = useState('')
  const [format, setFormat] = useState('')
  const [search, setSearch] = useState('')
  const inputRef = useRef(null)

  useEffect(() => {
    if (isOpen) {
      setStepIndex(0)
      setPlatform('')
      setLanguage('')
      setChoice('')
      setFormat('')
      setSearch('')
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }, [isOpen, mode])

  if (!isOpen) return null

  const isAlgo = mode === 'algo'
  const steps = buildSteps(mode, platform)
  const step = steps[stepIndex] || 'topic'

  const matches = (text) => text.toLowerCase().includes(search.toLowerCase())
  const choiceList = isAlgo
    ? ALGO_TACTICS
    : platform === 'Twitter'
      ? TWITTER_STRATEGIES
      : TONALITIES

  const options = {
    platform: PLATFORMS.filter((p) => matches(p.label) || matches(p.desc)),
    language: LANGUAGES.filter((l) => matches(l)).map((l) => ({ id: l, label: l, desc: '' })),
    tone: choiceList.filter((t) => matches(t.label) || matches(t.desc)),
    tactic: choiceList.filter((t) => matches(t.label) || matches(t.desc)),
    format: FORMATS.filter((f) => matches(f.label) || matches(f.desc)),
    topic: [],
  }[step]

  const submit = () =>
    onSubmit({
      platform,
      language,
      tonality: choice,
      format: platform === 'Twitter' ? format || 'Single' : '',
      topic: search,
      mode,
    })

  const select = (id) => {
    if (step === 'platform') setPlatform(id)
    else if (step === 'language') setLanguage(id)
    else if (step === 'format') setFormat(id)
    else setChoice(id)
    setStepIndex((i) => i + 1)
    setSearch('')
    inputRef.current?.focus()
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      if (stepIndex > 0) {
        setStepIndex((i) => i - 1)
        setSearch('')
      } else {
        onClose()
      }
      return
    }
    if (e.key === 'Enter') {
      e.preventDefault()
      if (step === 'topic') submit()
      else if (options.length > 0) select(options[0].id)
    }
  }

  const placeholder = {
    platform: 'Search platform...',
    language: 'Search language...',
    tone: platform === 'Twitter' ? 'Search strategy...' : 'Search tonality...',
    tactic: 'Search tactic...',
    format: 'Single post or thread...',
    topic:
      platform === 'Twitter' && choice === 'Mid-Tier Reply'
        ? 'Paste the tweet you want to reply to...'
        : platform === 'Twitter' && choice === 'Brokerage'
          ? 'What tech/public sector topic should we bridge with Pepe?'
          : platform === 'Twitter' && choice === 'Miner Synergy'
            ? 'E.g. Hashrate, UTXO aging, Scrypt economics...'
            : isAlgo
              ? 'What should the post be about? (Press Enter to generate)'
              : 'What is this post about? (Press Enter to generate)',
  }[step]

  const crumbs = [
    { key: 'platform', icon: <Globe size={12} />, label: 'Platform', value: platform },
    { key: 'language', icon: <Globe size={12} />, label: 'Language', value: language },
    {
      key: isAlgo ? 'tactic' : 'tone',
      icon: isAlgo ? <Zap size={12} /> : <MessageSquare size={12} />,
      label: isAlgo ? 'Tactic' : platform === 'Twitter' ? 'Strategy' : 'Tonality',
      value: choice,
    },
    ...(platform === 'Twitter'
      ? [{ key: 'format', icon: <Hash size={12} />, label: 'Format', value: format }]
      : []),
    { key: 'topic', icon: <Hash size={12} />, label: 'Topic', value: '' },
  ]

  const containerVariants = {
    hidden: { opacity: 0, scale: 0.98, y: -20 },
    visible: { opacity: 1, scale: 1, y: 0, transition: { duration: 0.2, ease: 'easeOut' } },
    exit: { opacity: 0, scale: 0.98, y: 10, transition: { duration: 0.15 } }
  }

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-[100] flex items-start justify-center pt-[15vh] px-4"
      >
        <div
          className="absolute inset-0 bg-black/60 backdrop-blur-sm"
          onClick={onClose}
        />

        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          className={`relative w-full max-w-2xl overflow-hidden rounded-2xl shadow-2xl border ${
            isDark
              ? 'bg-[#111318] border-white/10 text-white shadow-black'
              : 'bg-white border-brand-200 text-brand-900 shadow-brand-500/20'
          }`}
        >
          {/* Header Status Bar */}
          <div className={`px-4 py-2 text-[11px] uppercase tracking-widest font-bold flex flex-wrap gap-x-4 gap-y-2 border-b ${isDark ? 'border-white/5 bg-white/5' : 'border-brand-100 bg-brand-50'}`}>
            {crumbs.map((crumb) => {
              const reached = steps.indexOf(crumb.key) <= stepIndex
              return (
                <span
                  key={crumb.key}
                  className={`${reached ? 'text-accent' : 'opacity-40'} transition-colors flex items-center gap-1.5`}
                >
                  {crumb.icon} {crumb.label}
                  {crumb.value && (
                    <span className="text-white normal-case ml-1 px-1.5 bg-accent/20 rounded">{crumb.value}</span>
                  )}
                </span>
              )
            })}
          </div>

          {/* Search / Input Bar */}
          <div className="flex items-center px-5 py-4 gap-4">
            <Command className={`shrink-0 ${isDark ? 'text-brand-500' : 'text-brand-400'}`} size={20} />
            <input
              ref={inputRef}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              className={`flex-1 bg-transparent text-lg outline-none font-medium placeholder:font-normal ${
                isDark ? 'placeholder:text-brand-600' : 'placeholder:text-brand-400'
              }`}
            />
          </div>

          {/* Results List */}
          {step !== 'topic' && (
            <div className={`max-h-[300px] overflow-y-auto border-t ${isDark ? 'border-white/5' : 'border-brand-100'} p-2`}>
              {options.map((option, idx) => (
                <button
                  key={option.id}
                  onClick={() => select(option.id)}
                  className={`w-full flex items-center justify-between px-4 py-3 rounded-xl text-left transition-colors ${
                    idx === 0
                      ? isDark ? 'bg-white/10' : 'bg-brand-50'
                      : isDark ? 'hover:bg-white/5' : 'hover:bg-brand-50/50'
                  }`}
                >
                  <div className="flex flex-col">
                    <span className="font-medium">{option.label}</span>
                    {option.desc && (
                      <span className={`text-xs ${isDark ? 'text-brand-500' : 'text-brand-500'}`}>{option.desc}</span>
                    )}
                  </div>
                  {idx === 0 && <span className={`text-[10px] flex items-center gap-1 px-2 py-1 rounded ${isDark ? 'bg-white/10 text-brand-300' : 'bg-brand-100 text-brand-600'}`}>Press <CornerDownLeft size={10}/></span>}
                </button>
              ))}

              {options.length === 0 && (
                <div className={`px-4 py-8 text-center text-sm ${isDark ? 'text-brand-500' : 'text-brand-400'}`}>
                  No results found.
                </div>
              )}
            </div>
          )}

          {step === 'topic' && (
            <div className={`px-6 py-6 border-t ${isDark ? 'border-white/5 bg-white/5' : 'border-brand-100 bg-brand-50'} flex justify-between items-center`}>
              <div className="text-sm opacity-60 flex items-center gap-2">
                Type your context and press <kbd className="px-1.5 py-0.5 rounded border border-current font-mono text-[10px]">ENTER</kbd>
              </div>
              <button
                onClick={submit}
                className="flex items-center gap-2 px-6 py-2 rounded-lg bg-accent text-brand-950 font-bold hover:opacity-90 transition-opacity shadow-lg shadow-accent/20"
              >
                Generate <ArrowRight size={16} />
              </button>
            </div>
          )}
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}
