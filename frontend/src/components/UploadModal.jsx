import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Upload, X, CheckCircle, Loader2 } from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_URL || ''

export default function UploadModal({ isOpen, onClose, isDark }) {
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [label, setLabel] = useState('')
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState('')
  const [isDragging, setIsDragging] = useState(false)
  const inputRef = useRef(null)

  useEffect(() => {
    if (isOpen) {
      setFile(null)
      setPreview(null)
      setLabel('')
      setLoading(false)
      setSuccess(false)
      setError('')
      setIsDragging(false)
    }
  }, [isOpen])

  const processFile = (selected) => {
    if (selected.size > 25 * 1024 * 1024) {
      setError('File is too large (max 25MB)')
      return
    }
    setFile(selected)
    setError('')
    const objectUrl = URL.createObjectURL(selected)
    setPreview(objectUrl)
  }

  const handleDragOver = (e) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = (e) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setIsDragging(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      processFile(e.dataTransfer.files[0])
    }
  }

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      processFile(e.target.files[0])
    }
  }

  const handleUpload = async () => {
    if (!file || !label.trim()) return
    setLoading(true)
    setError('')

    const formData = new FormData()
    formData.append('file', file)
    formData.append('label', label.trim())

    try {
      const res = await fetch(`${API_BASE}/api/community-art/upload`, {
        method: 'POST',
        body: formData,
      })
      if (!res.ok) throw new Error('Upload failed')
      setSuccess(true)
      setTimeout(() => {
        onClose()
      }, 2500)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

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
            {success ? (
              <div className="text-center py-8 space-y-4">
                <CheckCircle size={48} className="text-accent mx-auto" />
                <h4 className="font-bold text-xl">Upload Successful!</h4>
                <p className="opacity-70 text-sm">
                  Dein Content wurde eingereicht und wartet auf Freigabe durch einen Administrator.
                </p>
              </div>
            ) : (
              <>
                <div 
                  onClick={() => inputRef.current?.click()}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
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
                    onChange={handleFileChange} 
                    accept="image/png,image/jpeg,image/gif,video/mp4,video/webm" 
                    className="hidden" 
                  />
                  {preview ? (
                    file.type.startsWith('video/') ? (
                      <video src={preview} className="max-h-48 mx-auto rounded" controls />
                    ) : (
                      <img src={preview} alt="Preview" className="max-h-48 mx-auto rounded object-contain" />
                    )
                  ) : (
                    <div className="space-y-2 opacity-60">
                      <Upload size={32} className="mx-auto" />
                      <p className="text-sm font-medium">Click to select image or video</p>
                      <p className="text-xs">Max 25MB</p>
                    </div>
                  )}
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-semibold opacity-80">Category / Label</label>
                  <input
                    value={label}
                    onChange={(e) => setLabel(e.target.value)}
                    placeholder="e.g. Infographic, Pep Meme GM, Comparison"
                    className={`w-full px-4 py-2 rounded-lg border outline-none focus:border-accent ${
                      isDark 
                        ? 'bg-black/20 border-white/10 placeholder:text-white/30' 
                        : 'bg-brand-50 border-brand-200 placeholder:text-brand-400'
                    }`}
                  />
                </div>

                {error && <p className="text-red-500 text-sm font-medium text-center">{error}</p>}

                <button
                  onClick={handleUpload}
                  disabled={!file || !label.trim() || loading}
                  className="w-full py-3 rounded-lg bg-accent text-white font-bold disabled:opacity-50 transition-opacity flex items-center justify-center gap-2 shadow-lg shadow-accent/20"
                >
                  {loading ? <Loader2 size={18} className="animate-spin" /> : 'Upload'}
                </button>
              </>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}
