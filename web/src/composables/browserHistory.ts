// Scoped to this browser profile. Only the SHA-256 prefix appears in session IDs.
let memoryKey = ''
export function browserHeaders(): Record<string, string> {
  if (typeof window === 'undefined') return {}
  let key = memoryKey
  try {
    key = localStorage.getItem('skill-plaza:history-key') || key
  } catch {
    /* private mode */
  }
  if (!/^[a-f0-9]{64}$/.test(key)) {
    key = Array.from(crypto.getRandomValues(new Uint8Array(32)), (b) => b.toString(16).padStart(2, '0')).join('')
    try {
      localStorage.setItem('skill-plaza:history-key', key)
    } catch {
      /* tab-only history */
    }
  }
  memoryKey = key
  return { 'X-Plaza-Browser': key }
}
