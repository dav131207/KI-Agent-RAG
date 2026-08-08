import { useState, useEffect } from 'react'
import { Wallet } from 'lucide-react'

export default function WalletConnect() {
  const [address, setAddress] = useState(null)
  const [connecting, setConnecting] = useState(false)
  const [provider, setProvider] = useState(null)

  useEffect(() => {
    // Check if we already have a saved address in localStorage
    const saved = localStorage.getItem('peppool_address')
    if (saved) {
      setAddress(saved)
    }

    // Provider discovery
    const handleAnnounce = (e) => {
      if (e.detail?.provider?.id === 'peppool') {
        setProvider(e.detail.provider)
      }
    }
    
    window.addEventListener('pep_providers:announce', handleAnnounce)
    window.dispatchEvent(new Event('pep_providers:request'))

    // Fallback: check window.pep_providers array directly
    const checkArray = () => {
      const p = (window.pep_providers || []).find((x) => x.id === 'peppool')
      if (p) setProvider(p)
    }
    
    checkArray()
    const t1 = setTimeout(checkArray, 500)
    const t2 = setTimeout(checkArray, 2000)

    return () => {
      window.removeEventListener('pep_providers:announce', handleAnnounce)
      clearTimeout(t1)
      clearTimeout(t2)
    }
  }, [])

  const handleConnect = async () => {
    if (address) {
      // Disconnect
      try {
        if (provider) await provider.request('wallet_disconnect')
      } catch (e) {
        console.warn('Disconnect error:', e)
      }
      setAddress(null)
      localStorage.removeItem('peppool_address')
      return
    }

    if (!provider) {
      window.open('https://chromewebstore.google.com/detail/peppool-wallet/jfdajbjjeejnlelljgobbfmkkbcbggbp', '_blank')
      return
    }

    setConnecting(true)
    try {
      const result = await provider.request('wallet_connect')
      const addr = Array.isArray(result) ? result[0] : result
      if (addr) {
        setAddress(addr)
        localStorage.setItem('peppool_address', addr)
      }
    } catch (err) {
      console.error('Wallet connection failed:', err)
      alert(err.message || 'Failed to connect wallet')
    } finally {
      setConnecting(false)
    }
  }

  const formatAddress = (addr) => {
    if (!addr) return ''
    return `${addr.slice(0, 4)}...${addr.slice(-4)}`
  }

  return (
    <button
      onClick={handleConnect}
      disabled={connecting}
      className={`flex items-center justify-center gap-1.5 sm:gap-2 px-2.5 sm:px-4 py-1.5 sm:py-2 rounded-full text-xs sm:text-sm font-bold transition-all shadow-sm ${
        address 
          ? 'bg-accent/10 text-accent hover:bg-accent/20 border border-accent/30' 
          : 'bg-brand-800/80 dark:bg-brand-900/80 text-brand-50 hover:bg-brand-700 border border-brand-700/50 dark:border-white/10'
      }`}
    >
      <Wallet size={16} />
      <span>
        {connecting ? '...' : address ? formatAddress(address) : 'Connect'}
      </span>
    </button>
  )
}
