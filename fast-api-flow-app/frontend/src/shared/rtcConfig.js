const DEFAULT_ICE_SERVERS = [{ urls: 'stun:stun.l.google.com:19302' }]

function parseIceServers(raw) {
  if (!raw) return DEFAULT_ICE_SERVERS
  try {
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed) && parsed.length > 0) {
      return parsed
    }
  } catch {
    // Fall back to default when env is malformed.
  }
  return DEFAULT_ICE_SERVERS
}

function iceServersFromTurnEnv() {
  const turnUrl = (import.meta.env.VITE_TURN_URL || '').trim()
  if (!turnUrl) return null

  const username = (import.meta.env.VITE_TURN_USERNAME || '').trim()
  const credential = (import.meta.env.VITE_TURN_CREDENTIAL || '').trim()

  return [
    { urls: 'stun:stun.l.google.com:19302' },
    {
      urls: turnUrl,
      ...(username ? { username } : {}),
      ...(credential ? { credential } : {}),
    },
  ]
}

export const RTC_CONFIG = {
  iceServers:
    iceServersFromTurnEnv() ??
    parseIceServers(import.meta.env.VITE_ICE_SERVERS),
}
