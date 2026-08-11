import { useState } from 'react'
import { motion } from 'framer-motion'
import { ThumbsDown, ThumbsUp } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import EmotePicker from './EmotePicker'
import remarkGfm from 'remark-gfm'
import { trackEvent } from '../lib/analytics'

function linkify(text) {
  if (!text) return text
  return text.replace(
    /(?<!\]\()(https?:\/\/[^\s<>"{}|\\^`[\]]+|discord\.gg\/[^\s<>"{}|\\^`[\]]+)/g,
    (url) => {
      const trimmed = url.replace(/[.,;:!?]+$/, '')
      let display = 'Link'
      try {
        const normalized = /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`
        const u = new URL(normalized)
        display = u.hostname.replace(/^www\./, '')
      } catch {
        display = 'Link'
      }
      return `[${display}](${trimmed})`
    }
  )
}

const markdownComponents = {
  a: ({ node, href, ...props }) => {
    const handleClick = () => {
      const hrefLower = (href || '').toLowerCase()
      let conversionType = 'link'
      if (hrefLower.includes('discord')) conversionType = 'discord'
      else if (hrefLower.includes('pepeblocks.com/faucet')) conversionType = 'faucet'
      else if (hrefLower.includes('coinomi')) conversionType = 'wallet'
      trackEvent('conversion', { conversion_type: conversionType, url: href })
    }
    return <a href={href} onClick={handleClick} target="_blank" rel="noopener noreferrer" {...props} />
  },
}

// A thumbs-down says an answer was bad but not what was wrong with it, and
// "bad" alone gives nothing to act on. Four fixed reasons keep the extra tap
// cheap while making the signal usable.
const FEEDBACK_REASONS = [
  { id: 'wrong', label: 'Wrong' },
  { id: 'unclear', label: 'Unclear' },
  { id: 'incomplete', label: 'Incomplete' },
  { id: 'tone', label: 'Wrong tone' },
]

// Answers were stored truncated at 200 characters, which is too little to
// reuse as an example of a good reply. Still capped, just high enough to keep
// the row size sane.
const FEEDBACK_TEXT_LIMIT = 4000

export default function Message({ msg, isDark, userMessage, ragChunks, ragChunkIds, isSocialPost }) {
  const isUser = msg.role === 'user'
  const [feedback, setFeedback] = useState(null)
  const [askReason, setAskReason] = useState(false)

  const sendFeedback = (type, reason) => {
    const metadata = {}
    if (typeof ragChunks === 'number') metadata.rag_chunk_count = ragChunks
    if (ragChunkIds?.length) metadata.chunk_ids = ragChunkIds
    if (reason) metadata.reason = reason

    trackEvent('feedback', {
      feedback: type,
      message: msg.text?.slice(0, FEEDBACK_TEXT_LIMIT),
      user_message: userMessage?.slice(0, FEEDBACK_TEXT_LIMIT),
      metadata: Object.keys(metadata).length ? metadata : undefined,
    })
  }

  const handleFeedback = (type) => {
    if (feedback) return
    setFeedback(type)
    if (type === 'thumbs_down') {
      // Record it immediately; the reason is an optional refinement so a user
      // who ignores the prompt still leaves a usable rating behind.
      sendFeedback(type, null)
      setAskReason(true)
    } else {
      sendFeedback(type, null)
    }
  }

  const handleReason = (reason) => {
    setAskReason(false)
    sendFeedback('thumbs_down_reason', reason)
  }

  const textWithLinks = linkify(msg.text)

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: 'easeOut' }}
      className={`flex gap-2 sm:gap-3 md:gap-4 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
    >
      {isUser ? (
        <img
          src="/user.png"
          alt="User"
          className="flex-shrink-0 w-7 h-7 sm:w-8 sm:h-8 md:w-9 md:h-9 rounded-xl object-cover shadow-sm"
        />
      ) : (
        <img
          src="/agent.png"
          alt="Professor Pepe"
          className="flex-shrink-0 w-7 h-7 sm:w-8 sm:h-8 md:w-9 md:h-9 rounded-xl object-cover shadow-sm"
        />
      )}

      <div className={`max-w-[88%] sm:max-w-[85%] md:max-w-[80%] min-w-0 ${isUser ? 'items-end' : 'items-start'} flex flex-col gap-1.5 sm:gap-2`}>
        <div className={`message-bubble-${isUser ? 'user' : 'agent'} px-3 py-2 sm:px-4 sm:py-2.5 md:px-5 md:py-3.5 w-full`}>
          {msg.image && (
            <motion.img
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.4 }}
              src={msg.image}
              alt="Generated visual"
              className="mb-2 sm:mb-3 rounded-xl max-w-full max-h-48 sm:max-h-56 md:max-h-64 h-auto w-auto mx-auto shadow-sm"
            />
          )}
          {msg.text && (
            <div className="prose prose-sm dark:prose-invert max-w-none break-words [overflow-wrap:anywhere]">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                {msg.emote ? `${textWithLinks.trim()} ![emote](${msg.emote})` : textWithLinks}
              </ReactMarkdown>
              {isSocialPost && <EmotePicker text={msg.text} />}
            </div>
          )}
        </div>
        {!isUser && msg.text && (
          <div className="flex items-center gap-1 px-1">
            <button
              onClick={() => handleFeedback('thumbs_up')}
              disabled={feedback}
              className={`p-1 rounded-md transition-colors ${
                feedback === 'thumbs_up'
                  ? 'text-green-500'
                  : 'text-brand-400 hover:text-green-500 dark:text-brand-500 dark:hover:text-green-400'
              } disabled:opacity-50`}
              aria-label="Helpful"
            >
              <ThumbsUp size={12} className="sm:w-3.5 sm:h-3.5" />
            </button>
            <button
              onClick={() => handleFeedback('thumbs_down')}
              disabled={feedback}
              className={`p-1 rounded-md transition-colors ${
                feedback === 'thumbs_down'
                  ? 'text-red-500'
                  : 'text-brand-400 hover:text-red-500 dark:text-brand-500 dark:hover:text-red-400'
              } disabled:opacity-50`}
              aria-label="Not helpful"
            >
              <ThumbsDown size={12} className="sm:w-3.5 sm:h-3.5" />
            </button>

            {askReason && (
              <div className="flex flex-wrap items-center gap-1 ml-1">
                <span className="text-[9px] sm:text-[10px] text-brand-400 dark:text-brand-500">
                  What was wrong?
                </span>
                {FEEDBACK_REASONS.map((reason) => (
                  <button
                    key={reason.id}
                    onClick={() => handleReason(reason.id)}
                    className="px-1.5 py-0.5 rounded-md text-[9px] sm:text-[10px] border border-white/10 text-brand-400 hover:text-white hover:border-accent/50 hover:bg-accent/10 transition-colors"
                  >
                    {reason.label}
                  </button>
                ))}
                <button
                  onClick={() => setAskReason(false)}
                  className="px-1 text-[9px] sm:text-[10px] text-brand-500 hover:text-brand-300 transition-colors"
                  aria-label="Skip"
                >
                  ✕
                </button>
              </div>
            )}
          </div>
        )}
        <span className="text-[9px] sm:text-[10px] text-brand-400 dark:text-brand-500 px-1">
          {msg.time}
        </span>
      </div>
    </motion.div>
  )
}
