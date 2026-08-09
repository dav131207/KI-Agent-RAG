import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Send, Loader2, Paperclip } from 'lucide-react'
import Message from './Message'
import ImageModal from './ImageModal'
import SocialPostModal from './SocialPostModal'
import UploadModal from './UploadModal'
import CommunityArtModal from './CommunityArtModal'
import { DEFAULT_LABELS, getLabels } from '../lib/commandLabels'
import { measureLatency, trackEvent } from '../lib/analytics'

const API_BASE = import.meta.env.VITE_API_URL || ''

const COMMANDS = [
  { id: 'getcoins', prompt: 'get coins' },
  { id: 'meme', prompt: 'random meme' },
  { id: 'rarepepe', prompt: 'rare pepe' },
  { id: 'social', prompt: 'create social media post' },
  { id: 'communityart', prompt: 'Community Art' },
]

export default function Chat({ isDark }) {
  const [language, setLanguage] = useState('English')
  const labels = getLabels(language)

  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [typingText, setTypingText] = useState('')
  const [modalImage, setModalImage] = useState(null)
  const [isSocialModalOpen, setIsSocialModalOpen] = useState(false)
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false)
  const [isArtModalOpen, setIsArtModalOpen] = useState(false)
  const [showSwipeHint, setShowSwipeHint] = useState(true)
  const bottomRef = useRef(null)

  const handleSocialSubmit = ({ platform, language, tonality, topic }) => {
    setIsSocialModalOpen(false)
    const prompt = `create a social media post. Platform: ${platform}. Language: ${language}. Tonality: ${tonality}. Topic: ${topic}`
    handleSubmit(null, { id: 'social', display: labels['social'], send: prompt })
  }

  const handleArtSubmit = async (label) => {
    setIsArtModalOpen(false)
    setLoading(true)
    const userMsg = { role: 'user', text: `Show me some Community Pepe Art for: ${label}`, time: formatTime(new Date()) }
    setMessages((prev) => [...prev, userMsg])
    try {
      const res = await fetch(`${API_BASE}/api/community-art/random?label=${encodeURIComponent(label)}`)
      if (!res.ok) throw new Error('Failed to fetch art')
      const data = await res.json()
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: data.art.description || `Here is some community art for ${label}!`,
          image: data.art.url,
          time: formatTime(new Date()),
        },
      ])
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', text: `⚠️ ${err.message}`, time: formatTime(new Date()) },
      ])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetch(`${API_BASE}/api/language`)
      .then((res) => (res.ok ? res.json() : { language: 'English' }))
      .then((data) => setLanguage(data.language || 'English'))
      .catch(() => setLanguage('English'))
  }, [])

  useEffect(() => {
    const fetchInitialGreeting = async () => {
      try {
        setLoading(true)
        const response = await fetch(`${API_BASE}/api/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            topic: '',
            message: 'Generate a short initial greeting for the chat as Professor Pepe. Be completely random every time: sometimes cheeky, sometimes funny, sometimes ranting. Maximum 2 sentences. Do not mention that you are an AI.',
            history: [],
            stream: true,
          }),
        })
        if (!response.ok) return
        
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let fullText = ''
        
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          fullText += decoder.decode(value, { stream: true })
          setTypingText(fullText)
        }
        
        setMessages([{ role: 'assistant', text: fullText, time: formatTime(new Date()) }])
        setTypingText('')
      } catch (err) {
        setMessages([{ role: 'assistant', text: labels.welcome, time: formatTime(new Date()) }])
      } finally {
        setLoading(false)
      }
    }

    if (messages.length === 0 && !loading) {
      fetchInitialGreeting()
    }
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, typingText])

  const handleSubmit = async (e, command = null) => {
    if (e && e.preventDefault) e.preventDefault()
    const displayText = command ? command.display : input.trim()
    const sendText = command ? command.send : input.trim()
    const commandId = command ? command.id : null
    if (!displayText || !sendText || loading) return

    const startTime = performance.now()

    if (command) {
      trackEvent('command_click', { command: commandId })
    } else {
      trackEvent('message_send', { message: sendText })
    }

    const userMsg = { role: 'user', text: displayText, time: formatTime(new Date()) }
    setMessages((prev) => [...prev, userMsg])
    if (!command) setInput('')
    setLoading(true)
    setTypingText('')

    if (sendText.toLowerCase() === 'rare pepe') {
      try {
        const pepe = await fetchRarePepe()
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            text: '',
            image: pepe.url,
            time: formatTime(new Date()),
          },
        ])
      } catch (err) {
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            text: `⚠️ ${err.message || 'No rare pepe found.'}`,
            time: formatTime(new Date()),
          },
        ])
      } finally {
        setLoading(false)
        trackEvent('request_latency', { latency_ms: measureLatency(startTime), command: commandId || sendText })
      }
      return
    }

    if (sendText.toLowerCase() === 'get coins') {
      try {
        const data = await fetchGetCoins()
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            text: data.text,
            time: formatTime(new Date()),
          },
        ])
      } catch (err) {
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            text: `⚠️ ${err.message || 'Could not load get coins info.'}`,
            time: formatTime(new Date()),
          },
        ])
      } finally {
        setLoading(false)
        trackEvent('request_latency', { latency_ms: measureLatency(startTime), command: commandId || sendText })
      }
      return
    }

    try {
      const wantsImage = /\b(show|image|picture|pic|photo|visual|draw|meme)\b/i.test(sendText)
      const isSocialCommand = /^create\s+a?\s*social\s+media\s+post/i.test(sendText)
      // A mining/synergy post argues from network data, so it gets the live
      // on-chain card instead of a random meme, which would undercut it.
      const wantsChainCard =
        isSocialCommand && /Tonality:\s*[^.]*\b(miner|synergy)\b/i.test(sendText)

      let imageUrl = null
      if (wantsChainCard) {
        // The card 503s when the explorer is down; probe the JSON endpoint
        // first (same 60s cache, no image rendering) so a dead explorer leaves
        // no broken image in the chat.
        const chainOk = await fetch(`${API_BASE}/api/chain-stats`)
          .then((r) => r.ok)
          .catch(() => false)
        imageUrl = chainOk ? `${API_BASE}/api/chain-stats.png?t=${Date.now()}` : null
      } else if (wantsImage || isSocialCommand) {
        imageUrl = await fetchImage(sendText)
      }

      const history = messages
        .filter((m) => m.role === 'user' || m.role === 'assistant')
        .slice(-10)
        .map((m) => ({ role: m.role, text: m.text }))

      const response = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic: '',
          message: sendText,
          history,
          stream: true,
        }),
      })

      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: 'Unknown error' }))
        throw new Error(err.detail || `HTTP ${response.status}`)
      }

      const ragChunks = Number(response.headers.get('X-RAG-Chunks') || 0)
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let fullText = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value, { stream: true })
        fullText += chunk
        setTypingText(fullText)
      }

      let emoteUrl = null
      if (fullText && Math.random() < 0.35) {
        emoteUrl = await fetchEmote(fullText)
      }

      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: fullText,
          image: imageUrl,
          emote: emoteUrl,
          time: formatTime(new Date()),
          ragChunks,
        },
      ])
      setTypingText('')
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: `⚠️ ${err.message || 'Something went wrong. Please try again.'}`,
          time: formatTime(new Date()),
        },
      ])
    } finally {
      setLoading(false)
      trackEvent('request_latency', { latency_ms: measureLatency(startTime), command: commandId || sendText })
    }
  }

  const fetchImage = async (search) => {
    try {
      const res = await fetch(`${API_BASE}/api/image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: search }),
      })
      if (!res.ok) return null
      const data = await res.json()
      return data.url || null
    } catch {
      return null
    }
  }

  const fetchEmote = async (text) => {
    try {
      const res = await fetch(`${API_BASE}/api/emote`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      })
      if (!res.ok) return null
      const data = await res.json()
      return data.url || null
    } catch {
      return null
    }
  }

  const fetchRarePepe = async () => {
    const history = messages
      .filter((m) => m.role === 'user' || m.role === 'assistant')
      .slice(-10)
      .map((m) => ({ role: m.role, text: m.text }))

    const res = await fetch(`${API_BASE}/api/rare_pepe`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: 'rare pepe', history }),
    })
    if (!res.ok) throw new Error('No rare pepe found')
    return res.json()
  }

  const fetchGetCoins = async () => {
    const res = await fetch(`${API_BASE}/api/get_coins`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    })
    if (!res.ok) throw new Error('Could not load get coins info')
    return res.json()
  }

  return (
    <div className="flex flex-col h-full relative">
      {/* messages */}
      <div className="flex-1 overflow-y-auto scrollbar-thin px-3 sm:px-4 md:px-8 py-4 sm:py-6 pb-64 space-y-4 sm:space-y-6">
        <AnimatePresence initial={false}>
          {messages.map((msg, idx) => {
            const precedingUserMessage =
              msg.role === 'assistant'
                ? [...messages.slice(0, idx)].reverse().find((m) => m.role === 'user')?.text
                : null
            return (
              <div key={idx} onClick={(e) => {
                if (e.target.tagName === 'IMG') setModalImage(e.target.src)
              }}>
                <Message msg={msg} isDark={isDark} userMessage={precedingUserMessage} ragChunks={msg.ragChunks} />
              </div>
            )
          })}
        </AnimatePresence>

        {typingText && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex gap-2 sm:gap-4"
          >
            <img
              src="/agent.png"
              alt="Professor Pepe"
              className="flex-shrink-0 w-7 h-7 sm:w-8 sm:h-8 md:w-9 md:h-9 rounded-xl object-cover shadow-sm"
            />
            <div className={`message-bubble-agent px-3 py-2 sm:px-4 sm:py-2.5 md:px-5 md:py-3.5 max-w-[88%] sm:max-w-[85%] md:max-w-[80%]`}>
              <p className="whitespace-pre-wrap text-sm sm:text-base">{typingText}</p>
              <span className="inline-block mt-2 w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
            </div>
          </motion.div>
        )}

        {loading && !typingText && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex gap-2 sm:gap-4"
          >
            <img
              src="/agent.png"
              alt="Professor Pepe"
              className="flex-shrink-0 w-7 h-7 sm:w-8 sm:h-8 md:w-9 md:h-9 rounded-xl object-cover shadow-sm"
            />
            <div className={`px-3 py-2 sm:px-4 sm:py-3 md:px-5 md:py-4 rounded-2xl rounded-tl-sm ${isDark ? 'bg-brand-800/80' : 'bg-white'} border border-brand-100 dark:border-white/10 flex items-center gap-2`}>
              <span className="typing-dot" style={{ animationDelay: '0ms' }} />
              <span className="typing-dot" style={{ animationDelay: '150ms' }} />
              <span className="typing-dot" style={{ animationDelay: '300ms' }} />
            </div>
          </motion.div>
        )}

        <div ref={bottomRef} className="h-32 md:h-48 shrink-0" />
      </div>

      {/* input area */}
      <div className="absolute bottom-0 left-0 right-0 z-20 px-3 sm:px-4 md:px-8 pt-12 pb-6 sm:pb-8 bg-gradient-to-t from-brand-900 via-brand-900/95 to-transparent pointer-events-none">
        <form onSubmit={handleSubmit} className="max-w-3xl mx-auto relative pointer-events-auto">
          {/* horizontally scrollable flex row on mobile, flex-wrap on desktop */}
          <div className="relative">
            <AnimatePresence>
              {showSwipeHint && (
                <motion.div 
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="absolute right-0 top-0 bottom-3 z-10 md:hidden pointer-events-none flex items-center pr-1 bg-gradient-to-l from-brand-900/90 to-transparent w-16 justify-end rounded-r-full"
                >
                  <motion.div
                    animate={{ x: [0, -10, 0] }}
                    transition={{ repeat: Infinity, duration: 1.5 }}
                    className="text-white drop-shadow-lg"
                  >
                    <span className="text-xl">👈</span>
                  </motion.div>
                </motion.div>
              )}
            </AnimatePresence>
            <div 
              onScroll={() => setShowSwipeHint(false)}
              className="flex overflow-x-auto md:overflow-visible snap-x hide-scrollbar md:flex-wrap md:justify-center gap-2 mb-2 sm:mb-3 py-2 px-2 -mx-2"
            >
              {COMMANDS.map((cmd) => (
              <button
                key={cmd.id}
                type="button"
                onClick={() => {
                  if (cmd.id === 'social') {
                    setIsSocialModalOpen(true)
                  } else if (cmd.id === 'communityart') {
                    setIsArtModalOpen(true)
                  } else {
                    handleSubmit(null, { id: cmd.id, display: labels[cmd.id], send: cmd.prompt })
                  }
                }}
                disabled={loading}
                className="snap-start flex-none w-[140px] md:flex-1 md:w-auto min-h-[44px] px-3 md:px-4 py-2 rounded-full text-[11px] font-medium text-center leading-tight transition-all duration-300 hover:scale-[1.03] hover:-translate-y-0.5 bg-white/5 border border-white/10 text-brand-300 hover:text-white hover:border-accent/50 hover:bg-accent/10 hover:shadow-[0_0_15px_rgba(38,154,76,0.2)] disabled:opacity-50 disabled:hover:scale-100 disabled:hover:translate-y-0"
              >
                <span className="md:hidden block">{labels?.[`${cmd.id}Short`] || labels?.[cmd.id] || cmd.id}</span>
                <span className="hidden md:block">{labels?.[cmd.id] || cmd.id}</span>
              </button>
            ))}
            </div>
          </div>

          <div className="flex items-center gap-1.5 sm:gap-2 rounded-full border px-2 sm:px-2.5 py-1.5 sm:py-2 shadow-lg transition-all duration-300 focus-within:ring-2 focus-within:ring-accent/40 focus-within:shadow-accent/20 bg-white/5 backdrop-blur-md border-white/10 focus-within:border-accent/50">
            <button
              type="button"
              onClick={() => setIsUploadModalOpen(true)}
              disabled={loading}
              className="p-2 sm:p-2.5 rounded-full text-brand-300 hover:text-accent hover:bg-accent/10 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              aria-label="Upload Art"
            >
              <Paperclip size={18} />
            </button>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={labels.placeholder}
              className="flex-1 bg-transparent px-2 sm:px-3 py-1.5 sm:py-2 outline-none text-sm transition-colors min-w-0 placeholder:text-brand-500 text-brand-50"
            />
            <button
              type="submit"
              disabled={!input.trim() || loading}
              className="p-2 sm:p-2.5 rounded-full btn-primary disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100 active:scale-90 transition-transform flex-shrink-0"
              aria-label="Send"
            >
              {loading ? <Loader2 size={16} className="sm:w-[18px] sm:h-[18px] animate-spin" /> : <Send size={16} className="sm:w-[18px] sm:h-[18px]" />}
            </button>
          </div>
        </form>
      </div>

      <ImageModal src={modalImage} onClose={() => setModalImage(null)} />
      <SocialPostModal
        isOpen={isSocialModalOpen}
        onClose={() => setIsSocialModalOpen(false)}
        onSubmit={handleSocialSubmit}
        isDark={isDark}
      />
      <UploadModal 
        isOpen={isUploadModalOpen} 
        onClose={() => setIsUploadModalOpen(false)} 
        isDark={isDark} 
      />
      <CommunityArtModal
        isOpen={isArtModalOpen}
        onClose={() => setIsArtModalOpen(false)}
        onSubmit={handleArtSubmit}
        isDark={isDark}
      />
    </div>
  )
}

function formatTime(date) {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}
