import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Command, Globe, MessageSquare, Hash, ArrowRight, CornerDownLeft } from 'lucide-react'

const LANGUAGES = [
  'English', 'German', 'Spanish', 'French', 
  'Mandarin', 'Arabic', 'Japanese', 'Russian', 'Hindi', 'Portuguese'
]

const PLATFORMS = [
  { id: 'Twitter', label: 'Twitter / X', desc: 'Short, punchy, high-engagement' },
  { id: 'Reddit', label: 'Reddit', desc: 'Long-form, analytical, community-focused' },
  { id: 'TikTok', label: 'TikTok', desc: 'Viral script, visual hooks, Gen-Z vibe' }
]

const TONALITIES = [
  { id: 'Humorous', label: 'Humorous', desc: 'Sarcastic & witty meme style' },
  { id: 'Professional', label: 'Professional', desc: 'Direct, factual, and serious' },
  { id: 'Hype', label: 'Hype', desc: 'High energy, bullish sentiment' },
  { id: 'Educational', label: 'Educational', desc: 'Informative tech breakdown' },
  { id: 'Shill', label: 'Shill', desc: 'Aggressive marketing, tag influencers (break the bubble)' },
  { id: 'Philosophical', label: 'Philosophical', desc: 'Abstract thoughts on decentralization' }
]

const TWITTER_STRATEGIES = [
  { id: 'Standard', label: 'Standard (In-Cluster)', desc: 'Classic Pepe style with cashtags' },
  { id: 'Brokerage', label: 'Brokerage (Cross-Cluster)', desc: 'Bridge Crypto history with Govtech/Tech. No cashtags' },
  { id: 'Mid-Tier Reply', label: 'Mid-Tier Reply', desc: 'High-value reply to a specific tweet' },
  { id: 'Engagement', label: 'Engagement (Weak Ties)', desc: 'Ask structural questions to provoke replies' }
]

export default function SocialPostModal({ isOpen, onClose, onSubmit, isDark }) {
  const [step, setStep] = useState(0) // 0: Platform, 1: Lang, 2: Tone, 3: Topic
  
  const [platform, setPlatform] = useState('')
  const [language, setLanguage] = useState('')
  const [tonality, setTonality] = useState('')
  const [topic, setTopic] = useState('')
  const [search, setSearch] = useState('')
  const inputRef = useRef(null)

  useEffect(() => {
    if (isOpen) {
      setStep(0)
      setPlatform('')
      setLanguage('')
      setTonality('')
      setTopic('')
      setSearch('')
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }, [isOpen])

  if (!isOpen) return null

  // Filter lists based on search input
  const filteredPlatforms = PLATFORMS.filter(p => 
    p.label.toLowerCase().includes(search.toLowerCase()) || 
    p.desc.toLowerCase().includes(search.toLowerCase())
  )
  const filteredLanguages = LANGUAGES.filter(l => l.toLowerCase().includes(search.toLowerCase()))
  const currentStrategies = platform === 'Twitter' ? TWITTER_STRATEGIES : TONALITIES
  const filteredTonalities = currentStrategies.filter(t => 
    t.label.toLowerCase().includes(search.toLowerCase()) || 
    t.desc.toLowerCase().includes(search.toLowerCase())
  )

  const handleKeyDown = (e, items) => {
    if (e.key === 'Escape') {
      if (step > 0) {
        if (platform === 'Reddit' && step === 3) {
          setStep(1)
        } else {
          setStep(s => s - 1)
        }
        setSearch('')
      } else {
        onClose()
      }
      return
    }

    if (e.key === 'Enter') {
      e.preventDefault()
      if (step === 0 && items.length > 0) {
        setPlatform(items[0].id)
        setStep(1)
        setSearch('')
      } else if (step === 1 && items.length > 0) {
        setLanguage(items[0])
        if (platform === 'Reddit') {
          setTonality('')
          setStep(3)
        } else {
          setStep(2)
        }
        setSearch('')
      } else if (step === 2 && items.length > 0) {
        setTonality(items[0].id)
        setStep(3)
        setSearch('')
      } else if (step === 3) {
        onSubmit({ platform, language, tonality, topic: search })
      }
    }
  }

  const containerVariants = {
    hidden: { opacity: 0, scale: 0.98, y: -20 },
    visible: { opacity: 1, scale: 1, y: 0, transition: { duration: 0.2, ease: "easeOut" } },
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
            <span className={`${step >= 0 ? 'text-accent' : 'opacity-40'} transition-colors flex items-center gap-1.5`}><Globe size={12}/> Platform {platform && <span className="text-white normal-case ml-1 px-1.5 bg-accent/20 rounded">{platform}</span>}</span>
            <span className={`${step >= 1 ? 'text-accent' : 'opacity-40'} transition-colors flex items-center gap-1.5`}><Globe size={12}/> Language {language && <span className="text-white normal-case ml-1 px-1.5 bg-accent/20 rounded">{language}</span>}</span>
            {platform !== 'Reddit' && (
              <span className={`${step >= 2 ? 'text-accent' : 'opacity-40'} transition-colors flex items-center gap-1.5`}><MessageSquare size={12}/> {platform === 'Twitter' ? 'Strategy' : 'Tonality'} {tonality && <span className="text-white normal-case ml-1 px-1.5 bg-accent/20 rounded">{tonality}</span>}</span>
            )}
            <span className={`${step >= 3 ? 'text-accent' : 'opacity-40'} transition-colors flex items-center gap-1.5`}><Hash size={12}/> Topic</span>
          </div>

          {/* Search / Input Bar */}
          <div className="flex items-center px-5 py-4 gap-4">
            <Command className={`shrink-0 ${isDark ? 'text-brand-500' : 'text-brand-400'}`} size={20} />
            <input
              ref={inputRef}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => {
                const items = step === 0 ? filteredPlatforms : step === 1 ? filteredLanguages : step === 2 ? filteredTonalities : []
                handleKeyDown(e, items)
              }}
              placeholder={
                step === 0 ? "Search platform..." : 
                step === 1 ? "Search language..." : 
                step === 2 && platform !== 'Reddit' ? (platform === 'Twitter' ? "Search strategy..." : "Search tonality...") : 
                platform === 'Twitter' && tonality === 'Mid-Tier Reply' ? "Paste the tweet you want to reply to..." :
                platform === 'Twitter' && tonality === 'Brokerage' ? "What tech/public sector topic should we bridge with Pepe?" :
                platform === 'Twitter' && tonality === 'Engagement' ? "What structural topic should we ask about?" :
                "What is this post about? (Press Enter to generate)"
              }
              className={`flex-1 bg-transparent text-lg outline-none font-medium placeholder:font-normal ${
                isDark ? 'placeholder:text-brand-600' : 'placeholder:text-brand-400'
              }`}
            />
          </div>

          {/* Results List */}
          {step < 3 && (
            <div className={`max-h-[300px] overflow-y-auto border-t ${isDark ? 'border-white/5' : 'border-brand-100'} p-2`}>
              {step === 0 && filteredPlatforms.map((p, idx) => (
                <button
                  key={p.id}
                  onClick={() => { setPlatform(p.id); setStep(1); setSearch(''); inputRef.current?.focus() }}
                  className={`w-full flex items-center justify-between px-4 py-3 rounded-xl text-left transition-colors ${
                    idx === 0 
                      ? isDark ? 'bg-white/10' : 'bg-brand-50' 
                      : isDark ? 'hover:bg-white/5' : 'hover:bg-brand-50/50'
                  }`}
                >
                  <div className="flex flex-col">
                    <span className="font-medium">{p.label}</span>
                    <span className={`text-xs ${isDark ? 'text-brand-500' : 'text-brand-500'}`}>{p.desc}</span>
                  </div>
                  {idx === 0 && <span className={`text-[10px] flex items-center gap-1 px-2 py-1 rounded ${isDark ? 'bg-white/10 text-brand-300' : 'bg-brand-100 text-brand-600'}`}>Press <CornerDownLeft size={10}/></span>}
                </button>
              ))}

              {step === 1 && filteredLanguages.map((l, idx) => (
                <button
                  key={l}
                  onClick={() => { 
                    setLanguage(l); 
                    if (platform === 'Reddit') {
                      setTonality('');
                      setStep(3);
                    } else {
                      setStep(2);
                    }
                    setSearch(''); 
                    inputRef.current?.focus();
                  }}
                  className={`w-full flex items-center justify-between px-4 py-3 rounded-xl text-left transition-colors ${
                    idx === 0 
                      ? isDark ? 'bg-white/10' : 'bg-brand-50' 
                      : isDark ? 'hover:bg-white/5' : 'hover:bg-brand-50/50'
                  }`}
                >
                  <span className="font-medium">{l}</span>
                  {idx === 0 && <span className={`text-[10px] flex items-center gap-1 px-2 py-1 rounded ${isDark ? 'bg-white/10 text-brand-300' : 'bg-brand-100 text-brand-600'}`}>Press <CornerDownLeft size={10}/></span>}
                </button>
              ))}

              {step === 2 && filteredTonalities.map((t, idx) => (
                <button
                  key={t.id}
                  onClick={() => { setTonality(t.id); setStep(3); setSearch(''); inputRef.current?.focus() }}
                  className={`w-full flex items-center justify-between px-4 py-3 rounded-xl text-left transition-colors ${
                    idx === 0 
                      ? isDark ? 'bg-white/10' : 'bg-brand-50' 
                      : isDark ? 'hover:bg-white/5' : 'hover:bg-brand-50/50'
                  }`}
                >
                  <div className="flex flex-col">
                    <span className="font-medium">{t.label}</span>
                    <span className={`text-xs ${isDark ? 'text-brand-500' : 'text-brand-500'}`}>{t.desc}</span>
                  </div>
                  {idx === 0 && <span className={`text-[10px] flex items-center gap-1 px-2 py-1 rounded ${isDark ? 'bg-white/10 text-brand-300' : 'bg-brand-100 text-brand-600'}`}>Press <CornerDownLeft size={10}/></span>}
                </button>
              ))}

              {((step === 0 && filteredPlatforms.length === 0) || (step === 1 && filteredLanguages.length === 0) || (step === 2 && filteredTonalities.length === 0)) && (
                <div className={`px-4 py-8 text-center text-sm ${isDark ? 'text-brand-500' : 'text-brand-400'}`}>
                  No results found.
                </div>
              )}
            </div>
          )}

          {step === 3 && (
            <div className={`px-6 py-6 border-t ${isDark ? 'border-white/5 bg-white/5' : 'border-brand-100 bg-brand-50'} flex justify-between items-center`}>
              <div className="text-sm opacity-60 flex items-center gap-2">
                Type your context and press <kbd className="px-1.5 py-0.5 rounded border border-current font-mono text-[10px]">ENTER</kbd>
              </div>
              <button
                onClick={() => onSubmit({ platform, language, tonality, topic: search })}
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
