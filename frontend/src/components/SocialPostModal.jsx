import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Command, Globe, MessageSquare, Hash, ArrowRight, CornerDownLeft, Target, Image as ImageIcon } from 'lucide-react'

const LANGUAGES = [
  'English', 'German', 'Spanish', 'French',
  'Mandarin', 'Arabic', 'Japanese', 'Russian', 'Hindi', 'Portuguese'
]

const PLATFORMS = [
  { id: 'Twitter', label: 'Twitter / X', desc: 'Short, punchy, high-engagement' },
  { id: 'Reddit', label: 'Reddit', desc: 'Long-form, analytical, community-focused' },
  { id: 'TikTok', label: 'TikTok', desc: 'Viral script, visual hooks, Gen-Z vibe' }
]

// One list of goals in plain language. It replaces the old split between
// tonalities, Twitter strategies and algorithm tactics, which overlapped
// ("Engagement" and "Reply Bait" both chased replies) and were named in jargon
// a newcomer could not decode. The question is what the post should achieve.
const GOALS = [
  { id: 'Community', label: 'Post to the community', desc: 'Classic Pepe style, with cashtags and the usual handles' },
  { id: 'Explain', label: 'Explain something', desc: 'Break the tech down so anyone can follow it' },
  { id: 'Outside', label: 'Reach people outside crypto', desc: 'No slang — framed for a tech or public-sector audience' },
  { id: 'Discussion', label: 'Start a discussion', desc: 'Ends on a question that gets people replying' },
  { id: 'Poll', label: 'Run a community poll', desc: 'A short scale everyone can answer in one tap' },
  { id: 'Data', label: 'Show network data', desc: 'Hashrate and mining, with a live chart attached' },
  { id: 'Reply', label: 'Reply to someone', desc: 'A useful reply to somebody else\'s post' },
  { id: 'Provoke', label: 'Provoke disagreement', desc: 'A sharp take people will want to correct' },
]

const FORMATS = [
  { id: 'Single', label: 'Single Post', desc: 'One post, hard limit 280 characters' },
  { id: 'Thread', label: 'Thread', desc: 'Numbered thread, each part under 280 characters' }
]

// Where the picture comes from. Community art is matched against the finished
// post rather than the topic, which is why it offers a shortlist instead of
// attaching one image blind.
const VISUALS = [
  { id: 'Community', label: 'Community art', desc: 'Matched to the finished post, with alternatives to choose from' },
  { id: 'Rare', label: 'Rare Pepe', desc: 'From the Rare Pepe collection' },
  { id: 'Random', label: 'Random Pepe', desc: 'A meme picked to fit the post' },
  { id: 'None', label: 'No image', desc: 'Text only' },
]

// A post arguing from network data gets the live chart, so that goal offers it
// as its first option rather than a meme.
const CHAIN_VISUAL = {
  id: 'Chain',
  label: 'On-chain chart',
  desc: 'Live hashrate and block data, rendered as a card',
}

function visualsFor(goal) {
  return goal === 'Data' ? [CHAIN_VISUAL, ...VISUALS] : VISUALS
}

// Steps are derived, not hardcoded: the format step only exists for Twitter.
function buildSteps(platform) {
  const steps = ['platform', 'language', 'goal']
  if (platform === 'Twitter') steps.push('format')
  steps.push('visual', 'topic')
  return steps
}

export default function SocialPostModal({ isOpen, onClose, onSubmit, isDark }) {
  const [stepIndex, setStepIndex] = useState(0)
  const [platform, setPlatform] = useState('')
  const [language, setLanguage] = useState('')
  const [goal, setGoal] = useState('')
  const [format, setFormat] = useState('')
  const [visual, setVisual] = useState('')
  const [search, setSearch] = useState('')
  const inputRef = useRef(null)

  useEffect(() => {
    if (isOpen) {
      setStepIndex(0)
      setPlatform('')
      setLanguage('')
      setGoal('')
      setFormat('')
      setVisual('')
      setSearch('')
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }, [isOpen])

  if (!isOpen) return null

  const steps = buildSteps(platform)
  const step = steps[stepIndex] || 'topic'

  const matches = (text) => text.toLowerCase().includes(search.toLowerCase())
  const options = {
    platform: PLATFORMS.filter((p) => matches(p.label) || matches(p.desc)),
    language: LANGUAGES.filter((l) => matches(l)).map((l) => ({ id: l, label: l, desc: '' })),
    goal: GOALS.filter((g) => matches(g.label) || matches(g.desc)),
    format: FORMATS.filter((f) => matches(f.label) || matches(f.desc)),
    visual: visualsFor(goal).filter((v) => matches(v.label) || matches(v.desc)),
    topic: [],
  }[step]

  const submit = () =>
    onSubmit({
      platform,
      language,
      goal,
      format: platform === 'Twitter' ? format || 'Single' : '',
      visual: visual || (goal === 'Data' ? 'Chain' : 'Random'),
      topic: search,
    })

  const select = (id) => {
    if (step === 'platform') setPlatform(id)
    else if (step === 'language') setLanguage(id)
    else if (step === 'format') setFormat(id)
    else if (step === 'visual') setVisual(id)
    else setGoal(id)
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

  // The topic step asks for whatever that specific goal actually needs.
  const TOPIC_PROMPTS = {
    Reply: 'Paste the post you want to reply to...',
    Outside: 'Which tech or public-sector topic should we bridge to?',
    Data: 'E.g. hashrate, block times, Scrypt economics...',
    Provoke: 'Which common assumption should we push back on?',
    Explain: 'What should we explain?',
    Poll: 'What should people place themselves on? (e.g. how long they have been here)',
  }

  const placeholder = {
    platform: 'Search platform...',
    language: 'Search language...',
    goal: 'What should this post achieve?',
    format: 'One post or a thread?',
    visual: 'Which image should go with it?',
    topic: TOPIC_PROMPTS[goal] || 'What is this post about? (Press Enter to generate)',
  }[step]

  const crumbs = [
    { key: 'platform', icon: <Globe size={12} />, label: 'Platform', value: platform },
    { key: 'language', icon: <Globe size={12} />, label: 'Language', value: language },
    { key: 'goal', icon: <Target size={12} />, label: 'Goal', value: goal },
    ...(platform === 'Twitter'
      ? [{ key: 'format', icon: <MessageSquare size={12} />, label: 'Format', value: format }]
      : []),
    { key: 'visual', icon: <ImageIcon size={12} />, label: 'Image', value: visual },
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
        className="fixed inset-0 z-[100] flex items-start justify-center overflow-y-auto px-4 pt-[8vh] pb-8 sm:pt-[15vh]"
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
            <div className={`max-h-[45vh] sm:max-h-[300px] overflow-y-auto border-t ${isDark ? 'border-white/5' : 'border-brand-100'} p-2`}>
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
