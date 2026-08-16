import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Upload, X, CheckCircle, Loader2, Copy, AlertCircle, Trash2 } from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_URL || ''

const MAX_FILES = 15
const MAX_BYTES = 25 * 1024 * 1024
// Matches what the server accepts. webp was missing from both, which is how a
// perfectly ordinary downloaded image came back refused.
const ACCEPTED =
  'image/png,image/jpeg,image/gif,image/webp,image/avif,image/bmp,image/tiff,video/mp4,video/webm'

export default function UploadModal({ isOpen, onClose, isDark }) {
  const [files, setFiles] = useState([])
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState(null)
  const [error, setError] = useState('')
  const [isDragging, setIsDragging] = useState(false)
  const inputRef = useRef(null)

  useEffect(() => {
    if (isOpen) {
      setFiles([])
      setLoading(false)
      setResults(null)
      setError('')
      setIsDragging(false)
    }
  }, [isOpen])

  // Object URLs are revoked when the entry goes away, or every preview would
  // hold its file in memory for as long as the tab lives.
  useEffect(() => {
    return () => files.forEach((entry) => URL.revokeObjectURL(entry.preview))
  }, [files])

  const addFiles = (selected) => {
    const incoming = Array.from(selected || [])
    if (!incoming.length) return

    const problems = []
    const accepted = []

    for (const file of incoming) {
      if (file.size > MAX_BYTES) {
        problems.push(`${file.name} is larger than 25MB`)
        continue
      }
      // Catches the same file picked twice in one go. Identical content under
      // two names is caught by the server, which compares the bytes.
      const known = (entry) =>
        entry.file.name === file.name && entry.file.size === file.size
      if (files.some(known) || accepted.some(known)) continue
      accepted.push({ file, preview: URL.createObjectURL(file) })
    }

    const room = MAX_FILES - files.length
    if (accepted.length > room) {
      problems.push(`Only ${MAX_FILES} files at a time — the rest were skipped`)
    }

    setFiles((prev) => [...prev, ...accepted.slice(0, Math.max(0, room))])
    setError(problems.join('. '))
  }

  const removeFile = (index) => {
    setFiles((prev) => {
      URL.revokeObjectURL(prev[index].preview)
      return prev.filter((_, i) => i !== index)
    })
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setIsDragging(false)
    addFiles(e.dataTransfer.files)
  }

  const handleUpload = async () => {
    if (!files.length) return
    setLoading(true)
    setError('')

    const formData = new FormData()
    files.forEach((entry) => formData.append('files', entry.file))

    try {
      const res = await fetch(`${API_BASE}/api/community-art/upload`, {
        method: 'POST',
        body: formData,
      })
      const data = await res.json().catch(() => null)
      if (!res.ok) throw new Error(data?.detail || 'Upload failed')
      setResults(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  const STATUS_STYLE = {
    added: { icon: CheckCircle, className: 'text-accent', word: 'Added' },
    duplicate: { icon: Copy, className: 'text-amber-500', word: 'Already there' },
    rejected: { icon: AlertCircle, className: 'text-red-500', word: 'Rejected' },
  }

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-[100] flex items-center justify-center overflow-y-auto p-4"
      >
        <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={!loading ? onClose : undefined} />

        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          className={`relative w-full max-w-md max-h-[90vh] overflow-y-auto rounded-2xl shadow-2xl border ${
            isDark ? 'bg-brand-900 border-white/10 text-white' : 'bg-white border-brand-200 text-brand-900'
          }`}
        >
          <div className={`p-4 border-b flex justify-between items-center ${isDark ? 'border-white/10' : 'border-brand-100'}`}>
            <h3 className="font-bold text-lg flex items-center gap-2">
              <Upload size={18} className="text-accent" />
              Upload Community Art
            </h3>
            <button onClick={onClose} disabled={loading} className="opacity-50 hover:opacity-100 transition-opacity">
              <X size={20} />
            </button>
          </div>

          <div className="p-6 space-y-6">
            {results ? (
              <div className="space-y-4">
                <div className="text-center space-y-1">
                  <CheckCircle size={40} className="text-accent mx-auto" />
                  <h4 className="font-bold text-lg">
                    {results.added} of {results.results.length} added
                  </h4>
                  <p className="opacity-70 text-sm">
                    {results.added > 0
                      ? 'Submitted and waiting for an administrator to approve them.'
                      : 'Nothing new was added.'}
                  </p>
                </div>

                {/* Per file, because a batch that silently drops half of it
                    leaves you guessing which half. */}
                <div className="space-y-1.5 max-h-56 overflow-y-auto">
                  {results.results.map((entry, index) => {
                    const style = STATUS_STYLE[entry.status] || STATUS_STYLE.rejected
                    const Icon = style.icon
                    return (
                      <div key={index} className="flex items-start gap-2 text-xs">
                        <Icon size={14} className={`${style.className} shrink-0 mt-0.5`} />
                        <span className="flex-1 min-w-0">
                          <span className="block truncate" title={entry.filename}>
                            {entry.filename}
                          </span>
                          {/* The server says why it refused a file; showing
                              only the verdict left nothing to act on. */}
                          {entry.reason && (
                            <span className="block opacity-60 text-[10px]">
                              {entry.reason}
                            </span>
                          )}
                          {entry.art?.label && (
                            <span className="block opacity-60 text-[10px]">
                              Filed under “{entry.art.label}”
                            </span>
                          )}
                        </span>
                        <span className={`${style.className} shrink-0 font-medium`}>
                          {style.word}
                        </span>
                      </div>
                    )
                  })}
                </div>

                <button
                  onClick={onClose}
                  className="w-full py-2.5 rounded-lg bg-accent text-white font-bold shadow-lg shadow-accent/20"
                >
                  Done
                </button>
              </div>
            ) : (
              <>
                <div
                  onClick={() => inputRef.current?.click()}
                  onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
                  onDragLeave={(e) => { e.preventDefault(); setIsDragging(false) }}
                  onDrop={handleDrop}
                  className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors ${
                    isDragging
                      ? 'border-accent bg-accent/10'
                      : isDark
                        ? 'border-white/20 hover:border-accent hover:bg-white/5'
                        : 'border-brand-300 hover:border-accent hover:bg-brand-50'
                  }`}
                >
                  <input
                    type="file"
                    ref={inputRef}
                    multiple
                    onChange={(e) => { addFiles(e.target.files); e.target.value = '' }}
                    accept={ACCEPTED}
                    className="hidden"
                  />
                  <div className="space-y-2 opacity-60">
                    <Upload size={28} className="mx-auto" />
                    <p className="text-sm font-medium">
                      {files.length
                        ? `${files.length} of ${MAX_FILES} selected — click to add more`
                        : 'Click or drop files — up to 15 at once'}
                    </p>
                    <p className="text-xs">Max 25MB each</p>
                  </div>
                </div>

                {files.length > 0 && (
                  <div className="grid grid-cols-4 gap-2">
                    {files.map((entry, index) => (
                      <div key={index} className="relative group aspect-square">
                        {entry.file.type.startsWith('video/') ? (
                          <div className="w-full h-full rounded-lg bg-black/20 flex items-center justify-center text-[9px] font-semibold opacity-70">
                            VIDEO
                          </div>
                        ) : (
                          <img
                            src={entry.preview}
                            alt={entry.file.name}
                            title={entry.file.name}
                            className="w-full h-full object-cover rounded-lg"
                          />
                        )}
                        <button
                          onClick={() => removeFile(index)}
                          disabled={loading}
                          aria-label={`Remove ${entry.file.name}`}
                          className="absolute -top-1.5 -right-1.5 p-1 rounded-full bg-red-500 text-white opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity"
                        >
                          <Trash2 size={10} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                <p className="text-xs opacity-60 text-center">
                  Each file is categorised and described automatically from what
                  it shows — nothing to fill in.
                </p>

                {error && <p className="text-red-500 text-sm font-medium text-center">{error}</p>}

                <button
                  onClick={handleUpload}
                  disabled={!files.length || loading}
                  className="w-full py-3 rounded-lg bg-accent text-white font-bold disabled:opacity-50 transition-opacity flex items-center justify-center gap-2 shadow-lg shadow-accent/20"
                >
                  {loading ? (
                    <>
                      <Loader2 size={18} className="animate-spin" />
                      Uploading {files.length}...
                    </>
                  ) : (
                    `Upload${files.length > 1 ? ` ${files.length} files` : ''}`
                  )}
                </button>
              </>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}
