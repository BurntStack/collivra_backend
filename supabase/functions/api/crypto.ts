function b64decode(s: string): Uint8Array {
  return Uint8Array.from(atob(s), (ch) => ch.charCodeAt(0))
}

async function getKey(): Promise<CryptoKey> {
  const raw = Deno.env.get('FIELD_ENCRYPTION_KEY')
  if (!raw) throw new Error('FIELD_ENCRYPTION_KEY is not set')
  return await crypto.subtle.importKey('raw', b64decode(raw), 'AES-GCM', false, ['encrypt', 'decrypt'])
}

export async function encryptField(plain: string): Promise<string> {
  const iv = crypto.getRandomValues(new Uint8Array(12))
  const ct = new Uint8Array(await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv }, await getKey(), new TextEncoder().encode(plain)))
  const out = new Uint8Array(iv.length + ct.length)
  out.set(iv)
  out.set(ct, iv.length)
  return btoa(String.fromCharCode(...out))
}

export async function decryptField(stored: string): Promise<string> {
  const bytes = b64decode(stored)
  const plain = await crypto.subtle.decrypt(
    { name: 'AES-GCM', iv: bytes.slice(0, 12) }, await getKey(), bytes.slice(12))
  return new TextDecoder().decode(plain)
}

async function getSigningKey(): Promise<CryptoKey> {
  const raw = Deno.env.get('STATE_SIGNING_KEY') ?? Deno.env.get('FIELD_ENCRYPTION_KEY')
  if (!raw) throw new Error('STATE_SIGNING_KEY is not set')
  return await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(raw),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign', 'verify']
  )
}

export async function signSocialState(data: { userId: string; platform: string; exp: number }): Promise<string> {
  const payload = JSON.stringify(data)
  const key = await getSigningKey()
  const sig = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(payload))
  const sigB64 = btoa(String.fromCharCode(...new Uint8Array(sig)))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  const dataB64 = btoa(payload)
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  return `${dataB64}.${sigB64}`
}

export async function verifySocialState(state: string): Promise<{ userId: string; platform: string; exp: number } | null> {
  const parts = state.split('.')
  if (parts.length !== 2) return null
  try {
    const [dataB64, sigB64] = parts
    const payloadStr = atob(dataB64.replace(/-/g, '+').replace(/_/g, '/'))
    const sigBytes = Uint8Array.from(atob(sigB64.replace(/-/g, '+').replace(/_/g, '/')), (c) => c.charCodeAt(0))
    const key = await getSigningKey()
    const valid = await crypto.subtle.verify('HMAC', key, sigBytes, new TextEncoder().encode(payloadStr))
    if (!valid) return null
    const data = JSON.parse(payloadStr)
    if (Date.now() > data.exp) return null
    return data
  } catch {
    return null
  }
}
