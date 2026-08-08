const API_BASE = import.meta.env.VITE_API_URL || ''

function getOrCreateSessionId() {
  const key = 'pepe_session'
  let sessionId = document.cookie
    .split('; ')
    .find((row) => row.startsWith(`${key}=`))
    ?.split('=')[1]

  if (!sessionId) {
    sessionId = `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
    // 30 days, secure/same-site lax so it is sent with API requests.
    document.cookie = `${key}=${sessionId}; path=/; max-age=${60 * 60 * 24 * 30}; SameSite=Lax`
  }

  return sessionId
}

export async function trackEvent(eventType, data = {}) {
  try {
    const walletAddress = localStorage.getItem('peppool_address')

    await fetch(`${API_BASE}/api/event`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        event_type: eventType,
        session_id: getOrCreateSessionId(),
        user_agent: navigator.userAgent,
        wallet_address: walletAddress || null,
        ...data,
      }),
    })
  } catch {
    // Silently ignore analytics errors so they never block the user.
  }
}

export function measureLatency(startTime) {
  return Math.round(performance.now() - startTime)
}
